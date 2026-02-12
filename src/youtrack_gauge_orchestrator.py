#!/usr/bin/env python3
"""YouTrack-driven Gauge/Selenium automation orchestrator.

Flow:
1) Read issue from YouTrack.
2) Try to find existing relevant Gauge spec.
3) If found, run only matched specs.
4) If not found, generate a new Gauge spec using AI and save to generated_specs/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request


@dataclass
class Config:
    youtrack_base_url: str
    youtrack_token: str
    project_key: str
    gauge_bin: str = "gauge"
    specs_root: str = "specs"
    generated_specs_root: str = "generated_specs"


class YouTrackClient:
    def __init__(self, base_url: str, token: str, project_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_key = project_key

    def get_issue(self, issue_id: str) -> dict:
        fields = "id,idReadable,summary,description,tags(name),customFields(name,value(name))"
        url = f"{self.base_url}/api/issues/{parse.quote(issue_id)}?fields={fields}"
        req = request.Request(url)
        req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(f"YouTrack API error ({exc.code}): {exc.read().decode('utf-8', errors='ignore')}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"YouTrack connection error: {exc}") from exc


def tokenize(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+", text.lower()) if len(tok) > 2}


def load_specs(specs_root: Path) -> list[Path]:
    if not specs_root.exists():
        return []
    return sorted(specs_root.rglob("*.spec"))


def select_relevant_specs(issue: dict, specs: Iterable[Path]) -> list[Path]:
    issue_text = f"{issue.get('summary', '')}\n{issue.get('description', '')}"
    issue_tokens = tokenize(issue_text)

    matched: list[tuple[int, Path]] = []
    for spec in specs:
        content = spec.read_text(encoding="utf-8", errors="ignore")
        score = len(issue_tokens.intersection(tokenize(content)))
        if score > 0:
            matched.append((score, spec))

    matched.sort(key=lambda item: item[0], reverse=True)
    return [spec for _, spec in matched[:5]]


def run_gauge(gauge_bin: str, spec_paths: list[Path]) -> int:
    cmd = [gauge_bin, "run", *[str(path) for path in spec_paths]]
    print(f"[INFO] Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def generate_spec_with_ai(issue: dict, output_dir: Path) -> Path:
    """Generates a .spec file with OpenAI Responses API if OPENAI_API_KEY is set.

    If there is no key, writes a structured template for manual/next-step completion.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    issue_id = issue.get("idReadable", "UNKNOWN")
    title = issue.get("summary", "Untitled Issue")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:60] or "generated"
    target = output_dir / f"{issue_id.lower()}-{slug}.spec"

    prompt = (
        "Aşağıdaki YouTrack issue için Gauge spec yaz. "
        "Selenium ile çalışacak şekilde net adımlar üret. "
        "Türkçe senaryo adı kullan, adımlar kısa ve uygulanabilir olsun.\n\n"
        f"Issue: {json.dumps(issue, ensure_ascii=False)}"
    )

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if api_key:
        generated = _call_openai_responses(api_key=api_key, model=model, prompt=prompt)
        spec_content = generated.strip()
    else:
        spec_content = _fallback_spec_template(issue)

    target.write_text(spec_content + "\n", encoding="utf-8")
    print(f"[INFO] New spec written: {target}")
    return target


def _call_openai_responses(api_key: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You create deterministic Gauge .spec files for Selenium-based web testing.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            },
        ],
    }

    req = request.Request(
        "https://api.openai.com/v1/responses",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface API failures as runtime error
        raise RuntimeError(f"AI generation failed: {exc}") from exc

    text_parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))

    if not text_parts:
        raise RuntimeError("AI generation returned empty output.")
    return "\n".join(text_parts)


def _fallback_spec_template(issue: dict) -> str:
    summary = issue.get("summary", "Başlıksız İş")
    description = issue.get("description", "")
    return f"""# {summary}

## {summary} - Mutlu Yol
* Sayfa açılır
* Kullanıcı ilgili iş akışını başlatır
* Beklenen sonuç doğrulanır

### Notlar
- Issue ID: {issue.get('idReadable', 'N/A')}
- Açıklama: {description}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTrack -> Gauge automation orchestrator")
    parser.add_argument("issue_id", help="YouTrack issue readable id, e.g. SHOP-123")
    parser.add_argument("--specs-root", default=os.getenv("SPECS_ROOT", "specs"))
    parser.add_argument("--generated-specs-root", default=os.getenv("GENERATED_SPECS_ROOT", "generated_specs"))
    parser.add_argument("--gauge-bin", default=os.getenv("GAUGE_BIN", "gauge"))
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Config:
    base_url = os.getenv("YOUTRACK_BASE_URL", "")
    token = os.getenv("YOUTRACK_TOKEN", "")
    project_key = os.getenv("YOUTRACK_PROJECT_KEY", "")

    missing = [
        key
        for key, value in {
            "YOUTRACK_BASE_URL": base_url,
            "YOUTRACK_TOKEN": token,
            "YOUTRACK_PROJECT_KEY": project_key,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Config(
        youtrack_base_url=base_url,
        youtrack_token=token,
        project_key=project_key,
        gauge_bin=args.gauge_bin,
        specs_root=args.specs_root,
        generated_specs_root=args.generated_specs_root,
    )


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args)
        yt = YouTrackClient(config.youtrack_base_url, config.youtrack_token, config.project_key)
        issue = yt.get_issue(args.issue_id)

        specs = load_specs(Path(config.specs_root))
        relevant = select_relevant_specs(issue, specs)

        if relevant:
            print(f"[INFO] Found {len(relevant)} related spec(s). Running existing tests.")
            return run_gauge(config.gauge_bin, relevant)

        print("[INFO] No related spec found. Generating new spec with AI.")
        new_spec = generate_spec_with_ai(issue, Path(config.generated_specs_root))
        return run_gauge(config.gauge_bin, [new_spec])

    except Exception as exc:  # noqa: BLE001 - single CLI error boundary
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

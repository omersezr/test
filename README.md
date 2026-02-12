# YouTrack + AI + Gauge/Selenium Otomasyon Başlangıç Projesi

Bu proje, verdiğiniz YouTrack işi için şu akışı otomatik çalıştırır:

1. Issue'yu YouTrack API'den alır.
2. Mevcut Gauge `.spec` dosyaları içinde ilgili testleri bulmaya çalışır.
3. İlgili test varsa sadece onları çalıştırır.
4. İlgili test yoksa AI ile yeni bir `.spec` üretir ve çalıştırır.

> Hedef: "YouTrackten işi verince otomatik olarak ilgili testleri koştur, yoksa yeni test yaz" yaklaşımının MVP'si.

## Kurulum

Önkoşullar:
- Python 3.10+
- Gauge CLI (ve Selenium ile bağlı step implementation projeniz)

## Ortam değişkenleri

```bash
export YOUTRACK_BASE_URL="https://<your-domain>.youtrack.cloud"
export YOUTRACK_TOKEN="perm:xxxxxxxx"
export YOUTRACK_PROJECT_KEY="SHOP"

# Opsiyonel
export OPENAI_API_KEY="sk-..."        # varsa gerçek AI spec üretimi açılır
export OPENAI_MODEL="gpt-4.1-mini"
export GAUGE_BIN="gauge"
```

## Çalıştırma

```bash
python3 src/youtrack_gauge_orchestrator.py SHOP-123
```

## Davranış detayı

- `specs/` altındaki `.spec` dosyaları issue metni ile token bazlı eşleştirilir.
- Eşleşme varsa en yüksek skorlu ilk 5 spec çalıştırılır.
- Eşleşme yoksa `generated_specs/` altına yeni spec yazılır.
- `OPENAI_API_KEY` yoksa yine dosya üretilir ama şablon formatta olur.

## Sonraki adımlar (önerilen)

- Selenium step implementation'larını AI ile de üretmek (Java/C#/JS).
- Locator sözlüğü (`data-testid`) standardı eklemek.
- CI pipeline: her issue tetikleyicisi sonrası smoke + regression.
- YouTrack workflow/webhook ile tetikleme.

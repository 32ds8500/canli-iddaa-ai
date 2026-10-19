# Deploy Kılavuzu

## Ön koşul: geçerli API anahtarı
Sistem canlı veri için API-Football anahtarı ister. Anahtar **askıya alınmış** hesaplardan gelirse
uygulama çalışır ama veri çekemez ve bunu açıkça bildirir.
Durumu kontrol: `https://dashboard.api-football.com` veya `verify_leagues.py`.

## Ortam değişkenleri (hepsi opsiyonel; anahtar zorunlu)
| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `API_FOOTBALL_KEY` | api-football anahtarı | (boş) |
| `DATABASE_URL` | DB adresi | `sqlite:///./data/app.db` |
| `ENABLE_SCHEDULER` | Arka plan tarayıcı | `true` |
| `DAILY_QUOTA` / `PER_MINUTE_QUOTA` | Kota | `100` / `10` |
| `QUOTA_RESERVE` | Ayrılan pay | `15` |
| `LIVE_POLL_INTERVAL_SECONDS` | Canlı tarama aralığı | `180` |

> **Not (ücretsiz planlar):** Çoğu ücretsiz platformun dosya sistemi **geçicidir**.
> SQLite verisi yeniden başlatmada sıfırlanır; canlı tahmin ve performans geçmişi kalıcı olmaz.
> Kalıcılık isterseniz: Fly.io volume veya ücretsiz Postgres (Neon/Supabase) + `DATABASE_URL`.

---

## Seçenek A — Render (ücretsiz, önerilen)
1. Projeyi GitHub'a gönderin (aşağıdaki Git adımları).
2. Render → **New → Blueprint** → depoyu seçin. `render.yaml` otomatik okunur.
3. `API_FOOTBALL_KEY` değerini Render panelinde girin (`sync: false`).
4. Deploy. Sağlık kontrolü: `/api/health`.

## Seçenek B — Koyeb (ücretsiz)
1. GitHub'a gönderin.
2. Koyeb → **Create Service → GitHub** → **Dockerfile** builder.
3. Ortam değişkenlerini (özellikle `API_FOOTBALL_KEY`) ekleyin. Port `8000`.

## Seçenek C — Fly.io (kalıcı volume, kart gerekebilir)
```bash
fly launch --dockerfile Dockerfile
fly volumes create data --size 1
# fly.toml: [mounts] source="data" destination="/app/backend/data"
fly secrets set API_FOOTBALL_KEY=...
fly deploy
```

## Seçenek D — Bu cihazda yayınla (hesap gerekmez, ücretsiz)
Yerel çalıştır + Cloudflare hızlı tünel:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
cloudflared tunnel --url http://localhost:8000
```
- `https://<rastgele>.trycloudflare.com` adresi verir. Hesap gerekmez.
- URL geçicidir ve cihaz açık kaldıkça çalışır.

---

## Git ile yayına hazırlama
```bash
cd canli-iddaa-ai
git init
git add .
git commit -m "Canli Iddaa AI"
git branch -M main
git remote add origin https://github.com/<kullanici>/<repo>.git
git push -u origin main
```
`.gitignore` sayesinde `backend/.env` ve `*.db` **git'e girmez** (anahtar sızmaz).

## Docker ile yerel test (docker varsa)
```bash
docker build -t canli-iddaa-ai .
docker run --rm -p 8000:8000 -e API_FOOTBALL_KEY=... canli-iddaa-ai
```

## Üretim uyarıları
- Anahtarı asla commit etmeyin / paylaşmayın.
- Ücretsiz katmanda kota 100/gün; birden fazla örnek (instance) kotayı paylaşır.
- Ağır tarama (scheduler) açıkken ücretsiz platform uykuya dalıp kotayı boşa harcayabilir;
  gerekirse `ENABLE_SCHEDULER=false` yapıp yalnızca manuel yenileme kullanın.

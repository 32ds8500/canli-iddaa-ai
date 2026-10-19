# Kurulum ve Çalıştırma

Bu kılavuz, Canlı İddaa AI sistemini sıfırdan kurup çalıştırmak içindir.
Termux/PRoot (aarch64, Ubuntu) ortamlarında da test edilmiştir.

## 1. Gereksinimler
- Python 3.11+ (bu makinede 3.14)
- Node.js 18+ ve npm (yalnızca arayüz için)
- API-Football anahtarı (canlı veri için **zorunlu**)

## 2. Sağlayıcı seçimi

### A) FotMob — anahtar GEREKMEZ (önerilen)
```bash
cp backend/.env.example backend/.env
# .env icinde: PROVIDER_MODE=fotmob
```
FotMob herkese açık JSON uçları kullanır; kayıt/anahtar gerekmez.
Sağladığı alanlar: skor, dakika, şut, isabetli şut, korner, kart, topla oynama, xG.

### B) API-Football — anahtar gerekir
1. https://www.api-football.com adresinden ücretsiz hesap açıp API anahtarı alın.
2. `.env` içinde:
   ```
   PROVIDER_MODE=api-football
   API_FOOTBALL_KEY=sizin_anahtariniz
   ```
   (RapidAPI üzerinden aldıysanız `RAPIDAPI_KEY=...` kullanın.)
3. Anahtar **yalnızca sunucuda** kalır; tarayıcıya gönderilmez.
4. Hesap askıya alınmışsa API `{"errors":{"access":"Your account is suspended..."}}` döner;
   sistem bunu açıkça bildirir ve **sahte veri üretmez**.

## 3. Backend
```bash
cd backend
python3 -m pip install -r requirements.txt
PROVIDER_MODE=fotmob python3 scripts/verify_leagues.py
PROVIDER_MODE=fotmob uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- `verify_leagues.py`, 7 organizasyonu gerçek sağlayıcı yanıtıyla doğrular ve sonucu veritabanına yazar.
  - FotMob modunda anahtar gerekmez; 7/7 doğrulanır.
  - API-Football modunda anahtar yoksa **çıkış kodu 2** ile biter (hata değil, uyarıdır).
  - Beklenmeyen bir organizasyon kimliği çıkarsa açıkça bildirir; **kimlikler asla varsayılmaz**.

### Ortam değişkenleri (öne çıkanlar)
`backend/.env.example` dosyasına bakın. Başlıcaları:

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `PROVIDER_MODE` | `auto` / `fotmob` / `api-football` | `auto` |
| `API_FOOTBALL_KEY` | API-Football anahtarı (opsiyonel) | (boş) |
| `RAPIDAPI_KEY` | RapidAPI üzerinden API-Football | (boş) |
| `DATABASE_URL` | Veritabanı adresi | `sqlite:///./data/canli_iddaa.db` |
| `ENABLE_SCHEDULER` | Arka plan zamanlayıcı | `true` |
| `LIVE_REFRESH_SECONDS` | Canlı yenileme aralığı | `45` |
| `ENRICH_WATCHLIST_LIMIT` | Tur başına zenginleştirilecek maç | `3` |
| `QUOTA_DAILY_LIMIT` | Günlük istek limiti | `100` |
| `QUOTA_PER_MINUTE_LIMIT` | Dakikalık istek limiti | `10` |
| `QUOTA_RESERVE` | Ayrılan kontenjan | `15` |

## 4. Frontend (geliştirme)
```bash
cd frontend
npm install
npm run dev
```
- http://localhost:5173 adresinde açılır; `/api` ve `/ws` istekleri 8000 portuna yönlendirilir.

## 5. Frontend (üretim derlemesi)
```bash
cd frontend
npm run build
```
- `frontend/dist/` üretilir. Backend başlatıldığında bu klasör varsa arayüz doğrudan
  `http://localhost:8000/` üzerinden sunulur.

## 6. Testler
```bash
cd backend
python3 -m pytest -q
```
Testler sahte sağlayıcı ve geçici SQLite kullanır; gerçek ağ/kota tüketmez.

## Sık karşılaşılan sorunlar

### "Cannot find module .../glob/dist/cjs/src/index.js" (npm bozuk)
Bazı dağıtımlarda `glob` paketi eksik paketlenir. Çözüm:
```bash
curl -sSL --http1.1 -o /tmp/glob.tgz https://registry.npmjs.org/glob/-/glob-10.3.6.tgz
rm -rf /usr/share/node_modules/glob
mkdir -p /usr/share/node_modules/glob
tar -xzf /tmp/glob.tgz -C /tmp
cp -r /tmp/package/. /usr/share/node_modules/glob/
```

### npm "@rolldown/pluginutils tarball corrupted"
Bu proje bilinçli olarak React eklentisiz (esbuild JSX) Vite yapılandırması kullanır.
Ek bir React/Babel/Rolldown eklentisi eklemeyin. Önbellek bozuksa:
```bash
rm -rf ~/.npm/_cacache frontend/node_modules frontend/package-lock.json
npm install --no-fund --no-audit
```

### curl takılıyor
Bazı ortamlarda HTTP/2 sorun çıkarır; `curl --http1.1` kullanın.

### Canlı maç gelmiyor
1. `backend/.env` içinde `API_FOOTBALL_KEY` var mı?
2. `python3 scripts/verify_leagues.py` çıktısına bakın.
3. Arayüzde "Canlıyı yenile" düğmesine basın.
4. Kota dolmuşsa bekleyin; sistem otomatik ücretli plana **geçmez**.

## Güvenlik notları
- API anahtarını asla commit etmeyin (`.env` sürüm kontrolüne girmemeli).
- Üretimde `uvicorn`u bir ters proxy (nginx) arkasında ve HTTPS ile çalıştırın.

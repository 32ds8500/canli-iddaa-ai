# Canlı İddaa AI

Canlı futbol maçları için **gol** ve **korner** olasılıklarını ayrı modellerle üreten, tahminleri sürümleyerek kaydeden ve gerçek sonuçlarla karşılaştırıp performansı (Brier, LogLoss, kalibrasyon) ölçen analiz sistemi.

> **Önemli:** Bu yazılım bir **tahmin/analiz aracıdır**. Ürettiği olasılıklar kesinlik, kazanç veya bahis garantisi **değildir**. Yetersiz veri olduğunda sistem sonuç üretmez ve "Yetersiz veri" gösterir.

---

## Ne yapar?

- **Gerçek canlı veri:** Tek sağlayıcı (API-Football / api-sports.io) üzerinden canlı skor, dakika, şut, korner, tehlikeli atak, kart, topla oynama ve (varsa) xG çeker.
- **İki ayrı motor:** Gol olasılıkları ve korner olasılıkları birbirinden bağımsız hesaplanır.
- **Veri kalitesi:** İstatistik eksik/çelişkili olduğunda o tahmin üretilmez; arayüzde "Yetersiz veri" ve gerekçesi gösterilir.
- **Kayıt & ölçüm:** Her tahmin zaman damgası, dakika, skor, model adı/sürümü ve veri kalitesiyle saklanır. Maç bittiğinde sonuç eşleştirilir; Brier, LogLoss ve kalibrasyon hesaplanır.
- **Kota dostu:** Günlük 100 / dakikada 10 istek sınırına uyar, kontenjan ayırır, asla otomatik ücretli plana geçmez.

### 7 hedef organizasyon
Türkiye Süper Lig, İtalya Serie A, İspanya La Liga, Fransa Ligue 1, UEFA Şampiyonlar Ligi, UEFA Avrupa Ligi, UEFA Konferans Ligi.

> Sağlayıcı kimlikleri (league id) **varsayılmaz**; `scripts/verify_leagues.py` ile gerçek `/leagues` yanıtından **doğrulanır**.

---

## Mimari

```
backend/
  app/
    config.py            # ayarlar (.env)
    db.py                # SQLAlchemy + SQLite
    models/entities.py   # League, Team, Match, MatchStat, MatchEvent, StatSnapshot, Prediction, PredictionOutcome
    providers/           # api_football (birincil), football_data (ikincil), quota, cache, fixture
    ingest/              # canlı çekim + normalizasyon (veri kalitesi)
    engines/             # gol ve korner modelleri, özellik üretimi, güven, temel oranlar
    eval/                # sonuç eşleştirme, metrikler, kronolojik bölme, rapor
    services/            # tahmin servisi, maç görünümü, scheduler
    api/                 # FastAPI rotaları (sistem, maçlar, performans)
    main.py              # uygulama girişi (+ /ws/live, statik arayüz)
  scripts/verify_leagues.py
  tests/                 # birim + entegrasyon + API + uç durumlar
frontend/                # React + TypeScript (Vite) mobil öncelikli arayüz
```

- Sağlayıcı katmanı **arayüz (interface) arkasında** olduğundan ileride farklı sağlayıcı eklenebilir.
- Modeller **ağırlık tahminleri değil**, açıklanabilir istatistiksel olasılıklar üretir (şut/korner oranları, kalan süre, lig temel oranı).

---

## Hızlı Başlangıç

Ayrıntılı adımlar ve sorun giderme için: [`docs/KURULUM.md`](docs/KURULUM.md).

```bash
# 1) Backend
cd backend
cp .env.example .env          # API_FOOTBALL_KEY değerini girin
python3 -m pip install -r requirements.txt
python3 scripts/verify_leagues.py   # 7 organizasyonu gerçek yanıtla doğrular
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2) Frontend (geliştirme)
cd ../frontend
npm install
npm run dev                   # http://localhost:5173

# 3) Frontend (üretim derlemesi, backend tarafından sunulur)
npm run build                 # dist/ üretir; backend / arayüzü statik sunar
```

### API anahtarı
`backend/.env` içindeki `API_FOOTBALL_KEY` **sunucu tarafında** tutulur, tarayıcıya asla gönderilmez. Anahtar yoksa uygulama çalışır ama **canlı veri çekemez** ve bunu açıkça bildirir.

---

## Test

```bash
cd backend
python3 -m pytest -q
```

- Testler **izole** bir SQLite veritabanı ve **sahte (fake) sağlayıcı** kullanır → ağ/kota tüketmez.
- Kapsam: kota davranışı, metrikler (Brier/LogLoss), kronolojik bölme, normalizasyon/veri kalitesi, gol & korner motorları, özellik üretimi, sonuç eşleştirme, API akışları ve uç durumlar (429, bağlantı kesintisi).

---

## Performans ölçümü ilkeleri

- **Sızıntısız:** Eğitim/değerlendirme **kronolojik** ayrılır; gelecek veri geçmişi etkilemez.
- **Dürüst:** En az 30 sonuçlanmış tahmin olmadan yüzde/performans gösterilmez.
- **Şeffaf:** Her segment için Brier, LogLoss, temel oran ve kalibrasyon tablosu verilir.
- **Temel oran (baseline):** Lig ortalaması **priori** olarak etiketlenir; ölçülmüş gibi sunulmaz.

---

## Sınırlamalar (dürüstçe)

- API-Football ücretsiz planı sınırlı sezon/kotaya sahiptir (100 istek/gün, 10 istek/dk).
- `football-data.org` ücretsiz katmanı Süper Lig, Avrupa Ligi ve Konferans Ligi'ni **kapsamaz** ve canlı ayrıntılı istatistik sunmaz; yalnızca ikincil kaynak olarak belgelenmiştir.
- xG her ligde bulunmayabilir; bulunmayan yerlerde model xG'siz çalışır ve bu durum belirtilir.

## Lisans
Bu proje eğitim/analiz amaçlıdır. Kullanım sorumluluğu kullanıcıya aittir.

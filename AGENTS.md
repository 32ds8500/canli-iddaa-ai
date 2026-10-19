# AGENTS.md — Canlı İddaa AI

Bu dosya, projede çalışan geliştiriciler ve otomatik ajanlar için kısa yönergeler içerir.

## Proje özeti
Gerçek canlı futbol verisiyle **gol** ve **korner** olasılığı üreten analiz sistemi.
Backend: FastAPI + SQLAlchemy + SQLite (`backend/`). Arayüz: React + TypeScript + Vite (`frontend/`).

## Sık kullanılan komutlar

### Backend
```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m pytest -q                      # tüm testler (sahte sağlayıcı, ağ yok)
python3 scripts/verify_leagues.py         # 7 organizasyonu gerçek API ile doğrular (anahtar gerekir)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # geliştirme (5173), /api ve /ws -> 8000
npm run build      # tsc --noEmit && vite build -> dist/
```

## Değişiklikten sonra zorunlu doğrulama
1. `cd backend && python3 -m pytest -q` → **tüm testler geçmeli**.
2. Frontend'e dokunduysanız: `cd frontend && npm run build` → tip hatası olmadan derlenmeli.

## Mimari kurallar (bozmayın)
- **Gerçek veri şart:** Asla sahte/simüle veriyle "tahmin" üretmeyin. Sahte veri yalnızca **testlerde** kullanılır.
- **İki ayrı motor:** Gol ve korner mantığı `backend/app/engines/` altında ayrı kalmalı.
- **Yetersiz veri:** İstatistik eksik/çelişkiliyse tahmin üretilmez; "Yetersiz veri" + gerekçe döner.
- **Dürüst metrikler:** 30'dan az sonuçlanmış örnekte yüzde/performans gösterilmez.
- **Kota:** Günlük 100 / dakikada 10. Otomatik ücretli plana geçiş **yok**. Kota mantığı `backend/app/providers/quota.py`.
- **Sağlayıcı soyutlama:** Sağlayıcılar `FootballProvider` arayüzünü (`backend/app/providers/base.py`) uygular.
- **Tahmin sürümleme:** Tahminler değiştirilmez; `(match, market, model_version, dakika)` ile tekilleştirilir.
- **API anahtarı sunucuda:** `backend/.env` içinde; istemciye gönderilmez, commit edilmez.
- **SQLAlchemy:** Oturum `autoflush=False` kullanır. Yeni kayıt ekledikten sonra **aynı oturumda sorgulayacaksanız önce `db.flush()` çağırın** (aksi halde bekleyen satırlar görünmez).
- **Kod yorumları:** Kullanıcı istemedikçe yorum eklemeyin. Mevcut Türkçe/ASCII-tabanlı üslubu koruyun.

## Ortam notları (Termux/PRoot)
- Bazı ortamlarda `npm` bozuk olabilir (`glob` paketi eksik paketlenir). Ayrıntı: `docs/KURULUM.md`.
- Vite yapılandırması bilinçli olarak **React eklentisi olmadan** esbuild JSX kullanır (Rolldown tarball sorununu önlemek için). React/Babel/Rolldown eklentisi eklemeyin.
- `curl` HTTP/2'de takılabilir; `curl --http1.1` kullanın.

## Önemli dosyalar
- `backend/app/ingest/live.py` — canlı çekim + zenginleştirme (flush kuralı burada kritik).
- `backend/app/engines/` — modeller ve özellik üretimi.
- `backend/app/eval/` — sonuç eşleştirme, metrikler, rapor.
- `backend/app/providers/api_football.py` — birincil sağlayıcı.
- `backend/tests/` — birim/entegrasyon/API/uç durum testleri.
- `frontend/src/` — arayüz bileşenleri ve API istemcisi.

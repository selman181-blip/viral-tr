# Viral TR (YouTube)

Türkiye'de YouTube'da patlayan videoları bulur. **LLM/Claude çağrısı yoktur**, maliyet sıfırdır.

## Nasıl çalışır
- `mostPopular` (regionCode=TR) listelerini 11 kategori için çeker (günlük kota: ~12 birim/çalışma, limit 10.000).
- Türkçe olmayanları ve 72 saatten eski videoları eler.
- Skor = saatlik izlenme hızı (45) + izlenme/abone oranı (35) + etkileşim (20).
- Her çalışmada izlenme SQLite'a kaydedilir; ikinci çalışmadan itibaren iki ölçüm arası **gerçek hız** kullanılır.
- Çıktı: `docs/index.html` (GitHub Pages) + opsiyonel Telegram.

## Kurulum
1. Google Cloud Console > YouTube Data API v3'ü aç > API anahtarı oluştur.
2. GitHub repo > Settings > Secrets > Actions: `YT_API_KEY` ekle.
   (Telegram istersen: @BotFather ile bot aç, `TG_TOKEN` ve `TG_CHAT_ID` ekle.)
3. `viral.yml` dosyasını `.github/workflows/viral.yml` olarak koy.
4. Settings > Pages > Source: `main` branch, `/docs` klasörü.
5. Actions sekmesinden `viral-tr` iş akışını elle bir kez çalıştır.

## Yerelde çalıştırma
```
pip install -r requirements.txt
YT_API_KEY=anahtarin python main.py
```

## Sonraki adımlar
- X: Türkiye gündem listesi + gündem konularında tweet metrikleri
- Instagram: izleme listesindeki hesaplar (Türkiye IP'li ortam gerekir)

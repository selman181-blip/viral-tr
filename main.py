"""YouTube TR viral bulucu. Claude/LLM çağrısı YOKTUR; sadece YouTube Data API + SQLite.

Ortam değişkenleri:
  YT_API_KEY   (zorunlu)
  TG_TOKEN, TG_CHAT_ID  (opsiyonel, Telegram bildirimi)
"""
import html
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

from scoring import score_video, hours_since

API = "https://www.googleapis.com/youtube/v3"
KEY = os.environ.get("YT_API_KEY")
DB_PATH = "viral.db"
MAX_AGE_HOURS = 72          # bundan eski videolar viral sayılmaz
TOP_N = 30
# YouTube kategorileri: müzik, oyun, komedi, eğlence, haber, spor, film vs.
CATEGORIES = [None, "1", "10", "17", "20", "22", "23", "24", "25", "26", "28"]
TR_CHARS = re.compile(r"[ığüşöçİĞÜŞÖÇ]")


def yt(path, **params):
    params["key"] = KEY
    r = requests.get(f"{API}/{path}", params=params, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def fetch_candidates():
    """Türkiye 'mostPopular' listelerini kategori kategori toplar (her çağrı 1 kota)."""
    found = {}
    for cat in CATEGORIES:
        p = dict(part="snippet,statistics", chart="mostPopular", regionCode="TR", maxResults=50)
        if cat:
            p["videoCategoryId"] = cat
        data = yt("videos", **p)
        if not data:
            continue
        for it in data.get("items", []):
            found[it["id"]] = it
    return list(found.values())


def is_turkish(snippet):
    lang = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").lower()
    if lang:
        return lang.startswith("tr")
    return bool(TR_CHARS.search(snippet.get("title", "")))


def fetch_subs(channel_ids):
    subs = {}
    ids = list(channel_ids)
    for i in range(0, len(ids), 50):
        data = yt("channels", part="statistics", id=",".join(ids[i:i + 50]))
        if not data:
            continue
        for it in data.get("items", []):
            s = it["statistics"]
            subs[it["id"]] = None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0))
    return subs


def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS snap (vid TEXT, ts REAL, views INTEGER)")
    con.execute("CREATE INDEX IF NOT EXISTS i_snap ON snap(vid, ts)")
    return con


def recent_speed(con, vid, views, now_ts):
    """Önceki ölçümle şimdiki ölçüm arasındaki gerçek izlenme hızı (izlenme/saat)."""
    row = con.execute("SELECT ts, views FROM snap WHERE vid=? ORDER BY ts DESC LIMIT 1", (vid,)).fetchone()
    if not row:
        return None
    dh = (now_ts - row[0]) / 3600
    if dh < 0.5:
        return None
    return max(views - row[1], 0) / dh


def build_report(videos):
    rows = []
    for i, v in enumerate(videos, 1):
        url = f"https://www.youtube.com/watch?v={v['id']}"
        rows.append(
            f"<tr><td>{i}</td><td><a href='{url}'>{html.escape(v['title'])}</a>"
            f"<br><small>{html.escape(v['channel'])}</small></td>"
            f"<td>{v['score']}</td><td>{v['views']:,}</td><td>{v['vph']:,}</td>"
            f"<td>{v['reach']}x</td><td>%{v['eng']}</td><td>{v['age_h']} sa</td></tr>"
        )
    now = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Viral TR</title>
<style>body{{font-family:system-ui;margin:16px;max-width:1000px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left}}
a{{text-decoration:none}}</style></head><body>
<h2>Türkiye YouTube - Viral Liste</h2><p>Güncelleme: {now} (TSİ)</p>
<table><tr><th>#</th><th>Video</th><th>Skor</th><th>İzlenme</th><th>İzl./saat</th><th>İzl./abone</th><th>Etkileşim</th><th>Yaş</th></tr>
{''.join(rows)}</table></body></html>"""


def send_telegram(videos):
    token, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not token or not chat:
        return
    lines = ["🔥 Türkiye viral YouTube (ilk 10)\n"]
    for i, v in enumerate(videos[:10], 1):
        lines.append(f"{i}. {v['title']}\n   {v['channel']} | skor {v['score']} | {v['vph']:,} izl./saat\n   https://youtu.be/{v['id']}")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  data={"chat_id": chat, "text": "\n".join(lines), "disable_web_page_preview": True},
                  timeout=30)


def main():
    if not KEY:
        sys.exit("YT_API_KEY ortam değişkeni tanımlı değil.")
    now_ts = time.time()
    items = fetch_candidates()
    items = [it for it in items if is_turkish(it["snippet"])
             and hours_since(it["snippet"]["publishedAt"]) <= MAX_AGE_HOURS]
    subs = fetch_subs({it["snippet"]["channelId"] for it in items})

    con = db_connect()
    videos = []
    for it in items:
        sn, st = it["snippet"], it.get("statistics", {})
        views = int(st.get("viewCount", 0))
        v = dict(
            id=it["id"], title=sn["title"], channel=sn["channelTitle"],
            published_at=sn["publishedAt"], views=views,
            likes=int(st.get("likeCount", 0)), comments=int(st.get("commentCount", 0)),
            subs=subs.get(sn["channelId"]),
            recent_vph=recent_speed(con, it["id"], views, now_ts),
        )
        videos.append(score_video(v))
        con.execute("INSERT INTO snap VALUES (?,?,?)", (it["id"], now_ts, views))
    con.commit()
    con.close()

    videos.sort(key=lambda x: x["score"], reverse=True)
    videos = videos[:TOP_N]
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_report(videos))
    send_telegram(videos)
    print(f"{len(videos)} video listelendi -> docs/index.html")


if __name__ == "__main__":
    main()

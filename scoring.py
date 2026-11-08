"""Viral skoru: tamamen kural/sayı tabanlı, LLM veya token kullanmaz."""
import math
from datetime import datetime, timezone


def hours_since(published_iso, now=None):
    now = now or datetime.now(timezone.utc)
    p = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
    return max((now - p).total_seconds() / 3600, 0.5)


def score_video(v, now=None):
    """
    v: dict -> published_at, views, likes, comments, subs, (opsiyonel) recent_vph
    Üç sinyal birleşir:
      1) Hız: saatlik izlenme (varsa iki ölçüm arasındaki gerçek hız)
      2) Kanal normu: izlenme / abone (küçük kanaldan patlayanı yakalar)
      3) Etkileşim: (beğeni + 2*yorum) / izlenme
    """
    h = hours_since(v["published_at"], now)
    views = v["views"]
    vph = views / h
    if v.get("recent_vph"):
        vph = max(vph, v["recent_vph"])

    subs = max(v.get("subs") or 0, 1000)  # gizli/çok küçük kanallarda patlamayı önle
    reach = views / subs
    eng = (v["likes"] + 2 * v["comments"]) / max(views, 1)

    speed_pts = min(math.log10(1 + vph) / 5, 1.0) * 45        # ~100k izlenme/saat = tam puan
    reach_pts = min(math.log10(1 + reach) / 1.5, 1.0) * 35    # ~30x abone = tam puan
    eng_pts = min(eng / 0.10, 1.0) * 20                       # %10 etkileşim = tam puan

    v["vph"] = round(vph)
    v["reach"] = round(reach, 2)
    v["eng"] = round(eng * 100, 2)
    v["age_h"] = round(h, 1)
    v["score"] = round(speed_pts + reach_pts + eng_pts, 1)
    return v

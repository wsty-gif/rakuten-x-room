"""行事・カテゴリ別の「特集記事」用データを楽天から集める。

  - 定番テーマ（data/topics_config.json の evergreen）: 7日ごとに取り直す
  - 行事テーマ（data/calendar.json の events）: 開始の45日前から、2日ごとに取り直す（Pinterest は30〜45日先を探す人が多い）
結果は data/topics.json に保存し、build_site.py が topics/<slug>.html を生成する。
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any

from .config import CALENDAR_FILE, DATA_DIR, Settings
from .rakuten_client import Product, RakutenClient

TOPICS_FILE = DATA_DIR / "topics.json"
CONFIG_FILE = DATA_DIR / "topics_config.json"


def load_topics() -> dict[str, Any]:
    if TOPICS_FILE.exists():
        try:
            return json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _score(p: Product) -> float:
    sc = math.log10(p.review_count + 1) * 2.0 + (p.review_average - 4.0) * 3.0
    sc += min(p.affiliate_rate, 10) * 0.4 + min(p.point_rate, 10) * 0.2
    if 1500 <= p.price <= 15000:
        sc += 1.0
    if "中古" in p.name or "ジャンク" in p.name:
        sc -= 10
    return sc


def _to_dict(p: Product) -> dict[str, Any]:
    d = p.to_dict()
    d["score"] = round(_score(p), 2)
    return d


def fetch_topic_items(client: RakutenClient, keywords: list[str], min_rc: int = 50, min_avg: float = 4.2,
                      limit: int = 15) -> list[dict[str, Any]]:
    pool: dict[str, Product] = {}
    for kw in keywords[:3]:
        for page in (1, 2):
            try:
                for p in client.search(kw, None, 1000, 40000, sort="-reviewCount", hits=30, page=page):
                    if p.item_code not in pool:
                        pool[p.item_code] = p
            except Exception as e:
                print(f"  [warn] topic search {kw} p{page}: {e}")
                break
    items = [p for p in pool.values() if p.review_count >= min_rc and p.review_average >= min_avg and p.price > 0]
    items.sort(key=_score, reverse=True)
    out, shops = [], {}
    for p in items:
        if shops.get(p.shop_name, 0) >= 2:
            continue
        shops[p.shop_name] = shops.get(p.shop_name, 0) + 1
        out.append(_to_dict(p))
        if len(out) >= limit:
            break
    return out


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text.encode("ascii", "ignore").decode() or "").strip("-").lower()
    return s or "ev"


def refresh_topics(s: Settings, today: date | None = None, force: bool = False) -> dict[str, Any]:
    today = today or date.today()
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    cal = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    topics = load_topics()
    client = RakutenClient(s)
    refresh_days = int(cfg.get("refresh_days", 7))
    lead = int(cfg.get("event_lead_days", 45))
    now_iso = datetime.now().isoformat(timespec="seconds")
    n_fetched = 0

    def stale(t: dict[str, Any] | None, days: int) -> bool:
        if force or not t or not t.get("updated"):
            return True
        return datetime.fromisoformat(t["updated"]) < datetime.now() - timedelta(days=days)

    # ---- 定番テーマ ----
    for e in cfg.get("evergreen", []):
        slug = e["slug"]
        t = topics.get(slug)
        if not stale(t, refresh_days):
            continue
        items = fetch_topic_items(client, [e["keyword"]])
        if not items:
            continue
        topics[slug] = {"slug": slug, "kind": "evergreen", "title": e["title"], "keyword": e["keyword"],
                        "persona": e.get("persona", "all"), "months": e.get("months", []), "items": items,
                        "updated": now_iso, "first_seen": (t or {}).get("first_seen", now_iso)}
        n_fetched += 1

    # ---- 行事テーマ（45日前〜終了日）----
    for ev in cal.get("events", []):
        start = datetime.strptime(ev["start"], "%Y-%m-%d").date()
        end = datetime.strptime(ev["end"], "%Y-%m-%d").date()
        if not (start - timedelta(days=lead) <= today <= end):
            continue
        if not ev.get("keywords"):
            continue
        name = re.sub(r"（.*?）", "", ev["name"]).strip()
        slug = f"event-{ev['start']}-{_slug(name) if _slug(name) != 'ev' else abs(hash(name)) % 10000}"
        t = topics.get(slug)
        if not stale(t, 2):
            continue
        items = fetch_topic_items(client, ev["keywords"])
        if not items:
            continue
        topics[slug] = {"slug": slug, "kind": "event", "title": name, "keyword": ev["keywords"][0],
                        "event_type": ev.get("type", "season"), "start": ev["start"], "end": ev["end"],
                        "persona": (ev.get("targets") or ["all"])[0], "targets": ev.get("targets", []),
                        "hook": ev.get("hook", ""), "items": items, "updated": now_iso,
                        "first_seen": (t or {}).get("first_seen", now_iso)}
        n_fetched += 1

    # 終了して30日以上たった行事は外す（記事は残さない）
    for slug in list(topics):
        t = topics[slug]
        if t.get("kind") == "event" and t.get("end"):
            if datetime.strptime(t["end"], "%Y-%m-%d").date() + timedelta(days=30) < today:
                del topics[slug]

    DATA_DIR.mkdir(exist_ok=True)
    TOPICS_FILE.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[topics] 更新 {n_fetched} 件 / 合計 {len(topics)} テーマ")
    return topics


def topic_priority(t: dict[str, Any], today: date | None = None) -> float:
    """サイドバーや一覧での並び順。行事は近いほど上、定番は今月に検索される物を上。"""
    today = today or date.today()
    if t.get("kind") == "event":
        start = datetime.strptime(t["start"], "%Y-%m-%d").date()
        days = (start - today).days
        return 100 - min(abs(days), 60)
    months = t.get("months") or []
    return 50 + (10 if not months or today.month in months else 0)

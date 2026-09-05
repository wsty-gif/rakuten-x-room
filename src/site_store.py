"""ブログ生成用に、実行ごとの候補商品とテーマを data/site_items.json へ蓄積する。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .config import DATA_DIR
from .rakuten_client import Product
from .trend_engine import Theme

SITE_ITEMS_FILE = DATA_DIR / "site_items.json"
KEEP_DAYS_ITEMS = 400   # 1商品につき保持するテーマ履歴の上限


def load_site_items() -> dict[str, Any]:
    if SITE_ITEMS_FILE.exists():
        try:
            return json.loads(SITE_ITEMS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_site_items(cands: list[Product], theme: Theme, posts: list[dict[str, Any]], limit: int = 12) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    store = load_site_items()
    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    day = now.strftime("%Y-%m-%d")
    posted = {pst["product"].item_code: pst["text"] for pst in posts}

    for p in cands[:limit]:
        e = store.get(p.item_code) or {"first_seen": stamp, "themes": []}
        e.update({
            "item_code": p.item_code, "name": p.name, "price": p.price,
            "item_url": p.item_url, "affiliate_url": p.affiliate_url, "image_url": p.image_url,
            "shop_name": p.shop_name, "review_count": p.review_count, "review_average": p.review_average,
            "affiliate_rate": p.affiliate_rate, "point_rate": p.point_rate, "catchcopy": p.catchcopy,
            "genre_id": p.genre_id, "score": round(p.score, 2), "last_seen": stamp,
        })
        # 同じ日に同じテーマで複数回出た場合は1件にまとめる
        themes = [t for t in e["themes"] if not (t["date"] == day and t["slot"] == theme.slot)]
        themes.append({"date": day, "slot": theme.slot, "theme": theme.title,
                       "persona": theme.persona.key, "event_type": theme.event_type})
        e["themes"] = themes[-KEEP_DAYS_ITEMS:]
        if p.item_code in posted:
            e["posted_text"] = posted[p.item_code]
            e["posted_at"] = stamp
        store[p.item_code] = e

    SITE_ITEMS_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")

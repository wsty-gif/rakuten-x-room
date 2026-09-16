"""楽天ROOMは規約で機械的な投稿が禁止されているため、人が「コレ！」するための一覧を出力する。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import OUTPUT_DIR
from .rakuten_client import Product


def write_room_todo(picks: list[tuple[Product, str]], theme_title: str,
                    collections: dict[str, list[str]] | None = None) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = OUTPUT_DIR / f"room_todo_{today}.md"
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(f"# 楽天ROOMに追加する商品（{today}）\n\n")
            f.write("手順: 商品URLを開く → 共有 → 「ROOMに投稿」 → コメントを貼って投稿。\n")
            f.write("夜の分は20時までに入れておくと、購買ピーク（21〜24時）に乗ります。\n\n")
        f.write(f"## {datetime.now().strftime('%H:%M')} {theme_title}\n\n")
        for i, (p, comment) in enumerate(picks, 1):
            f.write(f"{i}. **{p.name[:60]}**\n")
            f.write(f"   - 価格: {p.price:,}円 / ★{p.review_average}（{p.review_count:,}件） / 料率 {p.affiliate_rate}% / P{p.point_rate}倍\n")
            f.write(f"   - 商品URL: {p.item_url}\n")
            f.write(f"   - コメント: {comment}\n\n")
        if collections:
            f.write("### コレクション案（ROOMの「コレクション」でまとめると回遊が増える）\n\n")
            for name, items in collections.items():
                f.write(f"- **{name}**: " + " / ".join(items) + "\n")
            f.write("\n")
    latest = OUTPUT_DIR / "room_todo_latest.md"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return str(path)

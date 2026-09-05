"""楽天ROOMは規約で機械的な投稿が禁止されているため、人が「コレ！」するための一覧を出力する。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import OUTPUT_DIR


def write_room_todo(posts: list[dict[str, Any]], theme_title: str) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = OUTPUT_DIR / f"room_todo_{today}.md"
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(f"# 楽天ROOMに追加する商品（{today}）\n\n")
            f.write("手順: ROOMアプリ → 「コレ！」 → 商品URLを貼って検索 → 一言コメントを付けて投稿。\n")
            f.write("投稿前にROOMへ追加しておくと、Xから来た人がすぐ見つけられます。\n\n")
        f.write(f"## {datetime.now().strftime('%H:%M')} {theme_title}\n\n")
        for i, pst in enumerate(posts, 1):
            p = pst["product"]
            lines = pst["text"].splitlines()
            comment = lines[1] if len(lines) > 1 else ""
            f.write(f"{i}. **{p.name[:60]}**\n")
            f.write(f"   - 価格: {p.price:,}円 / ★{p.review_average}（{p.review_count:,}件） / 料率 {p.affiliate_rate}%\n")
            f.write(f"   - 商品URL（ROOM検索用）: {p.item_url}\n")
            f.write(f"   - ROOM用コメント案: {comment}\n\n")
    latest = OUTPUT_DIR / "room_todo_latest.md"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return str(path)

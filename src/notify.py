"""スマホへのプッシュ通知（ntfy.sh）。投稿した商品をROOMに追加してもらうために送る。

ntfy は無料・アカウント不要の通知サービス。スマホに ntfy アプリを入れ、
.env の NTFY_TOPIC と同じ名前のトピックを購読しておくだけで届く。
トピック名は他人に推測されない長いランダム文字列にすること（例: rakumitsu-room-7f3k9q2x）。
"""
from __future__ import annotations

from typing import Any

import requests

from .config import _env


def send(topic: str, title: str, message: str, click: str = "", server: str = "https://ntfy.sh") -> bool:
    payload: dict[str, Any] = {"topic": topic, "title": title, "message": message, "tags": ["shopping_bags"]}
    if click:
        payload["click"] = click
        payload["actions"] = [{"action": "view", "label": "楽天で開く", "url": click}]
    r = requests.post(server.rstrip("/"), json=payload, timeout=15)
    if r.status_code >= 300:
        print(f"  [warn] ntfy {r.status_code}: {r.text[:100]}")
        return False
    return True


def notify_room_todo(posts: list[dict[str, Any]], theme_title: str) -> bool:
    topic = _env("NTFY_TOPIC")
    if not topic:
        return False
    server = _env("NTFY_SERVER", "https://ntfy.sh")
    ok = True
    for pst in posts:
        p = pst["product"]
        lines = [l for l in pst["text"].splitlines() if l.strip() and not l.startswith("#") and "ROOMはプロフ" not in l]
        comment = " ".join(lines)[:120]
        title = "ROOMに追加: " + p.name[:40]
        # 1行目はROOM用コメントだけにする（スマホで長押しコピーしてそのまま貼れる）
        body = (f"{comment}\n\n"
                f"― ↑この1行をROOMのコメントに貼る ―\n"
                f"{p.price:,}円 ★{p.review_average}（{p.review_count:,}件）\n"
                f"タップ → 楽天アプリ → 共有 → ROOMに投稿")
        try:
            ok = send(topic, title, body, p.item_url, server) and ok
        except Exception as e:
            print(f"  [warn] ntfy 送信失敗: {e}")
            ok = False
    if ok:
        print(f"  [ntfy] スマホに {len(posts)} 件の通知を送りました（トピック: {topic}）")
    return ok

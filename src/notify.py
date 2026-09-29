"""スマホへのプッシュ通知（ntfy.sh）。ROOMに追加する商品を、コメント付きで送る。

ntfy は無料・アカウント不要の通知サービス。スマホに ntfy アプリを入れ、
.env の NTFY_TOPIC と同じ名前のトピックを購読しておくだけで届く。
トピック名は他人に推測されない長いランダム文字列にすること（例: rakumitsu-room-7f3k9q2x）。

通知の使い方: タップ → 楽天アプリで商品が開く → 共有 → ROOMに投稿 → 通知本文（コメント）を長押しコピーして貼る。
"""
from __future__ import annotations

from typing import Any

import requests

from .config import _env
from .rakuten_client import Product


def send(topic: str, title: str, message: str, click: str = "", server: str = "https://ntfy.sh",
         priority: int = 3, tags: list[str] | None = None, attach: str = "", filename: str = "",
         label: str = "楽天で開く") -> bool:
    """attach: 画像などのURL。ntfy アプリが通知に画像を表示し、そのままスマホに保存できる。"""
    payload: dict[str, Any] = {"topic": topic, "title": title, "message": message,
                               "tags": tags or ["shopping_bags"], "priority": priority}
    if click:
        payload["click"] = click
        payload["actions"] = [{"action": "view", "label": label, "url": click}]
    if attach:
        payload["attach"] = attach
        if filename:
            payload["filename"] = filename
    r = requests.post(server.rstrip("/"), json=payload, timeout=15)
    if r.status_code >= 300:
        print(f"  [warn] ntfy {r.status_code}: {r.text[:100]}")
        return False
    return True


def notify_room_picks(picks: list[tuple[Product, str]], theme_title: str, presale=False) -> bool:
    """picks = [(商品, ROOMコメント), ...]。本文はコメントだけ（そのまま貼れる）。"""
    topic = _env("NTFY_TOPIC")
    if not topic or not picks:
        return False
    server = _env("NTFY_SERVER", "https://ntfy.sh")
    ok = True
    head = {"start": "【20時セール開始前】", "last": "【セール最終日】", "five": "【5と0のつく日】"}.get(presale, "【ブースト】" if presale else "")
    try:
        ok = send(topic, f"{head}ROOMに追加する {len(picks)} 件", theme_title.replace(" × ", "／"),
                  "", server, priority=4 if presale else 3, tags=["bell"]) and ok
    except Exception as e:
        print(f"  [warn] ntfy 送信失敗: {e}")
        ok = False
    for i, (p, comment) in enumerate(picks, 1):
        title = f"{i}/{len(picks)}｜{p.name[:28]}｜{p.price:,}円"
        try:
            ok = send(topic, title, comment, p.item_url, server) and ok
        except Exception as e:
            print(f"  [warn] ntfy 送信失敗: {e}")
            ok = False
    if ok:
        print(f"  [ntfy] スマホに {len(picks)} 件のROOM追加通知を送りました（トピック: {topic}）")
    return ok

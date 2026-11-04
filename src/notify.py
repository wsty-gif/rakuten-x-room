"""スマホへのプッシュ通知（ntfy.sh）。ROOMに追加する商品を、コメント付きで送る。

ntfy は無料・アカウント不要の通知サービス。スマホに ntfy アプリを入れ、
.env の NTFY_TOPIC と同じ名前のトピックを購読しておくだけで届く。
トピック名は他人に推測されない長いランダム文字列にすること（例: rakumitsu-room-7f3k9q2x）。

通知の使い方: 「コメントをコピー」→「ROOMに投稿」（ROOMの投稿画面が直接開く）→ コメント欄に貼って投稿。
「コメントをコピー」ボタンは ntfy の Android アプリとWeb版で表示される（iPhone では本文を長押ししてコピー）。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

from .config import _env
from .rakuten_client import Product


def send(topic: str, title: str, message: str, click: str = "", server: str = "https://ntfy.sh",
         priority: int = 3, tags: list[str] | None = None, attach: str = "", filename: str = "",
         label: str = "楽天で開く", actions: list[dict[str, Any]] | None = None) -> bool:
    """attach: 画像などのURL。ntfy アプリが通知に画像を表示し、そのままスマホに保存できる。
    actions: 通知のボタン（最大3つ）。省略時は click を開くボタンを1つ付ける。"""
    payload: dict[str, Any] = {"topic": topic, "title": title, "message": message,
                               "tags": tags or ["shopping_bags"], "priority": priority}
    if click:
        payload["click"] = click
        payload["actions"] = [{"action": "view", "label": label, "url": click}]
    if actions:
        payload["actions"] = actions
    if attach:
        payload["attach"] = attach
        if filename:
            payload["filename"] = filename
    r = requests.post(server.rstrip("/"), json=payload, timeout=15)
    if r.status_code >= 300:
        print(f"  [warn] ntfy {r.status_code}: {r.text[:100]}")
        return False
    return True


def room_post_url(item_code: str) -> str:
    """ROOM の「コレ！」投稿画面を直接開くURL（楽天公式の「ROOMに投稿」ボタンと同じ形）。"""
    return f"https://room.rakuten.co.jp/mix?itemcode={quote(item_code, safe=':')}&scid=we_room_upc60"


def room_actions(p: Product, comment: str) -> list[dict[str, Any]]:
    return [{"action": "copy", "label": "コメントをコピー", "value": comment},
            {"action": "view", "label": "ROOMに投稿", "url": room_post_url(p.item_code)},
            {"action": "view", "label": "楽天で見る", "url": p.item_url}]


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
            ok = send(topic, title, comment, room_post_url(p.item_code), server,
                      actions=room_actions(p, comment)) and ok
        except Exception as e:
            print(f"  [warn] ntfy 送信失敗: {e}")
            ok = False
    if ok:
        print(f"  [ntfy] スマホに {len(picks)} 件のROOM追加通知を送りました（トピック: {topic}）")
    return ok

"""スマホへのプッシュ通知（ntfy.sh）。ROOMに追加する商品を、コメント付きで送る。

ntfy は無料・アカウント不要の通知サービス。スマホに ntfy アプリを入れ、
.env の NTFY_TOPIC と同じ名前のトピックを購読しておくだけで届く。
トピック名は他人に推測されない長いランダム文字列にすること（例: rakumitsu-room-7f3k9q2x）。

通知の使い方:
  iPhone  … 通知をタップ → 開いたページの「コメントをコピーしてROOMを開く」→ コメント欄に貼って投稿。
  Android … 上と同じでもよいし、通知の「コメントをコピー」→「ROOMに投稿」でも同じ。
（ページはブログの room/go.html。商品とコメントは URL の # 以降に入れるのでサーバーには送られない）
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

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


def room_go_url(p: Product, comment: str) -> str:
    """コピーと ROOM を1タップで開くページ（build_site.py の room/go.html）。SITE_URL が無ければ ROOM を直接開く。"""
    base = _env("SITE_URL")
    if not base:
        return room_post_url(p.item_code)
    frag = urlencode({"i": p.item_code, "n": p.name[:60], "p": p.price, "c": comment}, quote_via=quote)
    return f"{base.rstrip('/')}/room/go.html#{frag}"


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
            ok = send(topic, title, comment, room_go_url(p, comment), server,
                      actions=room_actions(p, comment)) and ok
        except Exception as e:
            print(f"  [warn] ntfy 送信失敗: {e}")
            ok = False
    if ok:
        print(f"  [ntfy] スマホに {len(picks)} 件のROOM追加通知を送りました（トピック: {topic}）")
    return ok

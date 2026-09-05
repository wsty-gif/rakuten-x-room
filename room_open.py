"""ROOMへの追加を「人がボタンを押すだけ」にする補助ツール。  python room_open.py

ROOMの規約では機械的な投稿が禁止されているため、投稿そのものは自動化しない。
このツールがやるのは次の3つだけ:
  1. まだROOMに追加していない商品の楽天ページをブラウザで開く
  2. ROOM用のコメント案をクリップボードにコピーする
  3. あなたが商品ページの「ROOMに投稿する」ボタンを押して投稿したら、Enter で「完了」として記録する

Windowsの既定ブラウザで楽天にログインしておくこと。
"""
from __future__ import annotations

import json
import subprocess
import sys
import webbrowser

sys.stdout.reconfigure(encoding="utf-8")
from src.config import HISTORY_FILE


def copy_clipboard(text: str) -> None:
    try:
        subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
    except Exception:
        pass


def room_comment(text: str) -> str:
    """X投稿文から、ROOM用の一言（#PR行とCTA行とハッシュタグ行を除いた本文）を作る。"""
    lines = [l for l in text.splitlines() if l.strip()]
    body = [l for l in lines if not l.startswith("#PR") and "ROOMはプロフ" not in l and not l.startswith("#")]
    return " ".join(body)[:140] if body else ""


def main() -> None:
    if not HISTORY_FILE.exists():
        print("投稿履歴がありません。先に python main.py run で投稿してください。")
        return
    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    todo = [h for h in history if h.get("item_url") and not h.get("room_done")]
    if not todo:
        print("ROOMに追加待ちの商品はありません。")
        return
    print(f"ROOMに追加する商品: {len(todo)} 件\n")
    for i, h in enumerate(todo, 1):
        comment = room_comment(h.get("text", ""))
        print(f"[{i}/{len(todo)}] {h['item_name'][:60]}")
        print(f"   {h['price']:,}円  投稿日 {h['date'][:10]}  テーマ {h.get('theme', '')}")
        print(f"   コメント案（クリップボードにコピー済み）: {comment}")
        copy_clipboard(comment)
        webbrowser.open(h["item_url"])
        print("   → ブラウザで商品ページを開きました。ページ内の「ROOMに投稿する」を押し、コメントを貼って投稿してください。")
        ans = input("   投稿したら Enter（スキップは s、終了は q）: ").strip().lower()
        if ans == "q":
            break
        if ans == "s":
            print()
            continue
        h["room_done"] = True
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
        print("   完了として記録しました。\n")
    remaining = sum(1 for h in history if h.get("item_url") and not h.get("room_done"))
    print(f"残り {remaining} 件")


if __name__ == "__main__":
    main()

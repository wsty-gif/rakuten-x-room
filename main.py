"""X + 楽天ROOM アフィリエイト自動化 CLI

  python main.py plan  [--slot night]            今日のテーマと候補商品を表示（投稿しない）
  python main.py run   [--slot night] [--dry-run] 商品選定→投稿文生成→X投稿→ROOM追加リスト出力
  python main.py genres                          楽天ジャンルIDの一覧を取得
  python main.py report                          投稿履歴の集計
  --mock を付けると楽天APIを使わずサンプルデータで動作確認できる
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

from src.config import DATA_DIR, GENRES, HISTORY_FILE, Settings
from src.rakuten_client import Product, RakutenClient
from src.room_todo import write_room_todo
from src.selector import gather_candidates
from src.trend_engine import decide_theme
from src.writer import build_posts, weighted_len


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def save_history(h: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")


def default_slot() -> str:
    h = datetime.now().hour
    if h < 11:
        return "morning"
    if h < 17:
        return "noon"
    return "night"


class MockClient:
    """APIキー無しで流れを確認するためのダミー。"""

    def __init__(self):
        p = DATA_DIR / "mock_products.json"
        self.items = [Product(**d) for d in json.loads(p.read_text(encoding="utf-8"))]

    def ranking(self, genre_id=None, age=None, sex=None, realtime=False, page=1):
        for i, it in enumerate(self.items, 1):
            it.rank = i
            it.source = f"ranking:{genre_id or 'all'}{':rt' if realtime else ''}"
        return list(self.items)

    def search(self, keyword=None, *args, **kw):
        return [it for it in self.items if keyword and any(k in it.name for k in keyword.split())]

    def genres(self, genre_id=0):
        return list(GENRES.items())


def cmd_plan(args, s: Settings):
    history = load_history()
    slot = args.slot or default_slot()
    theme = decide_theme(date.today(), slot, history)
    print(theme.describe())
    client = MockClient() if args.mock else RakutenClient(s)
    cands = gather_candidates(client, theme, s, history)
    print(f"\n候補 {len(cands)} 件:")
    for p in cands:
        print(f"  {p.score:5.1f} | {p.price:>6,}円 | ★{p.review_average} ({p.review_count:,}) | 料率{p.affiliate_rate}% | {p.name[:50]}")
    return theme, cands, client, history


def cmd_run(args, s: Settings):
    theme, cands, client, history = cmd_plan(args, s)
    if not cands:
        print("候補がありません。フィルタ（MIN_REVIEW_COUNT 等）を緩めてください。")
        return
    posts = build_posts(cands, theme, s, s.posts_per_run)
    poster = None
    threads = None
    if not args.dry_run:
        if not s.x_ready():
            print("\nX APIのキーが未設定なので --dry-run と同じ動作にします。")
        else:
            from src.x_poster import XPoster
            poster = XPoster(s)
        if s.threads_ready():
            try:
                from src.threads_poster import ThreadsPoster
                threads = ThreadsPoster(s)
            except Exception as e:
                print(f"  [warn] Threads 初期化失敗（Xのみ投稿します）: {e}")

    for pst in posts:
        p = pst["product"]
        text = pst["text"]
        print("\n" + "=" * 50)
        print(f"[選定理由] {pst['why']}")
        print(f"[文字数] {weighted_len(text)}/280 units")
        print(text)
        print(f"[画像] {p.image_url}")
        tweet_id = ""
        threads_id = ""
        if poster:
            tweet_id = poster.post(text, p.image_url)
            print(f"[X 投稿完了] https://x.com/i/web/status/{tweet_id}")
        if threads:
            try:
                threads_id = threads.post(text, p.image_url)
                print(f"[Threads 投稿完了] id={threads_id}")
            except Exception as e:
                print(f"  [warn] Threads 投稿失敗: {e}")
        if poster:
            history.append({
                "date": datetime.now().isoformat(timespec="seconds"),
                "slot": theme.slot, "theme": theme.title, "persona": theme.persona.key,
                "item_code": p.item_code, "item_name": p.name[:80], "price": p.price,
                "item_url": p.item_url, "affiliate_rate": p.affiliate_rate,
                "text": text, "tweet_id": tweet_id, "threads_id": threads_id, "room_done": False,
            })
    if not args.mock:
        from src.site_store import save_site_items
        save_site_items(cands, theme, posts if poster else [])
    if poster:
        save_history(history)
        path = write_room_todo(posts, theme.title)
        print(f"\n[ROOM] 手動で「コレ！」する商品リストを書き出しました: {path}")
        from src.notify import notify_room_todo
        notify_room_todo(posts, theme.title)
    else:
        print("\n[dry-run] 履歴とROOMリストは書き出しません（本番投稿時のみ）。")


def cmd_genres(args, s: Settings):
    client = MockClient() if args.mock else RakutenClient(s)
    for gid, name in client.genres(0):
        print(f"{gid}\t{name}")


def cmd_report(args, s: Settings):
    h = load_history()
    print(f"投稿数: {len(h)}（うち本番 {sum(1 for x in h if not x.get('dry_run'))}）")
    by_p: dict[str, int] = {}
    for x in h:
        by_p[x.get("persona", "?")] = by_p.get(x.get("persona", "?"), 0) + 1
    for k, v in sorted(by_p.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    for x in h[-5:]:
        print(f"- {x['date'][:16]} [{x['slot']}] {x['theme']} → {x['item_name'][:40]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "run", "genres", "report"])
    ap.add_argument("--slot", choices=["morning", "noon", "night"])
    ap.add_argument("--dry-run", action="store_true", help="Xに投稿せず内容だけ表示")
    ap.add_argument("--mock", action="store_true", help="楽天APIを使わずサンプルデータで動作確認")
    args = ap.parse_args()
    s = Settings()
    if args.cmd != "report" and not args.mock and not s.rakuten_ready():
        print("RAKUTEN_APP_ID が未設定です。.env を作成してください（.env.example を参照）。--mock で動作確認は可能です。")
        sys.exit(1)
    {"plan": cmd_plan, "run": cmd_run, "genres": cmd_genres, "report": cmd_report}[args.cmd](args, s)


if __name__ == "__main__":
    main()

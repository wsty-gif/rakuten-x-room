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
    # ROOM 向けに網を広げて候補を集め（1,000円台・レビュー30件以上）、X 向けには従来の基準で絞る
    from src.room_picks import room_settings
    cands = gather_candidates(client, theme, room_settings(s), history, limit=40)
    x_cands = [p for p in cands if p.price >= s.min_price and p.review_count >= s.min_review_count]
    print(f"\n候補 {len(cands)} 件（X向け {len(x_cands)} 件）:")
    for p in x_cands[:15]:
        print(f"  {p.score:5.1f} | {p.price:>6,}円 | ★{p.review_average} ({p.review_count:,}) | 料率{p.affiliate_rate}% | {p.name[:50]}")
    return theme, cands, x_cands, client, history


def room_flow(cands, theme, s: Settings, history: list, posted: list, live: bool, presale=False) -> None:
    """ROOM に追加する商品を選び、コメントを付けて、通知とリストを出す。live=False なら表示のみ。"""
    from src.room_comment import collection_suggestions, room_comment
    from src.room_picks import pick_for_room
    picks_p = pick_for_room(cands, theme, s, history, posted, presale=presale)
    picks = [(p, room_comment(p, theme, presale=presale)) for p in picks_p]
    print("\n" + "-" * 50 + f"\n[ROOM] 追加候補 {len(picks)} 件" + ("（20時セール前ブースト）" if presale else ""))
    for i, (p, c) in enumerate(picks, 1):
        print(f" {i}. {p.price:>6,}円 ★{p.review_average} ({p.review_count:,}) 料率{p.affiliate_rate}% | {p.name[:40]}\n    → {c}")
    if not live:
        print("[dry-run] 通知・履歴・リストは書き出しません。")
        return
    for p, c in picks:
        if any(h.get("item_code") == p.item_code and h.get("kind") in (None, "room") and h.get("date", "")[:10] == datetime.now().strftime("%Y-%m-%d") for h in history):
            continue
        history.append({
            "date": datetime.now().isoformat(timespec="seconds"), "kind": "room", "slot": theme.slot,
            "theme": theme.title, "persona": theme.persona.key, "item_code": p.item_code,
            "item_name": p.name[:80], "price": p.price, "item_url": p.item_url,
            "affiliate_rate": p.affiliate_rate, "text": c, "room_done": False,
        })
    save_history(history)
    cols = collection_suggestions(picks, theme)
    path = write_room_todo(picks, theme.title + ("（20時セール前）" if presale else ""), cols)
    print(f"[ROOM] リストを書き出しました: {path}")
    from src.notify import notify_room_picks
    notify_room_picks(picks, theme.title, presale=presale)


def cmd_run(args, s: Settings):
    theme, cands, x_cands, client, history = cmd_plan(args, s)
    if not cands:
        print("候補がありません。フィルタ（MIN_REVIEW_COUNT 等）を緩めてください。")
        return
    posts = build_posts(x_cands or cands, theme, s, s.posts_per_run)
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
                # Threads はリンク付き投稿に追加料金も表示の抑制もないので、CTA行をリンクに置き換える
                from src.writer import CTA
                link = s.threads_link_url or s.room_url
                threads_text = text.replace(CTA, f"▶ {link}") if link else text
                threads_id = threads.post(threads_text, p.image_url)
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
                "image": getattr(poster, "last_had_image", False),
            })
    # ブログ用データは本番投稿時のみ蓄積する（dry-run で書くと GitHub 側の記録と競合するため）
    if poster:
        from src.site_store import save_site_items
        save_site_items(cands, theme, posts)
    if poster:
        save_history(history)
    # ROOM: X に出した商品を先頭に、ROOM 基準で複数点を選んで通知する
    room_flow(cands, theme, s, history, [pst["product"] for pst in posts], live=poster is not None)


def cmd_presale(args, s: Settings):
    """セール開始日・5と0のつく日・セール最終日の夕方に、ROOM へ多めに商品を送る（20時の購買ピークに備える）。"""
    import json as _json
    from src.config import CALENDAR_FILE
    today = date.today()
    cal = _json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    reason, kind = "", ""
    for ev in cal.get("events", []):
        if ev.get("type") != "sale":
            continue
        if ev["start"] == today.isoformat():
            reason, kind = f"{ev['name']} 開始日（20時〜）", "start"
        elif ev["end"] == today.isoformat():
            reason, kind = f"{ev['name']} 最終日", "last"
    if not reason and today.day in (5, 10, 15, 20, 25, 30):
        reason, kind = "5と0のつく日", "five"
    if not reason and not args.force:
        print("今日はセール開始日・最終日・5と0のつく日ではないので、事前ブーストは行いません。")
        return
    print(f"[presale] {reason or '手動実行'}")
    kind = kind or True
    history = load_history()
    theme = decide_theme(today, "night", history)
    client = MockClient() if args.mock else RakutenClient(s)
    from src.room_picks import room_settings
    cands = gather_candidates(client, theme, room_settings(s), history, limit=40)
    room_flow(cands, theme, s, history, [], live=not args.dry_run, presale=kind)


def cmd_engage(args, s: Settings):
    """反応を取るための投稿（投票 / 質問 / 豆知識）を1本投稿する。"""
    from src.engage import build_engagement_post
    history = load_history()
    post = build_engagement_post(date.today(), history)
    print(f"[種類] {post['kind']}")
    print(post["text"])
    if post.get("poll_options"):
        print("[投票] " + " / ".join(post["poll_options"]))
    if args.dry_run or not s.x_ready():
        print("\n[dry-run] 投稿しません。")
        return
    from src.x_poster import XPoster
    tweet_id = XPoster(s).post(post["text"], None, post.get("poll_options"))
    print(f"[X 投稿完了] https://x.com/i/web/status/{tweet_id}")
    threads_id = ""
    if s.threads_ready():
        try:
            from src.threads_poster import ThreadsPoster
            t_text = post["text"]
            if post.get("poll_options"):
                t_text += "\n\n" + "\n".join(f"・{o}" for o in post["poll_options"]) + "\n\n返信で教えてください。"
            threads_id = ThreadsPoster(s).post(t_text, None)
            print(f"[Threads 投稿完了] id={threads_id}")
        except Exception as e:
            print(f"  [warn] Threads 投稿失敗: {e}")
    history.append({"date": datetime.now().isoformat(timespec="seconds"), "slot": "evening", "kind": "engage",
                    "engage_key": post.get("engage_key"), "theme": f"反応投稿（{post['kind']}）", "persona": "all",
                    "text": post["text"], "tweet_id": tweet_id, "threads_id": threads_id})
    save_history(history)


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
    ap.add_argument("cmd", choices=["plan", "run", "engage", "presale", "genres", "report"])
    ap.add_argument("--force", action="store_true", help="presale: 対象日でなくても実行する")
    ap.add_argument("--slot", choices=["morning", "noon", "night"])
    ap.add_argument("--dry-run", action="store_true", help="Xに投稿せず内容だけ表示")
    ap.add_argument("--mock", action="store_true", help="楽天APIを使わずサンプルデータで動作確認")
    args = ap.parse_args()
    s = Settings()
    if args.cmd not in ("report", "engage") and not args.mock and not s.rakuten_ready():
        print("RAKUTEN_APP_ID が未設定です。.env を作成してください（.env.example を参照）。--mock で動作確認は可能です。")
        sys.exit(1)
    {"plan": cmd_plan, "run": cmd_run, "engage": cmd_engage, "presale": cmd_presale,
     "genres": cmd_genres, "report": cmd_report}[args.cmd](args, s)


if __name__ == "__main__":
    main()

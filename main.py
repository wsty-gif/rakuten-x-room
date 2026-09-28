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
import os
import sys
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

from src.config import DATA_DIR, GENRES, HISTORY_FILE, ROOT, Settings
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
            "date": datetime.now().isoformat(timespec="seconds"), "kind": "room",
            "slot": "presale" if presale else theme.slot,
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


def cmd_instagram(args, s: Settings):
    """今日 X に投稿した商品のうち、指定枠のものを Instagram にフィード投稿する（ブログ公開後に実行）。"""
    if not s.instagram_ready() and not args.dry_run:
        print("INSTAGRAM_ACCESS_TOKEN が未設定なので Instagram は飛ばします。")
        return
    import os
    from src.instagram_poster import InstagramPoster, wait_until_public
    from src.pin_image import safe_name
    from src.writer import CTA, _short_name, extract_deal
    base = s.site_url or (f"https://{os.environ.get('GITHUB_REPOSITORY_OWNER', '')}.github.io/" if os.environ.get("GITHUB_REPOSITORY_OWNER") else "")
    if not base:
        print("SITE_URL が不明なので Instagram は飛ばします。")
        return
    base = base.rstrip("/") + "/"
    allowed = {x.strip() for x in s.instagram_slots.split(",") if x.strip()}
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    todo = [h for h in history if (h.get("kind") or "product") == "product" and h.get("date", "")[:10] == today
            and h.get("slot") in allowed and not h.get("instagram_id") and h.get("item_code")]
    if not todo:
        print("Instagram に投稿する対象がありません。")
        return
    story_slots = {x.strip() for x in s.instagram_story_slots.split(",") if x.strip()}
    # ストーリーズは前回失敗分も拾う（今日の分に加え、昨日の夜枠がまだなら出す）
    yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    story_todo = [h for h in history if (h.get("kind") or "product") == "product" and h.get("item_code")
                  and not h.get("instagram_story_id") and h.get("slot") in story_slots
                  and (h.get("date", "")[:10] == today or (h.get("date", "")[:10] == yday and h.get("slot") == "night"))]
    reel_file = ROOT / "docs" / "reels" / f"{today}.mp4"
    reel_done = any(h.get("kind") == "reel" and h.get("date", "")[:10] == today and h.get("instagram_id") for h in history)
    reel_todo = s.instagram_reel and reel_file.exists() and not reel_done
    if not todo and not story_todo and not reel_todo:
        print("Instagram に投稿する対象がありません。")
        return
    poster = None if args.dry_run else InstagramPoster(s)
    from src.instagram_poster import build_caption
    from src.room_comment import _features
    from src.site_store import load_site_items
    store = load_site_items()

    # ---- フィード投稿 ----
    for h in todo:
        img_url = f"{base}ig/{safe_name(h['item_code'])}.jpg"
        item = store.get(h["item_code"])
        first = h.get("text", "").splitlines()[0].replace("#PR", "").strip() if h.get("text") else ""
        hook = first if 6 <= len(first) <= 30 else "レビュー件数が答えのやつ"
        feats = _features(item.get("caption", ""), item.get("name", "")) if item else []
        caption = build_caption(h, item, hook, feats)
        name = _short_name(h.get("item_name", ""), 36)
        print("\n" + "=" * 50 + f"\n[Instagram フィード] {name}\n画像: {img_url}\n{caption}")
        if not poster:
            continue
        if not wait_until_public(img_url, timeout_sec=300):
            print("  [warn] 画像がまだ公開されていないため、この商品は次回に回します")
            h["instagram_error"] = "image not public (timeout)"
            continue
        try:
            h["instagram_id"] = poster.post_image(img_url, caption)
            h.pop("instagram_error", None)
            print(f"[Instagram フィード投稿完了] id={h['instagram_id']}")
        except Exception as e:
            print(f"  [warn] Instagram フィード投稿失敗: {e}")
            h["instagram_error"] = str(e)[:200]

    # ---- ストーリーズ（画像。24時間で消える）----
    for h in story_todo:
        img_url = f"{base}story/{safe_name(h['item_code'])}.jpg"
        print(f"\n[Instagram ストーリーズ] {_short_name(h.get('item_name', ''), 36)}\n画像: {img_url}")
        if not poster:
            continue
        if not wait_until_public(img_url, timeout_sec=300):
            print("  [warn] ストーリーズ画像が未公開のため次回に回します")
            h["instagram_story_error"] = "image not public (timeout)"
            continue
        try:
            h["instagram_story_id"] = poster.post_story(img_url)
            h.pop("instagram_story_error", None)
            print(f"[Instagram ストーリーズ投稿完了] id={h['instagram_story_id']}")
        except Exception as e:
            print(f"  [warn] Instagram ストーリーズ投稿失敗: {e}")
            h["instagram_story_error"] = str(e)[:200]

    # ---- リール（1日1本）----
    if reel_todo:
        video_url = f"{base}reels/{today}.mp4"
        meta_file = ROOT / "docs" / "reels" / f"{today}.json"
        caption = json.loads(meta_file.read_text(encoding="utf-8")).get("caption", "") if meta_file.exists() else ""
        print(f"\n[Instagram リール] {video_url}\n{caption}")
        if poster:
            public = wait_until_public(video_url, timeout_sec=300)
            if public:
                try:
                    rid = poster.post_reel(video_url, caption)
                    history.append({"date": datetime.now().isoformat(timespec="seconds"), "kind": "reel", "slot": "night",
                                    "theme": "リール", "persona": "all", "text": caption[:200], "instagram_id": rid})
                    print(f"[Instagram リール投稿完了] id={rid}")
                except Exception as e:
                    print(f"  [warn] Instagram リール投稿失敗: {e}")
                    history.append({"date": datetime.now().isoformat(timespec="seconds"), "kind": "reel", "slot": "night",
                                    "theme": "リール", "persona": "all", "text": caption[:200], "instagram_error": str(e)[:200]})
            else:
                print("  [warn] 動画が未公開のため、リールは次回に回します")
            # TikTok / Shorts 用: 動画ページのリンクをスマホに送る（投稿は手動）
            try:
                from src.notify import send
                from src.config import _env
                topic = _env("NTFY_TOPIC")
                if topic and public:
                    tt = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
                    send(topic, f"TikTok用スライドと投稿文ができました（{today[5:].replace('-', '/')}）",
                         (tt.get("tiktok_caption") or "タップして開く")[:900], f"{base}reels/index.html", tags=["clapper"])
            except Exception as e:
                print(f"  [warn] 動画通知失敗: {e}")
    if poster:
        save_history(history)


def cmd_reel_build(args, s: Settings):
    """今日の商品から TikTok フォトモード用スライド一式と、同じ構成の動画（Instagram リール用）を作る。ブログ公開の前に実行する。
    出力: docs/reels/YYYY-MM-DD/01.jpg…（スライド）, YYYY-MM-DD_slides.zip, YYYY-MM-DD.mp4, YYYY-MM-DD.json（投稿文）"""
    from src.reel_video import build_reel, find_bgm
    from src.site_store import load_site_items
    from src.tiktok_slides import brand_of, make_slide_set, short_name, zip_slides
    from src.topics import load_topics
    today = datetime.now().strftime("%Y-%m-%d")
    history = load_history()
    store = load_site_items()

    # ---- 商品を集める（今日X/ROOMに出した物 → 直近の特集の行事 → サイトの新着）----
    seen, cands = set(), []
    def add(code, extra=None):
        if not code or code in seen:
            return
        it = store.get(code)
        if not it or not it.get("image_url"):
            return
        seen.add(code)
        d = dict(it)
        if extra:
            d.update(extra)
        cands.append(d)
    for h in history:
        if h.get("date", "")[:10] == today and (h.get("kind") or "product") in ("product", "room"):
            add(h.get("item_code"))
    event_topic = None
    for t in sorted(load_topics().values(), key=lambda x: x.get("start", "9999")):
        if t.get("kind") == "event" and t.get("start", "") >= today:
            event_topic = t
            for x in t["items"][:6]:
                if x.get("item_code") not in seen and x.get("image_url"):
                    seen.add(x["item_code"]); cands.append(dict(x))
            break
    for it in sorted(store.values(), key=lambda x: x.get("last_seen", ""), reverse=True)[:40]:
        add(it.get("item_code"))
    # レビュー数×評価で上位7点。同じ店は1点まで
    cands.sort(key=lambda x: -(float(x.get("review_average", 0) or 0) * (int(x.get("review_count", 0) or 0) ** 0.5)))
    picks, shops = [], set()
    for it in cands:
        if it.get("shop_name") in shops:
            continue
        shops.add(it.get("shop_name"))
        picks.append(it)
        if len(picks) >= 7:
            break
    if len(picks) < 3:
        print(f"スライド用の商品が足りません（{len(picks)}点）。")
        return

    # ---- タイトル（参考: 「人気ギフト予算2万円 7選」）----
    _, m, d = today.split("-")
    maxp = max(int(x["price"]) for x in picks)
    budget = next(b for b in (3000, 5000, 10000, 20000, 30000, 50000, 100000) if maxp <= b)
    budget_txt = f"{budget // 10000}万円" if budget >= 10000 else f"{budget:,}円"
    n = len(picks)
    NL = chr(10)
    if event_topic and event_topic.get("event_type") == "gift":
        title, theme_tag = f"{event_topic['title']}ギフト{NL}予算{budget_txt} {n}選", f"#{event_topic['title']}"
    elif event_topic and event_topic.get("event_type") == "sale":
        title, theme_tag = f"{event_topic['title']}で{NL}買うべき {n}選", "#楽天セール"
    elif event_topic:
        title, theme_tag = f"{event_topic['title']}に{NL}買っておきたい {n}選", "#季節の準備"
    else:
        title, theme_tag = f"楽天で今売れてる{NL}予算{budget_txt} {n}選", "#楽天購入品"
    brand_name = (os.environ.get("SITE_NAME") or "らくみつ｜楽天で見つけた良いもの").split("｜")[0]

    # ---- スライド一式 → zip → 動画 ----
    out_dir = ROOT / "docs" / "reels" / today
    paths = make_slide_set(picks, title, "レビュー4.2以上・50件以上だけ", brand_name, out_dir)
    zip_slides(paths, ROOT / "docs" / "reels" / f"{today}_slides.zip")
    clips = [(paths[0], 2.5)] + [(p, 3.0) for p in paths[1:-1]] + [(paths[-1], 2.5)]
    out = ROOT / "docs" / "reels" / f"{today}.mp4"
    bgm = find_bgm(ROOT / "assets" / "bgm")
    build_reel(clips, out, bgm)

    # ---- 投稿文（TikTok用 / Instagram用）----
    flat_title = title.replace(NL, " ")
    lines = []
    for i, x in enumerate(picks, 1):
        b = brand_of(x["name"], x.get("shop_name", ""))
        lines.append(f"{'①②③④⑤⑥⑦⑧⑨'[i-1]} {b}｜{short_name(x['name'], b, 24)} ¥{int(x['price']):,}")
    tiktok = NL.join([flat_title, ""] + lines + ["", "保存して、あとでゆっくり見返してね🔖", "商品はプロフィールのリンク（まとめサイト）から", "",
                        f"#楽天購入品 #楽天 {theme_tag} #買ってよかった #おすすめ #PR #楽天ROOM #tiktokで買い物 #プチプラ"])
    insta = NL.join([flat_title, ""] + lines + ["", "レビュー50件以上・評価4.2以上の物だけを毎日選んでいます。", "🔖 保存しておくとセールのときに探しやすいです",
                       "▶ 商品リンクはプロフィールのまとめサイトから", "",
                       f"#PR #楽天購入品 #楽天ROOM #楽天市場 {theme_tag} #買ってよかった #リピ買い #お得情報 #買い物メモ #暮らしを整える"])
    (ROOT / "docs" / "reels" / f"{today}.json").write_text(json.dumps({
        "title": flat_title, "caption": insta, "tiktok_caption": tiktok, "items": [x["item_code"] for x in picks],
        "slides": [p.name for p in paths]}, ensure_ascii=False), encoding="utf-8")
    print(f"[reel] {out.name} / スライド {len(paths)} 枚（{'BGM: ' + bgm.name if bgm else '無音'}）")
    print(tiktok)


def cmd_topics(args, s: Settings):
    """特集記事（行事・カテゴリ別）用の商品データを楽天から集めて data/topics.json に保存する。"""
    from src.topics import refresh_topics
    topics = refresh_topics(s, force=args.force)
    for t in sorted(topics.values(), key=lambda x: x.get("kind"))[:60]:
        print(f" - [{t['kind']:9s}] {t['title']:22s} {len(t['items']):2d}点  更新 {t['updated'][:10]}")


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
    ap.add_argument("cmd", choices=["plan", "run", "engage", "presale", "instagram", "reel-build", "topics", "genres", "report"])
    ap.add_argument("--force", action="store_true", help="presale: 対象日でなくても実行する")
    ap.add_argument("--slot", choices=["morning", "noon", "night"])
    ap.add_argument("--dry-run", action="store_true", help="Xに投稿せず内容だけ表示")
    ap.add_argument("--mock", action="store_true", help="楽天APIを使わずサンプルデータで動作確認")
    args = ap.parse_args()
    s = Settings()
    if args.cmd not in ("report", "engage", "instagram", "reel-build") and not args.mock and not s.rakuten_ready():
        print("RAKUTEN_APP_ID が未設定です。.env を作成してください（.env.example を参照）。--mock で動作確認は可能です。")
        sys.exit(1)
    {"plan": cmd_plan, "run": cmd_run, "engage": cmd_engage, "presale": cmd_presale, "instagram": cmd_instagram,
     "reel-build": cmd_reel_build, "topics": cmd_topics, "genres": cmd_genres, "report": cmd_report}[args.cmd](args, s)


if __name__ == "__main__":
    main()

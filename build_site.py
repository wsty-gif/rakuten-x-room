"""GitHub Pages 用の静的ブログを docs/ に生成する。  python build_site.py

入力: data/site_items.json（main.py run が毎回蓄積）
出力: docs/ 以下
  index.html                 トップ
  posts/YYYY-MM-DD.html      日別記事（前後の記事へのリンク付き）
  posts/index.html           記事一覧
  for/<persona>.html         誰向け別まとめ、 for/index.html 一覧
  ranking.html               レビュー評価ランキング
  about.html / privacy.html  運営者情報・選定基準 / プライバシーポリシー
  404.html, feed.xml, sitemap.xml, robots.txt, assets/og.png
SEO: ページ固有の title/description、canonical、OGP/Twitter Card、JSON-LD
     （WebSite/Organization, Article, CollectionPage, ItemList, BreadcrumbList）、
     セマンティックHTML、time要素、画像alt、遅延読み込み、内部リンク。
"""
from __future__ import annotations

import html
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
from src.config import GENRES, PERSONAS, ROOT, _env
from src.site_store import load_site_items
from src.trend_engine import SLOTS
from src.writer import _short_name, extract_deal

DOCS = ROOT / "docs"
SITE_NAME = _env("SITE_NAME", "らくみつ｜楽天で見つけた良いもの")
BRAND = SITE_NAME.split("｜")[0]
TAGLINE = SITE_NAME.split("｜")[1] if "｜" in SITE_NAME else ""
ROOM_URL = _env("ROOM_URL")
X_URL = _env("X_PROFILE_URL", "https://x.com/rakumitsu__room")
DAYS_ON_INDEX = 10
ITEMS_PER_DAY = 12
SLOT_JA = {"morning": "朝", "noon": "昼", "night": "夜"}


def site_url() -> str:
    u = _env("SITE_URL")
    if not u:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            owner, name = repo.split("/", 1)
            u = f"https://{owner}.github.io/{name}/"
    return (u.rstrip("/") + "/") if u else ""


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def jp_date(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(y)}年{int(m)}月{int(dd)}日"


def short_date(d: str) -> str:
    _, m, dd = d.split("-")
    return f"{int(m)}月{int(dd)}日"


# ---------------------------------------------------------------- デザイン
CSS = """
:root{--bg:#faf7f2;--paper:#fff;--ink:#1f2328;--sub:#5c6470;--rule:#e6e0d8;--acc:#b6462b;--acc-soft:#f4e6e0}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans JP",-apple-system,"Hiragino Sans","Yu Gothic",sans-serif;font-size:15px;line-height:1.85;-webkit-font-smoothing:antialiased;font-feature-settings:"palt"}
img{display:block;max-width:100%;height:auto}a{color:inherit}
.serif{font-family:"Shippori Mincho B1","Hiragino Mincho ProN","Yu Mincho",serif}
.wrap{max-width:960px;margin:0 auto;padding:0 22px}
header{border-bottom:1px solid var(--rule);background:var(--bg)}
.top{display:flex;align-items:baseline;justify-content:space-between;gap:20px;padding:22px 0 14px}
.wordmark{text-decoration:none;color:var(--ink)}.wordmark b{font-family:"Shippori Mincho B1",serif;font-size:26px;font-weight:700;letter-spacing:.06em}
.wordmark small{display:block;font-size:11px;color:var(--sub);letter-spacing:.12em;margin-top:2px}
nav{display:flex;gap:22px;font-size:13px;overflow-x:auto;padding-bottom:12px;scrollbar-width:none}nav::-webkit-scrollbar{display:none}
nav a{text-decoration:none;color:var(--ink);white-space:nowrap;padding-bottom:3px;border-bottom:1px solid transparent}nav a:hover,nav a[aria-current]{border-bottom-color:var(--ink)}
.notice{font-size:12px;color:var(--sub);padding:10px 0;border-bottom:1px solid var(--rule)}
main{padding-bottom:40px}
.crumb{font-size:12px;color:var(--sub);margin:22px 0 0}.crumb a{color:var(--sub);text-decoration:none}.crumb a:hover{text-decoration:underline}
.label{font-size:11px;letter-spacing:.18em;color:var(--acc);font-weight:700;margin:34px 0 8px}
h1.title{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:clamp(24px,4vw,34px);line-height:1.45;margin:6px 0 14px;letter-spacing:.02em}
.standfirst{color:var(--sub);font-size:15px;max-width:680px;margin:0 0 8px}
.dateline{font-size:12px;color:var(--sub);margin:0 0 26px}.dateline time{margin-right:12px}
h2.sec{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:21px;margin:44px 0 6px;letter-spacing:.03em}
.sec-sub{font-size:13px;color:var(--sub);margin:0 0 18px}
hr.rule{border:0;border-top:1px solid var(--rule);margin:36px 0}
/* 記事内の商品行 */
.row{display:grid;grid-template-columns:150px 1fr;gap:22px;padding:24px 0;border-top:1px solid var(--rule)}
.row:last-child{border-bottom:1px solid var(--rule)}
.row .thumb{background:#f1ede7}.row .thumb img{width:100%;aspect-ratio:1/1;object-fit:cover}
.row .n{font-family:"Shippori Mincho B1",serif;font-size:13px;color:var(--acc);letter-spacing:.1em;margin:0 0 4px}
.row h3{font-size:17px;line-height:1.55;margin:0 0 6px;font-weight:700}.row h3 a{text-decoration:none}.row h3 a:hover{text-decoration:underline}
.facts{font-size:13px;color:var(--sub);margin:0 0 8px}.facts b{color:var(--ink);font-weight:700}
.price{margin:0 0 8px;font-size:14px}.price b{font-size:22px;font-weight:700;letter-spacing:.01em}.price .eff{margin-left:10px;color:var(--acc);font-weight:700}
.memo{margin:0 0 12px;font-size:14px;color:#3a4048}
.go{display:inline-block;font-size:13px;font-weight:700;text-decoration:none;color:var(--ink);border:1px solid var(--ink);padding:8px 16px;border-radius:2px;transition:background .15s,color .15s}
.go:hover{background:var(--ink);color:#fff}
/* トップのグリッド */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px 22px}
.tile{text-decoration:none;color:inherit;display:block}
.tile .thumb{background:#f1ede7;margin-bottom:10px}.tile .thumb img{width:100%;aspect-ratio:1/1;object-fit:cover}
.tile .n{font-family:"Shippori Mincho B1",serif;font-size:12px;color:var(--acc);letter-spacing:.1em}
.tile h3{font-size:14px;line-height:1.55;margin:2px 0 4px;font-weight:700}.tile:hover h3{text-decoration:underline}
.tile .facts{margin:0 0 4px;font-size:12px}.tile .price{font-size:13px}.tile .price b{font-size:17px}
/* 一覧 */
.entries{list-style:none;margin:0;padding:0}
.entries li{display:grid;grid-template-columns:96px 1fr;gap:16px;padding:16px 0;border-top:1px solid var(--rule);align-items:baseline}
.entries li:last-child{border-bottom:1px solid var(--rule)}
.entries time{font-size:12px;color:var(--sub);font-variant-numeric:tabular-nums}
.entries a{text-decoration:none;font-weight:700;line-height:1.6}.entries a:hover{text-decoration:underline}
.entries small{display:block;font-size:12px;color:var(--sub);font-weight:400;margin-top:2px}
.pnav{display:flex;justify-content:space-between;gap:16px;margin:40px 0 0;font-size:13px}.pnav a{text-decoration:none;color:var(--ink);max-width:48%}.pnav a:hover{text-decoration:underline}.pnav span{display:block;color:var(--sub);font-size:11px;letter-spacing:.12em}
.who{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(2,1fr);gap:0 28px}
.who li{border-top:1px solid var(--rule);padding:14px 0}.who a{text-decoration:none;font-weight:700}.who a:hover{text-decoration:underline}.who small{display:block;font-size:12px;color:var(--sub);font-weight:400}
.prose p{margin:0 0 16px}.prose h2{font-family:"Shippori Mincho B1",serif;font-size:20px;margin:34px 0 10px}.prose ul{padding-left:20px}.prose li{margin-bottom:6px}
footer{border-top:1px solid var(--rule);padding:28px 0 40px;font-size:12px;color:var(--sub)}
footer .cols{display:flex;flex-wrap:wrap;gap:8px 22px;margin-bottom:12px}footer a{color:var(--sub);text-decoration:none}footer a:hover{text-decoration:underline}
@media (max-width:640px){.row{grid-template-columns:104px 1fr;gap:14px;padding:18px 0}.row h3{font-size:15px}.price b{font-size:19px}.grid{grid-template-columns:repeat(2,1fr);gap:20px 14px}.who{grid-template-columns:1fr}.entries li{grid-template-columns:1fr;gap:2px}.memo{font-size:13px}}
"""

FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@700&family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">')


def layout(title: str, body: str, rel: str, desc: str, canonical: str | None, jsonld: list[dict] | None = None,
           og_type: str = "website", current: str = "") -> str:
    base = site_url()
    page_url = (base + canonical) if (base and canonical is not None) else ""
    can = f'<link rel="canonical" href="{esc(page_url)}">' if page_url else ""
    og_img = f"{base}assets/og.png" if base else f"{rel}assets/og.png"
    og = (f'<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{esc(SITE_NAME)}">'
          f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">'
          f'<meta property="og:image" content="{esc(og_img)}"><meta property="og:locale" content="ja_JP">'
          + (f'<meta property="og:url" content="{esc(page_url)}">' if page_url else "")
          + '<meta name="twitter:card" content="summary_large_image">')
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    # Google Search Console の HTMLタグ認証コード（公開ページに埋め込む値なので秘密ではない）
    gsc = _env("GSC_VERIFICATION") or "iVy8LKuOONJ_5bkE3cqQXanhX1mp5nj"
    gsc_tag = f'<meta name="google-site-verification" content="{esc(gsc)}">' if gsc else ""
    navs = [("index.html", "新着", "home"), ("posts/index.html", "記事一覧", "posts"), ("ranking.html", "評価ランキング", "ranking"),
            ("for/index.html", "誰向けで探す", "for"), ("about.html", "選び方と運営者", "about")]
    nav = "".join(f'<a href="{rel}{h}"{" aria-current=\"page\"" if k == current else ""}>{t}</a>' for h, t, k in navs)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
{can}{og}{gsc_tag}
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_NAME)}" href="{rel}feed.xml">
{FONT_LINK}
<style>{CSS}</style>
{ld}
</head>
<body>
<header><div class="wrap">
<div class="top"><a class="wordmark" href="{rel}index.html"><b>{esc(BRAND)}</b><small>{esc(TAGLINE)}</small></a></div>
<nav aria-label="サイト内">{nav}</nav>
</div></header>
<div class="wrap notice">当サイトは楽天アフィリエイトの広告を含みます（PR）。商品リンク経由の購入で当サイトに報酬が発生します。価格・ポイント倍率は掲載時点のものです。</div>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
<div class="cols"><a href="{rel}about.html">選び方と運営者情報</a><a href="{rel}privacy.html">プライバシーポリシー</a><a href="{rel}posts/index.html">記事一覧</a><a href="{rel}feed.xml">RSS</a><a href="{esc(X_URL)}" rel="me">X</a>{f'<a href="{esc(ROOM_URL)}" rel="me">楽天ROOM</a>' if ROOM_URL else ''}</div>
<div>© {datetime.now().year} {esc(BRAND)}。掲載情報は楽天市場の公開データに基づきます。最新の価格・在庫は各商品ページでご確認ください。</div>
</div></footer>
</body>
</html>"""


# ---------------------------------------------------------------- 部品
def deal_of(e: dict[str, Any]) -> dict[str, str]:
    class P:
        name = e["name"]; catchcopy = e.get("catchcopy", ""); price = e["price"]; point_rate = e.get("point_rate", 1)
    return extract_deal(P())  # type: ignore[arg-type]


def facts_line(e: dict[str, Any], deal: dict[str, str]) -> str:
    parts = [f"<b>★{e['review_average']}</b>（レビュー{e['review_count']:,}件）"]
    if deal.get("rank1"):
        parts.append("楽天ランキング1位")
    if deal.get("discount"):
        parts.append(f"<b>{esc(deal['discount'])}</b>" + (f"・{esc(deal['deadline'])}" if deal.get("deadline") else ""))
    elif deal.get("deadline"):
        parts.append(esc(deal["deadline"]))
    if deal.get("ship"):
        parts.append("送料無料")
    return "　".join(parts)


def price_html(e: dict[str, Any]) -> str:
    pt = e.get("point_rate", 1)
    eff = f'<span class="eff">ポイント{pt}倍で実質 {int(e["price"] * (1 - pt / 100)):,}円</span>' if pt >= 2 else ""
    return f'<p class="price"><b>{e["price"]:,}</b>円{eff}</p>'


def memo_of(e: dict[str, Any]) -> str:
    if e.get("posted_text"):
        lines = [l for l in e["posted_text"].splitlines() if l.strip() and not l.startswith("#") and "ROOMはプロフ" not in l]
        # 1行目はフック。商品名行を除いた説明的な行を優先
        cand = [l for l in lines[1:] if not any(ch.isdigit() for ch in l[:2])] or lines[:1]
        return cand[0] if cand else ""
    import re
    cc = re.sub(r"[＼／\\/★☆【】\[\]｢｣「」]+", " ", e.get("catchcopy") or "")
    cc = re.sub(r"\s+", " ", cc).strip()
    # 店のキャッチコピーに効果効能の断定が含まれる場合は載せない（薬機法）
    from src.writer import NG_WORDS
    if any(w in cc for w in NG_WORDS + ["消える", "改善", "効く", "効果"]):
        return ""
    return cc[:70] if len(cc) >= 6 else ""


def row(e: dict[str, Any], n: int) -> str:
    deal = deal_of(e)
    name = _short_name(e["name"], 34)
    url = esc(e.get("affiliate_url") or e["item_url"])
    memo = memo_of(e)
    return f"""<article class="row">
<a class="thumb" href="{url}" rel="nofollow sponsored noopener" target="_blank"><img loading="lazy" width="600" height="600" src="{esc(e.get('image_url', ''))}" alt="{esc(name)}"></a>
<div>
<p class="n">{n:02d}</p>
<h3><a href="{url}" rel="nofollow sponsored noopener" target="_blank">{esc(name)}</a></h3>
<p class="facts">{facts_line(e, deal)}</p>
{price_html(e)}
{f'<p class="memo">{esc(memo)}</p>' if memo else ''}
<a class="go" href="{url}" rel="nofollow sponsored noopener" target="_blank">楽天市場で詳細を見る</a>
</div></article>"""


def tile(e: dict[str, Any], n: int) -> str:
    deal = deal_of(e)
    name = _short_name(e["name"], 30)
    url = esc(e.get("affiliate_url") or e["item_url"])
    return f"""<a class="tile" href="{url}" rel="nofollow sponsored noopener" target="_blank">
<div class="thumb"><img loading="lazy" width="600" height="600" src="{esc(e.get('image_url', ''))}" alt="{esc(name)}"></div>
<span class="n">{n:02d}</span><h3>{esc(name)}</h3>
<p class="facts">{facts_line(e, deal)}</p>{price_html(e)}</a>"""


def crumbs(rel: str, trail: list[tuple[str, str]]) -> tuple[str, dict]:
    base = site_url()
    parts = [f'<a href="{rel}index.html">ホーム</a>'] + [(f'<a href="{rel}{h}">{esc(t)}</a>' if h else esc(t)) for h, t in trail]
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement":
          [{"@type": "ListItem", "position": 1, "name": "ホーム", "item": base or "/"}] +
          [{"@type": "ListItem", "position": i + 2, "name": t, **({"item": base + h} if (h and base) else {})} for i, (h, t) in enumerate(trail)]}
    return '<p class="crumb">' + " › ".join(parts) + "</p>", ld


def item_list_ld(items: list[dict[str, Any]], name: str) -> dict:
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "numberOfItems": len(items),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": _short_name(e["name"], 40),
                                 "url": e.get("affiliate_url") or e["item_url"]} for i, e in enumerate(items)]}


def org_ld() -> dict:
    base = site_url()
    return {"@context": "https://schema.org", "@type": "Organization", "name": BRAND, "url": base or "/",
            "logo": f"{base}assets/og.png" if base else "assets/og.png", "sameAs": [u for u in (X_URL, ROOM_URL) if u]}


# 導入文のバリエーション（毎日同じ文にならないように日付で切り替える）
INTROS = [
    "{date}時点で楽天市場のランキングに入っている商品のうち、レビュー50件以上・評価4.2以上のものだけを残しました。{n}点、価格は税込、ポイント倍率から「実質いくらか」も添えています。",
    "{date}の楽天市場で、実際に注文が動いている商品を{n}点選びました。基準はレビュー50件以上と評価4.2以上。セール中の物は締切とポイント倍率を確認して載せています。",
    "楽天のリアルタイムランキングと年代別ランキングを{date}に確認し、{n}点に絞りました。レビューが少ない商品や評価4.2未満の商品は外しています。",
]
SLOT_LEADS = {
    "morning": "朝の時間帯に見られている商品です。短時間で判断できる日用品や、その日のうちに締切があるセール品を中心にしています。",
    "noon": "昼休みに見られている商品です。自分用のちょっとした買い物や、便利グッズが多くなります。",
    "night": "楽天市場で最も注文が多い夜の時間帯の商品です。単価がやや高いものや、じっくり比べたい商品もここに入ります。",
}


# ---------------------------------------------------------------- 生成
def build() -> None:
    store = load_site_items()
    if not store:
        print("data/site_items.json が空です。先に python main.py run（または --dry-run）を実行してください。")
        return
    items = list(store.values())
    base = site_url()
    today = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().isoformat(timespec="seconds")

    by_day: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": {}, "themes": {}})
    by_persona: dict[str, dict[str, Any]] = defaultdict(dict)
    for e in items:
        for t in e.get("themes", []):
            by_day[t["date"]]["items"][e["item_code"]] = e
            by_day[t["date"]]["themes"][t["slot"]] = t
            by_persona[t["persona"]][e["item_code"]] = e

    DOCS.mkdir(exist_ok=True)
    for sub in ("posts", "for", "assets"):
        (DOCS / sub).mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    og_src = ROOT / "assets" / "x_header_1500x500.png"
    if og_src.exists():
        shutil.copy(og_src, DOCS / "assets" / "og.png")
    urls: list[tuple[str, str]] = []

    # ---- 日別記事 ----
    days = sorted(by_day.keys(), reverse=True)
    meta: dict[str, dict[str, str]] = {}
    for d in days:
        info = by_day[d]
        top = sorted(info["items"].values(), key=lambda x: -x.get("score", 0))[:ITEMS_PER_DAY]
        themes = [info["themes"][k] for k in ("morning", "noon", "night") if k in info["themes"]]
        events = list(dict.fromkeys(t["theme"].split(" × ")[0].split("（")[0] for t in themes))
        personas = list(dict.fromkeys(PERSONAS[t["persona"]].label.split("（")[0] for t in themes if t["persona"] in PERSONAS))
        ev_txt = "・".join(events[:2]) if events else "楽天で今売れている物"
        title = f"{ev_txt}で買われている物{len(top)}選（{short_date(d)}）" + (f"｜{'・'.join(personas[:2])}向け" if personas else "")
        desc = (f"{jp_date(d)}に楽天市場で実際に売れている商品{len(top)}点。レビュー50件以上・評価4.2以上のものだけを選び、"
                f"ポイント倍率から実質価格を計算。" + "、".join(_short_name(x["name"], 14) for x in top[:3]) + " など。")
        meta[d] = {"title": title, "desc": desc}

    for i, d in enumerate(days):
        info = by_day[d]
        top = sorted(info["items"].values(), key=lambda x: -x.get("score", 0))[:ITEMS_PER_DAY]
        themes = [info["themes"][k] for k in ("morning", "noon", "night") if k in info["themes"]]
        cr, cr_ld = crumbs("../", [("posts/index.html", "記事一覧"), ("", short_date(d))])
        intro = INTROS[sum(map(int, d.split("-"))) % len(INTROS)].format(date=jp_date(d), n=len(top))
        body = (f'<article>{cr}<p class="label">DAILY PICKS</p><h1 class="title">{esc(meta[d]["title"])}</h1>'
                f'<p class="standfirst">{esc(intro)}</p>'
                f'<p class="dateline"><time datetime="{d}">{esc(jp_date(d))}</time>更新　文・{esc(BRAND)}</p>')
        n = 0
        for t in themes:
            sub = [e for e in top if any(tt["date"] == d and tt["slot"] == t["slot"] for tt in e["themes"])][:8]
            if not sub:
                continue
            ev = t["theme"].split(" × ")[0]
            pl = PERSONAS[t["persona"]].label if t["persona"] in PERSONAS else ""
            ev = ev.replace("）（", "・")
            body += f'<h2 class="sec">{esc(SLOT_JA.get(t["slot"], ""))}の部　{esc(ev)}</h2><p class="sec-sub">{esc(pl)}向けに選んだ{len(sub)}点。{esc(SLOT_LEADS.get(t["slot"], ""))}</p>'
            for e in sub:
                n += 1
                body += row(e, n)
        # 選び方
        body += ('<hr class="rule"><section class="prose"><h2>この記事の選び方</h2>'
                 '<p>楽天市場のランキングAPIとキーワード検索から候補を集め、レビュー件数・評価・アフィリエイト料率・ポイント倍率・価格帯で点数を付けて上位を掲載しています。'
                 '単価が1,500円未満の商品、レビュー50件未満、評価4.2未満、中古品は除外しています。'
                 '割引率や締切は商品名・キャッチコピーに書かれているものだけを転記し、こちらで推測した数字は載せていません。詳しくは<a href="../about.html">選び方と運営者情報</a>をご覧ください。</p></section>')
        # 前後の記事
        prev_d = days[i + 1] if i + 1 < len(days) else None
        next_d = days[i - 1] if i > 0 else None
        body += '<nav class="pnav" aria-label="前後の記事">'
        body += (f'<a href="{prev_d}.html"><span>前の記事</span>{esc(meta[prev_d]["title"])}</a>' if prev_d else "<span></span>")
        body += (f'<a href="{next_d}.html" style="text-align:right"><span>次の記事</span>{esc(meta[next_d]["title"])}</a>' if next_d else "")
        body += "</nav>"
        # 関連
        rel_personas = [k for k in dict.fromkeys(t["persona"] for t in themes) if k in PERSONAS]
        body += '<h2 class="sec">関連するまとめ</h2><ul class="who">' + "".join(
            f'<li><a href="../for/{k}.html">{esc(PERSONAS[k].label.split("（")[0])}に人気の楽天アイテム</a><small>{esc(PERSONAS[k].label)}</small></li>' for k in rel_personas
        ) + '<li><a href="../ranking.html">レビュー評価で選ぶ人気商品ランキング</a><small>掲載した全商品を評価×件数で並べ替え</small></li></ul></article>'
        article_ld = {"@context": "https://schema.org", "@type": "Article", "headline": meta[d]["title"][:110],
                      "description": meta[d]["desc"], "datePublished": f"{d}T21:00:00+09:00", "dateModified": f"{d}T21:00:00+09:00",
                      "author": {"@type": "Organization", "name": BRAND}, "publisher": org_ld(),
                      "image": [f"{base}assets/og.png"] if base else [], "mainEntityOfPage": f"{base}posts/{d}.html" if base else f"posts/{d}.html"}
        (DOCS / "posts" / f"{d}.html").write_text(
            layout(f"{meta[d]['title']}｜{BRAND}", body, "../", meta[d]["desc"], f"posts/{d}.html",
                   [article_ld, item_list_ld(top, meta[d]["title"]), cr_ld], "article", "posts"), encoding="utf-8")
        urls.append((f"posts/{d}.html", d))

    # ---- 記事一覧 ----
    cr, cr_ld = crumbs("../", [("", "記事一覧")])
    body = (f'{cr}<p class="label">ARCHIVE</p><h1 class="title">記事一覧</h1><p class="standfirst">毎日、朝・昼・夜の3回分をまとめて1本の記事にしています。</p>'
            '<ul class="entries">' + "".join(
                f'<li><time datetime="{d}">{esc(jp_date(d))}</time><div><a href="{d}.html">{esc(meta[d]["title"])}</a><small>{esc(meta[d]["desc"][:70])}…</small></div></li>' for d in days) + "</ul>")
    (DOCS / "posts" / "index.html").write_text(layout(f"記事一覧｜{BRAND}", body, "../", "楽天で売れている物の日別まとめ記事の一覧。", "posts/index.html", [cr_ld], "website", "posts"), encoding="utf-8")
    urls.append(("posts/index.html", today))

    # ---- 誰向け ----
    for key, persona in PERSONAS.items():
        if key == "all":
            continue
        pool = sorted(by_persona.get(key, {}).values(), key=lambda x: (x.get("last_seen", ""), x.get("score", 0)), reverse=True)[:30]
        short = persona.label.split("（")[0]
        title = f"{short}に人気の楽天アイテム{len(pool)}選"
        desc = f"{persona.label}向けに、楽天市場のランキングとレビューから選んだ商品を新しい順に。毎日更新。"
        gl = "・".join(GENRES.get(g, "") for g in persona.genres[:3])
        cr, cr_ld = crumbs("../", [("for/index.html", "誰向けで探す"), ("", short)])
        body = (f'<article>{cr}<p class="label">FOR</p><h1 class="title">{esc(title)}</h1>'
                f'<p class="standfirst">{esc(persona.label)}。よく見ているジャンルは{esc(gl)}。このページは新しく掲載した順に並び、古いものは順に外れます。</p>'
                f'<p class="dateline"><time datetime="{today}">{esc(jp_date(today))}</time>更新</p>')
        body += "".join(row(e, i + 1) for i, e in enumerate(pool)) if pool else "<p>まだ商品がありません。</p>"
        body += "</article>"
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc,
               "url": f"{base}for/{key}.html" if base else f"for/{key}.html", "dateModified": now_iso}, cr_ld]
        if pool:
            ld.append(item_list_ld(pool, title))
        (DOCS / "for" / f"{key}.html").write_text(layout(f"{title}｜{BRAND}", body, "../", desc, f"for/{key}.html", ld, "website", "for"), encoding="utf-8")
        urls.append((f"for/{key}.html", today))

    cr, cr_ld = crumbs("../", [("", "誰向けで探す")])
    body = (f'{cr}<p class="label">FOR</p><h1 class="title">誰向けで探す</h1><p class="standfirst">同じ「売れている物」でも、誰が買っているかで中身は変わります。近い立場のページから見てください。</p><ul class="who">'
            + "".join(f'<li><a href="{k}.html">{esc(v.label.split("（")[0])}に人気の楽天アイテム</a><small>{esc(v.label)}　掲載{len(by_persona.get(k, {}))}点</small></li>' for k, v in PERSONAS.items() if k != "all") + "</ul>")
    (DOCS / "for" / "index.html").write_text(layout(f"誰向けで探す｜{BRAND}", body, "../", "20代女性、30代女性、子育て世帯、20代・30代・40代男性。立場別の楽天おすすめまとめ。", "for/index.html", [cr_ld], "website", "for"), encoding="utf-8")
    urls.append(("for/index.html", today))

    # ---- ランキング ----
    ranked = sorted(items, key=lambda x: -(x["review_average"] * (x["review_count"] ** 0.5)))[:50]
    title = "レビュー評価で選ぶ楽天の人気商品ランキング"
    desc = "これまで掲載した楽天市場の商品を、レビュー評価と件数の両方で並べたランキング。毎日更新。"
    cr, cr_ld = crumbs("", [("", "評価ランキング")])
    body = (f'<article>{cr}<p class="label">RANKING</p><h1 class="title">{esc(title)}</h1>'
            f'<p class="standfirst">掲載した{len(items)}点を「評価 × レビュー件数の平方根」で並べています。件数だけだと定番品ばかり、評価だけだと件数の少ない商品が上に来るので、両方を掛けています。</p>'
            f'<p class="dateline"><time datetime="{today}">{esc(jp_date(today))}</time>更新</p>' + "".join(row(e, i + 1) for i, e in enumerate(ranked)) + "</article>")
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": f"{base}ranking.html" if base else "ranking.html", "dateModified": now_iso},
          item_list_ld(ranked, title), cr_ld]
    (DOCS / "ranking.html").write_text(layout(f"{title}｜{BRAND}", body, "", desc, "ranking.html", ld, "website", "ranking"), encoding="utf-8")
    urls.append(("ranking.html", today))

    # ---- 運営者情報・選び方 ----
    cr, cr_ld = crumbs("", [("", "選び方と運営者情報")])
    body = f"""{cr}<p class="label">ABOUT</p><h1 class="title">選び方と運営者情報</h1>
<section class="prose">
<p>{esc(BRAND)}は、楽天市場で「実際に売れていて、買った人の評価が高い物」だけを毎日3回選んで掲載しているサイトです。特定の店や商品を宣伝するためではなく、迷う時間を減らすために作っています。</p>
<h2>掲載の基準</h2>
<ul>
<li>楽天市場のリアルタイムランキング、年代・性別別ランキング、セール検索から候補を集めます。</li>
<li>レビュー50件以上、評価4.2以上の商品だけを残します。</li>
<li>単価1,500円未満、中古品、在庫切れの商品は除外します。</li>
<li>レビュー件数・評価・ポイント倍率・価格帯で点数を付け、上位を掲載します。同じ店の商品は1日2点までです。</li>
<li>割引率・締切・順位は、商品名やキャッチコピーに書かれている内容だけを転記します。こちらで推測した数字は載せません。</li>
</ul>
<h2>価格と「実質価格」について</h2>
<p>価格は掲載時点の税込表示です。「実質価格」は、表示価格からポイント倍率相当を差し引いた目安で、ポイントの付与条件（会員ランク、エントリー、支払い方法）によって実際の還元は変わります。購入前に必ず商品ページでご確認ください。</p>
<h2>広告について</h2>
<p>当サイトは楽天アフィリエイトに参加しています。商品リンクは広告リンクで、リンク経由で購入されると当サイトに報酬が支払われます。報酬の有無や料率は掲載順位に影響していますが、レビュー件数と評価の基準を満たさない商品は料率が高くても掲載しません。</p>
<h2>運営者</h2>
<p>{esc(BRAND)}（個人運営）。更新情報は<a href="{esc(X_URL)}">X</a>{f'と<a href="{esc(ROOM_URL)}">楽天ROOM</a>' if ROOM_URL else ''}でも発信しています。掲載内容の誤りや削除のご依頼はXのダイレクトメッセージでお知らせください。</p>
</section>"""
    (DOCS / "about.html").write_text(layout(f"選び方と運営者情報｜{BRAND}", body, "", f"{BRAND}の掲載基準、価格表示の考え方、広告について、運営者情報。", "about.html",
                                            [{"@context": "https://schema.org", "@type": "AboutPage", "name": "選び方と運営者情報", "url": f"{base}about.html" if base else "about.html"}, cr_ld], "website", "about"), encoding="utf-8")
    urls.append(("about.html", today))

    # ---- プライバシーポリシー ----
    cr, cr_ld = crumbs("", [("", "プライバシーポリシー")])
    body = f"""{cr}<p class="label">PRIVACY</p><h1 class="title">プライバシーポリシー</h1>
<section class="prose">
<h2>広告の配信について</h2>
<p>当サイトは、楽天グループ株式会社が提供する「楽天アフィリエイト」を利用しています。商品リンクをクリックして楽天市場で購入が行われた場合、当サイトに成果報酬が支払われます。この仕組みのため、楽天側でクッキー（Cookie）が使用されることがあります。クッキーの詳細と無効化の方法は、楽天の<a href="https://privacy.rakuten.co.jp/" rel="noopener" target="_blank">プライバシーポリシー</a>をご確認ください。</p>
<h2>アクセス解析について</h2>
<p>当サイトは現在、独自のアクセス解析ツールを設置していません。導入した場合は本ページで告知します。</p>
<h2>外部サービス</h2>
<p>当サイトはGitHub Pages上で公開され、Google Fontsを読み込んでいます。各サービスの利用規約・プライバシーポリシーはそれぞれの提供元に従います。</p>
<h2>免責事項</h2>
<p>掲載している価格・ポイント倍率・在庫は掲載時点の情報で、変更されることがあります。当サイトの情報によって生じた損害について、運営者は責任を負いません。最終的な購入判断は各商品ページの最新情報でご確認ください。</p>
<p>制定日：2026年9月6日</p>
</section>"""
    (DOCS / "privacy.html").write_text(layout(f"プライバシーポリシー｜{BRAND}", body, "", f"{BRAND}のプライバシーポリシー。広告・クッキー・免責事項について。", "privacy.html", [cr_ld], "website", ""), encoding="utf-8")
    urls.append(("privacy.html", today))

    # ---- トップ ----
    latest = days[0] if days else None
    body = (f'<p class="label" style="margin-top:38px">TODAY</p><h1 class="title">楽天で「本当に売れている物」だけ、毎日3回。</h1>'
            f'<p class="standfirst">ランキングとレビューから、レビュー50件以上・評価4.2以上の商品だけを選んでいます。セール中はポイント倍率から実質価格を計算します。</p>')
    if latest:
        top = sorted(by_day[latest]["items"].values(), key=lambda x: -x.get("score", 0))[:6]
        body += (f'<p class="dateline"><time datetime="{latest}">{esc(jp_date(latest))}</time>更新</p>'
                 f'<div class="grid">' + "".join(tile(e, i + 1) for i, e in enumerate(top)) + "</div>"
                 f'<p style="margin-top:22px"><a href="posts/{latest}.html">この日の{len(by_day[latest]["items"])}点をすべて見る</a></p>')
    body += '<h2 class="sec">最近の記事</h2><ul class="entries">' + "".join(
        f'<li><time datetime="{d}">{esc(jp_date(d))}</time><div><a href="posts/{d}.html">{esc(meta[d]["title"])}</a></div></li>' for d in days[:DAYS_ON_INDEX]) + "</ul>"
    body += '<h2 class="sec">誰向けで探す</h2><p class="sec-sub">立場が近い人のページから見ると早いです。</p><ul class="who">' + "".join(
        f'<li><a href="for/{k}.html">{esc(v.label.split("（")[0])}に人気の楽天アイテム</a><small>{esc(v.label)}</small></li>' for k, v in PERSONAS.items() if k != "all") + "</ul>"
    body += ('<h2 class="sec">このサイトについて</h2><p class="standfirst">選び方の基準、価格表示の考え方、広告についての説明は<a href="about.html">選び方と運営者情報</a>にまとめています。'
             '掲載した全商品の<a href="ranking.html">評価ランキング</a>もあります。</p>')
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": base or "/", "description": "楽天市場で本当に売れている物を毎日3回、レビューと評価で厳選。", "publisher": org_ld()}, org_ld()]
    (DOCS / "index.html").write_text(layout(SITE_NAME, body, "", "楽天市場で本当に売れている物を毎日3回、レビュー50件以上・評価4.2以上の商品だけ厳選。ポイント倍率から実質価格も計算。", "", ld, "website", "home"), encoding="utf-8")
    urls.append(("", today))

    # ---- 404 ----
    body = '<p class="label" style="margin-top:38px">404</p><h1 class="title">ページが見つかりません</h1><p class="standfirst">URLが変わったか、削除された可能性があります。<a href="/">トップページ</a>か<a href="/posts/index.html">記事一覧</a>からお探しください。</p>'
    (DOCS / "404.html").write_text(layout(f"ページが見つかりません｜{BRAND}", body, "/", "", None, None, "website", ""), encoding="utf-8")

    # ---- RSS / sitemap / robots ----
    if base:
        rss_items = "".join(
            f"<item><title>{esc(meta[d]['title'])}</title><link>{esc(base)}posts/{d}.html</link><guid>{esc(base)}posts/{d}.html</guid>"
            f"<description>{esc(meta[d]['desc'])}</description><pubDate>{datetime.strptime(d, '%Y-%m-%d').strftime('%a, %d %b %Y 21:00:00 +0900')}</pubDate></item>" for d in days[:20])
        (DOCS / "feed.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE_NAME)}</title><link>{esc(base)}</link>'
            f'<description>楽天で本当に売れている物を毎日厳選</description><language>ja</language>{rss_items}</channel></rss>', encoding="utf-8")
        (DOCS / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{d}</lastmod></url>" for u, d in urls) + "</urlset>", encoding="utf-8")
        (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    else:
        (DOCS / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    print(f"生成完了: docs/  日別記事 {len(days)} 本、商品 {len(items)} 点、ページ {len(urls) + 1}、URL {base or '(SITE_URL 未設定)'}")


if __name__ == "__main__":
    build()

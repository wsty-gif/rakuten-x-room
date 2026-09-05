"""GitHub Pages 用の静的ブログを docs/ に生成する。  python build_site.py

入力: data/site_items.json（main.py run が毎回蓄積）
出力: docs/index.html, docs/posts/YYYY-MM-DD.html（日別記事）, docs/for/<persona>.html（誰向け別）,
      docs/ranking.html, docs/feed.xml, docs/sitemap.xml, docs/robots.txt
"""
from __future__ import annotations

import html
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
from src.config import GENRES, PERSONAS, ROOT, _env
from src.site_store import load_site_items
from src.writer import _short_name, extract_deal

DOCS = ROOT / "docs"
SITE_NAME = _env("SITE_NAME", "らくみつ｜楽天で見つけた良いもの")
ROOM_URL = _env("ROOM_URL")
X_URL = _env("X_PROFILE_URL", "https://x.com/rakumitsu__room")
DAYS_ON_INDEX = 14
ITEMS_PER_DAY = 12


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


CSS = """
:root{--c:#ff6b4a;--n:#242c42;--g:#6b7280;--bg:#fff7f0;--card:#fff}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic",sans-serif;background:var(--bg);color:var(--n);line-height:1.6}
a{color:var(--c)}header{background:#fff;border-bottom:3px solid var(--c)}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
.brand{display:flex;align-items:center;gap:10px;padding:14px 0;text-decoration:none;color:var(--n);font-weight:700;font-size:18px}
.brand .logo{width:34px;height:34px;border-radius:50%;background:var(--c);display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:14px}
nav a{margin-right:14px;font-size:14px;color:var(--n)}
.pr{background:#fff3ec;border:1px solid #ffd2c4;color:#8a3b25;font-size:12px;padding:8px 12px;border-radius:8px;margin:14px 0}
h1{font-size:22px;margin:18px 0 6px}h2{font-size:18px;margin:28px 0 10px;border-left:5px solid var(--c);padding-left:10px}
.lead{color:var(--g);font-size:14px;margin:0 0 10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:1/1;object-fit:cover;background:#f3f4f6}
.card .body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.card h3{font-size:15px;margin:0;line-height:1.4}.card h3 a{color:var(--n);text-decoration:none}
.meta{font-size:12px;color:var(--g);margin:0}.deal{font-size:13px;color:#b42318;margin:0;font-weight:600}
.price{font-size:18px;font-weight:700;margin:0}.price small{font-size:12px;color:var(--g);font-weight:400;margin-left:6px}
.why{font-size:13px;margin:0;color:#374151}
.btn{margin-top:auto;display:block;text-align:center;background:var(--c);color:#fff;text-decoration:none;padding:10px;border-radius:8px;font-weight:700;font-size:14px}
.list{list-style:none;padding:0;margin:0}.list li{background:#fff;border-radius:10px;padding:12px 14px;margin-bottom:8px}
.list a{text-decoration:none;color:var(--n);font-weight:600}.list .d{font-size:12px;color:var(--g);margin-right:8px}
.tags a{display:inline-block;background:#fff;border:1px solid #ffd2c4;border-radius:999px;padding:6px 12px;margin:0 8px 8px 0;font-size:13px;text-decoration:none;color:var(--n)}
footer{margin:40px 0 30px;font-size:12px;color:var(--g);text-align:center}
"""


def layout(title: str, body: str, rel: str, desc: str = "", canonical: str = "") -> str:
    base = site_url()
    can = f'<link rel="canonical" href="{esc(base + canonical)}">' if base and canonical is not None else ""
    og = f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">'
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{can}{og}
<link rel="alternate" type="application/rss+xml" href="{rel}feed.xml">
<style>{CSS}</style></head><body>
<header><div class="wrap"><a class="brand" href="{rel}index.html"><span class="logo">らく</span>{esc(SITE_NAME)}</a>
<nav><a href="{rel}index.html">新着</a><a href="{rel}ranking.html">人気ランキング</a>{''.join(f'<a href="{rel}for/{k}.html">{esc(v.label.split("（")[0])}</a>' for k, v in PERSONAS.items() if k != "all")}</nav></div></header>
<main class="wrap">
<div class="pr">PR：当サイトは楽天アフィリエイトプログラムに参加しており、商品リンクから購入されると当サイトに報酬が支払われます。価格・ポイント倍率は掲載時点の情報です。</div>
{body}
</main>
<footer><div class="wrap">{esc(SITE_NAME)} ｜ <a href="{esc(X_URL)}">X</a>{' ｜ <a href="' + esc(ROOM_URL) + '">楽天ROOM</a>' if ROOM_URL else ''}<br>掲載情報は楽天市場の公開データに基づきます。最新の価格は各商品ページでご確認ください。</div></footer>
</body></html>"""


def card(e: dict[str, Any]) -> str:
    deal = extract_deal_from_entry(e)
    name = _short_name(e["name"], 30)
    parts = []
    if deal.get("discount"):
        parts.append(deal["discount"] + (f"（{deal['deadline']}）" if deal.get("deadline") else ""))
    elif deal.get("deadline"):
        parts.append(deal["deadline"])
    if deal.get("rank1"):
        parts.append(deal["rank1"])
    if deal.get("ship"):
        parts.append("送料無料")
    pt = e.get("point_rate", 1)
    eff = f'<small>P{pt}倍・実質{int(e["price"] * (1 - pt / 100)):,}円</small>' if pt >= 2 else ""
    why = ""
    if e.get("posted_text"):
        lines = [l for l in e["posted_text"].splitlines() if l.strip() and not l.startswith("#") and "ROOMはプロフ" not in l]
        why = lines[0] if lines else ""
    elif e.get("catchcopy"):
        why = e["catchcopy"][:60]
    url = esc(e.get("affiliate_url") or e["item_url"])
    return f"""<article class="card">
<a href="{url}" rel="nofollow sponsored noopener" target="_blank"><img loading="lazy" src="{esc(e.get('image_url', ''))}" alt="{esc(name)}"></a>
<div class="body"><h3><a href="{url}" rel="nofollow sponsored noopener" target="_blank">{esc(name)}</a></h3>
<p class="meta">★{e['review_average']}（レビュー{e['review_count']:,}件）｜{esc(e['shop_name'])}</p>
{f'<p class="deal">{esc("・".join(parts))}</p>' if parts else ''}
<p class="price">{e['price']:,}円{eff}</p>
{f'<p class="why">{esc(why)}</p>' if why else ''}
<a class="btn" href="{url}" rel="nofollow sponsored noopener" target="_blank">楽天市場で見る</a></div></article>"""


def extract_deal_from_entry(e: dict[str, Any]) -> dict[str, str]:
    class P:  # extract_deal は Product を期待するので最低限の属性だけ持つ
        name = e["name"]; catchcopy = e.get("catchcopy", ""); price = e["price"]; point_rate = e.get("point_rate", 1)
    return extract_deal(P())  # type: ignore[arg-type]


def jp_date(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(y)}年{int(m)}月{int(dd)}日"


def build() -> None:
    store = load_site_items()
    if not store:
        print("data/site_items.json が空です。先に python main.py run（または --dry-run）を実行してください。")
        return
    items = list(store.values())

    # 日別・ペルソナ別にまとめる
    by_day: dict[str, dict[str, Any]] = defaultdict(lambda: {"items": {}, "themes": {}})
    by_persona: dict[str, dict[str, Any]] = defaultdict(dict)
    for e in items:
        for t in e.get("themes", []):
            d = by_day[t["date"]]
            d["items"][e["item_code"]] = e
            d["themes"][t["slot"]] = t
            by_persona[t["persona"]][e["item_code"]] = e

    DOCS.mkdir(exist_ok=True)
    (DOCS / "posts").mkdir(exist_ok=True)
    (DOCS / "for").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    base = site_url()
    urls: list[tuple[str, str]] = []

    # ---- 日別記事 ----
    days = sorted(by_day.keys(), reverse=True)
    day_meta: dict[str, dict[str, str]] = {}
    for d in days:
        info = by_day[d]
        top = sorted(info["items"].values(), key=lambda x: -x.get("score", 0))[:ITEMS_PER_DAY]
        themes = [info["themes"][k] for k in ("morning", "noon", "night") if k in info["themes"]]
        events = []
        personas = []
        for t in themes:
            ev = t["theme"].split(" × ")[0]
            ev = ev.split("（")[0]
            if ev not in events:
                events.append(ev)
            pl = PERSONAS.get(t["persona"]).label.split("（")[0] if t["persona"] in PERSONAS else ""
            if pl and pl not in personas:
                personas.append(pl)
        ev_txt = "・".join(events[:2]) if events else "楽天で今売れている物"
        title = f"【{jp_date(d)}】{ev_txt}で買われている物 TOP{len(top)}" + (f"｜{'・'.join(personas[:2])}向け" if personas else "")
        desc = f"{jp_date(d)}に楽天市場で実際に売れている商品を、レビュー件数・評価・ポイント倍率で選んだ{len(top)}点。" + ("、".join(_short_name(x["name"], 14) for x in top[:3]) + " など。")
        intro = (f"<p class=\"lead\">{esc(jp_date(d))}時点の楽天ランキングとセール情報から、"
                 f"レビュー50件以上・評価4.2以上の商品だけを選び、ポイント倍率で「実質いくらか」まで計算しています。</p>")
        body = f"<h1>{esc(title)}</h1>{intro}"
        # スロットごとの見出し
        for t in themes:
            pl = PERSONAS.get(t["persona"]).label if t["persona"] in PERSONAS else ""
            body += f"<h2>{esc(t['theme'].split(' × ')[0])}｜{esc(pl)}</h2>"
            sub = [e for e in top if any(tt["date"] == d and tt["slot"] == t["slot"] for tt in e["themes"])]
            body += '<div class="grid">' + "".join(card(e) for e in sub[:8]) + "</div>"
        body += "<h2>関連ページ</h2><p class=\"tags\">" + "".join(
            f'<a href="../for/{k}.html">{esc(PERSONAS[k].label.split("（")[0])}向け</a>' for k in {t["persona"] for t in themes} if k in PERSONAS
        ) + '<a href="../ranking.html">レビュー評価ランキング</a></p>'
        path = DOCS / "posts" / f"{d}.html"
        path.write_text(layout(title, body, "../", desc, f"posts/{d}.html"), encoding="utf-8")
        urls.append((f"posts/{d}.html", d))
        day_meta[d] = {"title": title, "desc": desc}

    # ---- ペルソナ別ページ ----
    for key, persona in PERSONAS.items():
        if key == "all":
            continue
        pool = sorted(by_persona.get(key, {}).values(), key=lambda x: (x.get("last_seen", ""), x.get("score", 0)), reverse=True)[:30]
        title = f"{persona.label}に人気の楽天アイテム{len(pool)}選"
        desc = f"{persona.label}向けに、楽天市場のランキングとレビューから選んだ商品まとめ。毎日自動更新。"
        gl = "・".join(GENRES.get(g, "") for g in persona.genres[:3])
        body = f"<h1>{esc(title)}</h1><p class=\"lead\">主なジャンル: {esc(gl)}。レビュー50件以上・評価4.2以上のものだけ掲載しています。</p>"
        body += '<div class="grid">' + "".join(card(e) for e in pool) + "</div>" if pool else "<p>まだ商品がありません。</p>"
        (DOCS / "for" / f"{key}.html").write_text(layout(title, body, "../", desc, f"for/{key}.html"), encoding="utf-8")
        urls.append((f"for/{key}.html", datetime.now().strftime("%Y-%m-%d")))

    # ---- ランキング ----
    ranked = sorted(items, key=lambda x: -(x["review_average"] * (x["review_count"] ** 0.5)))[:50]
    title = "レビュー評価で選ぶ楽天の人気商品ランキング TOP50"
    body = f"<h1>{esc(title)}</h1><p class=\"lead\">これまでに掲載した商品を、レビュー評価と件数の両方で並べました。「たくさん売れていて、かつ満足度が高い」順です。</p>"
    body += '<div class="grid">' + "".join(card(e) for e in ranked) + "</div>"
    (DOCS / "ranking.html").write_text(layout(title, body, "", "楽天市場の人気商品をレビュー評価順に。毎日自動更新。", "ranking.html"), encoding="utf-8")
    urls.append(("ranking.html", datetime.now().strftime("%Y-%m-%d")))

    # ---- トップページ ----
    latest = days[0] if days else None
    body = f"<h1>{esc(SITE_NAME)}</h1><p class=\"lead\">楽天市場で「本当に売れている物」だけを、レビュー件数・評価・ポイント倍率で毎日3回選んで掲載しています。</p>"
    if latest:
        top = sorted(by_day[latest]["items"].values(), key=lambda x: -x.get("score", 0))[:6]
        body += f"<h2>今日のおすすめ（{esc(jp_date(latest))}）</h2><div class=\"grid\">" + "".join(card(e) for e in top) + "</div>"
        body += f'<p><a href="posts/{latest}.html">→ {esc(day_meta[latest]["title"])}</a></p>'
    body += "<h2>誰向けで探す</h2><p class=\"tags\">" + "".join(
        f'<a href="for/{k}.html">{esc(v.label)}</a>' for k, v in PERSONAS.items() if k != "all") + "</p>"
    body += "<h2>日別の記事</h2><ul class=\"list\">" + "".join(
        f'<li><span class="d">{esc(d)}</span><a href="posts/{d}.html">{esc(day_meta[d]["title"])}</a></li>' for d in days[:DAYS_ON_INDEX]) + "</ul>"
    (DOCS / "index.html").write_text(layout(SITE_NAME, body, "", "楽天市場で本当に売れている物を毎日自動で厳選。レビュー・評価・ポイント倍率で選ぶ。", ""), encoding="utf-8")
    urls.append(("", datetime.now().strftime("%Y-%m-%d")))

    # ---- RSS / sitemap / robots ----
    if base:
        rss_items = "".join(
            f"<item><title>{esc(day_meta[d]['title'])}</title><link>{esc(base)}posts/{d}.html</link>"
            f"<guid>{esc(base)}posts/{d}.html</guid><description>{esc(day_meta[d]['desc'])}</description>"
            f"<pubDate>{datetime.strptime(d, '%Y-%m-%d').strftime('%a, %d %b %Y 21:00:00 +0900')}</pubDate></item>" for d in days[:20])
        (DOCS / "feed.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE_NAME)}</title>'
            f'<link>{esc(base)}</link><description>楽天で本当に売れている物を毎日厳選</description>{rss_items}</channel></rss>', encoding="utf-8")
        (DOCS / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{d}</lastmod></url>" for u, d in urls) + "</urlset>", encoding="utf-8")
        (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    else:
        (DOCS / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    print(f"生成完了: docs/  日別記事 {len(days)} 本、商品 {len(items)} 点、URL {base or '(SITE_URL 未設定: 相対リンクのみ)'}")


if __name__ == "__main__":
    build()

"""GitHub Pages 用の静的ブログを docs/ に生成する。  python build_site.py

構成は日本の一般的なブログ（トップバー / ヘッダー / スライダー / 2カラム: 本文＋サイドバー）。
入力: data/site_items.json（main.py run が毎回蓄積）、data/calendar.json（セール予定）
出力: docs/ 以下
  index.html                 トップ（スライダー、誰向けアイコン、記事一覧、サイドバー）
  posts/YYYY-MM-DD.html      日別記事（目次、商品ボックス、選び方、前後の記事）
  posts/index.html           記事一覧
  for/<persona>.html         誰向け別まとめ、 for/index.html
  ranking.html               レビュー評価ランキング
  about.html / privacy.html  運営者情報・選定基準 / プライバシーポリシー
  404.html, feed.xml, sitemap.xml, robots.txt, assets/
SEO: 固有 title/description、canonical、OGP、JSON-LD（WebSite/Organization/Article/CollectionPage/ItemList/BreadcrumbList）
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
from src.config import CALENDAR_FILE, GENRES, PERSONAS, ROOT, _env
from src.site_store import load_site_items
from src.writer import NG_WORDS, _short_name, extract_deal

DOCS = ROOT / "docs"
SITE_NAME = _env("SITE_NAME", "らくみつ｜楽天で見つけた良いもの")
BRAND = SITE_NAME.split("｜")[0]
TAGLINE = SITE_NAME.split("｜")[1] if "｜" in SITE_NAME else ""
ROOM_URL = _env("ROOM_URL")
X_URL = _env("X_PROFILE_URL", "https://x.com/rakumitsu__room")
THREADS_URL = _env("THREADS_PROFILE_URL", "https://www.threads.net/@rakumitsu__room")
ITEMS_PER_DAY = 12
SLOT_JA = {"morning": "朝", "noon": "昼", "night": "夜"}
PERSONA_SHORT = {k: v.label.split("（")[0] for k, v in PERSONAS.items()}
PERSONA_DESC = {k: (v.label.split("（")[1].rstrip("）") if "（" in v.label else "") for k, v in PERSONAS.items()}


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


# ---------------------------------------------------------------- アイコン（インラインSVG）
ICONS = {
    "search": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
    "x": '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M18.9 2H22l-7.6 8.7L23.3 22h-7l-5.5-7.2L4.5 22H1.4l8.1-9.3L0.7 2h7.2l5 6.6L18.9 2zm-1.2 18h1.9L7.4 3.9H5.4L17.7 20z"/></svg>',
    "threads": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3c-5 0-8 3.5-8 9s3 9 8 9c4 0 7-2.3 7-5.6 0-2.8-2-4.4-4.8-4.4-2.4 0-4 1.2-4 3 0 1.6 1.3 2.6 3 2.6 2.2 0 3.5-1.6 3.6-4.6"/><path d="M8.2 9c.8-1.6 2.2-2.4 4-2.4 2.6 0 4.2 1.5 4.6 4"/></svg>',
    "room": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M6 8h12l1 13H5L6 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
    "rss": '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><circle cx="5" cy="19" r="2.2"/><path d="M3 10a11 11 0 0 1 11 11h-3a8 8 0 0 0-8-8v-3z"/><path d="M3 3a18 18 0 0 1 18 18h-3A15 15 0 0 0 3 6V3z"/></svg>',
    "tag": '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 12V4h8l10 10-8 8L3 12z"/><circle cx="8" cy="9" r="1.5" fill="currentColor"/></svg>',
    "list": '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1.2" fill="currentColor"/><circle cx="3.5" cy="12" r="1.2" fill="currentColor"/><circle cx="3.5" cy="18" r="1.2" fill="currentColor"/></svg>',
    "crown": '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z"/></svg>',
    "cal": '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    "user": '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/></svg>',
    "check": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg>',
}
# 誰向けアイコン（線画）
PERSONA_ICON = {
    "20s_woman": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6l1 6H8l1-6z"/><path d="M8 9h8v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V9z"/><path d="M12 13v4"/></svg>',
    "30s_woman": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg>',
    "mama": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="5"/><path d="M9.5 9.5h.01M14.5 9.5h.01"/><path d="M10 12c1 1 3 1 4 0"/><path d="M7 21c0-3 2-5 5-5s5 2 5 5"/></svg>',
    "20s_man": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="3" y="13" width="4" height="7" rx="1.5"/><rect x="17" y="13" width="4" height="7" rx="1.5"/></svg>',
    "30s_man": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L5 14h6l-1 8 9-13h-6l0-7z"/></svg>',
    "40s_man": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 8h9v11a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V8z"/><path d="M16 10h2a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-2"/><path d="M7 8c0-3 2-5 4.5-5S16 5 16 8"/></svg>',
}


# ---------------------------------------------------------------- スタイル
CSS = """
:root{--acc:#ff6b4a;--acc-d:#e0552f;--acc-l:#fff1eb;--ink:#333;--sub:#777;--line:#e9e5e0;--bg:#f4f2ee;--card:#fff;--gold:#f1b41b;--red:#d3452c;--navy:#2b3450}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:70px}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans JP",-apple-system,"Hiragino Sans","Yu Gothic",Meiryo,sans-serif;font-size:16px;line-height:1.8;-webkit-font-smoothing:antialiased}
a{color:var(--acc-d)}img{display:block;max-width:100%;height:auto}
.wrap{max-width:1140px;margin:0 auto;padding:0 16px}
/* トップバー */
.topbar{background:var(--acc);color:#fff;font-size:12px}
.topbar .wrap{display:flex;justify-content:space-between;align-items:center;height:30px}
.topbar .sns{display:flex;gap:14px}.topbar a{color:#fff;display:inline-flex;align-items:center;gap:4px;text-decoration:none}
/* ヘッダー */
.hdr{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.hdr .wrap{display:flex;align-items:center;justify-content:space-between;height:62px;gap:16px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font-weight:700;font-size:19px;white-space:nowrap;flex-shrink:0}
.brand img{width:36px;height:36px;border-radius:50%}
.gnav{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0;justify-content:flex-end}.gnav::-webkit-scrollbar{display:none}
.gnav a{white-space:nowrap;font-size:13px;color:var(--ink);text-decoration:none;padding:8px 11px;border-radius:6px}.gnav a:hover{background:var(--acc-l);color:var(--acc-d)}
/* スライダー */
.slider{background:#fff;border-bottom:1px solid var(--line);padding:18px 0 14px}
.track{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding:0 16px 6px;scrollbar-width:none}.track::-webkit-scrollbar{display:none}
.slide{flex:0 0 360px;scroll-snap-align:start;text-decoration:none;color:var(--ink);position:relative}
.slide .thumb{border-radius:12px}.slide .cat{position:absolute;top:10px;left:10px}
.slide h3{font-size:15px;font-weight:700;margin:10px 4px 0;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.slide .date{font-size:12px;color:var(--sub);margin:2px 4px 0}
.dots{display:flex;justify-content:center;gap:6px;margin-top:8px}.dots span{width:7px;height:7px;border-radius:50%;background:#ddd}.dots span.on{background:var(--acc)}
/* サムネイル（商品画像4枚のコラージュ） */
.thumb{aspect-ratio:16/9;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:2px;overflow:hidden;background:#eee;border-radius:10px}
.thumb img{width:100%;height:100%;object-fit:cover}.thumb.one{grid-template-columns:1fr}
.cat{display:inline-block;background:var(--acc);color:#fff;font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;line-height:1.5}
.cat.gray{background:var(--navy)}
/* 2カラム */
.cols{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:28px;margin:28px auto 40px}
.main>section,.main>article{background:var(--card);border-radius:14px;padding:26px 24px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.side .box{background:var(--card);border-radius:14px;padding:20px;margin-bottom:22px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
h2.sec{display:flex;align-items:center;gap:8px;font-size:19px;margin:0 0 18px;padding-bottom:10px;border-bottom:2px solid var(--line);position:relative}
h2.sec::after{content:"";position:absolute;left:0;bottom:-2px;width:64px;height:2px;background:var(--acc)}
h2.sec svg{color:var(--acc)}
.side h3.sh{font-size:15px;margin:0 0 14px;padding:8px 12px;background:var(--acc);color:#fff;border-radius:6px;text-align:center}
/* 誰向けアイコン */
.who{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.who a{text-decoration:none;color:var(--ink);text-align:center;font-size:12px;font-weight:700;line-height:1.4}
.who .ic{width:58px;height:58px;margin:0 auto 8px;border-radius:50%;background:var(--acc);color:#fff;display:flex;align-items:center;justify-content:center;transition:transform .15s}
.who .ic svg{width:28px;height:28px}.who a:hover .ic{transform:translateY(-3px)}
/* 記事カード */
.cards{display:grid;grid-template-columns:1fr 1fr;gap:22px 18px}
.pcard{text-decoration:none;color:var(--ink);position:relative;display:block}
.pcard .cat{position:absolute;top:8px;right:8px}
.pcard h3{font-size:15px;font-weight:700;margin:10px 0 4px;line-height:1.55}.pcard:hover h3{color:var(--acc-d)}
.pcard .date{font-size:12px;color:var(--sub)}
.more{display:block;text-align:center;margin:22px auto 0;width:200px;border:1px solid var(--ink);border-radius:999px;padding:9px;text-decoration:none;color:var(--ink);font-size:14px;font-weight:700}.more:hover{background:var(--ink);color:#fff}
/* サイドバー部品 */
.search{display:flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}.search input{flex:1;border:0;padding:9px 12px;font-size:14px;outline:none}.search button{border:0;background:var(--acc);color:#fff;padding:0 14px;cursor:pointer;display:flex;align-items:center}
.prof{text-align:center}.prof img{width:96px;height:96px;border-radius:50%;margin:4px auto 10px}.prof b{display:block;font-size:16px}.prof p{font-size:13px;color:var(--sub);text-align:left;margin:10px 0 0;line-height:1.75}
.prof .sns{display:flex;justify-content:center;gap:10px;margin-top:12px}.prof .sns a{width:34px;height:34px;border-radius:50%;border:1px solid var(--line);display:inline-flex;align-items:center;justify-content:center;color:var(--ink)}
.rank{list-style:none;margin:0;padding:0}.rank li{display:grid;grid-template-columns:80px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);position:relative}.rank li:last-child{border-bottom:0}
.rank .im{position:relative}.rank .im img{width:80px;height:80px;object-fit:cover;border-radius:8px}.rank .im b{position:absolute;top:-6px;left:-6px;width:24px;height:24px;border-radius:50%;background:var(--acc);color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center}
.rank .im b.g1{background:var(--gold)}.rank .im b.g2{background:#9aa5b1}.rank .im b.g3{background:#c98a5a}
.rank a{text-decoration:none;color:var(--ink);font-size:13px;font-weight:700;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.rank small{display:block;color:var(--sub);font-size:12px;font-weight:400;margin-top:3px}
.cats{list-style:none;margin:0;padding:0}.cats li{border-bottom:1px solid var(--line)}.cats li:last-child{border-bottom:0}.cats a{display:flex;justify-content:space-between;padding:10px 4px;text-decoration:none;color:var(--ink);font-size:14px}.cats a:hover{color:var(--acc-d)}.cats span{color:var(--sub);font-size:12px}
.ev{list-style:none;margin:0;padding:0}.ev li{display:grid;grid-template-columns:56px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}.ev li:last-child{border-bottom:0}
.ev time{background:var(--acc-l);color:var(--acc-d);border-radius:6px;text-align:center;font-weight:700;font-size:12px;line-height:1.3;padding:5px 0;align-self:start}.ev small{display:block;color:var(--sub)}
/* 記事本文 */
.post h1{font-size:clamp(21px,3vw,27px);line-height:1.5;margin:8px 0 10px}
.meta{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;font-size:12px;color:var(--sub);margin-bottom:16px}
.eyecatch{margin:0 0 20px}.eyecatch .thumb{border-radius:12px}
.intro{font-size:15px;margin:0 0 18px}
.toc{background:#faf8f5;border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:0 0 26px}
.toc b{display:block;font-size:14px;margin-bottom:6px}.toc ol{margin:0;padding-left:22px;font-size:14px}.toc li{margin:4px 0}.toc a{color:var(--ink);text-decoration:none}.toc a:hover{color:var(--acc-d)}
h2.h{font-size:19px;margin:34px 0 14px;padding:10px 14px;background:var(--acc-l);border-left:5px solid var(--acc);border-radius:0 8px 8px 0}
.lead{font-size:14px;color:var(--sub);margin:-4px 0 16px}
/* 商品ボックス（独自） */
.item{border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px;display:grid;grid-template-columns:150px 1fr;gap:16px;position:relative;background:#fff}
.item .no{position:absolute;top:-10px;left:12px;background:var(--navy);color:#fff;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px}
.item .pic img{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:8px;border:1px solid var(--line)}
.item h3{font-size:16px;margin:4px 0 6px;line-height:1.5}.item h3 a{color:var(--ink);text-decoration:none}.item h3 a:hover{color:var(--acc-d)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}.badges span{font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;background:#f3f4f6;color:#444}
.badges .sale{background:var(--red);color:#fff}.badges .top{background:var(--gold);color:#4a3200}.badges .pt{background:var(--navy);color:#fff}.badges .dl{background:#fff;border:1px solid var(--red);color:var(--red)}
.stars{color:var(--gold);letter-spacing:1px;font-size:14px}.stars b{color:var(--ink);margin-left:4px}.stars small{color:var(--sub);margin-left:6px;font-weight:400}
.pr{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:6px 0}
.pr b{font-size:24px;color:var(--red)}.pr b small{font-size:13px}.pr .eff{font-size:13px;background:var(--acc-l);color:var(--acc-d);font-weight:700;padding:3px 10px;border-radius:6px}
.pr .shop{font-size:12px;color:var(--sub)}
.pt3{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:8px 0 10px}
.pt3 div{background:#faf8f5;border-radius:8px;padding:8px 6px;text-align:center;font-size:12px;color:var(--sub);line-height:1.4}.pt3 b{display:block;font-size:14px;color:var(--ink)}
.memo{font-size:13px;color:#555;margin:0 0 10px;padding-left:10px;border-left:3px solid var(--acc-l)}
.cta{display:flex;gap:8px;flex-wrap:wrap}
.btn{flex:1;min-width:150px;display:inline-flex;align-items:center;justify-content:center;gap:6px;background:var(--acc);color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:11px 14px;border-radius:8px;box-shadow:0 3px 0 var(--acc-d)}
.btn:hover{background:var(--acc-d);box-shadow:none;transform:translateY(2px)}
.btn.sub{background:#fff;color:var(--ink);border:1px solid var(--line);box-shadow:none;flex:0 0 auto}
.note{background:#faf8f5;border-radius:10px;padding:14px 18px;font-size:14px;margin:26px 0 0}
.pnav{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:26px 0 0}
.pnav a{border:1px solid var(--line);border-radius:10px;padding:12px 14px;text-decoration:none;color:var(--ink);font-size:13px;font-weight:700;line-height:1.5}.pnav a span{display:block;color:var(--sub);font-size:11px;font-weight:400}
.pnav a.n{text-align:right}
.crumb{font-size:12px;color:var(--sub);margin:16px 0 0}.crumb a{color:var(--sub);text-decoration:none}
.entries{list-style:none;margin:0;padding:0}.entries li{display:grid;grid-template-columns:150px 1fr;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}.entries li:last-child{border-bottom:0}
.entries .thumb{border-radius:8px}.entries a{text-decoration:none;color:var(--ink);font-weight:700;font-size:15px;line-height:1.55}.entries a:hover{color:var(--acc-d)}.entries small{display:block;color:var(--sub);font-size:12px;font-weight:400;margin-top:4px}
.prose h2{font-size:19px;margin:30px 0 12px;padding:10px 14px;background:var(--acc-l);border-left:5px solid var(--acc);border-radius:0 8px 8px 0}.prose p{margin:0 0 14px;font-size:15px}.prose ul{padding-left:22px;font-size:15px}.prose li{margin-bottom:6px}
footer{background:var(--navy);color:#c9cfdd;font-size:12px;padding:28px 0 32px;margin-top:20px}
footer .wrap{display:flex;flex-wrap:wrap;gap:10px 22px;justify-content:center}footer a{color:#fff;text-decoration:none}footer .copy{width:100%;text-align:center;margin-top:8px}
@media (max-width:900px){.cols{grid-template-columns:1fr;gap:20px;margin-top:18px}.who{grid-template-columns:repeat(3,1fr)}.slide{flex-basis:78vw}.gnav{justify-content:flex-start}.brand{font-size:17px}}
@media (max-width:600px){.cards{grid-template-columns:1fr 1fr;gap:16px 12px}.pcard h3{font-size:13px}.main>section,.main>article{padding:20px 14px}.item{grid-template-columns:110px 1fr;gap:12px;padding:14px 12px}.pt3{grid-template-columns:1fr 1fr 1fr;gap:4px}.pt3 div{font-size:11px}.pr b{font-size:21px}.entries li{grid-template-columns:120px 1fr}.pnav{grid-template-columns:1fr}.pnav a.n{text-align:left}.topbar .tag{display:none}}
"""

FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">')

SLIDER_JS = """<script>
(function(){var t=document.querySelector('.track');if(!t)return;var d=document.querySelectorAll('.dots span');var n=t.children.length;var i=0;
function go(k){i=(k+n)%n;t.scrollTo({left:t.children[i].offsetLeft-16,behavior:'smooth'});d.forEach(function(s,j){s.className=j===i?'on':''});}
var timer=setInterval(function(){go(i+1)},4500);t.addEventListener('pointerdown',function(){clearInterval(timer)});
t.addEventListener('scroll',function(){var k=Math.round(t.scrollLeft/(t.children[0].offsetWidth+16));if(k!==i){i=Math.min(k,n-1);d.forEach(function(s,j){s.className=j===i?'on':''});}});})();
</script>"""


# ---------------------------------------------------------------- 共通部品
def collage(imgs: list[str], alt: str, cls: str = "thumb") -> str:
    imgs = [i for i in imgs if i][:4]
    if not imgs:
        return f'<div class="{cls} one"><img src="../assets/og.png" alt="{esc(alt)}"></div>'
    if len(imgs) == 1:
        return f'<div class="{cls} one"><img loading="lazy" src="{esc(imgs[0])}" alt="{esc(alt)}"></div>'
    while len(imgs) < 4:
        imgs = imgs + imgs
    return f'<div class="{cls}">' + "".join(f'<img loading="lazy" src="{esc(u)}" alt="">' for u in imgs[:4]) + "</div>"


def deal_of(e: dict[str, Any]) -> dict[str, str]:
    class P:
        name = e["name"]; catchcopy = e.get("catchcopy", ""); price = e["price"]; point_rate = e.get("point_rate", 1)
    return extract_deal(P())  # type: ignore[arg-type]


def stars(avg: float) -> str:
    full = int(round(avg))
    return "★" * full + "☆" * (5 - full)


def _is_keyword_list(text: str) -> bool:
    """「牛丼 肉 業務用 時短 冷凍食品 …」のような検索用の単語列かどうか。"""
    toks = text.split(" ")
    return len(toks) >= 6 and sum(len(t) for t in toks) / len(toks) <= 5 and "。" not in text and "、" not in text


def memo_of(e: dict[str, Any]) -> str:
    """商品の「一言」。商品説明文から拾った特徴 → キャッチコピー（文章のものだけ）の順。"""
    from src.room_comment import _features
    feats = _features(e.get("caption", ""), e.get("name", ""), max_n=2)
    if feats:
        return "。".join(feats)[:80]
    cc = re.sub(r"[＼／\\/★☆【】\[\]｢｣「」]+", " ", e.get("catchcopy") or "")
    cc = re.sub(r"\s+", " ", cc).strip()
    if not cc or _is_keyword_list(cc) or cc.count(" ") >= 4 or any(w in cc for w in NG_WORDS + ["消える", "改善", "効く", "効果"]):
        return ""
    if re.search(r"(OFF|％|%|クーポン|ポイント|送料|円|まで|限定|SALE|セール|楽天|店|ショップ|大賞|受賞|No\.?1|1位|ランキング)", cc):
        return ""
    return cc[:70] if len(cc) >= 6 else ""


def item_box(e: dict[str, Any], n: int) -> str:
    """商品ボックス。写真 / バッジ / 星 / 価格と実質 / 3つの数字 / 一言 / ボタン。"""
    deal = deal_of(e)
    name = _short_name(e["name"], 36)
    url = esc(e.get("affiliate_url") or e["item_url"])
    pt = e.get("point_rate", 1)
    badges = []
    if deal.get("discount"):
        badges.append(f'<span class="sale">{esc(deal["discount"])}</span>')
    if deal.get("deadline"):
        badges.append(f'<span class="dl">{esc(deal["deadline"])}</span>')
    if deal.get("rank1"):
        badges.append('<span class="top">楽天ランキング1位</span>')
    if pt >= 2:
        badges.append(f'<span class="pt">ポイント{pt}倍</span>')
    if deal.get("ship"):
        badges.append("<span>送料無料</span>")
    eff = f'<span class="eff">実質 {int(e["price"] * (1 - pt / 100)):,}円</span>' if pt >= 2 else ""
    memo = memo_of(e)
    return f"""<div class="item" id="item{n}">
<span class="no">No.{n}</span>
<a class="pic" href="{url}" rel="nofollow sponsored noopener" target="_blank"><img loading="lazy" width="600" height="600" src="{esc(e.get('image_url', ''))}" alt="{esc(name)}"></a>
<div>
<h3><a href="{url}" rel="nofollow sponsored noopener" target="_blank">{esc(name)}</a></h3>
{f'<div class="badges">{"".join(badges)}</div>' if badges else ''}
<div class="stars">{stars(e['review_average'])}<b>{e['review_average']}</b><small>（{e['review_count']:,}件のレビュー）</small></div>
<p class="pr"><b>{e['price']:,}<small>円</small></b>{eff}<span class="shop">{esc(e['shop_name'])}</span></p>
<div class="pt3"><div>評価<b>{e['review_average']}</b></div><div>レビュー<b>{e['review_count']:,}件</b></div><div>ポイント<b>{pt}倍</b></div></div>
{f'<p class="memo">{esc(memo)}</p>' if memo else ''}
<div class="cta"><a class="btn" href="{url}" rel="nofollow sponsored noopener" target="_blank">楽天市場で見る</a><a class="btn sub" href="{esc(e['item_url'])}#itemReview" rel="nofollow noopener" target="_blank">レビューを読む</a></div>
</div></div>"""


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
            "logo": f"{base}assets/icon.png" if base else "assets/icon.png", "sameAs": [u for u in (X_URL, THREADS_URL, ROOM_URL) if u]}


def upcoming_events(n: int = 5) -> list[dict[str, str]]:
    try:
        cal = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    today = date.today()
    out = []
    for ev in cal.get("events", []):
        s = datetime.strptime(ev["start"], "%Y-%m-%d").date()
        e = datetime.strptime(ev["end"], "%Y-%m-%d").date()
        if e < today or s > today + timedelta(days=60):
            continue
        status = "開催中" if s <= today <= e else f"あと{(s - today).days}日"
        out.append({"name": re.sub(r"（.*?）", "", ev["name"]), "start": ev["start"], "end": ev["end"], "status": status, "type": ev.get("type", "")})
    out.sort(key=lambda x: x["start"])
    return out[:n]


# ---------------------------------------------------------------- レイアウト
def sidebar(rel: str, popular: list[dict[str, Any]], persona_counts: dict[str, int]) -> str:
    base = site_url()
    q = f"site:{base.replace('https://', '').rstrip('/')} " if base else ""
    ev_html = "".join(
        f'<li><time>{int(ev["start"][5:7])}/{int(ev["start"][8:10])}<br><span style="font-weight:400">{esc(ev["status"])}</span></time>'
        f'<div>{esc(ev["name"])}<small>{esc(short_date(ev["start"]))}〜{esc(short_date(ev["end"]))}</small></div></li>' for ev in upcoming_events())
    rank_html = "".join(
        f'<li><div class="im"><img loading="lazy" src="{esc(e.get("image_url", ""))}" alt=""><b class="g{i}">{i}</b></div>'
        f'<div><a href="{esc(e.get("affiliate_url") or e["item_url"])}" rel="nofollow sponsored noopener" target="_blank">{esc(_short_name(e["name"], 34))}</a>'
        f'<small>★{e["review_average"]}・{e["review_count"]:,}件　{e["price"]:,}円</small></div></li>' for i, e in enumerate(popular[:5], 1))
    cats = "".join(f'<li><a href="{rel}for/{k}.html">{esc(PERSONA_SHORT[k])}<span>{persona_counts.get(k, 0)}件</span></a></li>' for k in PERSONAS if k != "all")
    return f"""<aside class="side">
<div class="box"><form class="search" action="https://www.google.com/search" method="get" target="_blank"><input type="text" name="q" placeholder="{esc(q)}キーワード" aria-label="サイト内検索"><button type="submit" aria-label="検索">{ICONS['search']}</button></form></div>
<div class="box prof"><img src="{rel}assets/icon.png" alt="{esc(BRAND)}" width="96" height="96"><b>{esc(BRAND)}</b>
<p>楽天市場で「本当に売れていて、買った人の評価が高い物」だけを毎日3回選んでいます。<br>・レビュー50件以上、評価4.2以上だけ<br>・セール中は「実質いくらか」を計算<br>・割引や締切は商品名にある数字だけ転記</p>
<div class="sns"><a href="{esc(X_URL)}" aria-label="X">{ICONS['x']}</a><a href="{esc(THREADS_URL)}" aria-label="Threads">{ICONS['threads']}</a>{f'<a href="{esc(ROOM_URL)}" aria-label="楽天ROOM">{ICONS["room"]}</a>' if ROOM_URL else ''}<a href="{rel}feed.xml" aria-label="RSS">{ICONS['rss']}</a></div></div>
<div class="box"><h3 class="sh">人気商品 TOP5</h3><ol class="rank">{rank_html}</ol><a class="more" style="width:auto;margin-top:14px;font-size:13px;padding:7px" href="{rel}ranking.html">ランキングをすべて見る</a></div>
<div class="box"><h3 class="sh">近日のセール・行事</h3><ul class="ev">{ev_html or '<li>予定はありません</li>'}</ul></div>
<div class="box"><h3 class="sh">誰向けで探す</h3><ul class="cats">{cats}</ul></div>
</aside>"""


def layout(title: str, main_html: str, rel: str, desc: str, canonical: str | None, side_html: str,
           jsonld: list[dict] | None = None, og_type: str = "website", slider_html: str = "",
           og_image: str = "", extra_head: str = "") -> str:
    base = site_url()
    page_url = (base + canonical) if (base and canonical is not None) else ""
    can = f'<link rel="canonical" href="{esc(page_url)}">' if page_url else ""
    og_img = og_image or (f"{base}assets/og.png" if base else f"{rel}assets/og.png")
    og = (f'<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{esc(SITE_NAME)}">'
          f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">'
          f'<meta property="og:image" content="{esc(og_img)}"><meta property="og:locale" content="ja_JP">'
          + (f'<meta property="og:url" content="{esc(page_url)}">' if page_url else "")
          + '<meta name="twitter:card" content="summary_large_image">')
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    gsc = _env("GSC_VERIFICATION") or "iVy8LKuOONJ_5bkE3cqQXanhX1mp5nj-hfd78z7YnZ4"
    gsc_tag = f'<meta name="google-site-verification" content="{esc(gsc)}">' if gsc else ""
    # Pinterest のウェブサイト認証（HTMLタグ方式）。GitHub の Variables に PINTEREST_VERIFICATION を入れると全ページに入る
    pin = _env("PINTEREST_VERIFICATION") or "9da569e0e21ab8cecf88656524b65ba1"
    gsc_tag += f'<meta name="p:domain_verify" content="{esc(pin)}">' if pin else ""
    gnav = "".join(f'<a href="{rel}for/{k}.html">{esc(PERSONA_SHORT[k])}</a>' for k in PERSONAS if k != "all")
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
{can}{og}{gsc_tag}{extra_head}
<link rel="icon" href="{rel}assets/icon.png">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_NAME)}" href="{rel}feed.xml">
{FONT_LINK}
<style>{CSS}</style>
{ld}
</head>
<body>
<div class="topbar"><div class="wrap"><span class="tag">{esc(TAGLINE)}。レビュー50件以上・評価4.2以上だけ。</span>
<span class="sns"><a href="{esc(X_URL)}">{ICONS['x']}</a><a href="{esc(THREADS_URL)}">{ICONS['threads']}</a>{f'<a href="{esc(ROOM_URL)}">{ICONS["room"]}</a>' if ROOM_URL else ''}<a href="{rel}feed.xml">{ICONS['rss']}</a></span></div></div>
<header class="hdr"><div class="wrap"><a class="brand" href="{rel}index.html"><img src="{rel}assets/icon.png" alt="" width="36" height="36">{esc(BRAND)}</a>
<nav class="gnav" aria-label="カテゴリー">{gnav}<a href="{rel}ranking.html">ランキング</a><a href="{rel}posts/index.html">記事一覧</a></nav></div></header>
{slider_html}
<div class="wrap cols">
<div class="main">{main_html}</div>
{side_html}
</div>
<footer><div class="wrap"><a href="{rel}index.html">ホーム</a><a href="{rel}about.html">選び方と運営者情報</a><a href="{rel}privacy.html">プライバシーポリシー</a><a href="{rel}posts/index.html">記事一覧</a><a href="{rel}ranking.html">ランキング</a>
<div class="copy">当サイトは楽天アフィリエイトの広告を含みます（PR）。掲載情報は楽天市場の公開データに基づき、価格・ポイント倍率は掲載時点のものです。<br>© {datetime.now().year} {esc(BRAND)}</div></div></footer>
{SLIDER_JS if slider_html else ''}
</body>
</html>"""


# 導入文のバリエーション
INTROS = [
    "{date}時点で楽天市場のランキングに入っている商品のうち、レビュー50件以上・評価4.2以上のものだけを残しました。{n}点、価格は税込。ポイント倍率から「実質いくらか」も添えています。",
    "{date}の楽天市場で、実際に注文が動いている商品を{n}点選びました。基準はレビュー50件以上と評価4.2以上。セール中の物は締切とポイント倍率を確認して載せています。",
    "楽天のリアルタイムランキングと年代別ランキングを{date}に確認し、{n}点に絞りました。レビューが少ない商品や評価4.2未満の商品は外しています。",
]
SLOT_LEADS = {
    "morning": "朝に見られている商品。短時間で判断できる日用品や、その日のうちに締切があるセール品が中心です。",
    "noon": "昼休みに見られている商品。自分用のちょっとした買い物や便利グッズが多くなります。",
    "night": "楽天市場で最も注文が多い夜の時間帯の商品。単価がやや高いものや、じっくり比べたい商品もここに入ります。",
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
    persona_counts = {k: len(v) for k, v in by_persona.items()}
    popular = sorted(items, key=lambda x: -(x["review_average"] * (x["review_count"] ** 0.5)))

    DOCS.mkdir(exist_ok=True)
    for sub in ("posts", "for", "assets"):
        (DOCS / sub).mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    for src, dst in (("x_header_1500x500.png", "og.png"), ("x_icon_400.png", "icon.png")):
        if (ROOT / "assets" / src).exists():
            shutil.copy(ROOT / "assets" / src, DOCS / "assets" / dst)
    urls: list[tuple[str, str]] = []

    # ---- 日別記事のメタ ----
    days = sorted(by_day.keys(), reverse=True)
    meta: dict[str, dict[str, Any]] = {}
    for d in days:
        info = by_day[d]
        top = sorted(info["items"].values(), key=lambda x: -x.get("score", 0))[:ITEMS_PER_DAY]
        themes = [info["themes"][k] for k in ("morning", "noon", "night") if k in info["themes"]]
        events = list(dict.fromkeys(t["theme"].split(" × ")[0].split("（")[0] for t in themes))
        personas = list(dict.fromkeys(PERSONA_SHORT[t["persona"]] for t in themes if t["persona"] in PERSONAS))
        ev_txt = "・".join(events[:2]) if events else "楽天で今売れている物"
        title = f"{ev_txt}で買われている物{len(top)}選（{short_date(d)}）" + (f"｜{'・'.join(personas[:2])}向け" if personas else "")
        desc = (f"{jp_date(d)}に楽天市場で実際に売れている商品{len(top)}点。レビュー50件以上・評価4.2以上のものだけを選び、"
                f"ポイント倍率から実質価格を計算。" + "、".join(_short_name(x["name"], 14) for x in top[:3]) + " など。")
        meta[d] = {"title": title, "desc": desc, "top": top, "themes": themes, "cat": events[0] if events else "今売れている物",
                   "imgs": [x.get("image_url", "") for x in top[:4]]}

    def post_card(d: str) -> str:
        m = meta[d]
        return (f'<a class="pcard" href="posts/{d}.html">{collage(m["imgs"], m["title"])}<span class="cat">{esc(m["cat"])}</span>'
                f'<h3>{esc(m["title"])}</h3><span class="date">{esc(jp_date(d))}</span></a>')

    # ---- 日別記事 ----
    for i, d in enumerate(days):
        m = meta[d]
        top, themes = m["top"], m["themes"]
        cr, cr_ld = crumbs("../", [("posts/index.html", "記事一覧"), ("", short_date(d))])
        intro = INTROS[sum(map(int, d.split("-"))) % len(INTROS)].format(date=jp_date(d), n=len(top))
        # 目次
        toc = "".join(f'<li><a href="#sec{j}">{esc(SLOT_JA.get(t["slot"], ""))}の部：{esc(t["theme"].split(" × ")[0].split("（")[0])}（{esc(PERSONA_SHORT.get(t["persona"], ""))}向け）</a></li>' for j, t in enumerate(themes, 1))
        toc += '<li><a href="#howto">この記事の選び方</a></li>'
        body = (f'<article class="post">{cr}<div class="meta"><span class="cat">{esc(m["cat"])}</span><time datetime="{d}">{esc(jp_date(d))}</time><span>文・{esc(BRAND)}</span></div>'
                f'<h1>{esc(m["title"])}</h1><div class="eyecatch">{collage(m["imgs"], m["title"])}</div>'
                f'<p class="intro">{esc(intro)}</p><nav class="toc"><b>目次</b><ol>{toc}</ol></nav>')
        n = 0
        for j, t in enumerate(themes, 1):
            sub = [e for e in top if any(tt["date"] == d and tt["slot"] == t["slot"] for tt in e["themes"])][:8]
            if not sub:
                continue
            ev = t["theme"].split(" × ")[0].replace("）（", "・")
            body += f'<h2 class="h" id="sec{j}">{esc(SLOT_JA.get(t["slot"], ""))}の部　{esc(ev)}</h2><p class="lead">{esc(PERSONAS[t["persona"]].label if t["persona"] in PERSONAS else "")}向けに選んだ{len(sub)}点。{esc(SLOT_LEADS.get(t["slot"], ""))}</p>'
            for e in sub:
                n += 1
                body += item_box(e, n)
        body += ('<h2 class="h" id="howto">この記事の選び方</h2><div class="note">楽天市場のランキングとキーワード検索から候補を集め、レビュー件数・評価・ポイント倍率・価格帯で点数を付けて上位を掲載しています。'
                 '単価1,500円未満、レビュー50件未満、評価4.2未満、中古品は除外。割引率や締切は商品名・キャッチコピーに書かれているものだけを転記し、推測した数字は載せていません。'
                 '詳しくは<a href="../about.html">選び方と運営者情報</a>をご覧ください。</div>')
        prev_d = days[i + 1] if i + 1 < len(days) else None
        next_d = days[i - 1] if i > 0 else None
        body += '<nav class="pnav" aria-label="前後の記事">'
        body += (f'<a href="{prev_d}.html"><span>‹ 前の記事</span>{esc(meta[prev_d]["title"])}</a>' if prev_d else "<span></span>")
        body += (f'<a class="n" href="{next_d}.html"><span>次の記事 ›</span>{esc(meta[next_d]["title"])}</a>' if next_d else "")
        body += "</nav></article>"
        rel_personas = [k for k in dict.fromkeys(t["persona"] for t in themes) if k in PERSONAS]
        body += f'<section><h2 class="sec">{ICONS["tag"]}関連するまとめ</h2><ul class="cats">' + "".join(
            f'<li><a href="../for/{k}.html">{esc(PERSONA_SHORT[k])}に人気の楽天アイテム<span>{persona_counts.get(k, 0)}件</span></a></li>' for k in rel_personas
        ) + '<li><a href="../ranking.html">レビュー評価で選ぶ人気商品ランキング</a></li></ul></section>'
        article_ld = {"@context": "https://schema.org", "@type": "Article", "headline": m["title"][:110], "description": m["desc"],
                      "datePublished": f"{d}T21:00:00+09:00", "dateModified": f"{d}T21:00:00+09:00",
                      "author": {"@type": "Organization", "name": BRAND}, "publisher": org_ld(),
                      "image": [x for x in m["imgs"] if x][:3] or ([f"{base}assets/og.png"] if base else []),
                      "mainEntityOfPage": f"{base}posts/{d}.html" if base else f"posts/{d}.html"}
        first_img = next((x for x in m["imgs"] if x), "")
        # Pinterest リッチピン（記事）用のメタ情報
        rich = (f'<meta property="article:published_time" content="{d}T21:00:00+09:00">'
                f'<meta property="article:modified_time" content="{d}T21:00:00+09:00">'
                f'<meta property="article:author" content="{esc(BRAND)}"><meta property="article:section" content="楽天 おすすめ">')
        (DOCS / "posts" / f"{d}.html").write_text(
            layout(f"{m['title']}｜{BRAND}", body, "../", m["desc"], f"posts/{d}.html", sidebar("../", popular, persona_counts),
                   [article_ld, item_list_ld(top, m["title"]), cr_ld], "article", og_image=first_img, extra_head=rich), encoding="utf-8")
        urls.append((f"posts/{d}.html", d))

    # ---- 記事一覧 ----
    cr, cr_ld = crumbs("../", [("", "記事一覧")])
    body = (f'<section>{cr}<h2 class="sec" style="margin-top:14px">{ICONS["list"]}記事一覧</h2><ul class="entries">' + "".join(
        f'<li>{collage(meta[d]["imgs"], meta[d]["title"])}<div><a href="{d}.html">{esc(meta[d]["title"])}</a><small>{esc(jp_date(d))}　{esc(meta[d]["desc"][:60])}…</small></div></li>' for d in days) + "</ul></section>")
    (DOCS / "posts" / "index.html").write_text(layout(f"記事一覧｜{BRAND}", body, "../", "楽天で売れている物の日別まとめ記事の一覧。", "posts/index.html", sidebar("../", popular, persona_counts), [cr_ld]), encoding="utf-8")
    urls.append(("posts/index.html", today))

    # ---- 誰向け ----
    for key, persona in PERSONAS.items():
        if key == "all":
            continue
        pool = sorted(by_persona.get(key, {}).values(), key=lambda x: (x.get("last_seen", ""), x.get("score", 0)), reverse=True)[:30]
        title = f"{PERSONA_SHORT[key]}に人気の楽天アイテム{len(pool)}選"
        desc = f"{persona.label}向けに、楽天市場のランキングとレビューから選んだ商品を新しい順に。毎日更新。"
        gl = "・".join(GENRES.get(g, "") for g in persona.genres[:3])
        cr, cr_ld = crumbs("../", [("for/index.html", "誰向けで探す"), ("", PERSONA_SHORT[key])])
        body = (f'<article class="post">{cr}<div class="meta"><span class="cat gray">{esc(PERSONA_SHORT[key])}</span><time datetime="{today}">{esc(jp_date(today))}更新</time></div>'
                f'<h1>{esc(title)}</h1><div class="eyecatch">{collage([x.get("image_url", "") for x in pool[:4]], title)}</div>'
                f'<p class="intro">{esc(persona.label)}。よく見ているジャンルは{esc(gl)}。新しく掲載した順に並び、古いものは順に外れます。</p>')
        body += "".join(item_box(e, i + 1) for i, e in enumerate(pool)) if pool else "<p>まだ商品がありません。</p>"
        body += "</article>"
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": f"{base}for/{key}.html" if base else f"for/{key}.html", "dateModified": now_iso}, cr_ld]
        if pool:
            ld.append(item_list_ld(pool, title))
        (DOCS / "for" / f"{key}.html").write_text(layout(f"{title}｜{BRAND}", body, "../", desc, f"for/{key}.html", sidebar("../", popular, persona_counts), ld), encoding="utf-8")
        urls.append((f"for/{key}.html", today))

    cr, cr_ld = crumbs("../", [("", "誰向けで探す")])
    body = (f'<section>{cr}<h2 class="sec" style="margin-top:14px">{ICONS["tag"]}誰向けで探す</h2><p class="lead">同じ「売れている物」でも、誰が買っているかで中身は変わります。近い立場のページから見てください。</p><div class="cards">' + "".join(
        f'<a class="pcard" href="{k}.html">{collage([x.get("image_url", "") for x in sorted(by_persona.get(k, {}).values(), key=lambda x: -x.get("score", 0))[:4]], PERSONA_SHORT[k])}'
        f'<span class="cat gray">{persona_counts.get(k, 0)}件</span><h3>{esc(PERSONA_SHORT[k])}に人気の楽天アイテム</h3><span class="date">{esc(PERSONA_DESC[k])}</span></a>' for k in PERSONAS if k != "all") + "</div></section>")
    (DOCS / "for" / "index.html").write_text(layout(f"誰向けで探す｜{BRAND}", body, "../", "20代女性、30代女性、子育て世帯、20代・30代・40代男性。立場別の楽天おすすめまとめ。", "for/index.html", sidebar("../", popular, persona_counts), [cr_ld]), encoding="utf-8")
    urls.append(("for/index.html", today))

    # ---- ランキング ----
    ranked = popular[:50]
    title = "レビュー評価で選ぶ楽天の人気商品ランキング"
    desc = "これまで掲載した楽天市場の商品を、レビュー評価と件数の両方で並べたランキング。毎日更新。"
    cr, cr_ld = crumbs("", [("", "評価ランキング")])
    body = (f'<article class="post">{cr}<div class="meta"><span class="cat gray">ランキング</span><time datetime="{today}">{esc(jp_date(today))}更新</time></div><h1>{esc(title)}</h1>'
            f'<p class="intro">掲載した{len(items)}点を「評価 × レビュー件数の平方根」で並べています。件数だけだと定番品ばかり、評価だけだと件数の少ない商品が上に来るので、両方を掛けています。</p>'
            + "".join(item_box(e, i + 1) for i, e in enumerate(ranked)) + "</article>")
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": f"{base}ranking.html" if base else "ranking.html", "dateModified": now_iso},
          item_list_ld(ranked, title), cr_ld]
    (DOCS / "ranking.html").write_text(layout(f"{title}｜{BRAND}", body, "", desc, "ranking.html", sidebar("", popular, persona_counts), ld), encoding="utf-8")
    urls.append(("ranking.html", today))

    # ---- 運営者情報 / プライバシー ----
    cr, cr_ld = crumbs("", [("", "選び方と運営者情報")])
    body = f"""<article class="post prose">{cr}<h1>選び方と運営者情報</h1>
<p>{esc(BRAND)}は、楽天市場で「実際に売れていて、買った人の評価が高い物」だけを毎日3回選んで掲載しているサイトです。特定の店や商品を宣伝するためではなく、迷う時間を減らすために作っています。</p>
<h2>掲載の基準</h2>
<ul><li>楽天市場のリアルタイムランキング、年代・性別別ランキング、セール検索から候補を集めます。</li>
<li>レビュー50件以上、評価4.2以上の商品だけを残します。</li>
<li>単価1,500円未満、中古品、在庫切れの商品は除外します。</li>
<li>レビュー件数・評価・ポイント倍率・価格帯で点数を付け、上位を掲載します。同じ店の商品は1日2点までです。</li>
<li>割引率・締切・順位は、商品名やキャッチコピーに書かれている内容だけを転記します。こちらで推測した数字は載せません。</li></ul>
<h2>価格と「実質価格」について</h2>
<p>価格は掲載時点の税込表示です。「実質価格」は表示価格からポイント倍率相当を差し引いた目安で、ポイントの付与条件（会員ランク、エントリー、支払い方法）により実際の還元は変わります。購入前に必ず商品ページでご確認ください。</p>
<h2>広告について</h2>
<p>当サイトは楽天アフィリエイトに参加しています。商品リンクは広告リンクで、リンク経由で購入されると当サイトに報酬が支払われます。報酬の有無や料率は掲載順位に影響していますが、レビュー件数と評価の基準を満たさない商品は料率が高くても掲載しません。</p>
<h2>運営者</h2>
<p>{esc(BRAND)}（個人運営）。更新情報は<a href="{esc(X_URL)}">X</a>、<a href="{esc(THREADS_URL)}">Threads</a>{f'、<a href="{esc(ROOM_URL)}">楽天ROOM</a>' if ROOM_URL else ''}でも発信しています。掲載内容の誤りや削除のご依頼はXのダイレクトメッセージでお知らせください。</p></article>"""
    (DOCS / "about.html").write_text(layout(f"選び方と運営者情報｜{BRAND}", body, "", f"{BRAND}の掲載基準、価格表示の考え方、広告について、運営者情報。", "about.html", sidebar("", popular, persona_counts),
                                            [{"@context": "https://schema.org", "@type": "AboutPage", "name": "選び方と運営者情報", "url": f"{base}about.html" if base else "about.html"}, cr_ld]), encoding="utf-8")
    urls.append(("about.html", today))

    cr, cr_ld = crumbs("", [("", "プライバシーポリシー")])
    body = f"""<article class="post prose">{cr}<h1>プライバシーポリシー</h1>
<h2>広告の配信について</h2>
<p>当サイトは、楽天グループ株式会社が提供する「楽天アフィリエイト」を利用しています。商品リンクをクリックして楽天市場で購入が行われた場合、当サイトに成果報酬が支払われます。この仕組みのため、楽天側でクッキー（Cookie）が使用されることがあります。詳細は楽天の<a href="https://privacy.rakuten.co.jp/" rel="noopener" target="_blank">プライバシーポリシー</a>をご確認ください。</p>
<h2>アクセス解析について</h2><p>当サイトは現在、独自のアクセス解析ツールを設置していません。導入した場合は本ページで告知します。</p>
<h2>外部サービス</h2><p>当サイトはGitHub Pages上で公開され、Google Fontsを読み込んでいます。サイト内検索はGoogle検索に遷移します。各サービスの利用規約・プライバシーポリシーはそれぞれの提供元に従います。</p>
<h2>免責事項</h2><p>掲載している価格・ポイント倍率・在庫は掲載時点の情報で、変更されることがあります。当サイトの情報によって生じた損害について、運営者は責任を負いません。最終的な購入判断は各商品ページの最新情報でご確認ください。</p>
<p>制定日：2026年9月6日</p></article>"""
    (DOCS / "privacy.html").write_text(layout(f"プライバシーポリシー｜{BRAND}", body, "", f"{BRAND}のプライバシーポリシー。広告・クッキー・免責事項について。", "privacy.html", sidebar("", popular, persona_counts), [cr_ld]), encoding="utf-8")
    urls.append(("privacy.html", today))

    # ---- トップ ----
    slides = [f'<a class="slide" href="posts/{d}.html">{collage(meta[d]["imgs"], meta[d]["title"])}<span class="cat">{esc(meta[d]["cat"])}</span><h3>{esc(meta[d]["title"])}</h3><span class="date">{esc(jp_date(d))}</span></a>' for d in days[:3]]
    slides.append(f'<a class="slide" href="ranking.html">{collage([x.get("image_url", "") for x in popular[:4]], "ランキング")}<span class="cat gray">ランキング</span><h3>レビュー評価で選ぶ楽天の人気商品ランキング</h3><span class="date">毎日更新</span></a>')
    for k in ("30s_woman", "mama"):
        pool = sorted(by_persona.get(k, {}).values(), key=lambda x: -x.get("score", 0))[:4]
        if pool:
            slides.append(f'<a class="slide" href="for/{k}.html">{collage([x.get("image_url", "") for x in pool], PERSONA_SHORT[k])}<span class="cat gray">{esc(PERSONA_SHORT[k])}</span><h3>{esc(PERSONA_SHORT[k])}に人気の楽天アイテム</h3><span class="date">{esc(PERSONA_DESC[k])}</span></a>')
    slider = f'<div class="slider"><div class="track">{"".join(slides)}</div><div class="dots">' + "".join('<span class="on"></span>' if i == 0 else "<span></span>" for i in range(len(slides))) + "</div></div>"
    who = "".join(f'<a href="for/{k}.html"><span class="ic">{PERSONA_ICON.get(k, "")}</span>{esc(PERSONA_SHORT[k])}</a>' for k in PERSONAS if k != "all")
    body = (f'<section><h2 class="sec">{ICONS["tag"]}誰向けで探す</h2><div class="who">{who}</div></section>'
            f'<section><h2 class="sec">{ICONS["list"]}記事一覧</h2><div class="cards">' + "".join(post_card(d) for d in days[:8]) + f'</div><a class="more" href="posts/index.html">もっと見る</a></section>')
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": base or "/", "description": "楽天市場で本当に売れている物を毎日3回、レビューと評価で厳選。", "publisher": org_ld()}, org_ld()]
    (DOCS / "index.html").write_text(layout(SITE_NAME, body, "", "楽天市場で本当に売れている物を毎日3回、レビュー50件以上・評価4.2以上の商品だけ厳選。ポイント倍率から実質価格も計算。", "", sidebar("", popular, persona_counts), ld, "website", slider), encoding="utf-8")
    urls.append(("", today))

    # ---- 404 ----
    body = '<section><h2 class="sec">ページが見つかりません</h2><p>URLが変わったか、削除された可能性があります。<a href="/">トップページ</a>か<a href="/posts/index.html">記事一覧</a>からお探しください。</p></section>'
    (DOCS / "404.html").write_text(layout(f"ページが見つかりません｜{BRAND}", body, "/", "", None, sidebar("/", popular, persona_counts)), encoding="utf-8")

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
        n_cards = 0 if os.environ.get("SKIP_CARDS") else generate_cards(items)
        n_pins = write_pin_feeds(items, by_persona, base)
    else:
        (DOCS / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        n_pins = n_cards = 0

    print(f"生成完了: docs/  日別記事 {len(days)} 本、商品 {len(items)} 点、ページ {len(urls) + 1}、カード画像 {n_cards} 点、Pinterest用フィード {n_pins} 件、URL {base or '(SITE_URL 未設定)'}")


# ---------------------------------------------------------------- Pinterest 自動公開用 RSS
PIN_LEAD = {
    "20s_woman": "自分へのご褒美に", "30s_woman": "毎日の家事をラクに", "mama": "子育て中の家に",
    "20s_man": "一人暮らしに", "30s_man": "時短と効率化に", "40s_man": "家族みんなで", "all": "迷ったらこれ",
}


def _rfc822(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%a, %d %b %Y %H:%M:%S +0900")
    except Exception:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")


def _pin_image(url: str) -> str:
    """Rakuten のサムネイルURLから縮小指定を外し、大きい元画像を使う（ピンは大きい画像が有利）。"""
    return re.sub(r"\?_ex=\d+x\d+", "", url or "")


def _card_url(e: dict[str, Any], base: str) -> str:
    """生成済みの縦長カード画像（docs/pins/<code>.jpg）があればその公開URL。"""
    from src.pin_image import safe_name
    if (DOCS / "pins" / f"{safe_name(e['item_code'])}.jpg").exists():
        return f"{base}pins/{safe_name(e['item_code'])}.jpg"
    return ""


def card_hook(e: dict[str, Any]) -> str:
    """カードの見出し（人の言葉）。X投稿文の1行目があればそれ、無ければ行事・誰向けから作る。"""
    if e.get("posted_text"):
        first = e["posted_text"].splitlines()[0].replace("#PR", "").strip()
        if 6 <= len(first) <= 28:
            return first
    themes = e.get("themes") or []
    last = themes[-1] if themes else {}
    ev, et = _event_words(last)
    persona = last.get("persona", "all")
    who = PERSONA_SHORT.get(persona, "")
    if et == "gift" and ev:
        return f"{ev}、まだ決めてない人へ"
    if et == "sale" and ev:
        return f"{ev}で買っておきたい一品"
    if et == "season" and ev:
        return f"{ev}の準備、これから"
    return f"{who}が今買っているもの" if who else "レビュー件数が答えのやつ"


def generate_cards(items: list[dict[str, Any]], days: int = 7, cap: int = 150) -> int:
    """最近の商品について、Pinterest 用（2:3）と Instagram 用（4:5）のカード画像を生成する。"""
    from src.pin_image import make_cards
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    recent = sorted([e for e in items if e.get("image_url") and e.get("last_seen", "") >= cutoff],
                    key=lambda x: x.get("last_seen", ""), reverse=True)[:cap]
    made = 0
    for e in recent:
        prod = dict(e)
        prod["short_name"] = _short_name(e["name"], 36)
        prod["hook"] = card_hook(e)
        prod["memo"] = memo_of(e)
        try:
            pin, _ = make_cards(prod, DOCS / "pins", DOCS / "ig", BRAND, TAGLINE, deal_of(e), out_story=DOCS / "story")
            made += 1 if pin else 0
        except Exception as ex:
            print(f"  [warn] card {e['item_code']}: {ex}")
    return made


def _event_words(last: dict[str, Any]) -> tuple[str, str]:
    """直近テーマから (行事名, 種別) を返す。例: ('敬老の日', 'gift')"""
    ev = (last.get("theme") or "").split(" × ")[0].split("（")[0].strip()
    return ev, last.get("event_type", "baseline")


def pin_title(e: dict[str, Any], last: dict[str, Any]) -> str:
    """検索される言葉を先頭に置く（Pinterest は画像の検索エンジン）。"""
    name = _short_name(e["name"], 34)
    ev, et = _event_words(last)
    persona = last.get("persona", "all")
    if et == "gift" and ev:
        head = f"{ev}のギフトに"
    elif et == "sale" and ev:
        head = f"{ev}で買うなら"
    elif et == "season" and ev:
        head = ev
    else:
        head = f"{PERSONA_SHORT.get(persona, '')}に人気" if persona in PERSONA_SHORT else "楽天で人気"
    deal = deal_of(e)
    tail = deal.get("discount") or ("楽天ランキング1位" if deal.get("rank1") else "")
    return "｜".join(x for x in [head, name, tail] if x)[:100]


def pin_item(e: dict[str, Any], base: str) -> str:
    deal = deal_of(e)
    name = _short_name(e["name"], 40)
    themes = e.get("themes") or []
    last = themes[-1] if themes else {}
    persona = last.get("persona", "all")
    link = f"{base}posts/{last['date']}.html" if last.get("date") else f"{base}for/{persona}.html"
    title = pin_title(e, last)
    memo = memo_of(e)
    pt = e.get("point_rate", 1)
    deal_txt = "、".join(x for x in [
        deal.get("discount", "") + (f"（{deal['deadline']}）" if deal.get("deadline") and deal.get("discount") else ""),
        deal.get("deadline", "") if not deal.get("discount") else "",
        f"ポイント{pt}倍で実質{int(e['price'] * (1 - pt / 100)):,}円" if pt >= 2 else "",
        "送料無料" if deal.get("ship") else "",
    ] if x)
    ev, et = _event_words(last)
    who = PERSONAS[persona].label.split("（")[0] if persona in PERSONAS else "みんな"
    if et in ("gift", "sale", "season") and ev:
        first = f"{ev}に向けて、{who}の間で売れている{name}。"
    else:
        first = f"{who}に人気の{name}。{PIN_LEAD.get(persona, PIN_LEAD['all'])}。"
    desc = (first
            + (f"{memo} " if memo else "")
            + f"レビュー{e['review_count']:,}件で★{e['review_average']}。{e['price']:,}円"
            + (f"（{deal_txt}）" if deal_txt else "") + "。"
            + "楽天市場で本当に売れている物だけを、レビュー50件以上・評価4.2以上の基準で毎日まとめています。#楽天購入品 #楽天ROOM #PR")[:480]
    card = _card_url(e, base)
    img = card or _pin_image(e.get("image_url", ""))
    return (f"<item><title>{esc(title)}</title><link>{esc(link)}</link><guid isPermaLink=\"false\">{esc(e['item_code'])}</guid>"
            f"<description>{esc(desc)}</description><pubDate>{_rfc822(e.get('last_seen', ''))}</pubDate>"
            f"<enclosure url=\"{esc(img)}\" type=\"image/jpeg\" length=\"0\"/>"
            f"<media:content url=\"{esc(img)}\" medium=\"image\"/></item>")


def write_pin_feeds(items: list[dict[str, Any]], by_persona: dict[str, dict[str, Any]], base: str, limit: int = 60) -> int:
    """docs/pin/all.xml と docs/pin/<persona>.xml を出す。Pinterest の「RSSフィードから自動公開」に登録する。"""
    (DOCS / "pin").mkdir(exist_ok=True)
    head = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>'
            f"<title>{esc(SITE_NAME)}</title><link>{esc(base)}</link><language>ja</language>"
            "<description>楽天で本当に売れている物。レビュー50件以上・評価4.2以上だけ。</description>")
    tail = "</channel></rss>"
    total = 0

    def newest(lst):
        return sorted([e for e in lst if e.get("image_url")], key=lambda x: x.get("last_seen", ""), reverse=True)[:limit]

    all_items = newest(items)
    (DOCS / "pin" / "all.xml").write_text(head + "".join(pin_item(e, base) for e in all_items) + tail, encoding="utf-8")
    total += len(all_items)
    for key in PERSONAS:
        if key == "all":
            continue
        lst = newest(by_persona.get(key, {}).values())
        (DOCS / "pin" / f"{key}.xml").write_text(head + "".join(pin_item(e, base) for e in lst) + tail, encoding="utf-8")
    return total


if __name__ == "__main__":
    build()

"""楽天ROOM 向けの商品選定。

X向けの選定（1回1点、話題性重視）とは基準を変える。ROOMで買う人は
  ・30〜40代女性が中心。食品・日用品・子ども用品・キッチン・コスメ・インテリアが動く
  ・買い回り（お買い物マラソン）中は 1,000〜3,000円の送料無料品を「店舗数稼ぎ」で買う
  ・セール開始日（20時）と 5と0のつく日 に購買が集中する
  ・1万円超の商品は動きにくい
ROOMのランクS/Aは「投稿から楽天市場へ誘導した人数」で決まるので、点数を出すことが報酬率にも効く。
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Any

from .config import Settings
from .rakuten_client import Product
from .selector import already_posted, name_key, posted_keys
from .trend_engine import Theme
from .writer import extract_deal

# ROOMで動きやすいジャンル（トップジャンルID → 加点）
ROOM_GENRE_BOOST = {
    100227: 2.0,   # 食品
    551167: 1.5,   # スイーツ
    100533: 2.0,   # キッズ・ベビー
    215783: 1.5,   # 日用品
    558944: 1.5,   # キッチン
    100804: 1.2,   # インテリア
    100939: 1.5,   # コスメ
    216131: 1.0,   # バッグ・小物
    101213: 1.0,   # ペット
    100371: 0.8,   # レディース
    566382: 0.8,   # おもちゃ
    562637: 0.5,   # 家電
}
# 商品名に含まれるとROOMで動きやすい語
ROOM_WORDS = ["送料無料", "訳あり", "まとめ買い", "大容量", "詰め合わせ", "セット", "お試し", "ギフト", "名入れ",
              "おむつ", "米", "kg", "洗剤", "トイレットペーパー", "水", "炭酸水", "コーヒー", "冷凍", "レトルト",
              "収納", "時短", "韓国", "プチプラ", "ランキング1位"]


def room_score(p: Product, theme: Theme, today: date) -> float:
    sc = p.score * 0.6  # X向けスコアは6割の重みで引き継ぐ
    # 価格帯: ROOMは 1,000〜5,000円が主戦場
    if 1000 <= p.price <= 3000:
        sc += 2.0
    elif 3000 < p.price <= 6000:
        sc += 1.2
    elif p.price > 10000:
        sc -= 1.5
    # 買い回り中は 1,000〜2,000円の送料無料が最も動く
    ev = theme.title
    if theme.event_type == "sale" and "マラソン" in ev and 1000 <= p.price <= 2000 and "送料無料" in p.name:
        sc += 2.5
    # お得の根拠
    deal = extract_deal(p)
    if deal.get("discount"):
        sc += 1.2
    if deal.get("deadline"):
        sc += 0.8
    if deal.get("ship"):
        sc += 0.8
    sc += min(p.point_rate, 10) * 0.2
    sc += min(p.affiliate_rate, 10) * 0.3
    # ジャンル（取得経路のランキングジャンルから判定）
    for src in p.source.split("|"):
        m = re.match(r"ranking:(\d+):", src)
        if m:
            sc += ROOM_GENRE_BOOST.get(int(m.group(1)), 0.0)
            break
    sc += sum(0.4 for w in ROOM_WORDS if w in p.name)
    # ギフト行事中はギフト表記を強く
    if theme.event_type == "gift" and any(w in p.name for w in ("ギフト", "プレゼント", "名入れ", "のし")):
        sc += 2.0
    # 5と0のつく日はカード払いで倍率が上がるので、単価が少し高くても動く
    if today.day in (5, 10, 15, 20, 25, 30) and 3000 <= p.price <= 8000:
        sc += 0.6
    return sc


def room_pick_count(theme: Theme, s: Settings, today: date, presale: bool = False) -> int:
    n = s.room_picks_per_run
    if presale:
        return max(n * 2, 8)
    if theme.event_type == "sale":
        n = int(n * 1.5)
    if today.day in (5, 10, 15, 20, 25, 30):
        n += 1
    return n


def pick_for_room(cands: list[Product], theme: Theme, s: Settings, history: list[dict[str, Any]],
                  posted: list[Product], today: date | None = None, presale: bool = False) -> list[Product]:
    """ROOM に送る商品を選ぶ。X に投稿した商品を先頭に、残りを ROOM 基準で埋める。"""
    today = today or date.today()
    n = room_pick_count(theme, s, today, presale)
    posted_before = posted_keys(history)  # 一度でも ROOM・SNS に出した商品は二度と出さない
    out: list[Product] = []
    seen: set[str] = set()
    for p in posted:
        if p.item_code not in seen:
            out.append(p)
            seen.add(p.item_code)
    scored = []
    for p in cands:
        if p.item_code in seen or already_posted(p, posted_before) or name_key(p.name) in {name_key(x.name) for x in out}:
            continue
        scored.append((room_score(p, theme, today), p))
    scored.sort(key=lambda x: -x[0])
    shops: dict[str, int] = {}
    for p in out:
        shops[p.shop_name] = shops.get(p.shop_name, 0) + 1
    for sc, p in scored:
        if len(out) >= n:
            break
        if shops.get(p.shop_name, 0) >= 2:
            continue
        shops[p.shop_name] = shops.get(p.shop_name, 0) + 1
        out.append(p)
        seen.add(p.item_code)
    return out


def room_settings(s: Settings) -> Settings:
    """ROOM 用に候補の網を広げた設定（1,000円台と、レビュー30件以上まで拾う）。"""
    return replace(s, min_price=min(s.min_price, 1000), min_review_count=min(s.min_review_count, 30))

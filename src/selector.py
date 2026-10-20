"""テーマに沿って楽天から商品候補を集め、スコアリングして絞る。"""
from __future__ import annotations

import math
import re
from typing import Any

from .config import Settings
from .rakuten_client import Product, RakutenClient
from .trend_engine import Theme


def name_key(name: str) -> str:
    """同じ商品かどうかを見分けるための商品名の要約。宣伝文句（【】や＼／、★…★）と記号を落とした先頭16文字。
    店やサイズ違いで商品コードが変わっても、同じ商品なら同じ値になる。"""
    n = re.sub(r"【.*?】|\[.*?\]|［.*?］|＼.*?／|★.*?★|<.*?>|＜.*?＞|《.*?》|≪.*?≫", "", name)
    n = re.sub(r"[\s　!-/:-@\[-`{-~、。・！？＼／★☆♪％]+", "", n)
    return n[:16]


def posted_keys(history: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """これまでに SNS・ROOM リストに出した商品（期間の制限なし）。(商品コード, 商品名の要約)"""
    codes, names = set(), set()
    for h in history:
        if h.get("item_code"):
            codes.add(h["item_code"])
            if len(name_key(h.get("item_name", ""))) >= 8:
                names.add(name_key(h["item_name"]))
    return codes, names


def already_posted(p: Product, keys: tuple[set[str], set[str]]) -> bool:
    codes, names = keys
    return p.item_code in codes or name_key(p.name) in names


def _bad_name(name: str) -> bool:
    ng = ["中古", "ジャンク", "アダルト", "R18", "受付終了"]
    return any(x in name for x in ng)


def score_product(p: Product, theme: Theme, s: Settings) -> float:
    if p.price <= 0:
        return -1
    sc = 0.0
    sc += math.log10(p.review_count + 1) * 1.5            # 売れている実績
    sc += (p.review_average - 4.0) * 3.0                   # 満足度
    sc += min(p.affiliate_rate, 10) * 0.6                  # 料率（8%なら+4.8）
    sc += min(p.point_rate, 10) * 0.25                     # ポイント倍率＝お得感
    if p.rank:
        sc += max(0.0, (31 - p.rank) / 10)                 # ランキング上位ボーナス
    # 価格の当たりゾーン。安すぎると報酬が小さく、高すぎるとXでは決まらない
    if 3000 <= p.price <= 10000:
        sc += 1.5
    elif 2000 <= p.price < 3000 or 10000 < p.price <= 15000:
        sc += 0.7
    if theme.event_type == "sale" and p.point_rate >= 3:
        sc += 1.0
    if theme.event_type == "gift" and ("ギフト" in p.name or "プレゼント" in p.name or "名入れ" in p.name):
        sc += 1.0
    if p.source.startswith("ranking") and ":rt" in p.source:
        sc += 0.8                                          # リアルタイムで動いている
    # 「誰向け」との一致。ペルソナのランキングやテーマのジャンルから来た物を優先し、
    # 総合ランキング由来（誰向けでもない物）は少し下げる
    persona = theme.persona
    sources = p.source.split("|")
    in_genre = any(s.startswith(f"ranking:{g}:") for g in theme.genres for s in sources)
    in_search = any(s.startswith("search:") for s in sources)
    if persona.age is not None and persona.sex is not None:
        tag = f":{persona.age}{'f' if persona.sex else 'm'}"
        in_persona = any(tag in s for s in sources)
        if in_persona:
            sc += 3.0
        if not in_persona and not in_genre and not in_search:
            sc -= 3.0                                      # 総合ランキングにしか出ていない＝誰向けでもない
    if in_genre:
        sc += 4.0                                          # テーマのジャンルで売れている
    if in_search and theme.event_type in ("sale", "gift"):
        sc += 1.5                                          # イベントの検索語で見つかった
    if len(p.name) > 120:
        sc -= 0.5                                          # 商品名が長すぎる店はSEO詰め込み系
    return sc


def gather_candidates(client, theme: Theme, s: Settings,
                      history: list[dict[str, Any]], limit: int = 15) -> list[Product]:
    persona = theme.persona
    pool: dict[str, Product] = {}

    def add(items: list[Product]):
        for p in items:
            if not p.item_code:
                continue
            if p.item_code in pool:
                # 複数のランキングに出ている商品は、出所を全部記録する（スコアで加点される）
                q = pool[p.item_code]
                q.source = f"{q.source}|{p.source}"
                if p.rank and (q.rank is None or p.rank < q.rank):
                    q.rank = p.rank
            else:
                pool[p.item_code] = p

    # 1) 総合リアルタイムランキング（今この瞬間に動いている物）
    try:
        add(client.ranking(None, realtime=True))
    except Exception as e:  # ランキングが取れなくても続行
        print(f"  [warn] realtime ranking: {e}")

    # 2) ペルソナ（年代×性別）のデイリーランキング
    if persona.age is not None and persona.sex is not None:
        try:
            add(client.ranking(None, persona.age, persona.sex))
        except Exception as e:
            print(f"  [warn] persona ranking: {e}")

    # 3) テーマのジャンル別ランキング（先頭ジャンルはリアルタイムも見る）
    for i, g in enumerate(theme.genres[:3]):
        try:
            add(client.ranking(g))
            if i == 0:
                add(client.ranking(g, realtime=True))
        except Exception as e:
            print(f"  [warn] ranking genre {g}: {e}")

    # 4) イベントのキーワード検索（レビュー数順、価格帯で絞る）
    for kw in theme.keywords[:3]:
        try:
            add(client.search(kw, None, s.min_price, s.max_price, sort="-reviewCount", hits=30))
        except Exception as e:
            print(f"  [warn] search {kw}: {e}")

    # 一度でも出した商品は二度と出さない（同じ商品の別ショップ・別サイズも商品名で弾く）
    posted = posted_keys(history)
    out = []
    for p in pool.values():
        if already_posted(p, posted) or _bad_name(p.name):
            continue
        if not (s.min_price <= p.price <= s.max_price):
            continue
        if p.review_count < s.min_review_count or p.review_average < s.min_review_average:
            continue
        p.score = score_product(p, theme, s)
        out.append(p)
    out.sort(key=lambda x: -x.score)

    # 同じショップばかりにならないよう1ショップ2件まで
    seen_shop: dict[str, int] = {}
    seen_name: set[str] = set()
    final = []
    for p in out:
        n = seen_shop.get(p.shop_name, 0)
        if n >= 2 or name_key(p.name) in seen_name:
            continue
        seen_shop[p.shop_name] = n + 1
        seen_name.add(name_key(p.name))
        final.append(p)
        if len(final) >= limit:
            break
    return final

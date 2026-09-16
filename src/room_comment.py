"""楽天ROOM の「コレ！」に付けるコメントを作る。

ROOMで買われるコメントの型（売れているROOMの共通点）:
  1. 誰向けか、どんな場面で使うか（1文）
  2. 商品の具体的な特徴（商品説明文から拾う。効果効能の断定はしない）
  3. 数字の裏付け（レビュー件数・評価）
  4. お得情報（割引・締切・ポイント倍率・送料無料。商品名にある事実だけ）
  5. ROOM内検索で引っかかる語（ギフト・時短・まとめ買い など）を自然に含める
全体で 120〜220 文字。宣伝口調ではなく、友人に教える口調。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .config import PERSONAS
from .rakuten_client import Product
from .trend_engine import Theme
from .writer import NG_WORDS, _short_name, extract_deal

PROMO = re.compile(r"(送料|クーポン|ポイント|円|％|%|OFF|off|楽天|店|ショップ|レビュー|ランキング|期間|限定|発送|配送|注意|※|ご了承|お届け|在庫|注文|購入|セール|SALE|お買い物|キャンペーン|エントリー|http|＼|／)")
EFFECT = re.compile(r"(治|痩せ|効果|効く|改善|消える|予防|殺菌|除菌率|医療|完治|美白|若返)")
# 保管方法・免責・仕様表などの定型文（コメントに載せても買う理由にならない）
BOILER = re.compile(r"(保管|保存方法|直射日光|高温多湿|冷蔵|冷凍庫|解凍|賞味期限|消費期限|原材料|製造|販売者|内容量|栄養成分|アレルギー|ください|下さい|お願い|場合|可能性|返品|交換|同梱|ラッピング|メーカー|生産国|原産|サイズ表|規格|型番|JAN|対応機種|仕様|説明書|付属品|開封|使用上|使用前|使用後|お読み|了承)")
# 「買う理由」になりやすい語
CUES = ["ふっくら", "使い勝手", "皮ごと", "洗える", "軽い", "軽量", "大容量", "便利", "簡単", "選べる", "個包装", "無添加", "国産", "たっぷり",
        "ちょうどいい", "手軽", "そのまま", "時短", "丸洗い", "コンパクト", "静音", "省エネ", "肌", "やわらか", "ふわふわ", "もこもこ",
        "しっとり", "サクサク", "とろける", "厚み", "骨なし", "骨取り", "小分け", "食べやすい", "使いやすい", "持ちやすい", "収納",
        "折りたたみ", "調整", "サイズ", "カラー", "かわいい", "おしゃれ", "シンプル", "名入れ", "ギフト", "プレゼント", "喜ば"]

LEAD: dict[str, list[str]] = {
    "20s_woman": ["自分へのご褒美にちょうどいい価格。", "プチプラで探してる人に。", "SNSで見かけて気になってたやつ。"],
    "30s_woman": ["毎日の家事がちょっとラクになるやつ。", "忙しい平日の味方。", "買い置きしておくと安心なもの。"],
    "mama": ["子どもがいる家で助かった系。", "ママ友の間でよく話題になるやつ。", "まとめ買いしておくと楽になるもの。"],
    "20s_man": ["一人暮らしの部屋に1つあると便利。", "コスパで選ぶならこれ。", "レビューを見て買う人が多いやつ。"],
    "30s_man": ["毎日使うものほど良い物を、の代表。", "時短になる系。", "スペック比較して残ったやつ。"],
    "40s_man": ["家族みんなで使える定番。", "週末のお楽しみ用に。", "まとめ買い向き。"],
    "all": ["レビュー件数が答え、のタイプ。", "セールのたびに売れてる定番。", "迷ったらこれ、と言われがちなやつ。"],
}
CLOSERS = ["セール中に補充しておくと安心です。", "気になる人はお気に入り登録を。", "在庫が動きやすいので早めに。", "配送日も一緒に確認を。"]


def _features(caption: str, name: str, max_n: int = 2) -> list[str]:
    """商品説明文から、短く具体的な特徴を拾う。"""
    if not caption:
        return []
    text = re.sub(r"<[^>]+>", " ", caption)
    text = re.sub(r"[【】\[\]「」『』★☆■□●○◆◇▼▲◎♪＊*■]", " ", text)
    parts = re.split(r"[。\n\r！!？?]", text)
    scored: list[tuple[int, int, str]] = []
    for idx, part in enumerate(parts):
        p = re.sub(r"\s+", " ", part).strip(" 　・,、:：-－")
        if not (8 <= len(p) <= 42):
            continue
        if PROMO.search(p) or EFFECT.search(p) or BOILER.search(p) or any(w in p for w in NG_WORDS):
            continue
        if re.search(r"\d{2,}", p) and not re.search(r"(cm|mm|ml|g|kg|枚|個|本|袋|人|年|畳|色|種|切|尾|玉)", p):
            continue  # 意味の分からない数字列は避ける
        cue = sum(1 for c in CUES if c in p)
        if cue == 0 and idx > 6:
            continue  # 手がかり語が無い後半の文は仕様書の可能性が高い
        scored.append((-cue, idx, p))
    scored.sort()
    out: list[str] = []
    for _, _, p in scored:
        if p not in out:
            out.append(p)
        if len(out) >= max_n:
            break
    return out


def room_comment(p: Product, theme: Theme, today: date | None = None, presale: bool = False) -> str:
    today = today or date.today()
    seed = sum(ord(c) for c in p.item_code)
    persona = theme.persona
    deal = extract_deal(p)
    name = _short_name(p.name, 24)

    lead = LEAD.get(persona.key, LEAD["all"])[seed % 3]
    feats = _features(p.caption, p.name)
    feat_txt = ""
    if feats:
        feat_txt = "。".join(feats) + "。"
    elif p.catchcopy and 6 <= len(p.catchcopy) <= 40 and not PROMO.search(p.catchcopy) and not EFFECT.search(p.catchcopy):
        feat_txt = p.catchcopy.strip() + "。"

    proof = f"レビュー{p.review_count:,}件で★{p.review_average}。"
    if deal.get("rank1"):
        proof = f"楽天ランキング1位、{proof}"

    deals = []
    if deal.get("discount"):
        deals.append(deal["discount"] + (f"（{deal['deadline']}）" if deal.get("deadline") else ""))
    elif deal.get("deadline"):
        deals.append(deal["deadline"])
    if p.point_rate >= 2:
        deals.append(f"ポイント{p.point_rate}倍で実質{int(p.price * (1 - p.point_rate / 100)):,}円")
    if deal.get("ship") and "送料無料" not in " ".join(deals):
        deals.append("送料無料")
    deal_txt = "、".join(deals) + "。" if deals else f"{p.price:,}円。"

    # presale は "" / "start"（セール開始日） / "last"（最終日） / "five"（5と0のつく日） / True（手動）
    if presale == "start" or presale is True:
        head = "今夜20時スタート。開始直後に売り切れやすいので、先にお気に入りへ。"
    elif presale == "last":
        head = "セール今日まで。買い忘れがないか最終チェック。"
    elif presale == "five" or today.day in (5, 10, 15, 20, 25, 30):
        head = "今日は5と0のつく日。楽天カード払いでポイント4倍（エントリー必須）。"
    elif theme.event_type == "sale":
        head = theme.title.split(" × ")[0].split("（")[0] + "中に狙いたい1つ。"
    elif theme.event_type == "gift":
        head = theme.title.split(" × ")[0].split("（")[0] + "のプレゼント候補。"
    else:
        head = ""

    closer = CLOSERS[seed % len(CLOSERS)] if theme.event_type == "sale" or presale else ""
    text = " ".join(x for x in [head, lead, feat_txt, proof, deal_txt, closer] if x).strip()
    text = re.sub(r"\s+", "", text)  # ROOMは改行なしの1段落が読みやすい
    for w in NG_WORDS:
        text = text.replace(w, "")
    return text[:230]


def collection_suggestions(picks: list[tuple[Product, str]], theme: Theme) -> dict[str, list[str]]:
    """コレクション（まとめ）の案。ROOM内の回遊とついで買いを増やす。"""
    label = PERSONAS[theme.persona.key].label.split("（")[0] if theme.persona.key in PERSONAS else "みんな"
    ev = theme.title.split(" × ")[0].split("（")[0]
    out: dict[str, list[str]] = {}
    names = [_short_name(p.name, 22) for p, _ in picks]
    if theme.event_type in ("sale", "gift"):
        out[f"{ev}で買うもの"] = names
    out[f"{label}のリピート候補"] = names
    return out

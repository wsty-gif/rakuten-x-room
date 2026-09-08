"""投稿文の生成。Claude API があれば商品選定＋文章をClaudeに任せ、無ければテンプレート。

ルール（Xの規約・ステマ規制・楽天アフィリエイト規約に合わせる）
  - 先頭に #PR を必ず入れる（広告であることの明示）
  - 本文にURLを入れない（URL付き投稿はAPI料金が約13倍、かつ表示が抑制される）
  - 誘導は「ROOMはプロフから」に統一
  - 効果・効能の断定（治る、痩せる、シミが消える 等）は書かない（薬機法）
  - 「最安」「絶対」など根拠のない断定は書かない（景表法）
  - 全角換算140文字以内（Xは全角1文字=2ユニット、上限280ユニット）

購買意欲を動かす構成（テンプレート版・Claude版ともに同じ骨格）
  1行目  フック：誰向けか＋損失回避（「知らないと損」「今日が一番安い」）
  2行目  商品名（短く）＋一言のベネフィット
  3行目  社会的証明：レビュー件数・評価・ランキング
  4行目  お得の数字：割引・締切・ポイント倍率で実質いくらか
  5行目  ハッシュタグ
  6行目  CTA
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from .config import Settings
from .rakuten_client import Product
from .trend_engine import Theme

X_LIMIT_UNITS = 280
CTA = "▶ROOMはプロフから"
NG_WORDS = ["治る", "治す", "痩せる", "完治", "シミが消える", "必ず", "絶対", "100%", "医師推奨", "最安"]


def weighted_len(text: str) -> int:
    """Xの文字数カウント近似。全角・絵文字=2、半角=1。"""
    n = 0
    for ch in text:
        o = ord(ch)
        if o < 0x1100 or 0xFF61 <= o <= 0xFF9F:  # ASCII・ラテン・半角カナ
            n += 1
        else:
            n += 2
    return n


def _short_name(name: str, max_chars: int = 22) -> str:
    """楽天の長い商品名から、人が呼ぶ短い名前を作る。"""
    s = re.sub(r"[【\[［〈《（(][^】\]］〉》）)]*[】\]］〉》）)]", " ", name)   # 【送料無料】〈無塩〉などを除去
    s = re.sub(r"[＼／\\/|｜★☆◆◇■□●○▲▼→⇒※♪]+", " ", s)
    s = re.sub(r"\d{1,2}[/／]\d{1,2}[^ ]*", " ", s)                      # 日付・期限
    s = re.sub(r"\S*(OFF|off|％|%|円|倍|P|クーポン|送料無料|限定|セール|SALE|ポイント)\S*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = [p for p in s.split(" ") if len(p) >= 2]
    out = ""
    for p in parts:
        if len(out) + len(p) + 1 > max_chars:
            break
        out = (out + " " + p).strip()
    return out or name[:max_chars]


def extract_deal(p: Product) -> dict[str, str]:
    """商品名・キャッチコピーから「お得の根拠」を取り出す。無い物は作らない（景表法）。"""
    src = f"{p.name} {p.catchcopy}"
    d: dict[str, str] = {}
    m = re.search(r"(\d{2})\s*[%％]\s*(OFF|off|オフ|引)", src)
    if m:
        d["discount"] = f"{m.group(1)}%OFF"
    elif "半額" in src:
        d["discount"] = "半額"
    m = re.search(r"(\d{1,2})[/／](\d{1,2})[^\d]{0,4}?(\d{1,2}:\d{2})?\s*(まで|迄)", src)
    if m:
        d["deadline"] = f"{m.group(1)}/{m.group(2)}" + (f" {m.group(3)}" if m.group(3) else "") + "まで"
    else:
        m = re.search(r"(\d{1,2})日\s*(正午|\d{1,2}時)?\s*(まで|迄)", src)
        if m:
            d["deadline"] = f"{m.group(1)}日{m.group(2) or ''}まで"
    if re.search(r"(総合|楽天|ランキング)\s*1位", src) or "1位" in p.catchcopy:
        d["rank1"] = "楽天ランキング1位"
    if "送料無料" in src:
        d["ship"] = "送料無料"
    if p.point_rate >= 2:
        eff = int(p.price * (1 - p.point_rate / 100))
        d["points"] = f"P{p.point_rate}倍で実質{eff:,}円"
    return d


def sanitize(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)           # URLは絶対に入れない
    for w in NG_WORDS:
        text = text.replace(w, "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text.startswith("#PR"):
        text = "#PR " + text
    if CTA not in text:
        text = text.rstrip() + "\n" + CTA
    # 長すぎたら本文の中ほどを削る
    guard = 0
    while weighted_len(text) > X_LIMIT_UNITS and guard < 200:
        guard += 1
        lines = text.split("\n")
        inner = [i for i in range(1, len(lines) - 1) if len(lines[i]) >= 4 and not lines[i].startswith("#")]
        if not inner:
            text = text[: max(10, len(text) - 4)]
            continue
        idx = max(inner, key=lambda i: weighted_len(lines[i]))
        lines[idx] = lines[idx][:-3].rstrip() + "…"
        text = "\n".join(lines)
    return text


# ---------- テンプレート版 ----------
# 1行目のフック。「誰向け」ごとに、損失回避・共感・即決の3系統を用意しローテーション
PERSONA_HOOKS: dict[str, list[str]] = {
    "20s_woman": ["これ知らないの、正直もったいない", "プチプラで一番後悔しなかったやつ", "友達に聞かれて毎回これ答えてる"],
    "30s_woman": ["家事、あと10分短くしたい人へ", "毎日の小さなストレス、これで消えます", "買い替えるなら今日が一番安い"],
    "mama": ["子どもがいる家、結局これでした", "ママ友の間で回ってるやつ", "買ってすぐ元が取れた育児グッズ"],
    "20s_man": ["一人暮らしのQOLが1段上がる", "コスパで選ぶなら結論これ", "買わない理由が見つからなかった"],
    "30s_man": ["時間をお金で買うならこれ", "レビュー見て即決したやつ", "毎日使うものほど良い物を"],
    "40s_man": ["家族みんなが使ってる定番", "週末の楽しみが1段上がる", "まとめ買いは今日が正解"],
    "all": ["これ持ってない人、損してます", "今日買うのが一番お得です", "レビュー数が答えです"],
}
# セール時のフック。根拠のない「次は定価」「今日が最安」は書かない（景表法の有利誤認になる）
SALE_HOOKS = [
    "セール価格は期間中だけ。迷うなら今",
    "{deadline}。終わってから気づくと悔しいやつ",       # 締切が商品名にある時だけ
    "ポイント{pt}倍の今が狙い目",                         # ポイント倍率が2倍以上の時だけ
    "セール中にまとめ買いしてる人が多いやつ",
]
GIFT_HOOKS = ["{event}、まだ決めてない人へ", "外さないプレゼントはこれ", "毎年これで喜ばれてます"]


def _hook(theme: Theme, deal: dict[str, str], seed: int, p: Product) -> str:
    ev = theme.title.split(" × ")[0]
    ev_name = re.sub(r"（.*?）", "", ev).strip()
    if theme.event_type == "sale":
        pool = [SALE_HOOKS[0], SALE_HOOKS[3]]
        if deal.get("deadline"):
            pool.append(SALE_HOOKS[1])
        if p.point_rate >= 2:
            pool.append(SALE_HOOKS[2])
        # ペルソナのフックも半分の確率で混ぜる（セール文ばかりにならないように）
        pool += PERSONA_HOOKS.get(theme.persona.key, PERSONA_HOOKS["all"])[:2]
        h = pool[seed % len(pool)]
        return h.format(deadline=deal.get("deadline", ""), pt=p.point_rate, event=ev_name)
    if theme.event_type == "gift":
        return GIFT_HOOKS[seed % len(GIFT_HOOKS)].format(event=ev_name)
    hooks = PERSONA_HOOKS.get(theme.persona.key, PERSONA_HOOKS["all"])
    return hooks[seed % len(hooks)]


def template_post(p: Product, theme: Theme, s: Settings) -> str:
    deal = extract_deal(p)
    seed = hash(p.item_code) % 1000
    hook = _hook(theme, deal, seed, p)
    name = _short_name(p.name)
    # ショップのキャッチコピーが短ければベネフィットとして添える（例「累計10万枚」「30レシピ付」）
    cc = re.sub(r"[【】\[\]＼／|｜★☆]+", " ", p.catchcopy or "").strip()
    cc = re.sub(r"\s+", " ", cc)
    if cc and 4 <= len(cc) <= 26 and not re.search(r"(OFF|％|%|クーポン|まで|迄|\d/\d)", cc):
        name = f"{name}｜{cc}"

    # 社会的証明
    proof = f"★{p.review_average}・レビュー{p.review_count:,}件"
    if deal.get("rank1"):
        proof += "・" + deal["rank1"]

    # お得の根拠（あるものだけ並べる）
    parts = []
    if deal.get("discount"):
        parts.append(deal["discount"] + (f" {deal['deadline']}" if deal.get("deadline") else ""))
    elif deal.get("deadline"):
        parts.append(deal["deadline"])
    price = f"{p.price:,}円"
    if deal.get("points"):
        price += f"（{deal['points']}）"
    elif deal.get("ship"):
        price += "・送料無料"
    parts.append(price)
    deal_line = "｜".join(parts)

    # ハッシュタグは1つに絞る（多いほど表示が抑えられる）。セール中は検索されるイベントタグを優先
    ev = theme.title.split(" × ")[0]
    if theme.event_type == "sale" and "スーパーSALE" in ev:
        tags = "#楽天スーパーSALE"
    elif theme.event_type == "sale" and "マラソン" in ev:
        tags = "#お買い物マラソン"
    else:
        tags = theme.persona.hashtags[0]
    # 3回に1回、返信を促す一言を足す（反応が付くと表示が伸びる）
    asks = ["使ってる人いたら感想ください", "これ買った人、正直どうでした？", "気になる人は保存しておくと便利です"]
    ask = asks[seed % 3] if seed % 3 == 0 else ""
    text = f"#PR {hook}\n{name}\n{proof}\n{deal_line}\n{ask}\n{tags}\n{CTA}".replace("\n\n", "\n")
    return sanitize(text)


# ---------- Claude 版 ----------
SYSTEM = """あなたは日本のSNSアフィリエイトで10年以上、楽天ROOMとXを運用してきたプロのコピーライターです。
与えられた「今日のテーマ」と「商品候補」から、Xで最も購買につながりそうな商品を選び、読んだ人が「今日買わないと損だ」と感じる投稿文を書きます。

構成（この順で、各1行）:
1. フック: 誰向けかが一目で分かり、損失回避か共感で始める（例「家事あと10分短くしたい人へ」「これ知らないの、もったいない」）
2. 商品名を人が呼ぶ短い名前にして、一言のベネフィット（何がどう変わるか）
3. 社会的証明: レビュー件数・評価・ランキングなど「数字」
4. お得の根拠: 割引率・締切・ポイント倍率で「実質いくら」か。商品名やキャッチコピーに根拠がある数字だけ使う
5. ハッシュタグ2個
6. 最後の行は「▶ROOMはプロフから」だけ

厳守事項:
- 投稿文の先頭は必ず「#PR 」で始める（ステマ規制対応）
- URLは絶対に入れない
- 全角換算140文字以内（改行含む）。短い文を重ねる
- 効果・効能の断定（治る、痩せる、消える）、根拠のない「最安」「絶対」「必ず」は禁止（薬機法・景表法）
- 締切や割引は、与えられた商品名・キャッチコピーに書かれているものだけ。無ければ書かない
- 自分が使ったという嘘の体験談は書かない。「レビューで多い声」「○件のレビューで★4.8」など事実ベースで
- 宣伝口調ではなく、詳しい友人が本気で勧めるトーン。感嘆符は1つまで

出力は次のJSONのみ（前後に文章を付けない）:
{"picks": [{"item_code": "...", "why": "選定理由を1文", "text": "投稿文"}]}
"""


def claude_posts(cands: list[Product], theme: Theme, s: Settings, n: int) -> list[dict[str, Any]] | None:
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=s.anthropic_api_key or None)
    cand_lines = []
    for p in cands:
        cand_lines.append({
            "item_code": p.item_code, "name": p.name[:120], "price": p.price,
            "review_count": p.review_count, "review_average": p.review_average,
            "affiliate_rate": p.affiliate_rate, "point_rate": p.point_rate,
            "catchcopy": p.catchcopy[:80], "shop": p.shop_name, "source": p.source,
            "deal_facts": extract_deal(p),
        })
    user = (
        f"## 今日のテーマ\n{theme.describe()}\n投稿時間帯: {theme.slot}\n"
        f"文体: {theme.persona.tone}\n推奨ハッシュタグ: {' '.join(theme.persona.hashtags)}\n\n"
        f"## 商品候補（スコア順）\n{json.dumps(cand_lines, ensure_ascii=False, indent=1)}\n\n"
        f"この中から {n} 件を選び、それぞれ投稿文を書いてください。"
    )
    try:
        resp = client.messages.create(
            model="claude-opus-5",
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low"},
        )
    except Exception as e:
        print(f"  [warn] Claude API: {e}")
        return None
    if getattr(resp, "stop_reason", "") == "refusal":
        return None
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    picks = data.get("picks") or []
    by_code = {p.item_code: p for p in cands}
    out = []
    for pk in picks:
        p = by_code.get(pk.get("item_code", ""))
        if not p:
            continue
        out.append({"product": p, "text": sanitize(pk.get("text", "")), "why": pk.get("why", "")})
    return out or None


def build_posts(cands: list[Product], theme: Theme, s: Settings, n: int) -> list[dict[str, Any]]:
    if not cands:
        return []
    if s.claude_ready():
        got = claude_posts(cands[:15], theme, s, n)
        if got:
            return got[:n]
        print("  [info] Claudeが使えなかったのでテンプレート文にフォールバック")
    return [{"product": p, "text": template_post(p, theme, s), "why": f"スコア {p.score:.1f}"} for p in cands[:n]]

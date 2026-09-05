"""投稿文の生成。Claude API があれば商品選定＋文章をClaudeに任せ、無ければテンプレート。

ルール（Xの規約・ステマ規制・楽天アフィリエイト規約に合わせる）
  - 先頭に #PR を必ず入れる（広告であることの明示）
  - 本文にURLを入れない（URL付き投稿はAPI料金が約13倍、かつ表示が抑制される）
  - 誘導は「ROOMはプロフから」に統一
  - 効果・効能の断定（治る、痩せる、シミが消える 等）は書かない（薬機法）
  - 全角換算140文字以内（Xは全角1文字=2ユニット、上限280ユニット）
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


def _short_name(name: str, max_chars: int = 28) -> str:
    """楽天の長い商品名から最初の意味のある部分を取り出す。"""
    s = re.sub(r"[【\[][^】\]]*[】\]]", " ", name)       # 【送料無料】などを除去
    s = re.sub(r"\s+", " ", s).strip()
    parts = s.split(" ")
    s = parts[0] if len(parts[0]) >= 6 else " ".join(parts[:3])
    return s[:max_chars]


def sanitize(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)           # URLは絶対に入れない
    for w in NG_WORDS:
        text = text.replace(w, "")
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
        inner = [i for i in range(1, len(lines) - 1) if len(lines[i]) >= 4]
        if not inner:
            text = text[: max(10, len(text) - 4)]
            continue
        idx = max(inner, key=lambda i: weighted_len(lines[i]))
        lines[idx] = lines[idx][:-3].rstrip() + "…"
        text = "\n".join(lines)
    return text


# ---------- テンプレート版 ----------
TEMPLATES = [
    "#PR {headline}\n{name}\n{price:,}円 / レビュー{rc:,}件 ★{ra}{pt}\n{tag1} {tag2}\n{cta}",
    "#PR {headline}\n\n{name}\n⭐{ra}（{rc:,}件）｜{price:,}円{pt}\n\n{tag1} {tag2}\n{cta}",
    "#PR これ{rc:,}人がレビューして★{ra}。\n{name}\n{price:,}円{pt}\n{tag1} {tag2}\n{cta}",
]


def _headline(theme: Theme) -> str:
    """読者に見せる1行目。テーマ名から作る（calendar.json の hook は運用メモなので使わない）。"""
    ev = theme.title.split(" × ")[0]
    m = re.match(r"(.+?)（開催中）", ev)
    if m:
        return f"{m.group(1)} 開催中"
    m = re.match(r"(.+?)（(\d+)日後）", ev)
    if m:
        return f"{m.group(1)}まであと{m.group(2)}日"
    # イベント無しの日は「5と0のつく日」などの定期フックがあれば使う
    for h in theme.hooks:
        if "：" in h:
            return h.split("：")[0]
    return "今売れてるもの"


def template_post(p: Product, theme: Theme, s: Settings) -> str:
    pt = f"・ポイント{p.point_rate}倍" if p.point_rate >= 2 else ""
    tags = theme.persona.hashtags
    text = random.choice(TEMPLATES).format(
        headline=_headline(theme), name=_short_name(p.name),
        price=p.price, rc=p.review_count, ra=p.review_average, pt=pt,
        tag1=tags[0], tag2=tags[1] if len(tags) > 1 else "", cta=CTA,
    )
    return sanitize(text)


# ---------- Claude 版 ----------
SYSTEM = """あなたは日本のSNSアフィリエイトで10年以上、楽天ROOMとXを運用してきたプロです。
与えられた「今日のテーマ」と「商品候補」から、Xで最も購買につながりそうな商品を選び、投稿文を書きます。

厳守事項:
- 投稿文の先頭は必ず「#PR 」で始める（ステマ規制対応）
- URLは絶対に入れない。誘導は最後の行に「▶ROOMはプロフから」とだけ書く
- 全角換算140文字以内（改行含む）。短いほど良い
- 効果・効能の断定、誇大表現、「最安」「絶対」「必ず」は禁止（薬機法・景表法）
- 商品名は正式名称をそのまま貼らず、人が呼ぶ短い名前に言い換える
- レビュー件数・評価・価格・ポイント倍率など「数字」を最低1つ入れる
- 誰向けかを意識した文体にする。宣伝口調ではなく、友人に勧めるトーン
- ハッシュタグは2個まで、末尾の1行前に置く
- 自分が使ったという嘘の体験談は書かない。「レビューで多い声」「○○件のレビューで★4.5」など事実ベースで書く

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

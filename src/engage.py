"""反応（返信・いいね・ブックマーク・投票）を取るための投稿。

Xのアルゴリズムは「反応のある投稿・アカウント」を優先表示する。商品紹介だけだと反応が付きにくいので、
1日1回、アンケート / 質問 / 豆知識 を回して反応の入口を作る。
  poll     : 投票（Xの投票機能。押すだけなので最も反応が付きやすい）
  question : 返信を促す質問
  tip      : 保存（ブックマーク）されやすい楽天の豆知識
種類は日付で自動ローテーション。文面は事実ベースで、誇大表現や効能表現は入れない。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from .config import CALENDAR_FILE

POLLS: list[dict[str, Any]] = [
    {"q": "楽天のセール、何から見ますか？", "opts": ["食品・お取り寄せ", "日用品のまとめ買い", "家電・ガジェット", "コスメ・ファッション"]},
    {"q": "楽天で買うとき、いちばん気にするのは？", "opts": ["レビュー件数", "ポイント倍率", "送料無料か", "配送の速さ"]},
    {"q": "ポイント、何に使ってますか？", "opts": ["次の楽天の買い物", "楽天ペイで街で", "楽天トラベル", "貯めてる"]},
    {"q": "5と0のつく日、意識して買ってる？", "opts": ["毎回合わせる", "たまに", "知ってるけど気にしない", "初めて知った"]},
    {"q": "楽天で「リピート買い」してるものある？", "opts": ["食品・飲料", "日用品", "ペット用品", "リピートはしない"]},
    {"q": "セールで買って後悔したことある？", "opts": ["ある（使わなかった）", "ある（安くなかった）", "ない", "そもそも買わない"]},
    {"q": "楽天のお買い物、スマホ？PC？", "opts": ["ほぼスマホ", "ほぼPC", "半々", "アプリ限定"]},
    {"q": "冬支度、いちばん先に買うのは？", "opts": ["着る毛布・電気毛布", "加湿器", "こたつ・暖房", "まだ何も"]},
    {"q": "ふるさと納税、もう済ませた？", "opts": ["済んだ", "12月にまとめて", "迷ってる", "やってない"]},
    {"q": "楽天のレビュー、どこまで読む？", "opts": ["★1〜2を先に読む", "件数だけ見る", "写真付きだけ", "読まない"]},
]

QUESTIONS: list[str] = [
    "楽天で「これは買ってよかった」と胸を張って言えるもの、1つ教えてください。\n次の紹介の参考にします。",
    "セールのたびに必ず買うもの、ありますか？\nうちは米と炭酸水が定番になりつつあります。",
    "レビューが多いのに評価が低い商品、買ったことありますか？\n件数と評価、どっちを信じるか迷います。",
    "楽天で買った家電、当たりだったもの・外れだったものを教えてください。",
    "「実質価格」って気にしますか？\nポイント10倍なら3,000円が実質2,700円。この差で買う人、けっこう多い印象です。",
    "子育て中の方に質問です。楽天で買ってラクになったもの、何でしたか？",
    "冬に向けて買い替えを考えているもの、ありますか？\n電気毛布か加湿器か、迷っている人が多そうです。",
    "楽天のセールで「これは待つべきだった」と思った経験、ありますか？",
]

TIPS: list[str] = [
    "楽天の「5と0のつく日」は楽天カード払いでポイント4倍。\nただしエントリーが毎回必要です。忘れると通常倍率になります。",
    "楽天スーパーSALEの半額商品は、開始直後（20時）に売り切れることが多いです。\n事前に「お気に入り」に入れておくと開始と同時に買えます。",
    "お買い物マラソンは「買い回り店舗数」で倍率が上がります。\n1,000円以上の買い物1店ごとに+1倍、最大10店。日用品を分けて買うのが定番です。",
    "レビューは「★1と★2」を先に読むのが早いです。\n不満の内容が自分に関係なければ、それは良い商品です。",
    "商品名に「訳あり」とある食品は、味は同じで形やサイズが不揃いなだけのことが多いです。\n家で食べる分なら狙い目です。",
    "楽天のポイント倍率は「上限」があります。\nSPUは月ごとの獲得上限があるので、高額商品はセール日にまとめるより分散したほうが得なこともあります。",
    "「送料無料ライン」は店ごとに違います。\n3,980円以上で送料無料の店が多いので、あと少しで届くときは日用品を足すと送料分が浮きます。",
    "楽天市場アプリで買うとポイント+0.5倍。\nブラウザで商品を探して、買う直前だけアプリに切り替える人も多いです。",
    "ランキング1位の表示は「デイリー」「週間」「リアルタイム」などジャンルも期間もいろいろです。\n何のランキングかを確認すると、数字の重みが分かります。",
    "セール中に値段が上がっている商品もあります。\n「価格の履歴」が分からないときは、レビューの日付と当時の価格の書き込みが手がかりになります。",
    "楽天24やケンコーコムなど、まとめ買い系の店は「箱買い」の単価がドラッグストアより安いことが多いです。\n水・トイレットペーパー・洗剤はこれで固定化できます。",
    "ポイントの有効期限は「最後にポイントを獲得した日から1年」。\n毎月何か買っていれば通常ポイントは実質失効しません。期間限定ポイントだけ注意です。",
]


def _event_hook(today: date) -> str:
    """当日のセール・記念日を1行で。無ければ空。"""
    try:
        cal = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""
    for r in cal.get("recurring", []):
        if today.day in r.get("days_of_month", []):
            return r["name"]
    for ev in cal.get("events", []):
        s = datetime.strptime(ev["start"], "%Y-%m-%d").date()
        e = datetime.strptime(ev["end"], "%Y-%m-%d").date()
        if s <= today <= e and ev.get("type") == "sale":
            return ev["name"].split("（")[0] + " 開催中"
    return ""


def build_engagement_post(today: date, history: list[dict[str, Any]]) -> dict[str, Any]:
    """{'kind', 'text', 'poll_options'|None} を返す。種類は日付で回す。"""
    used = {h.get("engage_key") for h in history if h.get("kind") == "engage"}
    kinds = ["poll", "question", "tip", "poll", "tip", "question", "poll"]  # 週の中で投票を多めに
    kind = kinds[today.toordinal() % len(kinds)]
    hook = _event_hook(today)

    if kind == "poll":
        cands = [p for i, p in enumerate(POLLS) if f"poll{i}" not in used] or POLLS
        idx = today.toordinal() % len(cands)
        p = cands[idx]
        text = p["q"]
        if hook:
            text = f"【{hook}】\n" + text
        return {"kind": "poll", "text": text, "poll_options": p["opts"][:4], "engage_key": f"poll{POLLS.index(p)}"}

    if kind == "question":
        cands = [q for i, q in enumerate(QUESTIONS) if f"q{i}" not in used] or QUESTIONS
        q = cands[today.toordinal() % len(cands)]
        return {"kind": "question", "text": q, "poll_options": None, "engage_key": f"q{QUESTIONS.index(q)}"}

    cands = [t for i, t in enumerate(TIPS) if f"tip{i}" not in used] or TIPS
    t = cands[today.toordinal() % len(cands)]
    text = "【楽天の小ネタ】\n" + t
    if hook and "5と0" in hook and "5と0" not in t:
        text += f"\n\n今日は{hook}です。"
    return {"kind": "tip", "text": text, "poll_options": None, "engage_key": f"tip{TIPS.index(t)}"}

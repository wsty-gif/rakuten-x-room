"""TikTok 専用のギフト企画。「誰に」「予算いくら」を日替わりで決め、楽天から7点選ぶ。

X / Threads / ROOM / Instagram は従来どおり（ランキング＋行事）。TikTok だけ若い層向けのプレゼント企画にする。
  - 相手: 彼氏 / 彼女 / 記念日（大切な人） / お母さん / お父さん / 祖父母 / 友達
  - 予算: 相手ごとに 3,000〜30,000 円から日替わり
  - 行事（クリスマス・母の日など type=gift）が近いときは、その行事を優先する
選んだ商品は data/topics.json に kind="gift" として保存し、ブログにも特集ページを作る
（TikTok の「商品はプロフィールのリンクから」の受け皿）。
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any

from .config import CALENDAR_FILE, Settings
from .rakuten_client import Product, RakutenClient
from .topics import TOPICS_FILE, load_topics

NL = chr(10)

# title は「＼予算◯円／」の下に入る2行（改行 = NL）。1行 13 文字以内に収める
THEMES: list[dict[str, Any]] = [
    {"key": "kareshi", "who": "彼氏", "title": "彼氏がもらって" + NL + "嬉しかったギフト",
     "keywords": ["彼氏 プレゼント", "彼氏 誕生日プレゼント", "メンズ ギフト 人気"],
     "budgets": [5000, 10000, 20000], "tags": ["#彼氏プレゼント", "#彼氏へのプレゼント", "#カップル"],
     "hook": "彼氏へのプレゼント、迷ったらこれ🎁"},
    {"key": "kanojo", "who": "彼女", "title": "彼女がもらって" + NL + "嬉しかったギフト",
     "keywords": ["彼女 プレゼント", "彼女 誕生日プレゼント", "レディース ギフト おしゃれ"],
     "budgets": [5000, 10000, 20000], "tags": ["#彼女プレゼント", "#彼女へのプレゼント", "#カップル"],
     "hook": "彼女へのプレゼント、外さないやつ🎁"},
    {"key": "kinenbi", "who": "大切な人", "title": "特別な日にもらって" + NL + "嬉しかったギフト",
     "keywords": ["記念日 プレゼント", "記念日 ギフト", "サプライズ プレゼント"],
     "budgets": [10000, 20000, 30000], "tags": ["#記念日プレゼント", "#サプライズ", "#カップル"],
     "hook": "記念日のプレゼント、これなら間違いない🎁"},
    {"key": "haha", "who": "お母さん", "title": "お母さんに贈って" + NL + "喜ばれたギフト",
     "keywords": ["母 プレゼント", "お母さん プレゼント", "母 誕生日 ギフト"],
     "budgets": [5000, 10000], "tags": ["#母へのプレゼント", "#母の誕生日", "#親孝行"],
     "hook": "お母さんへのプレゼント、何あげるか決まった？🎁"},
    {"key": "chichi", "who": "お父さん", "title": "お父さんに贈って" + NL + "喜ばれたギフト",
     "keywords": ["父 プレゼント", "お父さん プレゼント", "父 誕生日 ギフト"],
     "budgets": [5000, 10000], "tags": ["#父へのプレゼント", "#父の誕生日", "#親孝行"],
     "hook": "お父さんへのプレゼント、迷ったらこれ🎁"},
    {"key": "sofubo", "who": "祖父母", "title": "祖父母に贈って" + NL + "喜ばれたギフト",
     "keywords": ["祖母 プレゼント", "祖父 プレゼント", "孫 から プレゼント"],
     "budgets": [3000, 5000, 10000], "tags": ["#祖父母へのプレゼント", "#おばあちゃん", "#おじいちゃん"],
     "hook": "おじいちゃん・おばあちゃんへのプレゼント🎁"},
    {"key": "tomo", "who": "友達", "title": "友達の誕生日に" + NL + "喜ばれたギフト",
     "keywords": ["友達 誕生日プレゼント", "女友達 プレゼント", "プチギフト おしゃれ"],
     "budgets": [3000, 5000], "tags": ["#友達へのプレゼント", "#誕生日プレゼント", "#プチギフト"],
     "hook": "友達の誕生日、センスいいって言われたやつ🎁"},
]

NG_WORDS = ["中古", "訳あり", "ふるさと納税", "業務用", "レンタル", "ジャンク", "サンプル", "お試し", "詰め替え",
            "まとめ買い", "ケース販売", "アダルト", "福袋",
            # 若い層のプレゼント企画に合わない物（法人・仏事・儀礼系）
            "胡蝶蘭", "開店祝い", "開業", "お供え", "供花", "香典", "法要", "仏", "御祝 法人", "法人", "のし紙のみ", "内祝い のみ",
            "ふぐ", "カニ", "うなぎ", "米 ", "お米", "10kg", "5kg", "ケース", "24本", "12本",
            "おむつ", "出産祝い", "ベビー", "赤ちゃん", "キッズ", "子供", "還暦", "喪中", "退職", "卒業", "入学", "お歳暮", "お中元"]
# テーマごとに寄せたい物（商品名に入っていれば加点。同じ語は1点まで＝財布が2つ並ばない）
PREFER = {
    "kareshi": ["財布", "キーケース", "腕時計", "ベルト", "イヤホン", "名刺入れ", "香水", "ボディケア", "コーヒー", "スニーカー", "ネックレス", "バッグ", "カードケース", "マグ"],
    "kanojo": ["ネックレス", "ピアス", "ブレスレット", "財布", "バッグ", "香水", "コスメ", "ドライヤー", "ヘアアイロン", "スキンケア", "ポーチ", "腕時計", "リング", "ルームウェア"],
    "kinenbi": ["ネックレス", "ペアリング", "ペア", "腕時計", "財布", "香水", "バッグ", "ピアス", "ブレスレット", "ドライヤー", "ヘアアイロン", "フラワー", "花束", "プリザーブド"],
    "haha": ["スキンケア", "フラワー", "花", "スイーツ", "ストール", "バッグ", "マッサージ", "美顔器", "ドライヤー", "財布", "お茶", "コスメ", "ハンドクリーム", "エプロン"],
    "chichi": ["ビール", "日本酒", "ウイスキー", "焼酎", "財布", "腕時計", "ゴルフ", "コーヒー", "肉", "おつまみ", "名入れ", "ベルト", "マッサージ", "タンブラー"],
    "sofubo": ["お茶", "スイーツ", "名入れ", "湯呑", "マッサージ", "カステラ", "お菓子", "靴下", "ブランケット", "羽毛", "枕", "フラワー", "ルームシューズ", "写真"],
    "tomo": ["コスメ", "ハンドクリーム", "スイーツ", "入浴剤", "マグカップ", "キャンドル", "ポーチ", "紅茶", "コーヒー", "タオル", "リップ", "ピアス", "ネックレス", "ルームウェア"],
}
GIFT_WORDS = ["ギフト", "プレゼント", "名入れ", "ラッピング", "贈り物", "誕生日", "記念日"]


def budget_text(b: int) -> str:
    return f"{b // 10000}万円" if b >= 10000 and b % 10000 == 0 else f"{b:,}円"


def _gift_event(today: date) -> dict[str, Any] | None:
    """今日が lead_days 以内の type=gift 行事があれば返す（近い順）。"""
    try:
        cal = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    best = None
    for ev in cal.get("events", []):
        if ev.get("type") != "gift":
            continue
        try:
            start = datetime.strptime(ev["start"], "%Y-%m-%d").date()
            end = datetime.strptime(ev["end"], "%Y-%m-%d").date()
        except Exception:
            continue
        lead = int(ev.get("lead_days", 14) or 14)
        if start - timedelta(days=lead) <= today <= end:
            if best is None or start < datetime.strptime(best["start"], "%Y-%m-%d").date():
                best = ev
    return best


def pick_theme(today: date | None = None) -> dict[str, Any]:
    """日替わりでテーマと予算を決める。行事が近い日は 2 日に 1 回は行事を使う。"""
    today = today or date.today()
    n = today.toordinal()
    base = dict(THEMES[n % len(THEMES)])
    base["budget"] = base["budgets"][(n // len(THEMES)) % len(base["budgets"])]
    ev = _gift_event(today)
    if ev and n % 2 == 0:
        name = re.sub(r"（.*?）", "", ev["name"]).strip()
        who_theme = base
        # 行事に合う相手を寄せる（クリスマス・バレンタイン→恋人、母の日→母、父の日→父、敬老の日→祖父母）
        for key, words in (("kanojo", ["クリスマス", "ホワイトデー"]), ("kareshi", ["バレンタイン"]),
                           ("haha", ["母の日"]), ("chichi", ["父の日"]), ("sofubo", ["敬老"])):
            if any(w in name for w in words):
                who_theme = dict(next(t for t in THEMES if t["key"] == key))
                break
        t = dict(who_theme)
        t.update({"key": f"{who_theme['key']}-{ev['start'][:4]}-{re.sub(chr(92) + 'W', '', name)}",
                  "event": name, "title": f"{name}に贈って" + NL + "喜ばれたギフト",
                  "keywords": ([f"{name} プレゼント {who_theme['who']}"] + list(ev.get("keywords", []))[:2]),
                  "tags": [f"#{name}", f"#{name}プレゼント"] + who_theme["tags"][:1],
                  "hook": f"{name}のプレゼント、まだ決めてない人へ🎁",
                  "budget": base["budget"]})
        return t
    return base


def _category(name: str, prefer: list[str]) -> set[str]:
    """商品名に含まれる「寄せたい物」の語（複数）。同じ語が既出なら選ばない＝財布が2つ並ばない。"""
    return {w for w in prefer if w in name}


def _score(p: Product, prefer: list[str] | None = None) -> float:
    sc = math.log10(p.review_count + 1) * 2.0 + (p.review_average - 4.0) * 3.0
    text = p.name + p.catchcopy
    if any(w in text for w in GIFT_WORDS):
        sc += 1.5
    if prefer and _category(p.name, prefer):
        sc += 3.0
    if any(w in text for w in NG_WORDS):
        sc -= 20
    return sc


def fetch_gift_items(client: RakutenClient, theme: dict[str, Any], s: Settings, n: int = 7) -> list[dict[str, Any]]:
    """予算の 35〜100% の価格帯で検索し、レビュー基準を満たす物から店・ジャンルを散らして n 点。"""
    budget = int(theme["budget"])
    pool: dict[str, Product] = {}

    def collect(min_price: int) -> None:
        for kw in theme["keywords"][:3]:
            for page in (1, 2):
                try:
                    for p in client.search(kw, None, min_price, budget, sort="-reviewCount", hits=30, page=page):
                        if p.item_code not in pool:
                            pool[p.item_code] = p
                except Exception as e:
                    print(f"  [warn] gift search {kw} p{page}: {e}")
                    break

    collect(max(1000, int(budget * 0.35)))
    if len(pool) < 20:
        collect(1000)
    items = [p for p in pool.values() if p.review_count >= s.min_review_count and p.review_average >= s.min_review_average
             and p.price > 0 and p.image_url and not any(w in p.name for w in NG_WORDS)]
    prefer = PREFER.get(theme["key"].split("-")[0], [])
    items.sort(key=lambda p: _score(p, prefer), reverse=True)
    out, shops, genres, cats = [], set(), {}, set()
    for p in items:
        cat = _category(p.name, prefer)
        if p.shop_name in shops or genres.get(p.genre_id, 0) >= 2 or (cat & cats):
            continue
        shops.add(p.shop_name)
        genres[p.genre_id] = genres.get(p.genre_id, 0) + 1
        cats |= cat
        d = p.to_dict()
        d["score"] = round(_score(p, prefer), 2)
        out.append(d)
        if len(out) >= n * 3:
            break
    # 画像が「文字だらけのバナー」しか無い商品は後回し（スライドの見た目のため）
    from .tiktok_slides import CLEAN_MAX, best_image_score
    for d in out:
        d["image_score"] = round(best_image_score(d), 1)
    clean = [d for d in out if d["image_score"] <= CLEAN_MAX]
    rest = sorted([d for d in out if d["image_score"] > CLEAN_MAX], key=lambda d: d["image_score"])
    return (clean + rest)[:n]


def save_gift_topic(theme: dict[str, Any], items: list[dict[str, Any]]) -> str:
    """ブログの特集ページ用に topics.json へ保存（kind=gift）。slug を返す。"""
    topics = load_topics()
    slug = f"gift-{re.sub(r'[^a-z0-9]+', '-', theme['key'].lower()).strip('-')}-{theme['budget']}"
    now_iso = datetime.now().isoformat(timespec="seconds")
    title = f"{theme.get('event') or theme['who']}へのプレゼント 予算{budget_text(theme['budget'])}"
    old = topics.get(slug) or {}
    topics[slug] = {"slug": slug, "kind": "gift", "title": title, "keyword": theme["keywords"][0],
                    "who": theme["who"], "budget": theme["budget"], "persona": "20s_woman", "months": [],
                    "items": items, "updated": now_iso, "first_seen": old.get("first_seen", now_iso)}
    TOPICS_FILE.parent.mkdir(exist_ok=True)
    TOPICS_FILE.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    return slug

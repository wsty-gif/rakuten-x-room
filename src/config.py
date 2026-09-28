"""設定の読み込み。値は .env から。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
HISTORY_FILE = DATA_DIR / "history.json"
CALENDAR_FILE = DATA_DIR / "calendar.json"

load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    """環境変数を読む。空文字は「未設定」とみなして既定値を返す（GitHub の未設定 Variables は空文字で渡るため）。"""
    return (os.environ.get(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


# 楽天市場 主要ジャンルID（第1階層）。`python main.py genres` で最新を確認できる。
GENRES: dict[int, str] = {
    100371: "レディースファッション",
    551177: "メンズファッション",
    100433: "インナー・下着・ナイトウェア",
    216131: "バッグ・小物・ブランド雑貨",
    558885: "靴",
    558929: "腕時計",
    216129: "ジュエリー・アクセサリー",
    100533: "キッズ・ベビー・マタニティ",
    566382: "おもちゃ",
    101070: "スポーツ・アウトドア",
    562637: "家電",
    211742: "TV・オーディオ・カメラ",
    100026: "パソコン・周辺機器",
    564500: "スマートフォン・タブレット",
    100227: "食品",
    551167: "スイーツ・お菓子",
    100316: "水・ソフトドリンク",
    510915: "ビール・洋酒",
    510901: "日本酒・焼酎",
    100804: "インテリア・寝具・収納",
    215783: "日用品雑貨・文房具・手芸",
    558944: "キッチン用品・食器・調理器具",
    200162: "本・雑誌・コミック",
    101205: "テレビゲーム",
    101164: "ホビー",
    503190: "車用品・バイク用品",
    100939: "美容・コスメ・香水",
    100938: "ダイエット・健康",
    551169: "医薬品・コンタクト・介護",
    101213: "ペット・ペットグッズ",
    100005: "花・ガーデン・DIY",
}


@dataclass(frozen=True)
class Persona:
    key: str
    label: str          # 誰向けか
    age: int | None     # 楽天ランキングAPIの age（10〜50）。None なら総合
    sex: int | None     # 0=男性 1=女性
    genres: list[int]   # 得意ジャンル
    tone: str           # 文体の指示
    hashtags: list[str]


PERSONAS: dict[str, Persona] = {
    "20s_woman": Persona(
        "20s_woman", "20代女性（自分磨き・プチプラ・映え）", 20, 1,
        [100939, 100371, 216131, 100804, 551167],
        "友達に教える感じ。カジュアルで軽い。絵文字は1〜2個",
        ["#楽天購入品", "#プチプラ"],
    ),
    "30s_woman": Persona(
        "30s_woman", "30代女性（暮らし・時短・コスパ）", 30, 1,
        [558944, 100804, 215783, 100227, 100939],
        "共感から入る。忙しい毎日がラクになる視点。落ち着いた口調",
        ["#楽天購入品", "#暮らしを整える"],
    ),
    "mama": Persona(
        "mama", "子育て世帯のママ・パパ", 30, 1,
        [100533, 566382, 100227, 215783, 558944],
        "子育て中の本音。安全性と時短、コスパを重視。やさしい口調",
        ["#楽天購入品", "#子育てグッズ"],
    ),
    "20s_man": Persona(
        "20s_man", "20代男性（ガジェット・一人暮らし）", 20, 0,
        [551177, 564500, 100026, 100804, 101205],
        "端的でスペック重視。無駄な装飾なし",
        ["#楽天購入品", "#ガジェット"],
    ),
    "30s_man": Persona(
        "30s_man", "30代男性（健康・効率化・家電）", 30, 0,
        [562637, 101070, 100026, 100938, 100804],
        "コスパと効率を語る。数字を1つ入れる",
        ["#楽天購入品", "#QOL向上"],
    ),
    "40s_man": Persona(
        "40s_man", "40代男性（家族・晩酌・車）", 40, 0,
        [562637, 510915, 503190, 100227, 558929],
        "落ち着いた大人の口調。家族目線",
        ["#楽天購入品", "#おうち時間"],
    ),
    "all": Persona(
        "all", "総合（全年代）", None, None,
        [],
        "誰にでも伝わる平易な言葉",
        ["#楽天購入品", "#楽天セール"],
    ),
}


@dataclass
class Settings:
    rakuten_app_id: str = field(default_factory=lambda: _env("RAKUTEN_APP_ID"))
    rakuten_access_key: str = field(default_factory=lambda: _env("RAKUTEN_ACCESS_KEY"))
    rakuten_affiliate_id: str = field(default_factory=lambda: _env("RAKUTEN_AFFILIATE_ID"))
    # アプリ登録の「許可されたWebサイト」に入れたドメイン（Originヘッダーとして送る）
    rakuten_allowed_origin: str = field(default_factory=lambda: _env("RAKUTEN_ALLOWED_ORIGIN", "https://www.rakuten.co.jp"))
    room_url: str = field(default_factory=lambda: _env("ROOM_URL"))

    x_api_key: str = field(default_factory=lambda: _env("X_API_KEY"))
    x_api_secret: str = field(default_factory=lambda: _env("X_API_SECRET"))
    x_access_token: str = field(default_factory=lambda: _env("X_ACCESS_TOKEN"))
    x_access_token_secret: str = field(default_factory=lambda: _env("X_ACCESS_TOKEN_SECRET"))
    x_attach_image: bool = field(default_factory=lambda: _env("X_ATTACH_IMAGE", "1") == "1")

    threads_access_token: str = field(default_factory=lambda: _env("THREADS_ACCESS_TOKEN"))
    threads_user_id: str = field(default_factory=lambda: _env("THREADS_USER_ID"))
    # Threads投稿の末尾に貼るリンク。空なら ROOM_URL を使う（ブログにしたいならブログURLを入れる）
    threads_link_url: str = field(default_factory=lambda: _env("THREADS_LINK_URL"))

    instagram_access_token: str = field(default_factory=lambda: _env("INSTAGRAM_ACCESS_TOKEN"))
    instagram_user_id: str = field(default_factory=lambda: _env("INSTAGRAM_USER_ID"))
    # Instagram に流す枠（1日1〜2投稿が適正）。カンマ区切り
    instagram_slots: str = field(default_factory=lambda: _env("INSTAGRAM_SLOTS", "noon,night"))
    # ストーリーズに流す枠（既定: 3枠すべて）。空文字で無効
    instagram_story_slots: str = field(default_factory=lambda: _env("INSTAGRAM_STORY_SLOTS", "morning,noon,night"))
    # リール（1日1本、夜枠）。0 で無効
    instagram_reel: bool = field(default_factory=lambda: _env("INSTAGRAM_REEL", "0") == "1")
    site_url: str = field(default_factory=lambda: _env("SITE_URL"))

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    posts_per_run: int = field(default_factory=lambda: _env_int("POSTS_PER_RUN", 1))
    no_repeat_days: int = field(default_factory=lambda: _env_int("NO_REPEAT_DAYS", 30))
    min_price: int = field(default_factory=lambda: _env_int("MIN_PRICE", 1500))
    max_price: int = field(default_factory=lambda: _env_int("MAX_PRICE", 20000))
    min_review_count: int = field(default_factory=lambda: _env_int("MIN_REVIEW_COUNT", 50))
    min_review_average: float = field(default_factory=lambda: _env_float("MIN_REVIEW_AVERAGE", 4.2))

    # ROOM 用: 1回の実行でROOMに送る商品数（セール日は自動で増える）、同じ商品を再送しない日数
    room_picks_per_run: int = field(default_factory=lambda: _env_int("ROOM_PICKS_PER_RUN", 4))
    room_no_repeat_days: int = field(default_factory=lambda: _env_int("ROOM_NO_REPEAT_DAYS", 60))

    def x_ready(self) -> bool:
        return all([self.x_api_key, self.x_api_secret, self.x_access_token, self.x_access_token_secret])

    def instagram_ready(self) -> bool:
        return bool(self.instagram_access_token) or (DATA_DIR / "instagram_token.json").exists()

    def threads_ready(self) -> bool:
        return bool(self.threads_access_token) or (DATA_DIR / "threads_token.json").exists()

    def rakuten_ready(self) -> bool:
        return bool(self.rakuten_app_id)

    def claude_ready(self) -> bool:
        return bool(self.anthropic_api_key) or bool(os.environ.get("ANTHROPIC_AUTH_TOKEN"))

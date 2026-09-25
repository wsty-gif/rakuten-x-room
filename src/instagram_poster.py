"""Instagram（Meta 公式 Instagram API with Instagram Login）へのフィード投稿。

必要な設定（.env / GitHub Secrets）
  INSTAGRAM_ACCESS_TOKEN  Meta 開発者アプリ（Instagram ユースケース）の User Token Generator で発行した長期トークン（60日）
  INSTAGRAM_USER_ID       省略可。無ければ /me で自動取得

Threads と同じ流れ: 画像URL＋キャプションでコンテナを作り、公開する。
画像は公開URLである必要があるので、GitHub Pages に置いたカード画像（/ig/<code>.jpg）を使う。
トークンは data/instagram_token.json に保存し、24時間以上経っていれば自動更新する。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import DATA_DIR, Settings

BASE = "https://graph.instagram.com/v21.0"
TOKEN_FILE: Path = DATA_DIR / "instagram_token.json"


class InstagramPoster:
    def __init__(self, s: Settings):
        self.s = s
        self.token = self._load_token()
        self.user_id = s.instagram_user_id or self._me()

    def _load_token(self) -> str:
        if TOKEN_FILE.exists():
            try:
                d = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                tok = d.get("access_token", "")
                ts = datetime.fromisoformat(d.get("refreshed_at"))
                if tok and datetime.now() - ts < timedelta(days=59):
                    if datetime.now() - ts > timedelta(hours=24):
                        tok = self._refresh(tok) or tok
                    return tok
            except Exception:
                pass
        tok = self.s.instagram_access_token
        if not tok:
            raise RuntimeError("INSTAGRAM_ACCESS_TOKEN が未設定です")
        self._save(tok)
        return tok

    def _save(self, tok: str) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({"access_token": tok, "refreshed_at": datetime.now().isoformat(timespec="seconds")}),
                              encoding="utf-8")

    def _refresh(self, tok: str) -> str | None:
        try:
            r = requests.get("https://graph.instagram.com/refresh_access_token",
                             params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=20)
            if r.status_code == 200 and r.json().get("access_token"):
                new = r.json()["access_token"]
                self._save(new)
                print("  [instagram] アクセストークンを更新しました")
                return new
            print(f"  [warn] instagram token refresh: {r.status_code} {r.text[:120]}")
        except Exception as e:
            print(f"  [warn] instagram token refresh: {e}")
        return None

    def _me(self) -> str:
        r = requests.get(f"{BASE}/me", params={"fields": "user_id,username", "access_token": self.token}, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram /me 失敗 {r.status_code}: {r.text[:200]}")
        j = r.json()
        return str(j.get("user_id") or j.get("id"))

    def _wait_container(self, creation_id: str, tries: int = 40, interval: int = 8) -> str:
        """コンテナの処理完了を待つ。動画は数分かかることがある。"""
        for _ in range(tries):
            st = requests.get(f"{BASE}/{creation_id}", params={"fields": "status_code,status", "access_token": self.token}, timeout=20)
            if st.status_code == 200:
                code = st.json().get("status_code")
                if code == "FINISHED":
                    return code
                if code in ("ERROR", "EXPIRED"):
                    raise RuntimeError(f"Instagram コンテナ {code}: {st.json().get('status')}")
            time.sleep(interval)
        return "TIMEOUT"

    def _publish(self, creation_id: str) -> str:
        r = requests.post(f"{BASE}/{self.user_id}/media_publish",
                          data={"creation_id": creation_id, "access_token": self.token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram 公開失敗 {r.status_code}: {r.text[:200]}")
        return str(r.json()["id"])

    def post_story(self, image_url: str) -> str:
        """ストーリーズ（画像）。スタンプやリンクはAPIから付けられないので、画像内の文言で誘導する。"""
        r = requests.post(f"{BASE}/{self.user_id}/media",
                          data={"media_type": "STORIES", "image_url": image_url, "access_token": self.token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram ストーリーズ作成失敗 {r.status_code}: {r.text[:200]}")
        cid = r.json()["id"]
        self._wait_container(cid, tries=8)
        return self._publish(cid)

    def post_reel(self, video_url: str, caption: str, share_to_feed: bool = True) -> str:
        """リール（9:16 mp4、公開URL）。処理に数分かかるので長めに待つ。"""
        r = requests.post(f"{BASE}/{self.user_id}/media",
                          data={"media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
                                "share_to_feed": "true" if share_to_feed else "false", "access_token": self.token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram リール作成失敗 {r.status_code}: {r.text[:200]}")
        cid = r.json()["id"]
        if self._wait_container(cid, tries=45, interval=8) != "FINISHED":
            raise RuntimeError("Instagram リールの処理がタイムアウトしました")
        return self._publish(cid)

    def post_image(self, image_url: str, caption: str) -> str:
        r = requests.post(f"{BASE}/{self.user_id}/media",
                          data={"image_url": image_url, "caption": caption[:2200], "access_token": self.token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram コンテナ作成失敗 {r.status_code}: {r.text[:200]}")
        creation_id = r.json()["id"]
        for attempt in range(6):
            st = requests.get(f"{BASE}/{creation_id}", params={"fields": "status_code", "access_token": self.token}, timeout=20)
            if st.status_code == 200 and st.json().get("status_code") == "FINISHED":
                break
            time.sleep(8)
        r = requests.post(f"{BASE}/{self.user_id}/media_publish",
                          data={"creation_id": creation_id, "access_token": self.token}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Instagram 公開失敗 {r.status_code}: {r.text[:200]}")
        return str(r.json()["id"])


PERSONA_TAGS = {
    "20s_woman": ["#プチプラ", "#自分磨き", "#購入品紹介"],
    "30s_woman": ["#時短家事", "#暮らしを整える", "#主婦の味方"],
    "mama": ["#子育てグッズ", "#ママの味方", "#育児便利グッズ"],
    "20s_man": ["#一人暮らし", "#ガジェット", "#QOL向上"],
    "30s_man": ["#時短", "#効率化", "#家電"],
    "40s_man": ["#おうち時間", "#晩酌", "#家族時間"],
}
EVENT_TAGS = {
    "sale": ["#楽天セール", "#お買い物マラソン", "#楽天スーパーセール"],
    "gift": ["#ギフト", "#プレゼント選び", "#贈り物"],
    "season": ["#季節の準備", "#暮らしの知恵"],
    "baseline": ["#買ってよかった", "#リピ買い"],
}
BASE_TAGS = ["#PR", "#楽天購入品", "#楽天ROOM", "#楽天市場", "#楽天でお買い物", "#おすすめ商品"]


def build_caption(entry: dict, item: dict | None, hook: str, features: list[str]) -> str:
    """Instagram のキャプション。1行目は人の言葉、続いて縦線の箇条書き、保存を促す一言、リンク案内、タグ12〜15個。"""
    from .writer import _short_name, extract_deal

    name = _short_name(entry.get("item_name") or (item or {}).get("name", ""), 36)
    price = int(entry.get("price") or (item or {}).get("price") or 0)
    ra = (item or {}).get("review_average", 0)
    rc = int((item or {}).get("review_count", 0) or 0)
    pt = int((item or {}).get("point_rate", 1) or 1)
    deal: dict = {}
    if item:
        class P:
            name = item["name"]; catchcopy = item.get("catchcopy", ""); price = item["price"]; point_rate = pt
        deal = extract_deal(P())  # type: ignore[arg-type]

    lines = [f"{hook}", "", f"▶ {name}"]
    facts = []
    if rc:
        facts.append(f"★{ra}（{rc:,}件のレビュー）")
    if price:
        p = f"{price:,}円"
        if pt >= 2:
            p += f" → ポイント{pt}倍で実質{int(price * (1 - pt / 100)):,}円"
        facts.append(p)
    if deal.get("discount") or deal.get("deadline"):
        facts.append(" ".join(x for x in [deal.get("discount", ""), deal.get("deadline", "")] if x))
    if deal.get("ship"):
        facts.append("送料無料")
    for f in features[:2]:
        facts.append(f)
    for i, f in enumerate(facts):
        lines.append(("└ " if i == len(facts) - 1 else "├ ") + f)

    persona = entry.get("persona", "all")
    who = {"20s_woman": "20代女性", "30s_woman": "30代女性", "mama": "子育て中の家", "20s_man": "一人暮らしの男性",
           "30s_man": "30代男性", "40s_man": "40代男性"}.get(persona, "")
    lines += ["", (f"{who}の間で今よく買われている物です。" if who else "今よく買われている物です。") + "レビューの多い順に、評価4.2以上だけを毎日選んでいます。",
              "", "🔖 保存しておくとセールのときに探しやすいです", "▶ 商品リンクはプロフィールのまとめサイトから", ""]

    theme = entry.get("theme", "")
    et = "sale" if "SALE" in theme or "マラソン" in theme or "感謝祭" in theme or "フライデー" in theme else \
         "gift" if any(k in theme for k in ("敬老", "クリスマス", "母の日", "父の日", "バレンタイン", "プレゼント")) else \
         "season" if any(k in theme for k in ("衣替え", "寒さ", "ハロウィン", "花粉", "猛暑", "新生活", "正月")) else "baseline"
    tags = BASE_TAGS + EVENT_TAGS.get(et, []) + PERSONA_TAGS.get(persona, []) + ["#買い物メモ", "#お得情報"]
    seen, uniq = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    lines.append(" ".join(uniq[:15]))
    return "\n".join(lines)[:2200]


def wait_until_public(url: str, timeout_sec: int = 240) -> bool:
    """GitHub Pages への反映を待つ（画像が 200 を返すまで）。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(15)
    return False

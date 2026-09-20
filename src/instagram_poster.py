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

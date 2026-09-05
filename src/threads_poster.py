"""Threads（Meta 公式 Threads API）への投稿。

必要な設定（.env / GitHub Secrets）
  THREADS_ACCESS_TOKEN  Metaアプリの「User Token Generator」で発行した長期トークン（60日有効）
  THREADS_USER_ID       省略可。無ければ /me で自動取得

トークンは data/threads_token.json に保存し、24時間以上経っていれば実行時に自動更新する。
（更新すると有効期限がまた60日延びるので、毎日動いていれば切れない）
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import DATA_DIR, Settings

BASE = "https://graph.threads.net/v1.0"
TOKEN_FILE: Path = DATA_DIR / "threads_token.json"


class ThreadsPoster:
    def __init__(self, s: Settings):
        self.s = s
        self.token = self._load_token()
        self.user_id = s.threads_user_id or self._me()

    # ---- トークン管理 ----
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
        tok = self.s.threads_access_token
        if not tok:
            raise RuntimeError("THREADS_ACCESS_TOKEN が未設定です")
        self._save(tok)
        return tok

    def _save(self, tok: str) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({"access_token": tok, "refreshed_at": datetime.now().isoformat(timespec="seconds")}),
                              encoding="utf-8")

    def _refresh(self, tok: str) -> str | None:
        try:
            r = requests.get(f"{BASE}/refresh_access_token",
                             params={"grant_type": "th_refresh_token", "access_token": tok}, timeout=20)
            if r.status_code == 200 and r.json().get("access_token"):
                new = r.json()["access_token"]
                self._save(new)
                print("  [threads] アクセストークンを更新しました")
                return new
            print(f"  [warn] threads token refresh: {r.status_code} {r.text[:120]}")
        except Exception as e:
            print(f"  [warn] threads token refresh: {e}")
        return None

    def _me(self) -> str:
        r = requests.get(f"{BASE}/me", params={"fields": "id,username", "access_token": self.token}, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Threads /me 失敗 {r.status_code}: {r.text[:200]}")
        return str(r.json()["id"])

    # ---- 投稿 ----
    def post(self, text: str, image_url: str | None = None) -> str:
        text = text[:490]
        params = {"text": text, "access_token": self.token}
        if image_url:
            params["media_type"] = "IMAGE"
            params["image_url"] = image_url
        else:
            params["media_type"] = "TEXT"
        r = requests.post(f"{BASE}/{self.user_id}/threads", data=params, timeout=30)
        if r.status_code != 200:
            if image_url:
                # 画像URLが弾かれたらテキストのみで再試行
                print(f"  [warn] threads 画像コンテナ失敗、テキストのみで投稿: {r.text[:120]}")
                return self.post(text, None)
            raise RuntimeError(f"Threads コンテナ作成失敗 {r.status_code}: {r.text[:200]}")
        creation_id = r.json()["id"]
        if image_url:
            time.sleep(15)  # 画像処理待ち（公式推奨は平均30秒。失敗時は下で再試行）
        for attempt in range(4):
            r = requests.post(f"{BASE}/{self.user_id}/threads_publish",
                              data={"creation_id": creation_id, "access_token": self.token}, timeout=30)
            if r.status_code == 200 and r.json().get("id"):
                return str(r.json()["id"])
            time.sleep(15)
        raise RuntimeError(f"Threads 公開失敗 {r.status_code}: {r.text[:200]}")

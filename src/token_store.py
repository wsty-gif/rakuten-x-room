"""Threads / Instagram のアクセストークンを data/<name>_token.enc に暗号化して保存する。

リポジトリを public にしても中身を読めないよう、鍵は環境変数 TOKEN_KEY（GitHub の Secrets）にだけ置く。
TOKEN_KEY が無いときはファイルに書かず、Secrets のトークン（THREADS_ACCESS_TOKEN など）をそのまま使う。

トークンを作り直して Secrets を差し替えたら、保存済みの古いトークンではなく新しい方を使う
（保存時に「元にした Secrets のトークン」の指紋を一緒に残し、変わっていたら入れ替える）。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Callable

from .config import DATA_DIR

LIFETIME = timedelta(days=59)   # 長期トークンは60日で切れる
REFRESH_AFTER = timedelta(hours=24)


def token_file(name: str):
    return DATA_DIR / f"{name}_token.enc"


def _fernet():
    key = os.environ.get("TOKEN_KEY", "").strip()
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16] if token else ""


def _load(name: str) -> dict | None:
    f, path = _fernet(), token_file(name)
    if not f or not path.exists():
        return None
    try:
        return json.loads(f.decrypt(path.read_bytes()).decode("utf-8"))
    except Exception as e:
        print(f"  [warn] {name} トークンファイルを読めません（TOKEN_KEY 違い？）: {type(e).__name__}")
        return None


def save(name: str, token: str, seed: str) -> None:
    f = _fernet()
    if not f:
        return
    DATA_DIR.mkdir(exist_ok=True)
    d = {"access_token": token, "refreshed_at": datetime.now().isoformat(timespec="seconds"), "seed": _fingerprint(seed)}
    token_file(name).write_bytes(f.encrypt(json.dumps(d).encode("utf-8")))


def current_token(name: str, seed: str, refresh: Callable[[str], str | None]) -> str:
    """使うべきトークンを返す。seed = Secrets のトークン。保存済みが同じ seed 由来で期限内ならそれを使い、24時間ごとに更新する。"""
    d = _load(name)
    # seed が空 = 平文 JSON から移したばかり（どの Secrets 由来か不明）。次の自動更新で記録される
    if d and d.get("access_token") and (not seed or d.get("seed") in ("", _fingerprint(seed))):
        try:
            age = datetime.now() - datetime.fromisoformat(d["refreshed_at"])
        except Exception:
            age = LIFETIME
        if age < LIFETIME:
            tok = d["access_token"]
            if age > REFRESH_AFTER:
                new = refresh(tok)
                if new:
                    save(name, new, seed)
                    return new
            return tok
    if not seed:
        raise RuntimeError(f"{name.upper()}_ACCESS_TOKEN が未設定です")
    save(name, seed, seed)
    return seed

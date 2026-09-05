"""GitHub の Secrets に登録する「名前」と「値」を表示する。  python show_env_for_github.py

画面に秘密の値が表示されるので、人に見られない場所で実行し、終わったらウィンドウを閉じること。
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")
from src.config import ROOT

NAMES = [
    "RAKUTEN_APP_ID", "RAKUTEN_ACCESS_KEY", "RAKUTEN_AFFILIATE_ID", "ROOM_URL",
    "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET",
    "ANTHROPIC_API_KEY", "NTFY_TOPIC",
]

env: dict[str, str] = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()

print("GitHub → リポジトリ → Settings → Secrets and variables → Actions → New repository secret")
print("次の Name / Secret を1つずつ登録する（空のものは登録しなくてよい）\n")
for n in NAMES:
    v = env.get(n, "")
    print(f"Name  : {n}")
    print(f"Secret: {v if v else '(空・登録不要)'}")
    print()

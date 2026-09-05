"""Threads の接続診断。投稿はしない。  python diag_threads.py"""
from __future__ import annotations

import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
from src.config import Settings

s = Settings()
tok = s.threads_access_token
if not tok:
    print("THREADS_ACCESS_TOKEN が未設定です（Threads連携は無効。Xのみ投稿されます）")
    sys.exit(0)

odd = [c for c in tok if c.isspace() or ord(c) > 126]
print(f"トークン: {len(tok)}文字, 先頭'{tok[:4]}'" + ("  ！空白や全角文字が混入" if odd else ""))

r = requests.get("https://graph.threads.net/v1.0/me",
                 params={"fields": "id,username,threads_profile_picture_url", "access_token": tok}, timeout=20)
if r.status_code == 200:
    j = r.json()
    print(f"認証OK: @{j.get('username')}（user id {j.get('id')}）として接続できています。")
    print("→ 次回の本番実行から、Xと同じ内容がThreadsにも投稿されます。")
else:
    print(f"認証NG: {r.status_code} {r.text[:300]}")
    print("→ よくある原因: トークンの貼り間違い / Threadsアプリ側で「ウェブサイトの権限」の招待を承認していない /")
    print("   権限 threads_basic・threads_content_publish が付いていない / トークンの期限切れ（60日）")
    sys.exit(1)

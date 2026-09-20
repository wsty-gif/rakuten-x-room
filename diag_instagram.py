"""Instagram の接続診断。投稿はしない。  python diag_instagram.py"""
from __future__ import annotations

import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
from src.config import Settings

s = Settings()
tok = s.instagram_access_token
if not tok:
    print("INSTAGRAM_ACCESS_TOKEN が未設定です（Instagram連携は無効。X/Threadsのみ投稿されます）")
    sys.exit(0)

odd = [c for c in tok if c.isspace() or ord(c) > 126]
print(f"トークン: {len(tok)}文字, 先頭'{tok[:4]}'" + ("  ！空白や全角文字が混入" if odd else ""))

r = requests.get("https://graph.instagram.com/v21.0/me",
                 params={"fields": "user_id,username,account_type", "access_token": tok}, timeout=20)
if r.status_code == 200:
    j = r.json()
    print(f"認証OK: @{j.get('username')}（user id {j.get('user_id') or j.get('id')}, 種別 {j.get('account_type')}）")
    print("→ 次回の昼・夜の実行から、カード画像が Instagram に投稿されます。")
else:
    print(f"認証NG: {r.status_code} {r.text[:300]}")
    print("→ よくある原因: トークンの貼り間違い / テスター招待を承認していない / 権限 instagram_business_content_publish が未追加")
    sys.exit(1)

"""X APIキーの診断。投稿はしない。キーの中身は表示せず、形と認証結果だけ出す。  python diag_x.py"""
from __future__ import annotations

import re
import sys

import tweepy

sys.stdout.reconfigure(encoding="utf-8")
from src.config import Settings

s = Settings()


def shape(name: str, v: str, expect: str, pattern: str) -> None:
    if not v:
        print(f"{name:22s}: 未設定")
        return
    odd = [c for c in v if c.isspace() or ord(c) > 126]
    flag = "" if re.fullmatch(pattern, v) else f"  ！形が想定と違う（想定: {expect}）"
    if odd:
        flag += "  ！空白や全角文字が混入"
    print(f"{name:22s}: {len(v)}文字, 先頭'{v[:4]}'{flag}")


shape("X_API_KEY", s.x_api_key, "25文字前後の英数字", r"[A-Za-z0-9]{20,40}")
shape("X_API_SECRET", s.x_api_secret, "50文字前後の英数字", r"[A-Za-z0-9]{40,60}")
shape("X_ACCESS_TOKEN", s.x_access_token, "数字-英数字（例 17桁-30文字）", r"\d{5,25}-[A-Za-z0-9]{20,60}")
shape("X_ACCESS_TOKEN_SECRET", s.x_access_token_secret, "45文字前後の英数字", r"[A-Za-z0-9]{35,60}")
print()

if not s.x_ready():
    print("4つ揃っていません。python setup_env.py で入れ直してください。")
    sys.exit(1)

client = tweepy.Client(
    consumer_key=s.x_api_key, consumer_secret=s.x_api_secret,
    access_token=s.x_access_token, access_token_secret=s.x_access_token_secret,
)
try:
    me = client.get_me(user_auth=True)
    print(f"認証OK: @{me.data.username}（{me.data.name}）としてログインできています。")
    print("→ PC上のキーは正しい。GitHub の Secrets に貼った値のどれかが違います（前後の空白・改行・貼り間違い）。")
except tweepy.errors.Unauthorized as e:
    print("認証NG: 401 Unauthorized")
    print("→ 4つのキーの組み合わせが無効です。よくある原因:")
    print("   1. アクセストークンを、権限を「読み取りと書き込み」に変える前に作った → 再生成が必要")
    print("   2. 別のアプリのキーが混ざっている（API Key と Access Token は同じアプリで発行）")
    print("   3. 「再生成」を押したあと、古い値を使っている")
    print("   4. Bearer Token や Client ID / Client Secret（OAuth 2.0）を貼っている")
    print(f"   詳細: {e}")
except tweepy.errors.Forbidden as e:
    print("認証は通るが権限不足（403）。アプリの権限が「読み取り」のままの可能性。")
    print(f"   詳細: {e}")
except Exception as e:
    print(f"その他のエラー: {type(e).__name__}: {e}")

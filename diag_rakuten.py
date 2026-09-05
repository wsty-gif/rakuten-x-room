"""楽天APIの接続診断。キーの中身は表示せず、形と接続結果だけを出す。  python diag_rakuten.py"""
from __future__ import annotations

import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
from src.config import Settings

s = Settings()
URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"


def shape(v: str) -> str:
    if not v:
        return "未設定"
    odd = [c for c in v if c.isspace() or ord(c) > 126]
    return f"{len(v)}文字, 先頭'{v[:3]}', 末尾'{v[-2:]}'" + ("  ！空白や全角文字が混入" if odd else "")


print("アプリID      :", shape(s.rakuten_app_id))
print("アクセスキー  :", shape(s.rakuten_access_key), "" if s.rakuten_access_key.startswith("pk_") else "！pk_ で始まっていない")
print("アフィリエイトID:", shape(s.rakuten_affiliate_id))
try:
    ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
    print("このPCの公開IP :", ip, "（楽天アプリ設定のIP制限に登録する値）")
except Exception as e:
    print("公開IPの取得失敗:", e)
print()

base = {"applicationId": s.rakuten_app_id, "accessKey": s.rakuten_access_key,
        "keyword": "タオル", "hits": 1, "format": "json", "formatVersion": 2}
RK = "https://www.rakuten.co.jp/"
import time
ORIGIN = s.rakuten_allowed_origin.rstrip("/")
H = {"Origin": ORIGIN, "Referer": ORIGIN + "/", "User-Agent": UA}
tests = [
    ("商品検索API", URL, base),
    ("ランキングAPI", "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601",
     {"applicationId": s.rakuten_app_id, "accessKey": s.rakuten_access_key, "format": "json", "formatVersion": 2}),
]
print(f"Origin: {ORIGIN}  （アプリ設定の「許可されたWebサイト」と一致させる）")
for name, url, params in tests:
    time.sleep(3)
    try:
        r = requests.get(url, params=params, headers=H, timeout=20)
        if r.status_code == 200:
            msg = f"OK 取得件数 {r.json().get('count')}"
        else:
            try:
                j = r.json()
                msg = (j.get("errors") or {}).get("errorMessage") or j.get("error_description") or str(j)[:120]
            except Exception:
                msg = r.text[:120]
        print(f"{name:34s} → {r.status_code} {msg}")
    except Exception as e:
        print(f"{name:34s} → 例外 {e}")

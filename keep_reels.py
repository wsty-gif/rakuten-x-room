"""公開中のリール動画（直近7日分）を docs/reels に引き継ぐ。

GitHub Pages は毎回 docs/ の内容で置き換えるため、そのままだと昨夜の動画が翌朝の更新で消える。
TikTok や YouTube Shorts に手で投稿する猶予を残すため、公開サイトから直近の動画を取り戻してから公開する。
  python keep_reels.py            （SITE_URL 環境変数、または GITHUB_REPOSITORY_OWNER から公開URLを決める）
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
REELS = ROOT / "docs" / "reels"
KEEP_DAYS = 7


def site_url() -> str:
    u = os.environ.get("SITE_URL", "").strip()
    if not u and os.environ.get("GITHUB_REPOSITORY_OWNER"):
        u = f"https://{os.environ['GITHUB_REPOSITORY_OWNER']}.github.io/"
    return u.rstrip("/") + "/" if u else ""


def main() -> None:
    base = site_url()
    if not base:
        print("SITE_URL が不明なのでスキップ")
        return
    REELS.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(f"{base}reels/index.json", timeout=20)
        entries = r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"index.json 取得失敗（初回なら正常）: {e}")
        entries = []
    cutoff = date.today() - timedelta(days=KEEP_DAYS)
    kept = 0
    for e in entries:
        d = e.get("date", "")
        try:
            if datetime.strptime(d, "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            continue
        for ext in ("mp4", "json", "_slides.zip"):
            dst = REELS / (f"{d}{ext}" if ext.startswith("_") else f"{d}.{ext}")
            if dst.exists():
                continue
            try:
                res = requests.get(f"{base}reels/{dst.name}", timeout=120)
                if res.status_code == 200 and res.content:
                    dst.write_bytes(res.content)
                    kept += 1
            except Exception as ex:
                print(f"  [warn] {d}.{ext}: {ex}")
    print(f"[keep_reels] 引き継いだファイル {kept} 件")


if __name__ == "__main__":
    main()

"""公開中のTikTokスライド・動画（直近7日分）を docs/reels に引き継ぐ。

GitHub Pages は毎回 docs/ の内容で置き換えるため、そのままだと昨夜のスライドが翌朝の更新で消える。
TikTok や YouTube Shorts に手で投稿する猶予を残すため、公開サイトから直近分を取り戻してから公開する。
index.json には頼らず、直近7日の日付を直接たどる（YYYY-MM-DD.json があればその日の分を全部取る）。
  python keep_reels.py            （SITE_URL 環境変数、または GITHUB_REPOSITORY_OWNER から公開URLを決める）
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
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


def fetch(url: str, dst: Path, timeout: int = 120) -> bool:
    if dst.exists():
        return False
    try:
        res = requests.get(url, timeout=timeout)
        if res.status_code == 200 and res.content:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(res.content)
            return True
    except Exception as ex:
        print(f"  [warn] {dst.name}: {ex}")
    return False


def main() -> None:
    base = site_url()
    if not base:
        print("SITE_URL が不明なのでスキップ")
        return
    REELS.mkdir(parents=True, exist_ok=True)
    kept = 0
    for back in range(KEEP_DAYS + 1):
        d = (date.today() - timedelta(days=back)).isoformat()
        meta = REELS / f"{d}.json"
        if not meta.exists():
            try:
                r = requests.get(f"{base}reels/{d}.json", timeout=20)
            except Exception as ex:
                print(f"  [warn] {d}.json: {ex}")
                continue
            if r.status_code != 200:
                continue
            meta.write_bytes(r.content)
            kept += 1
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            info = {}
        for name in info.get("slides", []):
            kept += fetch(f"{base}reels/{d}/{name}", REELS / d / name)
        kept += fetch(f"{base}reels/{d}_slides.zip", REELS / f"{d}_slides.zip")
        kept += fetch(f"{base}reels/{d}.mp4", REELS / f"{d}.mp4", timeout=180)
    print(f"[keep_reels] 引き継いだファイル {kept} 件")


if __name__ == "__main__":
    main()

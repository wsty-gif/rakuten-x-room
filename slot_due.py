"""今この時刻に投稿すべき枠（slot）を判定する。標準ライブラリだけで動く（pip 前に実行するため）。

GitHub Actions の定期実行は数時間遅れることがあるので、20分おきに起動して
「今の時間帯に該当する枠で、今日まだ投稿していないもの」があれば、その枠名を出力する。無ければ none。

  python3 slot_due.py            → auto 判定
  python3 slot_due.py night      → 強制的にその枠

時間帯（日本時間）:
  morning 06:50-09:30 / noon 11:45-14:30 / evening 18:20-19:25（反応投稿）/
  presale 19:30-20:05（セール開始日・最終日・5と0の日のみ）/ night 20:10-23:40
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
WINDOWS = [
    ("morning", 6 * 60 + 50, 9 * 60 + 30),
    ("noon", 11 * 60 + 45, 14 * 60 + 30),
    ("evening", 18 * 60 + 20, 19 * 60 + 25),
    ("presale", 19 * 60 + 30, 20 * 60 + 5),
    ("night", 20 * 60 + 10, 23 * 60 + 40),
]


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def presale_target(today: str) -> bool:
    cal = _load(ROOT / "data" / "calendar.json") or {}
    for ev in cal.get("events", []):
        if ev.get("type") == "sale" and today in (ev.get("start"), ev.get("end")):
            return True
    return int(today[8:10]) in (5, 10, 15, 20, 25, 30)


def main() -> None:
    forced = sys.argv[1].strip() if len(sys.argv) > 1 else "auto"
    if forced and forced != "auto":
        print(forced)
        return
    now = datetime.now(JST)
    today = now.date().isoformat()
    hm = now.hour * 60 + now.minute
    done: set[str] = set()
    for h in _load(ROOT / "data" / "history.json") or []:
        d = str(h.get("date", ""))
        if d[:10] != today:
            continue
        # 深夜0〜6時の投稿は「前日の夜枠が遅れて動いたもの」なので今日の実績には数えない
        try:
            if int(d[11:13]) < 6:
                continue
        except ValueError:
            pass
        kind = h.get("kind") or "product"
        if kind == "engage":
            done.add("evening")
        elif kind == "room" and h.get("slot") == "presale":
            done.add("presale")
        elif kind == "product":
            done.add(str(h.get("slot")))
    for slot, a, b in WINDOWS:
        if a <= hm <= b and slot not in done:
            if slot == "presale" and not presale_target(today):
                continue
            print(slot)
            return
    print("none")


if __name__ == "__main__":
    main()

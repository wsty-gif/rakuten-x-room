"""対話形式で .env を作る。キーはこのPC内の .env にだけ保存される。

使い方:  python setup_env.py
  - 各項目で、メモからコピーした値を貼り付けて Enter
  - 空のまま Enter すると、その項目は飛ばす（既存の値があれば残す）
  - 入力中の秘密の値は画面に表示されない
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

# (キー名, 説明, 秘密か, 期待する形のヒント)
ITEMS = [
    ("RAKUTEN_APP_ID", "楽天ウェブサービスのアプリID（数字の列）", False, lambda v: v.isdigit()),
    ("RAKUTEN_ACCESS_KEY", "楽天ウェブサービスのアクセスキー（pk_ で始まる）", True, lambda v: v.startswith("pk_")),
    ("RAKUTEN_AFFILIATE_ID", "楽天アフィリエイトID（ドット区切りの英数字）", False, lambda v: v.count(".") >= 3),
    ("ROOM_URL", "あなたの楽天ROOMのURL（https://room.rakuten.co.jp/...）", False, lambda v: v.startswith("https://room.rakuten.co.jp/")),
    ("X_API_KEY", "X の API Key（コンシューマーキー）", True, lambda v: len(v) >= 20),
    ("X_API_SECRET", "X の API Key Secret（コンシューマーシークレット）", True, lambda v: len(v) >= 40),
    ("X_ACCESS_TOKEN", "X の Access Token（数字-英数字 の形）", True, lambda v: "-" in v and len(v) >= 40),
    ("X_ACCESS_TOKEN_SECRET", "X の Access Token Secret", True, lambda v: len(v) >= 40),
    ("ANTHROPIC_API_KEY", "Claude APIキー（任意。無ければ空Enter）", True, lambda v: v.startswith("sk-ant-")),
]


def load(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main() -> None:
    if not ENV.exists():
        ENV.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(".env を .env.example から作成しました。\n")
    current = load(ENV)

    print("メモからコピーした値を貼り付けて Enter。空Enterで飛ばします。\n")
    for key, desc, secret, check in ITEMS:
        has = bool(current.get(key))
        label = f"[{key}] {desc}" + ("  （設定済み。変更しないなら空Enter）" if has else "")
        print(label)
        if secret and sys.stdin.isatty():
            raw = getpass.getpass("  値: ")
        else:
            raw = input("  値: ")
        v = raw.strip().strip('"').strip("'")
        if not v:
            print("  → 変更なし\n")
            continue
        if not check(v):
            print("  ！ 形が想定と違います。貼り間違いの可能性がありますが、このまま保存します。")
        current[key] = v
        print("  → 保存\n")

    # .env を書き戻す（コメント行は .env.example のものを維持）
    lines = []
    written = set()
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            lines.append(f"{k}={current.get(k, '')}")
            written.add(k)
        else:
            lines.append(line)
    for k, v in current.items():
        if k not in written:
            lines.append(f"{k}={v}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 50)
    print(f".env を保存しました: {ENV}")
    missing = [k for k, _, _, _ in ITEMS[:8] if not current.get(k)]
    if missing:
        print("未設定: " + ", ".join(missing))
    else:
        print("必須項目はすべて入っています。次は  python main.py plan  で楽天側の接続を確認してください。")


if __name__ == "__main__":
    main()

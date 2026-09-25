"""リール動画（9:16、15秒前後）を ffmpeg で自動生成する。

構成: タイトルカード(2.5s) → 商品カード×3(各4s、ゆっくりズーム) → 締めカード(2.5s)。カード間はクロスフェード。
BGM は assets/bgm/*.mp3 があれば使う（フェードアウト付き）。無ければ無音トラックを付ける（Instagram は音声トラック必須）。
ffmpeg はシステムのものを優先し、無ければ imageio-ffmpeg 同梱のバイナリを使う。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .pin_image import CORAL, CORAL_D, CREAM, FONT_CANDIDATES_BOLD, FONT_CANDIDATES_REG, INK, SUB, WHITE, _font, _wrap

W, H = 1080, 1920
FPS = 30
FADE = 0.5


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # type: ignore
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_title_card(title: str, sub: str, brand: str, out: Path) -> Path:
    im = Image.new("RGB", (W, H), CORAL)
    d = ImageDraw.Draw(im)
    # 白いカード
    d.rounded_rectangle([70, 560, W - 70, H - 560], radius=48, fill=CREAM)
    f_brand = _font(FONT_CANDIDATES_BOLD, 40)
    d.text(((W - d.textlength(brand, font=f_brand)) / 2, 640), brand, font=f_brand, fill=CORAL_D)
    f_title = _font(FONT_CANDIDATES_BOLD, 88)
    y = 760
    for part in title.split("\n"):
        for line in _wrap(d, part, f_title, W - 220, 2):
            d.text(((W - d.textlength(line, font=f_title)) / 2, y), line, font=f_title, fill=INK)
            y += 112
    f_sub = _font(FONT_CANDIDATES_REG, 40)
    d.text(((W - d.textlength(sub, font=f_sub)) / 2, y + 30), sub, font=f_sub, fill=SUB)
    f_foot = _font(FONT_CANDIDATES_REG, 30)
    foot = "レビュー50件以上・評価4.2以上だけ ｜ PR"
    d.text(((W - d.textlength(foot, font=f_foot)) / 2, H - 660), foot, font=f_foot, fill=SUB)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92)
    return out


def render_end_card(brand: str, tagline: str, out: Path) -> Path:
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    f_big = _font(FONT_CANDIDATES_BOLD, 76)
    lines = ["商品リンクは", "プロフィールの", "まとめサイトから"]
    y = 700
    for line in lines:
        d.text(((W - d.textlength(line, font=f_big)) / 2, y), line, font=f_big, fill=INK)
        y += 100
    d.rounded_rectangle([W / 2 - 220, y + 40, W / 2 + 220, y + 130], radius=45, fill=CORAL)
    f_btn = _font(FONT_CANDIDATES_BOLD, 40)
    t = "▶ プロフィールへ"
    d.text(((W - d.textlength(t, font=f_btn)) / 2, y + 60), t, font=f_btn, fill=WHITE)
    f_sub = _font(FONT_CANDIDATES_REG, 36)
    s = f"{brand}｜{tagline}｜毎日更新"
    d.text(((W - d.textlength(s, font=f_sub)) / 2, y + 220), s, font=f_sub, fill=SUB)
    f_foot = _font(FONT_CANDIDATES_REG, 30)
    d.text(((W - d.textlength("PR", font=f_foot)) / 2, H - 200), "PR", font=f_foot, fill=SUB)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92)
    return out


def find_bgm(bgm_dir: Path) -> Path | None:
    if not bgm_dir.exists():
        return None
    files = sorted([p for p in bgm_dir.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac")])
    return files[0] if files else None


def build_reel(clips: list[tuple[Path, float]], out: Path, bgm: Path | None = None) -> Path:
    """clips = [(画像パス, 秒数), ...]。9:16 の mp4 を書き出す。"""
    if len(clips) < 2:
        raise ValueError("clips は2枚以上必要です")
    args = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error"]
    for img, _ in clips:
        args += ["-i", str(img)]
    n = len(clips)
    total = sum(d for _, d in clips) - FADE * (n - 1)
    if bgm:
        args += ["-stream_loop", "-1", "-i", str(bgm)]
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    parts = []
    for i, (_, dur) in enumerate(clips):
        frames = int(dur * FPS)
        zoom = "min(zoom+0.0007,1.10)" if 0 < i < n - 1 else "1.0"  # 商品カードだけゆっくりズーム
        parts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"zoompan=z='{zoom}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
            f"format=yuv420p,setsar=1[v{i}]"
        )
    # クロスフェードを連鎖
    prev = "v0"
    offset = 0.0
    for i in range(1, n):
        offset += clips[i - 1][1] - FADE
        outlbl = "vout" if i == n - 1 else f"x{i}"
        parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.2f}[{outlbl}]")
        prev = outlbl
    fade_out_start = max(0.0, total - 1.5)
    parts.append(f"[{n}:a]atrim=0:{total:.2f},volume=0.85,afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=1.5[aout]")
    filter_complex = ";".join(parts)

    out.parent.mkdir(parents=True, exist_ok=True)
    args += ["-filter_complex", filter_complex, "-map", "[vout]", "-map", "[aout]",
             "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-r", str(FPS),
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg 失敗: " + res.stderr[-800:])
    return out

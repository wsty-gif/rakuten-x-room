"""Xのアイコン（400x400）とヘッダー（1500x500）を生成する。
使い方: python assets/make_profile_images.py
色や文言はこのファイル上部の定数を変えれば再生成できる。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FONT_B = "C:/Windows/Fonts/YuGothB.ttc"
FONT_M = "C:/Windows/Fonts/YuGothM.ttc"

# ---- 配色（楽天のクリムゾンレッドは商標なので避け、暖色のコーラルで統一） ----
BG = (255, 247, 240)        # 生成り
CORAL = (255, 107, 74)      # メイン
NAVY = (36, 44, 66)         # 文字
GOLD = (255, 196, 61)       # 星
WHITE = (255, 255, 255)

NAME = "らくみつ"
TAGLINE = "楽天で見つけた良いもの、毎日3つ。"
SUB = "レビュー1,000件超・★4.3以上だけ ｜ セール・5と0のつく日も速報"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill):
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def bag(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, fill, outline):
    """買い物袋。x,y は左上。"""
    draw.rounded_rectangle([x, y + h * 0.22, x + w, y + h], radius=w * 0.12, fill=fill, outline=outline, width=int(w * 0.04))
    # 持ち手
    hw = w * 0.5
    hx = x + (w - hw) / 2
    draw.arc([hx, y, hx + hw, y + h * 0.5], start=180, end=360, fill=outline, width=int(w * 0.05))


def make_icon(size: int = 400) -> Path:
    scale = 4
    s = size * scale
    img = Image.new("RGB", (s, s), CORAL)
    d = ImageDraw.Draw(img)
    # 白い丸
    m = s * 0.09
    d.ellipse([m, m, s - m, s - m], fill=BG)
    # 袋
    bw, bh = s * 0.40, s * 0.44
    bx, by = (s - bw) / 2, s * 0.30
    bag(d, bx, by, bw, bh, WHITE, NAVY)
    # 袋の上に星
    star(d, s * 0.50, s * 0.53, s * 0.10, GOLD)
    # 「らく」の文字を袋の下部に
    f = font(FONT_B, int(s * 0.10))
    txt = "らく"
    tw = d.textlength(txt, font=f)
    d.text(((s - tw) / 2, s * 0.60), txt, font=f, fill=NAVY)
    out = OUT / "x_icon_400.png"
    img.resize((size, size), Image.LANCZOS).save(out, optimize=True)
    return out


def make_header(w: int = 1500, h: int = 500) -> Path:
    scale = 2
    W, H = w * scale, h * scale
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 右側にコーラルの大きな円（アクセント）
    d.ellipse([W * 0.76, -H * 0.35, W * 1.20, H * 1.35], fill=CORAL)
    # 円の中に袋と星
    bw, bh = W * 0.11, W * 0.12
    bx, by = W * 0.855, H * 0.30
    bag(d, bx, by, bw, bh, WHITE, NAVY)
    star(d, bx + bw / 2, by + bh * 0.55, W * 0.027, GOLD)
    # 左テキスト（Xではヘッダー左下にアイコンが重なるので、内容は上寄せにする）
    f1 = font(FONT_B, int(H * 0.125))
    f2 = font(FONT_M, int(H * 0.062))
    f3 = font(FONT_B, int(H * 0.068))
    x0 = W * 0.06
    d.text((x0, H * 0.20), TAGLINE, font=f1, fill=NAVY)
    d.text((x0, H * 0.43), SUB, font=f2, fill=(90, 96, 112))
    # タグ風の3つ
    tags = ["#PR表記あり", "リンクはROOMから", "毎日 7:30 / 12:15 / 20:30"]
    tx = x0
    ty = H * 0.60
    for t in tags:
        tw = d.textlength(t, font=f3)
        pad = H * 0.04
        d.rounded_rectangle([tx, ty, tx + tw + pad * 2, ty + H * 0.13], radius=H * 0.065, fill=WHITE, outline=CORAL, width=int(H * 0.008))
        d.text((tx + pad, ty + H * 0.025), t, font=f3, fill=CORAL)
        tx += tw + pad * 2 + W * 0.015
    out = OUT / "x_header_1500x500.png"
    img.resize((w, h), Image.LANCZOS).save(out, optimize=True)
    return out


if __name__ == "__main__":
    print(make_icon())
    print(make_header())

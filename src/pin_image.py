"""商品の「情報カード画像」を自動生成する。

Pinterest 用 2:3（1000×1500）と Instagram 用 4:5（1080×1350）を同じデザインで出す。
構成: 上に商品写真（正方形）、下に商品名・評価とレビュー件数・価格と実質価格・割引バッジ・サイト名。
フォントは環境にある日本語フォントを探す（Windows: 游ゴシック / Linux: Noto Sans CJK）。
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CREAM = (253, 248, 243)
INK = (36, 44, 66)
SUB = (110, 116, 130)
CORAL = (255, 107, 74)
RED = (200, 50, 31)
GOLD = (241, 180, 27)
WHITE = (255, 255, 255)

FONT_CANDIDATES_BOLD = [
    "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/BIZ-UDGothicB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
]
FONT_CANDIDATES_REG = [
    "C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/BIZ-UDGothicR.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
]


def _font(cands: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in cands:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def safe_name(item_code: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", item_code)


def _original(url: str) -> str:
    return re.sub(r"\?_ex=\d+x\d+", "", url or "")


def fetch_image(url: str) -> Image.Image | None:
    for u in (_original(url), url):
        if not u:
            continue
        try:
            r = requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and r.content:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            continue
    return None


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    """白背景の正方形に収める（切らずに全体を見せる）。"""
    canvas = Image.new("RGB", (size, size), WHITE)
    w, h = img.size
    scale = min(size / w, size / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas.paste(img, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength("".join(lines) , font=font) < draw.textlength(text, font=font):
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def _badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, fg=WHITE, pad=(18, 8)) -> int:
    w = int(draw.textlength(text, font=font)) + pad[0] * 2
    h = font.size + pad[1] * 2
    x, y = xy
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill)
    draw.text((x + pad[0], y + pad[1] - 2), text, font=font, fill=fg)
    return w


def render_card(product: dict[str, Any], size: tuple[int, int], deal: dict[str, str], brand: str,
                tagline: str, img: Image.Image | None) -> Image.Image:
    W, H = size
    S = W / 1000  # 1000px 基準のスケール
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)

    # 上部ブランド帯
    f_brand = _font(FONT_CANDIDATES_BOLD, int(30 * S))
    d.rectangle([0, 0, W, int(64 * S)], fill=CORAL)
    d.text((int(40 * S), int(14 * S)), brand, font=f_brand, fill=WHITE)
    tw = d.textlength(tagline, font=_font(FONT_CANDIDATES_REG, int(24 * S)))
    d.text((W - int(40 * S) - tw, int(18 * S)), tagline, font=_font(FONT_CANDIDATES_REG, int(24 * S)), fill=WHITE)

    # 商品写真（影付き）
    pic_size = int(min(W - 100 * S, H * 0.56))
    pic_x = (W - pic_size) // 2
    pic_y = int(100 * S)
    if img is None:
        img = Image.new("RGB", (pic_size, pic_size), WHITE)
    sq = _rounded(_fit_square(img, pic_size), int(28 * S))
    shadow = Image.new("RGBA", (pic_size + int(40 * S), pic_size + int(40 * S)), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([int(20 * S), int(26 * S), pic_size + int(20 * S), pic_size + int(26 * S)],
                                             radius=int(28 * S), fill=(36, 44, 66, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(14 * S)))
    im.paste(shadow, (pic_x - int(20 * S), pic_y - int(20 * S)), shadow)
    im.paste(sq, (pic_x, pic_y), sq)

    # バッジ（割引 / ランキング1位 / ポイント倍率）
    f_badge = _font(FONT_CANDIDATES_BOLD, int(26 * S))
    bx, by = pic_x, pic_y + pic_size + int(28 * S)
    if deal.get("discount"):
        bx += _badge(d, (bx, by), deal["discount"], f_badge, RED) + int(12 * S)
    if deal.get("rank1"):
        bx += _badge(d, (bx, by), "楽天ランキング1位", f_badge, GOLD, fg=(74, 50, 0)) + int(12 * S)
    pt = int(product.get("point_rate", 1) or 1)
    if pt >= 2:
        bx += _badge(d, (bx, by), f"ポイント{pt}倍", f_badge, INK) + int(12 * S)
    if deal.get("ship") and bx < W * 0.7:
        _badge(d, (bx, by), "送料無料", f_badge, (230, 224, 216), fg=INK)
    y = by + int(62 * S)

    # 商品名（最大2行）
    f_title = _font(FONT_CANDIDATES_BOLD, int(44 * S))
    for line in _wrap(d, product["short_name"], f_title, W - int(100 * S), 2):
        d.text((int(50 * S), y), line, font=f_title, fill=INK)
        y += int(56 * S)
    y += int(6 * S)

    # 評価
    f_star = _font(FONT_CANDIDATES_BOLD, int(30 * S))
    f_sub = _font(FONT_CANDIDATES_REG, int(26 * S))
    avg = float(product.get("review_average", 0) or 0)
    stars = "★" * int(round(avg)) + "☆" * (5 - int(round(avg)))
    d.text((int(50 * S), y), stars, font=f_star, fill=GOLD)
    sx = int(50 * S) + d.textlength(stars, font=f_star) + int(14 * S)
    d.text((sx, y), f"{avg}", font=f_star, fill=INK)
    sx += d.textlength(f"{avg}", font=f_star) + int(14 * S)
    d.text((sx, y + int(4 * S)), f"レビュー{int(product.get('review_count', 0) or 0):,}件", font=f_sub, fill=SUB)
    y += int(52 * S)

    # 価格
    f_price = _font(FONT_CANDIDATES_BOLD, int(64 * S))
    f_yen = _font(FONT_CANDIDATES_BOLD, int(30 * S))
    price = int(product.get("price", 0) or 0)
    d.text((int(50 * S), y - int(6 * S)), f"{price:,}", font=f_price, fill=RED)
    px = int(50 * S) + d.textlength(f"{price:,}", font=f_price) + int(6 * S)
    d.text((px, y + int(26 * S)), "円", font=f_yen, fill=RED)
    if pt >= 2:
        eff = int(price * (1 - pt / 100))
        _badge(d, (int(px + 60 * S), y + int(14 * S)), f"実質 {eff:,}円", _font(FONT_CANDIDATES_BOLD, int(26 * S)), (255, 241, 235), fg=(224, 85, 47))
    y += int(84 * S)

    # 締切 / 一言
    f_note = _font(FONT_CANDIDATES_REG, int(26 * S))
    note = deal.get("deadline", "")
    if note:
        d.text((int(50 * S), y), f"⏰ {note}", font=f_note, fill=RED)

    # 下部
    f_foot = _font(FONT_CANDIDATES_REG, int(24 * S))
    foot = "楽天で本当に売れている物を毎日まとめています ｜ PR"
    d.text((int(50 * S), H - int(58 * S)), foot, font=f_foot, fill=SUB)
    return im


def make_cards(product: dict[str, Any], out_pin: Path, out_ig: Path, brand: str, tagline: str,
               deal: dict[str, str], force: bool = False) -> tuple[Path | None, Path | None]:
    """2枚を生成して保存。既に両方あれば何もしない。戻り値は (pin_path, ig_path)。"""
    name = safe_name(product["item_code"]) + ".jpg"
    p_pin, p_ig = out_pin / name, out_ig / name
    if not force and p_pin.exists() and p_ig.exists():
        return p_pin, p_ig
    img = fetch_image(product.get("image_url", ""))
    if img is None:
        return None, None
    out_pin.mkdir(parents=True, exist_ok=True)
    out_ig.mkdir(parents=True, exist_ok=True)
    render_card(product, (1000, 1500), deal, brand, tagline, img).save(p_pin, "JPEG", quality=88, optimize=True)
    render_card(product, (1080, 1350), deal, brand, tagline, img).save(p_ig, "JPEG", quality=88, optimize=True)
    return p_pin, p_ig

"""商品の「情報カード画像」を自動生成する（v2: 写真6割・見出し1本・価格3段・バッジ1つ）。

Pinterest 用 2:3（1000×1500）と Instagram 用 4:5（1080×1350）を同じデザインで出す。
構成:
  上 58%  写真パネル（同じ写真をぼかして敷き、その上に商品写真を丸角＋影で置く。左上にブランド、右上に割引バッジ）
  下 42%  見出し（人の言葉、コーラル）→ 商品名 → ★評価とレビュー件数 → 価格3段（元値取消線 / 今の価格 / 実質）→ 締切 → フッター
フォントは環境にある日本語フォントを探す（Windows: 游ゴシック / Linux: Noto Sans CJK）。
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

CREAM = (253, 248, 243)
INK = (36, 44, 66)
SUB = (110, 116, 130)
CORAL = (255, 107, 74)
CORAL_D = (224, 85, 47)
RED = (200, 50, 31)
GOLD = (241, 180, 27)
WHITE = (255, 255, 255)
LINE = (233, 226, 219)

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
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(cands: list[str], size: int) -> ImageFont.FreeTypeFont:
    key = (cands[0], size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for path in cands:
        if Path(path).exists():
            try:
                f = ImageFont.truetype(path, size)
                _FONT_CACHE[key] = f
                return f
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


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    im = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))), Image.LANCZOS)
    x, y = (im.size[0] - w) // 2, (im.size[1] - h) // 2
    return im.crop((x, y, x + w, y + h))


def _contain(img: Image.Image, w: int, h: int, bg=WHITE) -> Image.Image:
    canvas = Image.new("RGB", (w, h), bg)
    iw, ih = img.size
    scale = min(w / iw, h / ih)
    im = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))), Image.LANCZOS)
    canvas.paste(im, ((w - im.size[0]) // 2, (h - im.size[1]) // 2))
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
    if "".join(lines) != text and lines:
        lines[-1] = lines[-1][:-1].rstrip() + "…"
    return lines


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, fg=WHITE, pad=(18, 8), outline=None) -> int:
    w = int(draw.textlength(text, font=font)) + pad[0] * 2
    h = font.size + pad[1] * 2
    x, y = xy
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill, outline=outline, width=3 if outline else 0)
    draw.text((x + pad[0], y + pad[1] - 2), text, font=font, fill=fg)
    return w


def _discount_pct(deal: dict[str, str]) -> int | None:
    d = deal.get("discount", "")
    if d == "半額":
        return 50
    m = re.match(r"(\d{2})%OFF", d)
    return int(m.group(1)) if m else None


def render_card(product: dict[str, Any], size: tuple[int, int], deal: dict[str, str], brand: str,
                tagline: str, img: Image.Image | None) -> Image.Image:
    W, H = size
    S = W / 1000
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)

    # ---- 写真パネル（上 58%）----
    pad = int(36 * S)
    pw, ph = W - pad * 2, int(H * 0.58) - pad
    px, py = pad, pad
    if img is None:
        img = Image.new("RGB", (pw, ph), (240, 236, 230))
    bg = _cover(img, pw, ph).filter(ImageFilter.GaussianBlur(int(26 * S)))
    bg = ImageEnhance.Brightness(bg).enhance(0.92)
    panel = Image.new("RGB", (pw, ph), CREAM)
    panel.paste(bg, (0, 0))
    # 商品写真（内側に収め、丸角＋影）
    inner = int(min(pw, ph) * 0.84)
    photo = _rounded(_contain(img, inner, inner), int(26 * S))
    ix, iy = (pw - inner) // 2, (ph - inner) // 2
    shadow = Image.new("RGBA", (inner + int(60 * S), inner + int(60 * S)), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([int(30 * S), int(38 * S), inner + int(30 * S), inner + int(38 * S)],
                                             radius=int(26 * S), fill=(30, 30, 40, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(18 * S)))
    panel_rgba = panel.convert("RGBA")
    panel_rgba.alpha_composite(shadow, (ix - int(30 * S), iy - int(30 * S)))
    panel_rgba.alpha_composite(photo, (ix, iy))
    panel_r = _rounded(panel_rgba.convert("RGB"), int(34 * S))
    im.paste(panel_r, (px, py), panel_r)

    # ブランドピル（左上）
    f_brand = _font(FONT_CANDIDATES_BOLD, int(26 * S))
    _pill(d, (px + int(22 * S), py + int(22 * S)), brand, f_brand, CORAL, pad=(int(18 * S), int(8 * S)))
    # 割引バッジ（右上・丸・1つだけ）
    pct = _discount_pct(deal)
    badge_txt = deal.get("discount") if pct else ("1位" if deal.get("rank1") else "")
    if badge_txt:
        r = int(74 * S)
        cx, cy = px + pw - r - int(22 * S), py + r + int(22 * S)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED if pct else GOLD)
        f_b = _font(FONT_CANDIDATES_BOLD, int((34 if len(badge_txt) <= 3 else 26) * S))
        tw = d.textlength(badge_txt, font=f_b)
        d.text((cx - tw / 2, cy - f_b.size / 2 - int(4 * S)), badge_txt, font=f_b, fill=WHITE if pct else (74, 50, 0))
        if pct:
            f_s = _font(FONT_CANDIDATES_REG, int(18 * S))
            sub = "セール中"
            d.text((cx - d.textlength(sub, font=f_s) / 2, cy + int(20 * S)), sub, font=f_s, fill=WHITE)

    # ---- テキスト（下 42%）----
    x0 = pad + int(6 * S)
    y = py + ph + int(30 * S)
    max_w = W - x0 * 2

    # 見出し（人の言葉）
    hook = (product.get("hook") or "").strip()
    if hook:
        f_hook = _font(FONT_CANDIDATES_BOLD, int(46 * S))
        for line in _wrap(d, hook, f_hook, max_w, 2):
            d.text((x0, y), line, font=f_hook, fill=CORAL_D)
            y += int(58 * S)
        y += int(4 * S)

    # 商品名
    f_name = _font(FONT_CANDIDATES_BOLD, int(32 * S))
    for line in _wrap(d, product["short_name"], f_name, max_w, 2 if not hook else 1):
        d.text((x0, y), line, font=f_name, fill=INK)
        y += int(42 * S)
    y += int(6 * S)

    # 評価
    f_star = _font(FONT_CANDIDATES_BOLD, int(28 * S))
    f_sub = _font(FONT_CANDIDATES_REG, int(24 * S))
    avg = float(product.get("review_average", 0) or 0)
    stars = "★" * int(round(avg)) + "☆" * (5 - int(round(avg)))
    d.text((x0, y), stars, font=f_star, fill=GOLD)
    sx = x0 + d.textlength(stars, font=f_star) + int(12 * S)
    d.text((sx, y), f"{avg}", font=f_star, fill=INK)
    sx += d.textlength(f"{avg}", font=f_star) + int(12 * S)
    rc = int(product.get("review_count", 0) or 0)
    d.text((sx, y + int(4 * S)), f"{rc:,}人がレビュー", font=f_sub, fill=SUB)
    y += int(50 * S)

    # 価格3段: 元値（取消線）/ 今の価格 / 実質
    price = int(product.get("price", 0) or 0)
    pt = int(product.get("point_rate", 1) or 1)
    f_price = _font(FONT_CANDIDATES_BOLD, int(70 * S))
    f_yen = _font(FONT_CANDIDATES_BOLD, int(30 * S))
    # 元値の取り消し線は表示しない（割引率からの逆算は推定値で、二重価格表示の規制に触れる恐れがある）
    d.text((x0, y - int(8 * S)), f"{price:,}", font=f_price, fill=RED)
    pxw = x0 + d.textlength(f"{price:,}", font=f_price) + int(6 * S)
    d.text((pxw, y + int(28 * S)), "円", font=f_yen, fill=RED)
    if pt >= 2:
        eff = int(price * (1 - pt / 100))
        _pill(d, (int(pxw + 56 * S), y + int(14 * S)), f"P{pt}倍で実質 {eff:,}円", _font(FONT_CANDIDATES_BOLD, int(26 * S)),
              (255, 241, 235), fg=CORAL_D, pad=(int(16 * S), int(8 * S)))
    y += int(86 * S)

    # 締切 / 送料無料 のチップ（横並び）
    f_chip = _font(FONT_CANDIDATES_BOLD, int(24 * S))
    cx = x0
    if deal.get("deadline"):
        cx += _pill(d, (cx, y), f"⏰ {deal['deadline']}", f_chip, CREAM, fg=RED, outline=RED, pad=(int(16 * S), int(6 * S))) + int(12 * S)
    if deal.get("ship"):
        cx += _pill(d, (cx, y), "送料無料", f_chip, (236, 232, 226), fg=INK, pad=(int(16 * S), int(6 * S))) + int(12 * S)
    if cx > x0:
        y += int(56 * S)

    # 一言（商品説明から拾った特徴）
    memo = (product.get("memo") or "").strip()
    if memo and y < H - int(150 * S):
        f_memo = _font(FONT_CANDIDATES_REG, int(26 * S))
        d.rounded_rectangle([x0, y + int(4 * S), x0 + int(6 * S), y + int(64 * S)], radius=int(3 * S), fill=CORAL)
        for line in _wrap(d, memo, f_memo, max_w - int(24 * S), 2):
            d.text((x0 + int(20 * S), y), line, font=f_memo, fill=(70, 76, 90))
            y += int(34 * S)

    # フッター
    f_foot = _font(FONT_CANDIDATES_REG, int(22 * S))
    d.line([x0, H - int(78 * S), W - x0, H - int(78 * S)], fill=LINE, width=max(1, int(2 * S)))
    d.text((x0, H - int(62 * S)), "詳しくはプロフィールのリンクから", font=f_foot, fill=SUB)
    right = f"{tagline} ｜ PR"
    d.text((W - x0 - d.textlength(right, font=f_foot), H - int(62 * S)), right, font=f_foot, fill=SUB)
    return im


def make_cards(product: dict[str, Any], out_pin: Path, out_ig: Path, brand: str, tagline: str,
               deal: dict[str, str], force: bool = False, out_story: Path | None = None) -> tuple[Path | None, Path | None]:
    """Pinterest(2:3) / Instagram(4:5) / ストーリーズ・リール(9:16) を生成して保存。既にあれば何もしない。"""
    name = safe_name(product["item_code"]) + ".jpg"
    p_pin, p_ig = out_pin / name, out_ig / name
    p_story = (out_story / name) if out_story else None
    if not force and p_pin.exists() and p_ig.exists() and (p_story is None or p_story.exists()):
        return p_pin, p_ig
    img = fetch_image(product.get("image_url", ""))
    if img is None:
        return None, None
    out_pin.mkdir(parents=True, exist_ok=True)
    out_ig.mkdir(parents=True, exist_ok=True)
    render_card(product, (1000, 1500), deal, brand, tagline, img).save(p_pin, "JPEG", quality=90, optimize=True)
    render_card(product, (1080, 1350), deal, brand, tagline, img).save(p_ig, "JPEG", quality=90, optimize=True)
    if p_story:
        out_story.mkdir(parents=True, exist_ok=True)
        render_story(product, deal, brand, tagline, img).save(p_story, "JPEG", quality=90, optimize=True)
    return p_pin, p_ig


def render_story(product: dict[str, Any], deal: dict[str, str], brand: str, tagline: str, img: Image.Image) -> Image.Image:
    """9:16（1080×1920）。4:5 のカードを中央に置き、上下に余白を取る（ストーリーズは上下がUIで隠れるため）。"""
    card = render_card(product, (1080, 1350), deal, brand, tagline, img)
    im = Image.new("RGB", (1080, 1920), CREAM)
    # 背景: カードの写真部分をぼかして全面に
    bg = _cover(img, 1080, 1920).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.6)
    im.paste(bg, (0, 0))
    card_r = _rounded(card, 40)
    im.paste(card_r, (0, (1920 - 1350) // 2), card_r)
    d = ImageDraw.Draw(im)
    f = _font(FONT_CANDIDATES_BOLD, 34)
    t = "▶ 詳しくはプロフィールのリンクから"
    d.text(((1080 - d.textlength(t, font=f)) / 2, 1920 - 210), t, font=f, fill=WHITE)
    return im

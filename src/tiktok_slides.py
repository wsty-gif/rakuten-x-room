"""TikTok フォトモード用のスライド（9:16）を、参考投稿と同じ構成で作る。

1枚の構成: 淡いグレー背景 / 商品写真を上下に2枚（1枚しか無ければ中央に1枚） / 中央に半透明の白ラベル
           ラベル = ブランド名（大）・商品名（小）・価格（小）。それ以外の要素は置かない。
セット: タイトル1枚 → 商品 最大7枚 → 締め1枚。同じ画像列から mp4（各3秒・クロスフェード・BGM）も作る。
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from .pin_image import FONT_CANDIDATES_BOLD, FONT_CANDIDATES_REG, _contain, _cover, _font, _wrap, fetch_image
from .text_score import photo_band, text_score

CLEAN_MAX = 45.0      # これ以下なら「物の写真」として使う（説明文の帯を切った後の値）
SECOND_MAX = 20.0     # 2枚目（上下2段）に使うのはさらにきれいな物だけ
MIN_BAND = 0.6        # 説明文を切り落とした後に、元画像の高さの何割以上残るときだけ切る
_IMG_CACHE: dict[str, Image.Image | None] = {}


def cached_image(url: str) -> Image.Image | None:
    if url not in _IMG_CACHE:
        _IMG_CACHE[url] = fetch_image(url)
    return _IMG_CACHE[url]


def scored_images(item: dict[str, Any]) -> list[tuple[float, int, Image.Image]]:
    """商品の画像（最大3枚）を文字らしさの低い順に。(score, 元の順番, 画像)"""
    urls = [u for u in (item.get("image_urls") or []) if u] or [item.get("image_url", "")]
    out, seen = [], set()
    for i, u in enumerate(urls[:3]):
        if not u or u in seen:
            continue
        seen.add(u)
        img = cached_image(u)
        if img is None:
            continue
        # 画像の上下に説明文の帯が付いていれば先に切り落とし、残った写真の部分で文字らしさを測る
        y0, y1 = photo_band(img)
        if (y1 - y0) >= MIN_BAND and (y0 > 0.02 or y1 < 0.98):
            img = img.crop((0, int(y0 * img.height), img.width, int(y1 * img.height)))
        out.append((text_score(img), i, img))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def best_image_score(item: dict[str, Any]) -> float:
    """商品の一番きれいな画像の文字らしさ。画像が無ければ大きい値。"""
    sc = scored_images(item)
    return sc[0][0] if sc else 999.0


W, H = 1080, 1920
BG = (233, 231, 227)        # 参考投稿の灰色
INK = (40, 40, 44)
SUB = (95, 95, 100)
LABEL = (255, 255, 255, 200)
WHITE = (255, 255, 255)
# タイトル・締めスライド用の明朝体（参考は白い明朝体を写真の上に置く）
FONT_SERIF = [
    "C:/Windows/Fonts/yumin.ttf", "C:/Windows/Fonts/yumindb.ttf", "C:/Windows/Fonts/NotoSerifJP-VF.ttf",
    "C:/Windows/Fonts/BIZ-UDMinchoM.ttc", "C:/Windows/Fonts/msmincho.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSerifCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
]

SHOP_NOISE = re.compile(r"(楽天市場店|楽天市場|公式ショップ|公式|オンラインショップ|オンラインストア|ストア|ショップ|本店|支店|店|Yahoo|PayPay|SHOP|Shop|STORE|Store)")


def brand_of(name: str, shop: str) -> str:
    """商品名の先頭からブランドらしい語を取る。無ければ店名を整えて使う。"""
    s = re.sub(r"[【\[［（(][^】\]］）)]*[】\]］）)]", " ", name)
    s = re.sub(r"[＼／\\/|｜★☆◆■●]+", " ", s).strip()
    toks = [t for t in s.split(" ") if t]
    for t in toks[:3]:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9&'\-\.]{1,14}", t) and not re.fullmatch(r"(?i)(k\d+|pt\d+|sv\d+|\d+ct|xs|s|m|l|xl|ll|\d+l|\d+ml|\d+g|\d+kg)", t):
            return t
        if re.fullmatch(r"[ァ-ヴー]{2,10}", t) and not re.search(r"(セット|まとめ|送料|セール|ギフト|プレゼント|ランキング|ポイント|クーポン|レビュー|レディース|メンズ|キッズ|ベビー|ユニセックス|ブランド|サイズ|カラー|タイプ|ネックレス|ピアス|リング|ブレスレット|バッグ|ポーチ|イヤホン|スニーカー|タンブラー|マグ|キーケース|ドライヤー|アイロン|ストール|エプロン|タオル|キャンドル|ハンドクリーム|ダイヤモンド|パール|ゴールド|シルバー|プラチナ|スイーツ|カステラ|クッキー|チョコ|贈り物|オープン|ハート|クロス|プレミアム|デラックス|スペシャル|オリジナル|セレクト)", t):
            return t
    sh = _clean_brand(shop or "")
    # 「浄水器のブリタ」「玄米・雑穀米の通販 川島」→ 最後の固有名だけ
    if "の" in sh:
        tail = sh.split("の")[-1].strip()
        tail = tail.split()[-1] if tail.split() else tail
        if 2 <= len(tail) <= 8:
            sh = tail
    elif " " in sh:
        sh = sh.split()[-1] if len(sh.split()[-1]) >= 2 else sh.split()[0]
    return sh[:12] if sh else (toks[0][:10] if toks else "")


PROMO_TOKEN = re.compile(r"(受賞|ランキング|連続|送料無料|限定|セール|SALE|クーポン|ポイント|OFF|％|%|円|楽天|公式|正規|レビュー|特典|プレゼントあり|あす楽|即納|予約|新作|入荷|人気|おすすめ|話題|大人気|総合|\d+位|No\.?\d|年|月)")


def short_name(name: str, brand: str, max_len: int = 22) -> str:
    """ラベル用の商品名。ブランド名と宣伝語を除いた、物の名前だけを残す。"""
    s = re.sub(r"[【\[［（(《〈][^】\]］）)》〉]*[】\]］）)》〉]", " ", name)
    s = re.sub(r"[＼／\\/|｜★☆◆■●◎♪！!《》〈〉「」]+", " ", s)
    toks = []
    for t in s.split():
        if not t or PROMO_TOKEN.search(t) or t in toks:
            continue
        if brand and (t == brand or t.startswith(brand)):
            continue
        # 「日傘 日傘折りたたみ」のような前方一致の重複も1つに
        if any(t.startswith(u) or u.startswith(t) for u in toks if len(u) >= 2):
            continue
        toks.append(t)
    out = ""
    for t in toks:
        if len(out) + len(t) + 1 > max_len:
            break
        out = (out + " " + t).strip()
    if len(out) < 2:
        # 全部落ちた場合だけ、名前の先頭から宣伝語を除いて使う
        raw = [t for t in re.sub(r"[【\[［（(][^】\]］）)]*[】\]］）)]", " ", name).split() if not PROMO_TOKEN.search(t)]
        out = " ".join(raw)[:max_len] or name[:max_len]
    return out


def _clean_brand(s: str) -> str:
    s = re.sub(r"[【\[［（(][^】\]］）)]*[】\]］）)]", "", s)
    return SHOP_NOISE.sub("", s).strip(" ・-−|｜")


def image_clean_score(img: Image.Image) -> float:
    """宣伝バナーらしさ。彩度の高い画素（赤・黄の帯）と白でも灰でもない背景の割合が高いほど大きい。低いほど「物の写真」。"""
    small = img.convert("HSV").resize((48, 48))
    px = list(small.getdata())
    sat = sum(1 for h, s, v in px if s > 150 and v > 120) / len(px)
    # 四辺の均一さ（物撮りは背景が均一）
    rgb = img.convert("L").resize((48, 48))
    data = list(rgb.getdata())
    edge = data[:48] + data[-48:] + data[::48] + data[47::48]
    mean = sum(edge) / len(edge)
    var = sum((x - mean) ** 2 for x in edge) / len(edge)
    return sat * 2.0 + min(var, 4000) / 4000.0


def _label(im: Image.Image, brand: str, name: str, price: int, cy: int) -> None:
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_b = _font(FONT_CANDIDATES_REG, 62 if len(brand) <= 7 else (50 if len(brand) <= 10 else 40))
    f_n = _font(FONT_CANDIDATES_REG, 30)
    f_p = _font(FONT_CANDIDATES_REG, 28)
    lines = _wrap(d, name, f_n, 400, 2)
    bw = max(464, int(max(d.textlength(brand, font=f_b), *[d.textlength(l, font=f_n) for l in lines]) + 100))
    bh = 46 + f_b.size + 14 + len(lines) * 40 + 6 + f_p.size + 46
    x0, y0 = (W - bw) // 2, cy - bh // 2
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=LABEL)
    y = y0 + 40
    d.text(((W - d.textlength(brand, font=f_b)) / 2, y), brand, font=f_b, fill=INK)
    y += f_b.size + 16
    for l in lines:
        d.text(((W - d.textlength(l, font=f_n)) / 2, y), l, font=f_n, fill=INK)
        y += 40
    y += 4
    p = f"¥{price:,}"
    d.text(((W - d.textlength(p, font=f_p)) / 2, y), p, font=f_p, fill=INK)
    im.alpha_composite(ov)


def render_product_slide(item: dict[str, Any], imgs: list[Image.Image]) -> Image.Image:
    im = Image.new("RGBA", (W, H), BG + (255,))
    if len(imgs) >= 2:
        top = _cover(imgs[0], W, H // 2)
        bot = _cover(imgs[1], W, H - H // 2)
        im.paste(top, (0, 0))
        im.paste(bot, (0, H // 2))
    elif imgs:
        # 写真1枚のときも画面いっぱい（説明文の帯は scored_images で切り落とし済み。中央基準で切り抜く）
        im.paste(_cover(imgs[0], W, H), (0, 0))
    brand = brand_of(item["name"], item.get("shop_name", ""))
    _label(im, brand, short_name(item["name"], brand), int(item["price"]), H // 2)
    return im.convert("RGB")


PLAIN_COLORS = [(46, 46, 48), (58, 54, 52), (40, 46, 54), (70, 62, 58), (52, 50, 56)]


def _plain_backdrop(seed: int = 0) -> Image.Image:
    """無機質な背景（商品写真は使わない）。濃いグレーに、ごく薄いざらつきと上下のグラデーション、細い枠線。"""
    r, g, b = PLAIN_COLORS[seed % len(PLAIN_COLORS)]
    im = Image.new("RGB", (W, H), (r, g, b))
    grad = Image.linear_gradient("L").resize((W, H))  # 上が暗く下が明るい
    lighter = Image.new("RGB", (W, H), (min(r + 26, 255), min(g + 26, 255), min(b + 26, 255)))
    im = Image.composite(lighter, im, grad)
    noise = Image.effect_noise((W, H), 28).filter(ImageFilter.GaussianBlur(0.6))
    grain = Image.merge("RGB", (noise, noise, noise))
    im = Image.blend(im, grain, 0.08)
    d = ImageDraw.Draw(im)
    d.rectangle([54, 54, W - 55, H - 55], outline=(255, 255, 255), width=2)
    d.rectangle([66, 66, W - 67, H - 67], outline=(255, 255, 255), width=1)
    return im


def _photo_backdrop(img: Image.Image | None, seed: int = 0) -> Image.Image:
    """写真を全面に敷き、暗めにして文字を載せられるようにする。写真が無ければ無機質な背景。"""
    if img is None:
        return _plain_backdrop(seed)
    bg = _cover(img, W, H)
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    bg = ImageEnhance.Color(bg).enhance(0.8)
    return bg


def _center_text(d: ImageDraw.ImageDraw, text: str, font, y: int, fill=WHITE) -> int:
    d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
    return y + font.size


def render_title_slide(title: str, sub: str, brand: str, photo: Image.Image | None = None, top_line: str = "", seed: int = 0) -> Image.Image:
    """例: ＼予算2万円／ ／ 特別な日にもらって嬉しかった 人気ギフト ／ 7選"""
    im = _photo_backdrop(photo, seed)
    d = ImageDraw.Draw(im)
    f_top = _font(FONT_SERIF, 44)
    f_main = _font(FONT_SERIF, 66)
    f_big = _font(FONT_SERIF, 118)
    f_sub = _font(FONT_SERIF, 30)
    parts = [p for p in title.split(chr(10)) if p]
    big = parts[-1] if len(parts) >= 2 and len(parts[-1]) <= 4 else ""
    mains = parts[:-1] if big else parts
    main_lines = []
    for p in mains:
        main_lines += _wrap(d, p, f_main, W - 200, 2)
    total = (f_top.size + 30 if top_line else 0) + len(main_lines) * 92 + (f_big.size + 30 if big else 0)
    y = (H - total) // 2 - 40
    if top_line:
        y = _center_text(d, top_line, f_top, y) + 30
    for l in main_lines:
        _center_text(d, l, f_main, y)
        y += 92
    if big:
        y += 10
        _center_text(d, big, f_big, y)
    if sub:
        _center_text(d, sub, f_sub, H - 300, fill=(235, 235, 235))
    _center_text(d, brand, f_sub, H - 230, fill=(235, 235, 235))
    return im


def render_end_slide(brand: str, photo: Image.Image | None = None, seed: int = 0) -> Image.Image:
    im = _photo_backdrop(photo, seed)
    d = ImageDraw.Draw(im)
    f_t = _font(FONT_SERIF, 64)
    f_s = _font(FONT_SERIF, 32)
    y = H // 2 - 140
    for l in ["商品はプロフィールの", "リンクから見られます"]:
        _center_text(d, l, f_t, y)
        y += 92
    _center_text(d, "保存して、あとでゆっくり見返してね", f_s, y + 40, fill=(235, 235, 235))
    _center_text(d, brand + "｜PR", f_s, H - 230, fill=(235, 235, 235))
    return im


def load_item_images(item: dict[str, Any], max_n: int = 1) -> list[Image.Image]:
    """文字らしさの低い順に最大 max_n 枚。1枚目は最良の物（多少文字があっても使う）、
    2枚目は SECOND_MAX 以下のきれいな物だけ（無ければ1枚を全面に）。"""
    sc = scored_images(item)
    if not sc:
        return []
    out = [sc[0][2]]
    for s, _, img in sc[1:]:
        if len(out) >= max_n:
            break
        if s <= SECOND_MAX:
            out.append(img)
    return out


def make_slide_set(items: list[dict[str, Any]], title: str, sub: str, brand: str, out_dir: Path, top_line: str = "",
                   plain: bool = True, seed: int = 0) -> list[Path]:
    """out_dir/01.jpg … を作り、パスの一覧を返す（先頭タイトル、末尾締め）。
    plain=True なら先頭と末尾は商品写真を使わず無機質な背景に文字だけ。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    loaded = [(it, load_item_images(it)) for it in items]
    loaded = [(it, imgs) for it, imgs in loaded if imgs]
    cover = None if plain else (loaded[0][1][0] if loaded else None)
    paths: list[Path] = []
    p = out_dir / "01.jpg"
    render_title_slide(title, sub, brand, photo=cover, top_line=top_line, seed=seed).save(p, "JPEG", quality=92)
    paths.append(p)
    n = 2
    for it, imgs in loaded:
        p = out_dir / f"{n:02d}.jpg"
        render_product_slide(it, imgs).save(p, "JPEG", quality=92)
        paths.append(p)
        n += 1
    p = out_dir / f"{n:02d}.jpg"
    render_end_slide(brand, photo=None if plain else (loaded[-1][1][0] if loaded else None), seed=seed).save(p, "JPEG", quality=92)
    paths.append(p)
    return paths


def zip_slides(paths: list[Path], out_zip: Path) -> Path:
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, p.name)
    return out_zip

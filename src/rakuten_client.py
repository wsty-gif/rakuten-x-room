"""楽天ウェブサービス（商品検索 / ランキング / ジャンル検索）の薄いクライアント。"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Any

import requests

from .config import Settings

SEARCH_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
RANKING_URL = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
GENRE_URL = "https://openapi.rakuten.co.jp/ichibagt/api/IchibaGenre/Search/20260701"


@dataclass
class Product:
    item_code: str
    name: str
    price: int
    item_url: str          # 通常URL（ROOMで検索するときに使う）
    affiliate_url: str     # アフィリエイトURL（必要ならXの返信等に使う）
    image_url: str
    shop_name: str
    review_count: int
    review_average: float
    affiliate_rate: float  # %
    point_rate: int        # 倍率
    catchcopy: str
    genre_id: str
    rank: int | None = None
    source: str = ""       # どの経路で拾ったか（ranking:xxx / search:yyy）
    score: float = 0.0
    caption: str = ""      # 商品説明文（ROOMコメントの材料）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _enlarge(url: str) -> str:
    """128x128 の画像URLを 600x600 に。"""
    if not url:
        return url
    return re.sub(r"_ex=\d+x\d+", "_ex=600x600", url)


class RakutenClient:
    def __init__(self, settings: Settings, min_interval: float = 1.1):
        self.s = settings
        self.min_interval = min_interval
        self._last = 0.0
        self._session = requests.Session()
        # 2026年の新仕様では Origin ヘッダーが「許可されたWebサイト」と一致しないと 403 になる。
        # アプリ登録時に「許可されたWebサイト」へ www.rakuten.co.jp を入れているので、それを送る。
        origin = settings.rakuten_allowed_origin or "https://www.rakuten.co.jp"
        self._session.headers.update({
            "Origin": origin,
            "Referer": origin + "/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) rakuten-x-room-bot/1.0",
        })

    # ---- 内部 ----
    def _base_params(self) -> dict[str, Any]:
        p: dict[str, Any] = {
            "applicationId": self.s.rakuten_app_id,
            "format": "json",
            "formatVersion": 2,
        }
        if self.s.rakuten_access_key:
            p["accessKey"] = self.s.rakuten_access_key
        if self.s.rakuten_affiliate_id:
            p["affiliateId"] = self.s.rakuten_affiliate_id
        return p

    def _get(self, url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
        wait = time.time() - self._last
        if wait < self.min_interval:
            time.sleep(self.min_interval - wait)
        for attempt in range(retries):
            self._last = time.time()
            r = self._session.get(url, params=params, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise RuntimeError(f"楽天API エラー {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError(f"楽天API リトライ上限: {url}")

    @staticmethod
    def _to_product(item: dict[str, Any], source: str, rank: int | None = None) -> Product:
        imgs = item.get("mediumImageUrls") or []
        img = ""
        if imgs:
            first = imgs[0]
            img = first if isinstance(first, str) else first.get("imageUrl", "")
        return Product(
            item_code=str(item.get("itemCode", "")),
            name=str(item.get("itemName", "")),
            price=int(item.get("itemPrice") or 0),
            item_url=str(item.get("itemUrl", "")),
            affiliate_url=str(item.get("affiliateUrl") or item.get("itemUrl", "")),
            image_url=_enlarge(img),
            shop_name=str(item.get("shopName", "")),
            review_count=int(item.get("reviewCount") or 0),
            review_average=float(item.get("reviewAverage") or 0),
            affiliate_rate=float(item.get("affiliateRate") or 0),
            point_rate=int(item.get("pointRate") or 1),
            catchcopy=str(item.get("catchcopy", "")),
            genre_id=str(item.get("genreId", "")),
            rank=rank,
            source=source,
            caption=str(item.get("itemCaption", ""))[:800],
        )

    # ---- 公開 ----
    def ranking(self, genre_id: int | None = None, age: int | None = None,
                sex: int | None = None, realtime: bool = False, page: int = 1) -> list[Product]:
        p = self._base_params()
        # APIの制約: genreId と age/sex は同時指定不可。realtime と age/sex も同時指定不可。
        if genre_id:
            p["genreId"] = genre_id
        elif age is not None and sex is not None and not realtime:
            p["age"] = age
            p["sex"] = sex
        if realtime:
            p["period"] = "realtime"
        p["page"] = page
        data = self._get(RANKING_URL, p)
        items = data.get("Items") or data.get("items") or []
        sex_label = "" if sex is None else ("f" if sex else "m")
        label = f"ranking:{genre_id or 'all'}:{age or ''}{sex_label}{':rt' if realtime else ''}"
        out = []
        for i, it in enumerate(items, 1):
            it = it.get("Item", it) if isinstance(it, dict) else it
            out.append(self._to_product(it, label, rank=it.get("rank") or i))
        return out

    def search(self, keyword: str | None = None, genre_id: int | None = None,
               min_price: int | None = None, max_price: int | None = None,
               sort: str = "-reviewCount", hits: int = 30, page: int = 1) -> list[Product]:
        p = self._base_params()
        if keyword:
            p["keyword"] = keyword
        if genre_id:
            p["genreId"] = genre_id
        if min_price:
            p["minPrice"] = min_price
        if max_price:
            p["maxPrice"] = max_price
        p["sort"] = sort
        p["hits"] = hits
        p["page"] = page
        p["hasReviewFlag"] = 1
        p["availability"] = 1
        data = self._get(SEARCH_URL, p)
        items = data.get("Items") or data.get("items") or []
        label = f"search:{keyword or genre_id}"
        out = []
        for it in items:
            it = it.get("Item", it) if isinstance(it, dict) else it
            out.append(self._to_product(it, label))
        return out

    def genres(self, genre_id: int = 0) -> list[tuple[int, str]]:
        p = self._base_params()
        p.pop("affiliateId", None)
        p["genreId"] = genre_id
        data = self._get(GENRE_URL, p)
        children = data.get("children") or []
        out = []
        for c in children:
            c = c.get("child", c) if isinstance(c, dict) else c
            out.append((int(c["genreId"]), str(c.get("nameJa") or c.get("genreName", ""))))
        return out

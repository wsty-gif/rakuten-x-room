"""X（公式API v2）への投稿。tweepy 利用。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import requests
import tweepy

from .config import Settings


class XPoster:
    def __init__(self, s: Settings):
        self.s = s
        self.client = tweepy.Client(
            consumer_key=s.x_api_key, consumer_secret=s.x_api_secret,
            access_token=s.x_access_token, access_token_secret=s.x_access_token_secret,
        )
        auth = tweepy.OAuth1UserHandler(s.x_api_key, s.x_api_secret, s.x_access_token, s.x_access_token_secret)
        self.api_v1 = tweepy.API(auth)

    def _upload_image(self, url: str) -> str | None:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            suffix = ".jpg" if "jpg" in url or "jpeg" in url else ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(r.content)
                path = f.name
            media = self.api_v1.media_upload(filename=path)
            Path(path).unlink(missing_ok=True)
            return str(media.media_id)
        except Exception as e:
            print(f"  [warn] 画像アップロード失敗（画像なしで投稿します）: {e}")
            return None

    def post(self, text: str, image_url: str | None = None) -> str:
        media_ids = None
        if image_url and self.s.x_attach_image:
            mid = self._upload_image(image_url)
            if mid:
                media_ids = [mid]
        resp = self.client.create_tweet(text=text, media_ids=media_ids)
        return str(resp.data["id"])

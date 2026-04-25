"""Pollinations.ai 免費圖片生成（無需 API key，FLUX 後端）。

策略：產圖 → 上傳到 Supabase journals bucket（public）→ 回傳 public URL，
讓 LINE ImageMessage 直接 fetch 我們的 CDN，避免依賴 pollinations 即時可用度。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from urllib.parse import quote

import httpx

from . import supabase_client as db

log = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


async def fetch_image(prompt: str, width: int = 1024, height: int = 1024, seed: int | None = None) -> bytes:
    """打 pollinations 直接取 image bytes（FLUX schnell）。可能 5-15 秒。"""
    qs = f"?width={width}&height={height}&model=flux&nologo=true"
    if seed is not None:
        qs += f"&seed={seed}"
    url = f"{POLLINATIONS_BASE}/{quote(prompt)}{qs}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def generate_and_save(prompt: str, *, prefix: str = "gen", width: int = 1024, height: int = 1024) -> str | None:
    """產圖 → 上傳到 journals bucket（public）→ 回 public URL。失敗回 None。"""
    try:
        img_bytes = await fetch_image(prompt, width=width, height=height)
    except Exception as e:  # noqa: BLE001
        log.warning("pollinations fetch failed: %s", e)
        return None

    if len(img_bytes) < 1024:
        log.warning("pollinations returned too small image: %d bytes", len(img_bytes))
        return None

    # 用 prompt hash 當檔名，方便 cache（同 prompt 重複生不會重複上傳）
    h = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]
    path = f"{prefix}/{h}.jpg"
    try:
        url = await db.upload_to_bucket("journals", path, img_bytes, "image/jpeg")
        return url
    except Exception as e:  # noqa: BLE001
        log.warning("upload generated image failed: %s", e)
        return None

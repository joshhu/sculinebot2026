"""圖片：下載 → vision → Lumi 對話反應 → 背景產出風格化版本（Gemini img2img）。"""

from __future__ import annotations

import asyncio
import logging
import random

from linebot.v3.messaging import ImageMessage, TextMessage

from .. import gemini_client, supabase_client as db
from ..line_client import LineAPI
from ..services import entry as entry_svc, trip as trip_svc

log = logging.getLogger(__name__)


# 風格池：每張照片隨機挑一種，避免每張都長一樣
STYLES = [
    ("watercolor", "Repaint as a soft watercolor illustration, kawaii style, pastel palette, no text"),
    ("studio ghibli", "Reimagine in Studio Ghibli style, dreamy lighting, soft details, no text"),
    ("ukiyo-e",  "Restyle as a traditional Japanese ukiyo-e woodblock print, no text"),
    ("crayon",  "Restyle as a child's crayon drawing, vivid colors, paper texture, no text"),
    ("pixar",  "Restyle as a Pixar 3D render, cinematic warm lighting, no text"),
    ("oil painting",  "Restyle as a thick impasto oil painting, expressive brushstrokes, no text"),
    ("cyberpunk", "Restyle as cyberpunk neon-lit night scene, vibrant magenta and cyan, no text"),
]


async def handle(ev) -> None:
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)

    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=20)

        try:
            content = await api.get_message_content(ev.message.id)
        except Exception as e:  # noqa: BLE001
            log.exception("download image failed: %s", e)
            await api.reply_text(ev.reply_token, "嗚 圖片下載失敗，再傳一次試試？")
            return

        path = f"{user_id}/{trip_id or 'no_trip'}/{ev.message.id}.jpg"
        photo_url = await db.upload_to_bucket("media", path, content, "image/jpeg")

        try:
            ai_meta = await gemini_client.vision_describe(content, "image/jpeg")
        except Exception as e:  # noqa: BLE001
            log.exception("vision failed: %s", e)
            ai_meta = {"caption": "（沒看清楚）", "place_guess": None, "food_items": [], "mood_tags": []}

        if trip_id:
            await entry_svc.add_photo(trip_id, photo_url, ai_meta)

        try:
            reply = await gemini_client.react_to_photo(
                ai_meta.get("caption") or "",
                ai_meta.get("place_guess"),
                ai_meta.get("food_items") or [],
                in_trip=bool(trip_id),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("react_to_photo failed: %s", e)
            reply = ai_meta.get("caption") or "看到了～"

        if trip_id:
            await entry_svc.add_text(trip_id, f"【Lumi】{reply}", ai_meta={"role": "assistant"})

        await api.reply(ev.reply_token, [TextMessage(text=reply)])

    # 背景：產出風格化版本，push 過去
    asyncio.create_task(_send_stylized(user_id, ev.message.id, content, trip_id))


async def _send_stylized(user_id: str, message_id: str, original: bytes, trip_id: str | None) -> None:
    style_name, style_prompt = random.choice(STYLES)
    img = await gemini_client.stylize_image(original, style_prompt, "image/jpeg")
    if not img:
        return
    path = f"stylized/{user_id}/{message_id}_{style_name.replace(' ','_')}.jpg"
    url = await db.upload_to_bucket("journals", path, img, "image/jpeg")
    try:
        async with LineAPI() as api:
            await api.push(
                user_id,
                [
                    TextMessage(text=f"順手幫你畫成「{style_name}」風 ✨"),
                    ImageMessage(original_content_url=url, preview_image_url=url),
                ],
            )
    except Exception as e:  # noqa: BLE001
        log.debug("push stylized failed: %s", e)

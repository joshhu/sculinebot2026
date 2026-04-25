"""圖片訊息：下載 → 存 media bucket → Gemini vision → 存 entry → 回確認卡。"""

from __future__ import annotations

import logging
from datetime import datetime

from .. import gemini_client, supabase_client as db
from ..flex import trip_card
from ..line_client import LineAPI, make_flex
from ..services import entry as entry_svc, trip as trip_svc

log = logging.getLogger(__name__)


async def handle(ev) -> None:
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)
    if not trip_id:
        async with LineAPI() as api:
            await api.reply_text(ev.reply_token, "請先用「/開始 旅程名稱」開啟旅程，再傳照片喔")
        return

    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=20)

        try:
            content = await api.get_message_content(ev.message.id)
        except Exception as e:  # noqa: BLE001
            log.exception("download image failed: %s", e)
            await api.reply_text(ev.reply_token, "下載圖片失敗，再傳一次試試")
            return

        # 上傳 media bucket
        path = f"{user_id}/{trip_id}/{ev.message.id}.jpg"
        photo_url = await db.upload_to_bucket("media", path, content, "image/jpeg")

        # Gemini vision
        try:
            ai_meta = await gemini_client.vision_describe(content, "image/jpeg")
        except Exception as e:  # noqa: BLE001
            log.exception("vision failed: %s", e)
            ai_meta = {"caption": "（AI 暫時忙線，照片已存）", "place_guess": None}

        await entry_svc.add_photo(trip_id, photo_url, ai_meta)

        caption = ai_meta.get("caption") or "已記錄"
        place = ai_meta.get("place_guess")
        extra = f"📍 {place}" if place else None

        await api.reply(
            ev.reply_token,
            [make_flex("照片已記錄", trip_card.entry_confirm("📷", caption, extra))],
        )
    log.info("photo entry added: user=%s trip=%s", user_id, trip_id)

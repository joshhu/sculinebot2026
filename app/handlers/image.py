"""圖片：下載 → vision describe → Lumi 對話反應 → 回文字（不再是冷冰冰的確認卡）。"""

from __future__ import annotations

import logging

from linebot.v3.messaging import TextMessage

from .. import gemini_client, supabase_client as db
from ..line_client import LineAPI
from ..services import entry as entry_svc, trip as trip_svc

log = logging.getLogger(__name__)


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

        # 上傳 media bucket（不論有沒有 trip 都先存，可作除錯）
        path = f"{user_id}/{trip_id or 'no_trip'}/{ev.message.id}.jpg"
        photo_url = await db.upload_to_bucket("media", path, content, "image/jpeg")

        try:
            ai_meta = await gemini_client.vision_describe(content, "image/jpeg")
        except Exception as e:  # noqa: BLE001
            log.exception("vision failed: %s", e)
            ai_meta = {"caption": "（沒看清楚）", "place_guess": None, "food_items": [], "mood_tags": []}

        if trip_id:
            await entry_svc.add_photo(trip_id, photo_url, ai_meta)

        # 像朋友看到照片一樣回應
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

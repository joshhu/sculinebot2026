"""語音：下載 → 轉文字 → Lumi 對話回應。"""

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
            log.exception("download audio failed: %s", e)
            await api.reply_text(ev.reply_token, "嗚 語音下載失敗，再傳一次試試？")
            return

        path = f"{user_id}/{trip_id or 'no_trip'}/{ev.message.id}.m4a"
        audio_url = await db.upload_to_bucket("media", path, content, "audio/m4a")

        try:
            transcript = await gemini_client.transcribe_audio(content, "audio/m4a")
        except Exception as e:  # noqa: BLE001
            log.exception("transcribe failed: %s", e)
            transcript = ""

        if not transcript:
            await api.reply_text(ev.reply_token, "我沒聽清楚耶～環境太吵嗎？再說一次？")
            return

        if trip_id:
            await entry_svc.add_audio(trip_id, audio_url, transcript)

        try:
            reply = await gemini_client.react_to_voice(transcript, in_trip=bool(trip_id))
        except Exception as e:  # noqa: BLE001
            log.warning("react_to_voice failed: %s", e)
            reply = "嗯嗯～"

        if trip_id:
            await entry_svc.add_text(trip_id, f"【Lumi】{reply}", ai_meta={"role": "assistant"})

        await api.reply(ev.reply_token, [TextMessage(text=f"🎙 {transcript}\n\n{reply}")])

"""語音訊息：下載 → 存 media bucket → Gemini 轉文字 → 存 entry → 回確認卡。"""

from __future__ import annotations

import logging

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
            await api.reply_text(ev.reply_token, "請先用「/開始 旅程名稱」開啟旅程，再傳語音喔")
        return

    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=20)
        try:
            content = await api.get_message_content(ev.message.id)
        except Exception as e:  # noqa: BLE001
            log.exception("download audio failed: %s", e)
            await api.reply_text(ev.reply_token, "下載語音失敗，再傳一次試試")
            return

        path = f"{user_id}/{trip_id}/{ev.message.id}.m4a"
        audio_url = await db.upload_to_bucket("media", path, content, "audio/m4a")

        try:
            transcript = await gemini_client.transcribe_audio(content, "audio/m4a")
        except Exception as e:  # noqa: BLE001
            log.exception("transcribe failed: %s", e)
            transcript = ""

        if not transcript:
            transcript = "（語音識別失敗，原檔已存）"

        await entry_svc.add_audio(trip_id, audio_url, transcript)

        await api.reply(
            ev.reply_token,
            [
                make_flex(
                    "語音已記錄",
                    trip_card.entry_confirm(
                        "🎙️", transcript[:60] + ("…" if len(transcript) > 60 else "")
                    ),
                )
            ],
        )

"""位置訊息：座標 → Gemini 反查 → 存 entry。"""

from __future__ import annotations

import logging

from linebot.v3.messaging import FlexMessage

from .. import gemini_client
from ..flex import trip_card
from ..line_client import LineAPI
from ..services import entry as entry_svc, trip as trip_svc

log = logging.getLogger(__name__)


async def handle(ev) -> None:
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)
    if not trip_id:
        async with LineAPI() as api:
            await api.reply_text(ev.reply_token, "請先用「/開始 旅程名稱」開啟旅程，再傳位置喔")
        return

    msg = ev.message
    lat, lng = msg.latitude, msg.longitude
    user_label = msg.title or msg.address

    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=10)
        try:
            ai_meta = await gemini_client.reverse_location(lat, lng)
        except Exception as e:  # noqa: BLE001
            log.exception("reverse_location failed: %s", e)
            ai_meta = {"place_name": user_label, "nearby": [], "country": None}

        ai_meta["user_label"] = user_label
        await entry_svc.add_location(trip_id, lat, lng, ai_meta)

        place = ai_meta.get("place_name") or user_label or f"({lat:.4f},{lng:.4f})"
        nearby = ai_meta.get("nearby") or []
        extra = "附近：" + ", ".join(nearby[:3]) if nearby else None

        await api.reply(
            ev.reply_token,
            [
                FlexMessage(
                    alt_text="位置已記錄",
                    contents=trip_card.entry_confirm("📍", place, extra),
                )
            ],
        )

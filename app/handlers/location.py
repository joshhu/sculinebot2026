"""位置：座標 → Gemini 反查地名 + 附近景點 → Lumi 對話回應。"""

from __future__ import annotations

import logging

from linebot.v3.messaging import TextMessage

from .. import gemini_client
from ..line_client import LineAPI
from ..services import entry as entry_svc, trip as trip_svc

log = logging.getLogger(__name__)


async def handle(ev) -> None:
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)

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
        if trip_id:
            await entry_svc.add_location(trip_id, lat, lng, ai_meta)

        place = ai_meta.get("place_name") or user_label or f"({lat:.4f},{lng:.4f})"
        nearby = ai_meta.get("nearby") or []

        try:
            reply = await gemini_client.react_to_location(place, nearby, in_trip=bool(trip_id))
        except Exception as e:  # noqa: BLE001
            log.warning("react_to_location failed: %s", e)
            reply = f"📍 {place}"

        if trip_id:
            await entry_svc.add_text(trip_id, f"【Lumi】{reply}", ai_meta={"role": "assistant"})

        await api.reply(ev.reply_token, [TextMessage(text=reply)])

"""文字訊息處理。

支援指令：
  /開始 [標題]      — 開新旅程
  /結束              — 結束目前旅程並產生遊記
  /我的旅程          — 列出歷史旅程
  其他純文字         — 若有 active trip，存成 text entry
"""

from __future__ import annotations

import logging

from linebot.v3.messaging import (
    FlexMessage,
    QuickReply,
    QuickReplyItem,
    TextMessage,
)
from linebot.v3.messaging.models import MessageAction, PostbackAction

from ..flex import trip_card
from ..line_client import LineAPI
from ..services import entry as entry_svc
from ..services import trip as trip_svc

log = logging.getLogger(__name__)


def _quick_reply_in_trip() -> QuickReply:
    return QuickReply(
        items=[
            QuickReplyItem(
                action=PostbackAction(
                    label="🏁 結束旅程", data="action=close_trip", display_text="結束旅程"
                )
            ),
            QuickReplyItem(
                action=MessageAction(label="📚 我的旅程", text="/我的旅程")
            ),
        ]
    )


async def handle(ev) -> None:
    text = (ev.message.text or "").strip()
    user_id = ev.source.user_id

    if text.startswith("/開始"):
        await _cmd_start(ev, text[len("/開始"):].strip())
        return
    if text.startswith("/結束"):
        await _cmd_close(ev)
        return
    if text.startswith("/我的旅程"):
        await _cmd_list(ev)
        return
    if text.startswith("/"):
        async with LineAPI() as api:
            await api.reply_text(ev.reply_token, "可用指令：/開始 [標題]、/結束、/我的旅程")
        return

    # 一般文字 → 落到 active trip
    trip_id = await trip_svc.get_active_trip_id(user_id)
    if not trip_id:
        async with LineAPI() as api:
            await api.reply_text(
                ev.reply_token, "還沒開始旅程喔～輸入「/開始 旅程名稱」就能上路"
            )
        return

    await entry_svc.add_text(trip_id, text)
    async with LineAPI() as api:
        await api.reply(
            ev.reply_token,
            [
                FlexMessage(
                    alt_text="已記錄",
                    contents=trip_card.entry_confirm("📝", text[:40] + ("…" if len(text) > 40 else "")),
                    quick_reply=_quick_reply_in_trip(),
                )
            ],
        )


async def _cmd_start(ev, title: str) -> None:
    user_id = ev.source.user_id
    title = title or "未命名旅程"
    trip = await trip_svc.start_trip(user_id, title)
    async with LineAPI() as api:
        await api.reply(
            ev.reply_token,
            [
                FlexMessage(
                    alt_text=f"旅程 {title} 已開始",
                    contents=trip_card.trip_started(title),
                    quick_reply=_quick_reply_in_trip(),
                )
            ],
        )
    log.info("trip started: user=%s trip=%s title=%s", user_id, trip["id"], title)


async def _cmd_close(ev) -> None:
    # 委派到 postback handler 的相同邏輯
    from . import postback as h_postback

    await h_postback.close_trip_flow(ev.source.user_id, ev.reply_token)


async def _cmd_list(ev) -> None:
    from .. import supabase_client as db

    trips = await db.list_trips(ev.source.user_id, limit=10)
    async with LineAPI() as api:
        if not trips:
            await api.reply_text(ev.reply_token, "你還沒有任何旅程。輸入「/開始 旅程名稱」開始第一趟吧！")
            return
        await api.reply_flex(ev.reply_token, "我的旅程", trip_card.trips_carousel(trips))

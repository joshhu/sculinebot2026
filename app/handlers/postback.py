"""postback action handler。

支援 data：
  action=close_trip
  action=regenerate_journal
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qs

from linebot.v3.messaging import (
    ConfirmTemplate,
    TemplateMessage,
)
from linebot.v3.messaging.models import PostbackAction

from ..flex import help_carousel, trip_card
from ..line_client import LineAPI
from ..services import journal as journal_svc, trip as trip_svc
from .. import supabase_client as db

log = logging.getLogger(__name__)


async def handle(ev) -> None:
    data = parse_qs(ev.postback.data or "")
    action = (data.get("action") or [""])[0]

    if action == "close_trip_confirm":
        await _close_trip_confirm(ev)
        return
    if action == "close_trip":
        await close_trip_flow(ev.source.user_id, ev.reply_token)
        return
    if action == "regenerate_journal":
        await _regenerate_flow(ev)
        return
    if action == "show_help":
        async with LineAPI() as api:
            await api.reply_flex(ev.reply_token, "說明", help_carousel.build())
        return
    if action == "cancel":
        async with LineAPI() as api:
            await api.reply_text(ev.reply_token, "好的，繼續記錄吧～ 😊")
        return

    async with LineAPI() as api:
        await api.reply_text(ev.reply_token, f"未支援的 action: {action}")


async def _close_trip_confirm(ev) -> None:
    """Confirm template：避免使用者誤觸結束旅程。"""
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)
    async with LineAPI() as api:
        if not trip_id:
            await api.reply_text(ev.reply_token, "你目前沒有進行中的旅程喔～")
            return
        trip = await db.get_trip(trip_id)
        title = (trip or {}).get("title") or "這趟旅程"
        template = ConfirmTemplate(
            text=f"要結束「{title}」並產生遊記嗎？\n結束後就不能再新增紀錄囉。",
            actions=[
                PostbackAction(
                    label="✅ 結束並產生", data="action=close_trip", display_text="結束旅程"
                ),
                PostbackAction(label="❌ 還沒", data="action=cancel", display_text="繼續記錄"),
            ],
        )
        await api.reply(
            ev.reply_token,
            [TemplateMessage(alt_text=f"確定結束「{title}」？", template=template)],
        )


async def close_trip_flow(user_id: str, reply_token: str) -> None:
    """結束旅程：因為 Gemini Pro 可能 > 30 秒，先 reply 處理中，再用 push 補送遊記卡。"""
    trip_id = await trip_svc.get_active_trip_id(user_id)
    async with LineAPI() as api:
        if not trip_id:
            await api.reply_text(reply_token, "你目前沒有進行中的旅程")
            return

        # 立即 reply：避免 reply token 30 秒過期
        await api.reply_text(reply_token, "✍️ AI 正在整理你的旅程，請稍候 30 秒～")

    # 背景處理
    asyncio.create_task(_finalize_and_push(user_id, trip_id))


async def _finalize_and_push(user_id: str, trip_id: str) -> None:
    try:
        md_text, html_url, cover = await journal_svc.generate_and_publish(trip_id)
        await db.close_trip(trip_id, md_text, html_url, cover)
        await db.set_active_trip(user_id, None)
        trip = await db.get_trip(trip_id)
        title = (trip or {}).get("title") or "未命名旅程"
        async with LineAPI() as api:
            await api.push_flex(user_id, "遊記出爐", trip_card.journal_cover(title, html_url, cover))
    except Exception as e:  # noqa: BLE001
        log.exception("finalize trip failed: %s", e)
        async with LineAPI() as api:
            await api.push_text(user_id, f"產生遊記時發生錯誤：{e}")


async def _regenerate_flow(ev) -> None:
    user_id = ev.source.user_id
    # 找最近一個 closed trip
    trips = await db.list_trips(user_id, limit=5)
    target = next((t for t in trips if t.get("status") == "closed"), None)
    async with LineAPI() as api:
        if not target:
            await api.reply_text(ev.reply_token, "找不到可以重新生成的旅程")
            return
        await api.reply_text(ev.reply_token, "🔁 重新生成中，完成後會推給你～")

    asyncio.create_task(_regenerate_task(user_id, target["id"]))


async def _regenerate_task(user_id: str, trip_id: str) -> None:
    try:
        md_text, html_url, cover = await journal_svc.generate_and_publish(trip_id)
        await db.close_trip(trip_id, md_text, html_url, cover)
        trip = await db.get_trip(trip_id)
        title = (trip or {}).get("title") or "未命名旅程"
        async with LineAPI() as api:
            await api.push_flex(user_id, "遊記重生", trip_card.journal_cover(title, html_url, cover))
    except Exception as e:  # noqa: BLE001
        log.exception("regenerate failed: %s", e)
        async with LineAPI() as api:
            await api.push_text(user_id, f"重新生成時發生錯誤：{e}")

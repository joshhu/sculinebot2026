"""follow / unfollow 事件。"""

from __future__ import annotations

import asyncio
import logging

from linebot.v3.messaging import (
    ImageMessage,
    QuickReply,
    QuickReplyItem,
    TextMessage,
)
from linebot.v3.messaging.models import MessageAction

from .. import gemini_client
from .. import supabase_client as db
from ..line_client import LineAPI
from ..services import trip as trip_svc

log = logging.getLogger(__name__)


def _welcome_quick_reply() -> QuickReply:
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="📍 開始一趟旅程", text="/開始 我的旅程")),
        ]
    )


async def handle(ev) -> None:
    user_id = ev.source.user_id
    async with LineAPI() as api:
        try:
            profile = await api.get_profile(user_id)
        except Exception as e:  # noqa: BLE001
            log.warning("get_profile failed: %s", e)
            profile = {"display_name": None, "picture_url": None}

        await trip_svc.ensure_user(user_id, profile.get("display_name"), profile.get("picture_url"))

        name = profile.get("display_name") or "旅人"
        intro = (
            f"嗨 {name}！我是 Lumi 🌿\n"
            "我會陪你記錄旅程、生成遊記。\n"
            "把照片、心情、語音、地點隨便丟給我，旅程結束時我會幫你寫成一本可分享的線上遊記～\n\n"
            "想開始嗎？輸入「/開始 旅程名稱」或點下面的快速回覆 ✨"
        )
        await api.reply(
            ev.reply_token,
            [TextMessage(text=intro, quick_reply=_welcome_quick_reply())],
        )

    asyncio.create_task(_post_welcome_image(user_id))


async def _post_welcome_image(user_id: str) -> None:
    """背景產一張小熊歡迎圖（Gemini Nano Banana 2），用 push 補送。"""
    img = await gemini_client.generate_image(
        "Watercolor illustration. A cute kawaii bear with a camera waving hello. "
        "Cherry blossoms. Soft pastel palette. Square composition. No text."
    )
    if not img:
        return
    url = await db.upload_to_bucket("journals", f"welcome/{user_id}.jpg", img, "image/jpeg")
    try:
        async with LineAPI() as api:
            await api.push(user_id, [ImageMessage(original_content_url=url, preview_image_url=url)])
    except Exception as e:  # noqa: BLE001
        log.debug("push welcome image failed: %s", e)


async def handle_unfollow(ev) -> None:
    log.info("user %s unfollowed", ev.source.user_id)

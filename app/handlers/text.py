"""文字訊息：以 Lumi 人格對話。

支援指令：
  /開始 [標題]      — 開新旅程，順手生一張封面圖
  /結束              — 結束目前旅程並產生遊記
  /我的旅程          — 列出歷史旅程

非指令文字 → 以 Lumi 對話回覆（並落到 active trip 當作心得）
"""

from __future__ import annotations

import asyncio
import logging

from linebot.v3.messaging import (
    ImageMessage,
    QuickReply,
    QuickReplyItem,
    TextMessage,
)
from linebot.v3.messaging.models import MessageAction, PostbackAction

from .. import gemini_client, supabase_client as db
from ..flex import trip_card
from ..line_client import LineAPI, make_flex
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
            QuickReplyItem(action=MessageAction(label="📚 我的旅程", text="/我的旅程")),
        ]
    )


def _quick_reply_idle() -> QuickReply:
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="📍 開始旅程", text="/開始 我的旅程")),
            QuickReplyItem(action=MessageAction(label="📚 我的旅程", text="/我的旅程")),
        ]
    )


async def handle(ev) -> None:
    text = (ev.message.text or "").strip()
    if not text:
        return

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

    await _chat(ev, text)


# ---- 純對話（含落到 active trip） ----

async def _chat(ev, text: str) -> None:
    user_id = ev.source.user_id
    trip_id = await trip_svc.get_active_trip_id(user_id)

    history: list[dict] = []
    if trip_id:
        history = await db.list_entries(trip_id)

    # Loading + 並行：取對話回覆
    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=15)
        reply = await gemini_client.chat_reply(text, history, in_trip=bool(trip_id))

        # 寫紀錄：使用者話 + Lumi 回應，都串進 entries
        if trip_id:
            await entry_svc.add_text(trip_id, text)
            await entry_svc.add_text(trip_id, f"【Lumi】{reply}", ai_meta={"role": "assistant"})

        qr = _quick_reply_in_trip() if trip_id else _quick_reply_idle()
        await api.reply(ev.reply_token, [TextMessage(text=reply, quick_reply=qr)])


# ---- /開始 ----

async def _cmd_start(ev, title: str) -> None:
    user_id = ev.source.user_id
    title = title or "我的旅程"
    trip = await trip_svc.start_trip(user_id, title)

    # 立即先回 Flex 卡（30 秒內必回）
    async with LineAPI() as api:
        await api.show_loading(user_id, seconds=15)
        await api.reply(
            ev.reply_token,
            [
                make_flex(
                    f"旅程 {title} 已開始",
                    trip_card.trip_started(title),
                    quick_reply=_quick_reply_in_trip(),
                ),
                TextMessage(text=f"耶～「{title}」開動！跟我聊聊你準備去哪、想看什麼嘛 🌿"),
            ],
        )

    # 背景：產一張封面圖 + Lumi 開場白，用 push 補送
    asyncio.create_task(_post_start_cover(user_id, trip["id"], title))


async def _post_start_cover(user_id: str, trip_id: str, title: str) -> None:
    """背景產旅程封面圖（Gemini Nano Banana 2）。"""
    prompt = (
        f"Travel diary cover illustration for a trip titled '{title}'. "
        "Watercolor style, soft pastel colors, kawaii elements, scenic background. "
        "Square composition. No text."
    )
    img = await gemini_client.generate_image(prompt)
    if not img:
        return
    url = await db.upload_to_bucket("journals", f"covers/{trip_id}.jpg", img, "image/jpeg")
    try:
        c = db.get_client()
        c.table("trips").update({"cover_photo_url": url}).eq("id", trip_id).execute()
    except Exception:  # noqa: BLE001
        pass
    try:
        async with LineAPI() as api:
            await api.push(
                user_id,
                [
                    ImageMessage(original_content_url=url, preview_image_url=url),
                    TextMessage(text="🎨 我幫你畫了張封面～你今天想從哪裡開始？"),
                ],
            )
    except Exception as e:  # noqa: BLE001
        log.debug("push cover failed: %s", e)


# ---- /結束 ----

async def _cmd_close(ev) -> None:
    from . import postback as h_postback

    await h_postback.close_trip_flow(ev.source.user_id, ev.reply_token)


# ---- /我的旅程 ----

async def _cmd_list(ev) -> None:
    trips = await db.list_trips(ev.source.user_id, limit=10)
    async with LineAPI() as api:
        if not trips:
            await api.reply_text(ev.reply_token, "你還沒有任何旅程耶～想開始一趟嗎？輸入「/開始 旅程名稱」就行！")
            return
        await api.reply_flex(ev.reply_token, "我的旅程", trip_card.trips_carousel(trips))

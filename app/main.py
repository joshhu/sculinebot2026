"""FastAPI app — LINE webhook for AI 旅遊日記."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    AudioMessageContent,
    FollowEvent,
    ImageMessageContent,
    LocationMessageContent,
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
    UnfollowEvent,
)

from . import supabase_client as db
from .config import get_settings
from .handlers import audio as h_audio
from .handlers import follow as h_follow
from .handlers import image as h_image
from .handlers import location as h_location
from .handlers import postback as h_postback
from .handlers import text as h_text
from .line_client import LineAPI, get_parser

log = logging.getLogger("sculinebot")
logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

app = FastAPI(title="sculinebot2026", version="0.1.0")


@app.get("/")
async def root() -> dict:
    return {"app": "sculinebot2026", "ok": True}


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(default="")) -> JSONResponse:
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8")

    parser = get_parser()
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="invalid signature")
    except Exception as e:  # noqa: BLE001
        log.exception("webhook parse error: %s", e)
        raise HTTPException(status_code=400, detail="parse error")

    for ev in events:
        try:
            await _dispatch(ev)
        except Exception as e:  # noqa: BLE001
            log.exception("handler error on %s: %s", type(ev).__name__, e)

    return JSONResponse({"ok": True})


async def _lazy_fill_profile(user_id: str) -> None:
    """背景：若使用者沒有 display_name（例如舊好友未觸發 follow），補抓一次。"""
    try:
        existing = await db.get_user(user_id)
        if existing and existing.get("display_name"):
            return
        async with LineAPI() as api:
            p = await api.get_profile(user_id)
        await db.upsert_user(user_id, p.get("display_name"), p.get("picture_url"))
    except Exception as e:  # noqa: BLE001
        log.debug("lazy profile fill skipped: %s", e)


async def _dispatch(ev) -> None:
    # 進來的事件先 ensure user 存在（FK 保護），背景補 profile。
    src = getattr(ev, "source", None)
    user_id = getattr(src, "user_id", None) if src else None
    if user_id:
        await db.ensure_user_exists(user_id)
        asyncio.create_task(_lazy_fill_profile(user_id))

    if isinstance(ev, FollowEvent):
        await h_follow.handle(ev)
        return
    if isinstance(ev, UnfollowEvent):
        await h_follow.handle_unfollow(ev)
        return
    if isinstance(ev, PostbackEvent):
        await h_postback.handle(ev)
        return
    if isinstance(ev, MessageEvent):
        msg = ev.message
        if isinstance(msg, TextMessageContent):
            await h_text.handle(ev)
        elif isinstance(msg, ImageMessageContent):
            await h_image.handle(ev)
        elif isinstance(msg, AudioMessageContent):
            await h_audio.handle(ev)
        elif isinstance(msg, LocationMessageContent):
            await h_location.handle(ev)
        else:
            log.info("unsupported message type: %s", type(msg).__name__)
        return
    log.info("unhandled event: %s", type(ev).__name__)

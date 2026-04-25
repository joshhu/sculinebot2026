"""FastAPI app — LINE webhook for AI 旅遊日記."""

from __future__ import annotations

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

from .config import get_settings
from .handlers import audio as h_audio
from .handlers import follow as h_follow
from .handlers import image as h_image
from .handlers import location as h_location
from .handlers import postback as h_postback
from .handlers import text as h_text
from .line_client import get_parser

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


async def _dispatch(ev) -> None:
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

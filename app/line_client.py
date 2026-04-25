"""LINE Messaging API thin wrappers (line-bot-sdk v3)."""

from __future__ import annotations

import logging
from typing import Any

from linebot.v3.messaging import (
    ApiClient,
    AsyncApiClient,
    AsyncMessagingApi,
    AsyncMessagingApiBlob,
    Configuration,
    FlexMessage,
    Message,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser

from .config import get_settings

log = logging.getLogger(__name__)


def _config() -> Configuration:
    return Configuration(access_token=get_settings().line_channel_access_token)


def get_parser() -> WebhookParser:
    return WebhookParser(get_settings().line_channel_secret)


# --- Sync helpers (used in sync handlers / scripts) ---

def sync_api() -> MessagingApi:
    return MessagingApi(ApiClient(_config()))


def sync_blob() -> MessagingApiBlob:
    return MessagingApiBlob(ApiClient(_config()))


# --- Async helpers (used inside FastAPI request handlers) ---

class LineAPI:
    """One-shot async wrapper. Always use as `async with LineAPI() as api: ...`."""

    def __init__(self) -> None:
        self._client: AsyncApiClient | None = None

    async def __aenter__(self) -> "LineAPI":
        self._client = AsyncApiClient(_config())
        self.api = AsyncMessagingApi(self._client)
        self.blob = AsyncMessagingApiBlob(self._client)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.close()

    async def reply(self, reply_token: str, messages: list[Message]) -> None:
        await self.api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages)
        )

    async def reply_text(self, reply_token: str, text: str) -> None:
        await self.reply(reply_token, [TextMessage(text=text)])

    async def reply_flex(self, reply_token: str, alt: str, contents: dict) -> None:
        await self.reply(reply_token, [FlexMessage(alt_text=alt, contents=contents)])

    async def push(self, to: str, messages: list[Message]) -> None:
        await self.api.push_message(PushMessageRequest(to=to, messages=messages))

    async def push_text(self, to: str, text: str) -> None:
        await self.push(to, [TextMessage(text=text)])

    async def push_flex(self, to: str, alt: str, contents: dict) -> None:
        await self.push(to, [FlexMessage(alt_text=alt, contents=contents)])

    async def show_loading(self, chat_id: str, seconds: int = 20) -> None:
        try:
            await self.api.show_loading_animation(
                ShowLoadingAnimationRequest(chatId=chat_id, loadingSeconds=seconds)
            )
        except Exception as e:  # noqa: BLE001
            log.debug("show_loading failed: %s", e)

    async def get_message_content(self, message_id: str) -> bytes:
        return await self.blob.get_message_content(message_id=message_id)

    async def get_profile(self, user_id: str) -> dict:
        p = await self.api.get_profile(user_id)
        return {
            "user_id": p.user_id,
            "display_name": p.display_name,
            "picture_url": p.picture_url,
        }

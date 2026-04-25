"""follow / unfollow 事件。"""

from __future__ import annotations

import logging

from ..flex import welcome
from ..line_client import LineAPI
from ..services import trip as trip_svc

log = logging.getLogger(__name__)


async def handle(ev) -> None:
    user_id = ev.source.user_id
    async with LineAPI() as api:
        try:
            profile = await api.get_profile(user_id)
        except Exception as e:  # noqa: BLE001
            log.warning("get_profile failed: %s", e)
            profile = {"display_name": None, "picture_url": None}

        await trip_svc.ensure_user(user_id, profile.get("display_name"), profile.get("picture_url"))
        await api.reply_flex(ev.reply_token, "歡迎加入 AI 旅遊日記", welcome.build(profile.get("display_name")))


async def handle_unfollow(ev) -> None:
    log.info("user %s unfollowed", ev.source.user_id)
    # 暫不刪資料；保留以利使用者再加好友時還原

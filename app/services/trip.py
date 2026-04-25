"""旅程相關的 service 函式。"""

from __future__ import annotations

from .. import supabase_client as db


async def get_active_trip_id(line_user_id: str) -> str | None:
    user = await db.get_user(line_user_id)
    return user.get("active_trip_id") if user else None


async def ensure_user(line_user_id: str, display_name: str | None, picture_url: str | None) -> None:
    await db.upsert_user(line_user_id, display_name, picture_url)


async def start_trip(line_user_id: str, title: str) -> dict:
    return await db.create_trip(line_user_id, title)


async def stop_active_trip(line_user_id: str) -> None:
    await db.set_active_trip(line_user_id, None)

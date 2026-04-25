"""寫入單筆 trip_entries 的 service 包裝。"""

from __future__ import annotations

from .. import supabase_client as db


async def add_text(trip_id: str, raw_text: str, ai_meta: dict | None = None) -> dict:
    return await db.insert_entry(trip_id, "text", raw_text=raw_text, ai_meta=ai_meta)


async def add_photo(trip_id: str, photo_url: str, ai_meta: dict) -> dict:
    return await db.insert_entry(trip_id, "photo", photo_url=photo_url, ai_meta=ai_meta)


async def add_audio(trip_id: str, audio_url: str, transcript: str) -> dict:
    return await db.insert_entry(
        trip_id, "audio", audio_url=audio_url, raw_text=transcript, ai_meta={"transcript": transcript}
    )


async def add_location(trip_id: str, lat: float, lng: float, ai_meta: dict) -> dict:
    return await db.insert_entry(trip_id, "location", lat=lat, lng=lng, ai_meta=ai_meta)

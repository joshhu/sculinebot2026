"""Supabase wrapper：CRUD 與 Storage 上傳。

說明：supabase-py 同步 client 即可滿足需求；handler 內以 `await asyncio.to_thread`
呼叫，避免阻塞 event loop。
"""

from __future__ import annotations

import asyncio
import mimetypes
from datetime import datetime
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from .config import get_settings


@lru_cache
def get_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


# ---------- users ----------

async def upsert_user(line_user_id: str, display_name: str | None, picture_url: str | None) -> None:
    def _do() -> None:
        get_client().table("users").upsert(
            {
                "line_user_id": line_user_id,
                "display_name": display_name,
                "picture_url": picture_url,
            },
            on_conflict="line_user_id",
        ).execute()

    await asyncio.to_thread(_do)


async def get_user(line_user_id: str) -> dict | None:
    def _do() -> dict | None:
        r = (
            get_client()
            .table("users")
            .select("*")
            .eq("line_user_id", line_user_id)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    return await asyncio.to_thread(_do)


async def set_active_trip(line_user_id: str, trip_id: str | None) -> None:
    def _do() -> None:
        get_client().table("users").update({"active_trip_id": trip_id}).eq(
            "line_user_id", line_user_id
        ).execute()

    await asyncio.to_thread(_do)


# ---------- trips ----------

async def create_trip(line_user_id: str, title: str) -> dict:
    def _do() -> dict:
        r = (
            get_client()
            .table("trips")
            .insert({"user_id": line_user_id, "title": title, "status": "active"})
            .execute()
        )
        return r.data[0]

    trip = await asyncio.to_thread(_do)
    await set_active_trip(line_user_id, trip["id"])
    return trip


async def close_trip(trip_id: str, summary_md: str, html_url: str, cover_url: str | None) -> None:
    def _do() -> None:
        get_client().table("trips").update(
            {
                "status": "closed",
                "ended_at": datetime.utcnow().isoformat() + "Z",
                "summary_md": summary_md,
                "summary_html_url": html_url,
                "cover_photo_url": cover_url,
            }
        ).eq("id", trip_id).execute()

    await asyncio.to_thread(_do)


async def get_trip(trip_id: str) -> dict | None:
    def _do() -> dict | None:
        r = get_client().table("trips").select("*").eq("id", trip_id).limit(1).execute()
        return r.data[0] if r.data else None

    return await asyncio.to_thread(_do)


async def list_trips(line_user_id: str, limit: int = 10) -> list[dict]:
    def _do() -> list[dict]:
        r = (
            get_client()
            .table("trips")
            .select("*")
            .eq("user_id", line_user_id)
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    return await asyncio.to_thread(_do)


# ---------- entries ----------

async def insert_entry(
    trip_id: str,
    kind: str,
    *,
    raw_text: str | None = None,
    photo_url: str | None = None,
    audio_url: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    ai_meta: dict | None = None,
) -> dict:
    def _do() -> dict:
        r = (
            get_client()
            .table("trip_entries")
            .insert(
                {
                    "trip_id": trip_id,
                    "kind": kind,
                    "raw_text": raw_text,
                    "photo_url": photo_url,
                    "audio_url": audio_url,
                    "lat": lat,
                    "lng": lng,
                    "ai_meta": ai_meta,
                }
            )
            .execute()
        )
        return r.data[0]

    return await asyncio.to_thread(_do)


async def list_entries(trip_id: str) -> list[dict]:
    def _do() -> list[dict]:
        r = (
            get_client()
            .table("trip_entries")
            .select("*")
            .eq("trip_id", trip_id)
            .order("ts")
            .execute()
        )
        return r.data or []

    return await asyncio.to_thread(_do)


# ---------- storage ----------

async def upload_to_bucket(bucket: str, path: str, data: bytes, content_type: str | None = None) -> str:
    """Upload bytes，回傳 public URL（journals）或 signed URL（media）。"""

    def _do() -> str:
        c = get_client().storage.from_(bucket)
        ct = content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        c.upload(path=path, file=data, file_options={"content-type": ct, "upsert": "true"})
        if bucket == "journals":
            return c.get_public_url(path)
        # media (private) → 7 天 signed URL
        signed = c.create_signed_url(path, 60 * 60 * 24 * 7)
        return signed.get("signedURL") or signed.get("signedUrl") or ""

    return await asyncio.to_thread(_do)


# ---------- helpers ----------

def _now_path(prefix: str, ext: str) -> str:
    """`<prefix>/<YYYY/MM/DD>/<ts>.ext`"""
    now = datetime.utcnow()
    return f"{prefix}/{now:%Y/%m/%d}/{now:%Y%m%dT%H%M%S%f}.{ext}"

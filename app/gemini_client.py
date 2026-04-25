"""Google Gemini wrapper：影像、語音、文字。

採 google-genai SDK（>= 1.0）。所有呼叫 wrap 進 `asyncio.to_thread` 以免阻塞。
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types

from .config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


# ---------- 影像理解 ----------

VISION_PROMPT = (
    "你是旅遊紀錄助理。請根據這張照片產出 JSON，鍵為：\n"
    "  caption: 一句不超過 30 字的中文圖片描述（繁體台灣用語）\n"
    "  place_guess: 推測的景點/地點名稱（不確定填 null）\n"
    "  food_items: 若是食物，列出品項陣列；非食物為 []\n"
    "  mood_tags: 1-3 個情境標籤陣列，例如 ['夕陽', '海邊']\n"
    "只輸出 JSON，不要包 markdown。"
)


async def vision_describe(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    def _do() -> dict:
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                VISION_PROMPT,
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        try:
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001
            log.warning("vision JSON parse failed: %s", e)
            return {"caption": resp.text[:60], "place_guess": None, "food_items": [], "mood_tags": []}

    return await asyncio.to_thread(_do)


# ---------- 語音轉文字 ----------

async def transcribe_audio(audio_bytes: bytes, mime: str = "audio/m4a") -> str:
    def _do() -> str:
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime),
                "請將這段語音以繁體中文台灣用語逐字稿輸出，只輸出文字，不要加任何說明。",
            ],
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_do)


# ---------- 位置反查 ----------

async def reverse_location(lat: float, lng: float) -> dict:
    def _do() -> dict:
        prompt = (
            f"座標：lat={lat}, lng={lng}\n"
            "請以 JSON 回傳：{place_name: 最有可能的地名(中文), nearby: [3 個附近知名景點/餐廳], country: 國家}。\n"
            "若不確定填 null。只輸出 JSON。"
        )
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        try:
            return json.loads(resp.text)
        except Exception:  # noqa: BLE001
            return {"place_name": None, "nearby": [], "country": None}

    return await asyncio.to_thread(_do)


# ---------- 遊記生成 ----------

JOURNAL_SYSTEM = (
    "你是旅遊作家。根據使用者整趟旅程的紀錄（含照片描述、心得、地點、語音逐字稿），"
    "撰寫一篇結構良好的繁體中文遊記。\n"
    "規範：\n"
    "1. 用 Markdown 格式，標題用一級 #；按日期或地點分章用二級 ##\n"
    "2. 每章開頭引用一張代表照片，格式 `![描述](URL)`\n"
    "3. 文字風格自然、有畫面感、不油膩\n"
    "4. 結尾加一段 200 字內的旅程總感想\n"
    "5. 全文 800-2000 字，視素材多寡調整\n"
    "6. 只輸出 Markdown 本體，不要任何前言或後記說明"
)


async def generate_journal(trip_title: str, entries: list[dict]) -> str:
    def _do() -> str:
        material = json.dumps(entries, ensure_ascii=False, indent=2)
        prompt = f"旅程標題：{trip_title}\n\n素材（依時間排序）：\n{material}\n\n請產出 Markdown 遊記。"
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_pro,
            contents=[prompt],
            config=types.GenerateContentConfig(system_instruction=JOURNAL_SYSTEM),
        )
        return resp.text or ""

    return await asyncio.to_thread(_do)

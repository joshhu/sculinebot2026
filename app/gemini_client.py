"""Google Gemini wrapper（3.1 系列）。

採 google-genai SDK，使用：
- `response_json_schema` + Pydantic 模型強制結構化輸出（取代舊的 response_mime_type hint）
- `thinking_config` 控制推理深度（Gemini 3.x 特色）
- 多模態輸入用 `types.Part.from_bytes`

所有呼叫 wrap 進 `asyncio.to_thread` 以免阻塞 event loop。
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


# ---------- Pydantic 結構 ----------

class VisionDescription(BaseModel):
    caption: str = Field(description="一句不超過 30 字的中文圖片描述（繁體台灣用語）")
    place_guess: str | None = Field(default=None, description="推測的景點/地點名稱；不確定填 null")
    food_items: list[str] = Field(default_factory=list, description="若是食物，列出品項；非食物為空陣列")
    mood_tags: list[str] = Field(default_factory=list, description="1-3 個情境標籤，例如 ['夕陽', '海邊']")


class LocationReverse(BaseModel):
    place_name: str | None
    nearby: list[str] = Field(default_factory=list)
    country: str | None = None


# ---------- 共用 helper ----------

def _thinking(level: str | None) -> types.ThinkingConfig | None:
    """3.x 模型的 thinking_level：LOW / MEDIUM / HIGH。傳 None 則不附 thinking_config。"""
    if level is None:
        return None
    return types.ThinkingConfig(thinking_level=getattr(types.ThinkingLevel, level))


# ---------- 影像理解 ----------

VISION_PROMPT = "請根據這張照片產出符合 schema 的 JSON。caption 要用繁體中文台灣用語。"


async def vision_describe(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    def _do() -> dict:
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                VISION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VisionDescription,
                thinking_config=_thinking("LOW"),
            ),
        )
        # SDK 已 parse 為 Pydantic 物件可直接讀；若版本較舊則 fallback
        if getattr(resp, "parsed", None) is not None:
            return resp.parsed.model_dump()
        try:
            return VisionDescription.model_validate_json(resp.text).model_dump()
        except Exception as e:  # noqa: BLE001
            log.warning("vision schema parse failed: %s; raw=%s", e, (resp.text or "")[:120])
            return {
                "caption": (resp.text or "")[:60] or "（無描述）",
                "place_guess": None,
                "food_items": [],
                "mood_tags": [],
            }

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
            config=types.GenerateContentConfig(thinking_config=_thinking("LOW")),
        )
        return (resp.text or "").strip()

    return await asyncio.to_thread(_do)


# ---------- 位置反查 ----------

async def reverse_location(lat: float, lng: float) -> dict:
    def _do() -> dict:
        prompt = (
            f"座標：lat={lat}, lng={lng}\n"
            "請以繁體中文台灣用語回傳：place_name（最有可能的地名）、"
            "nearby（3 個附近知名景點/餐廳）、country（國家）。不確定的欄位填 null。"
        )
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LocationReverse,
                thinking_config=_thinking("LOW"),
            ),
        )
        if getattr(resp, "parsed", None) is not None:
            return resp.parsed.model_dump()
        try:
            return LocationReverse.model_validate_json(resp.text).model_dump()
        except Exception:  # noqa: BLE001
            return {"place_name": None, "nearby": [], "country": None}

    return await asyncio.to_thread(_do)


# ---------- 圖片生成（Nano Banana 2） ----------

async def generate_image(prompt: str) -> bytes | None:
    """純文字產圖。回傳 image bytes（JPEG/PNG），失敗回 None。"""

    def _do() -> bytes | None:
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_image,
            contents=[prompt],
        )
        for p in resp.candidates[0].content.parts:
            if getattr(p, "inline_data", None) and p.inline_data.data:
                return p.inline_data.data
        return None

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:  # noqa: BLE001
        log.warning("generate_image failed: %s", e)
        return None


async def stylize_image(image_bytes: bytes, prompt: str, mime: str = "image/jpeg") -> bytes | None:
    """圖生圖：基於使用者照片產出風格化版本。"""

    def _do() -> bytes | None:
        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_image,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                prompt,
            ],
        )
        for p in resp.candidates[0].content.parts:
            if getattr(p, "inline_data", None) and p.inline_data.data:
                return p.inline_data.data
        return None

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:  # noqa: BLE001
        log.warning("stylize_image failed: %s", e)
        return None


# ---------- 對話人格 Lumi ----------

LUMI_PERSONA = """你是「Lumi」，一個活潑可愛的旅伴 AI，會陪使用者一起記錄旅程。

# 個性
- 像朋友一樣，好奇、會主動問問題、給建議
- 用繁體中文台灣口語，可以加適度表情符號（不要太多）
- 用「欸」「哇」「我覺得」「好讚」這種口語
- 有畫面感，不要說官腔

# 規則
1. 每則回覆 50 字以內，簡短自然
2. 不要說「已記錄」「已儲存」「資料已成功寫入」這種機器話
3. 收到照片/語音/位置時，給出像朋友看到一樣的真實反應，並追問或給建議
4. 如果使用者沒在旅程中，輕輕暗示可以開始一趟，不要硬推
5. 每次只回一段，不要分點
6. 不要用 markdown / 列表 / 程式碼框
7. 可以反問、給延伸建議，例如「附近有 OO 也很值得去」「下一站打算去哪？」
"""


async def chat_reply(user_text: str, recent_entries: list[dict] | None = None, *, in_trip: bool = False) -> str:
    """以 Lumi 人格回覆。recent_entries 提供最近上下文。"""

    def _do() -> str:
        ctx_lines: list[str] = []
        if recent_entries:
            for e in recent_entries[-6:]:
                kind = e.get("kind")
                if kind == "text":
                    ctx_lines.append(f"使用者說：{e.get('raw_text','')}")
                elif kind == "photo":
                    cap = (e.get("ai_meta") or {}).get("caption") or "一張照片"
                    ctx_lines.append(f"使用者傳了照片：{cap}")
                elif kind == "audio":
                    ctx_lines.append(f"使用者語音：{(e.get('raw_text') or '')[:60]}")
                elif kind == "location":
                    place = (e.get("ai_meta") or {}).get("place_name") or "某個地點"
                    ctx_lines.append(f"使用者打卡：{place}")

        ctx = "\n".join(ctx_lines) if ctx_lines else "（這是對話的開頭）"
        state = "（目前在旅程中）" if in_trip else "（目前沒有進行中的旅程）"
        prompt = f"# 最近的對話脈絡\n{ctx}\n\n# 狀態\n{state}\n\n# 使用者剛剛說\n{user_text}\n\n請以 Lumi 的口吻回覆。"

        resp = get_client().models.generate_content(
            model=get_settings().gemini_model_fast,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=LUMI_PERSONA,
                thinking_config=_thinking("LOW"),
            ),
        )
        return (resp.text or "").strip() or "嗯嗯～繼續說 😊"

    return await asyncio.to_thread(_do)


async def react_to_photo(caption: str, place: str | None, food_items: list[str], in_trip: bool) -> str:
    """看到照片時的口語反應。"""
    facts = f"照片內容：{caption}"
    if place:
        facts += f"\n推測地點：{place}"
    if food_items:
        facts += f"\n食物：{', '.join(food_items)}"
    return await chat_reply(facts, in_trip=in_trip)


async def react_to_voice(transcript: str, in_trip: bool) -> str:
    """聽到語音時的回應。"""
    return await chat_reply(f"（這是語音轉文字）{transcript}", in_trip=in_trip)


async def react_to_location(place: str, nearby: list[str], in_trip: bool) -> str:
    """看到打卡位置時的反應。"""
    msg = f"使用者剛剛打卡到：{place}"
    if nearby:
        msg += f"\n附近知名的有：{', '.join(nearby[:3])}"
    return await chat_reply(msg, in_trip=in_trip)


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
            config=types.GenerateContentConfig(
                system_instruction=JOURNAL_SYSTEM,
                thinking_config=_thinking("HIGH"),
            ),
        )
        return resp.text or ""

    return await asyncio.to_thread(_do)

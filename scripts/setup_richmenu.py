"""一次性腳本：建立 + 上傳 Rich Menu。

設計：
- 2500 x 1686，3 欄 2 列
- 6 顆插畫圖示由 Gemini Nano Banana 2 即時產出（同一風格 prompt 前綴保持一致）
- PIL 合成卡片（白底圓角 + 陰影 + 圖示 + 中文標籤）
- Action 多樣：MessageAction / PostbackAction / CameraAction / CameraRollAction

執行：`uv run python scripts/setup_richmenu.py`
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import httpx
from google import genai
from google.genai import types as gemini_types
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
)
from linebot.v3.messaging.models import (
    CameraAction,
    CameraRollAction,
    MessageAction,
    PostbackAction,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402

WIDTH, HEIGHT = 2500, 1686
COLS, ROWS = 3, 2
CELL_W, CELL_H = WIDTH // COLS, HEIGHT // ROWS

# 統一的視覺風格 prompt 前綴，確保 6 顆圖示風格一致
STYLE_PREFIX = (
    "A single isolated icon, soft watercolor illustration, kawaii japanese style, "
    "pastel colors with subtle texture, centered on a clean off-white background "
    "(#F8F4ED), no text, no border, square composition. The subject is: "
)

CELLS = [
    {
        "key": "start",
        "label": "開始旅程",
        "subtitle": "/開始",
        "color": "#4A90E2",
        "icon_prompt": "a sparkling pink map pin with a small cherry blossom petal floating beside it",
        "action": MessageAction(label="開始旅程", text="/開始 我的旅程"),
    },
    {
        "key": "close",
        "label": "結束旅程",
        "subtitle": "產生遊記",
        "color": "#E2645B",
        "icon_prompt": "a small checkered finish flag with confetti particles around it",
        "action": PostbackAction(
            label="結束旅程", data="action=close_trip_confirm", display_text="結束旅程"
        ),
    },
    {
        "key": "list",
        "label": "我的旅程",
        "subtitle": "歷史紀錄",
        "color": "#7B61FF",
        "icon_prompt": "a small stack of three travel diary books in different pastel colors",
        "action": MessageAction(label="我的旅程", text="/我的旅程"),
    },
    {
        "key": "camera",
        "label": "立即拍照",
        "subtitle": "開啟相機",
        "color": "#36B37E",
        "icon_prompt": "a cute vintage instant camera with a heart-shaped flash",
        "action": CameraAction(label="拍照"),
    },
    {
        "key": "album",
        "label": "相簿選照",
        "subtitle": "開啟相簿",
        "color": "#FFAB00",
        "icon_prompt": "a stack of polaroid photos scattered with one slightly tilted",
        "action": CameraRollAction(label="相簿"),
    },
    {
        "key": "help",
        "label": "說明 & 設定",
        "subtitle": "怎麼用？",
        "color": "#00B8D9",
        "icon_prompt": "a glowing yellow lightbulb with small sparkles around it",
        "action": PostbackAction(
            label="說明", data="action=show_help", display_text="看看怎麼用"
        ),
    },
]


# --------------- 字體 ---------------

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


# --------------- 圖示產生 ---------------

def gen_icon(client: genai.Client, model: str, subject_prompt: str) -> Image.Image:
    full_prompt = STYLE_PREFIX + subject_prompt
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=model, contents=[full_prompt])
            for p in resp.candidates[0].content.parts:
                if getattr(p, "inline_data", None) and p.inline_data.data:
                    return Image.open(io.BytesIO(p.inline_data.data)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  retry {attempt+1}/3: {e}")
            time.sleep(2)
    raise RuntimeError(f"icon gen failed after retries: {last_err}")


# --------------- 卡片合成 ---------------

def render_menu(icons: list[Image.Image]) -> bytes:
    bg = Image.new("RGB", (WIDTH, HEIGHT), "#F8F4ED")
    draw = ImageDraw.Draw(bg)

    # 背景做一個淡淡的暈染
    overlay = Image.new("RGB", (WIDTH, HEIGHT), "#F8F4ED")
    od = ImageDraw.Draw(overlay)
    for i in range(0, WIDTH, 80):
        od.line([(i, 0), (i, HEIGHT)], fill=(248, 244, 237), width=1)
    bg = Image.blend(bg, overlay, 0.0)
    draw = ImageDraw.Draw(bg)

    f_label = _load_font(98)
    f_sub = _load_font(50)

    margin = 32
    for i, cell in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        x0, y0 = col * CELL_W, row * CELL_H
        x1, y1 = x0 + CELL_W, y0 + CELL_H

        # 1) 陰影層
        shadow = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            [margin + 8, margin + 14, CELL_W - margin + 8, CELL_H - margin + 14],
            radius=44,
            fill=(0, 0, 0, 36),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        bg.paste(shadow, (x0, y0), shadow)

        # 2) 卡片底
        card_bbox = [x0 + margin, y0 + margin, x1 - margin, y1 - margin]
        draw.rounded_rectangle(card_bbox, radius=44, fill="#FFFFFF")

        # 3) 上方有顏色的小色帶
        accent_h = 14
        accent = Image.new("RGB", (CELL_W - margin * 2, accent_h), cell["color"])
        bg.paste(accent, (x0 + margin, y0 + margin))
        # 把色帶下方接圓角
        draw.rectangle(
            [x0 + margin, y0 + margin + accent_h - 1, x1 - margin, y0 + margin + accent_h + 6],
            fill="#FFFFFF",
        )

        # 4) icon
        icon = icons[i]
        # 內框：扣掉色帶區
        inner_top = y0 + margin + accent_h + 24
        inner_bottom = y0 + CELL_H - margin - 220
        avail_h = inner_bottom - inner_top
        avail_w = CELL_W - margin * 2 - 60
        icon_size = min(avail_h, avail_w)
        icon_resized = icon.resize((icon_size, icon_size), Image.LANCZOS)
        ix = x0 + (CELL_W - icon_size) // 2
        iy = inner_top + (avail_h - icon_size) // 2
        bg.paste(icon_resized, (ix, iy))

        # 5) 標籤
        cx = x0 + CELL_W // 2
        label_y = y0 + CELL_H - margin - 130
        draw.text((cx, label_y), cell["label"], fill="#222222", font=f_label, anchor="mm")
        # subtitle
        sub_y = y0 + CELL_H - margin - 60
        draw.text((cx, sub_y), cell["subtitle"], fill=cell["color"], font=f_sub, anchor="mm")

    # LINE rich menu 上限 1 MB；PNG 帶水彩很容易爆，存 JPEG（quality 階梯式回退）
    for q in (90, 85, 80, 72, 65):
        buf = io.BytesIO()
        bg.save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
        data = buf.getvalue()
        if len(data) <= 950_000:  # 留點 margin
            print(f"  jpeg quality={q}, size={len(data) // 1024} KB")
            return data
    # 真的太大就硬縮一次
    bg2 = bg.resize((int(WIDTH * 0.92), int(HEIGHT * 0.92)), Image.LANCZOS).resize((WIDTH, HEIGHT), Image.LANCZOS)
    buf = io.BytesIO()
    bg2.save(buf, format="JPEG", quality=70, optimize=True, progressive=True)
    return buf.getvalue()


# --------------- LINE 上傳 ---------------

def build_request() -> RichMenuRequest:
    areas: list[RichMenuArea] = []
    for i, cell in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        areas.append(
            RichMenuArea(
                bounds=RichMenuBounds(x=col * CELL_W, y=row * CELL_H, width=CELL_W, height=CELL_H),
                action=cell["action"],
            )
        )
    return RichMenuRequest(
        size=RichMenuSize(width=WIDTH, height=HEIGHT),
        selected=True,
        name="sculinebot2026 v2",
        chat_bar_text="📔 旅遊日記選單",
        areas=areas,
    )


def upload_image(token: str, rich_menu_id: str, image_bytes: bytes, mime: str = "image/jpeg") -> None:
    r = httpx.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
        content=image_bytes,
        timeout=60.0,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"upload image failed: {r.status_code} {r.text}")


def main() -> None:
    settings = get_settings()
    print("→ 用 Gemini Nano Banana 2 產 6 顆圖示...")
    gemini_client = genai.Client(api_key=settings.gemini_api_key)
    icons: list[Image.Image] = []
    for cell in CELLS:
        print(f"  · {cell['key']}: {cell['icon_prompt'][:60]}")
        icons.append(gen_icon(gemini_client, settings.gemini_model_image, cell["icon_prompt"]))

    print("→ PIL 合成 menu 圖...")
    png_bytes = render_menu(icons)
    out = Path("richmenu_default.jpg")
    out.write_bytes(png_bytes)
    print(f"  saved {out} ({len(png_bytes) // 1024} KB)")

    print("→ 與 LINE 同步：")
    cfg = Configuration(access_token=settings.line_channel_access_token)
    with ApiClient(cfg) as client:
        api = MessagingApi(client)
        for menu in api.get_rich_menu_list().richmenus or []:
            if menu.name in ("sculinebot2026 default", "sculinebot2026 v2"):
                print(f"  · 刪除舊選單 {menu.rich_menu_id}")
                api.delete_rich_menu(rich_menu_id=menu.rich_menu_id)

        req = build_request()
        created = api.create_rich_menu(rich_menu_request=req)
        rich_menu_id = created.rich_menu_id
        print(f"  · 建立 {rich_menu_id}")
        upload_image(settings.line_channel_access_token, rich_menu_id, png_bytes, mime="image/jpeg")
        print("  · 上傳圖片完成")
        api.set_default_rich_menu(rich_menu_id=rich_menu_id)
        print(f"  · 設為預設 ✅")


if __name__ == "__main__":
    main()

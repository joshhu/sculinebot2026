"""一次性腳本：建立 + 上傳 Rich Menu 並設為預設。

執行：`uv run python scripts/setup_richmenu.py`

選單為 2 列 3 欄的版型（2500x1686）。
左上：📍 開始 / 中上：🏁 結束 / 右上：📚 我的旅程
左下：📷 拍照記錄 / 中下：🎙️ 語音記錄 / 右下：📍 打卡
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
)
from linebot.v3.messaging.models import MessageAction, PostbackAction

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402

WIDTH, HEIGHT = 2500, 1686
COLS, ROWS = 3, 2
CELL_W, CELL_H = WIDTH // COLS, HEIGHT // ROWS

CELLS = [
    {"emoji": "📍", "label": "開始旅程", "sub": "/開始 [標題]", "color": "#4A90E2", "action": MessageAction(label="開始旅程", text="/開始 我的旅程")},
    {"emoji": "🏁", "label": "結束旅程", "sub": "產生遊記", "color": "#E2645B", "action": PostbackAction(label="結束旅程", data="action=close_trip", display_text="結束旅程")},
    {"emoji": "📚", "label": "我的旅程", "sub": "歷史紀錄", "color": "#7B61FF", "action": MessageAction(label="我的旅程", text="/我的旅程")},
    {"emoji": "📷", "label": "拍照記錄", "sub": "傳照片即可", "color": "#36B37E", "action": MessageAction(label="拍照記錄", text="（請直接傳送一張照片）")},
    {"emoji": "🎙️", "label": "語音記錄", "sub": "說一段話", "color": "#FFAB00", "action": MessageAction(label="語音記錄", text="（請直接傳送語音訊息）")},
    {"emoji": "📍", "label": "位置打卡", "sub": "傳送位置", "color": "#00B8D9", "action": MessageAction(label="位置打卡", text="（請從 + 選單傳送位置）")},
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Apple Color Emoji.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_image() -> bytes:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    f_emoji = _load_font(220)
    f_label = _load_font(110)
    f_sub = _load_font(60)

    for i, cell in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        x0, y0 = col * CELL_W, row * CELL_H
        x1, y1 = x0 + CELL_W, y0 + CELL_H
        # 卡片底色（淡色）
        draw.rectangle([x0 + 12, y0 + 12, x1 - 12, y1 - 12], fill=cell["color"], outline=None)
        # 文字置中
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        # emoji
        draw.text((cx, cy - 200), cell["emoji"], fill="#FFFFFF", font=f_emoji, anchor="mm")
        # label
        draw.text((cx, cy + 40), cell["label"], fill="#FFFFFF", font=f_label, anchor="mm")
        # sub
        draw.text((cx, cy + 180), cell["sub"], fill="#FFFFFFCC", font=f_sub, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


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
        name="sculinebot2026 default",
        chat_bar_text="📔 旅遊日記選單",
        areas=areas,
    )


def upload_image(token: str, rich_menu_id: str, png_bytes: bytes) -> None:
    """v3 SDK 的 set_rich_menu_image 在 sync 路徑會走錯到 JSON encoder（會丟 bytes 進 json.dumps），
    因此這裡直接用 httpx 打 LINE blob endpoint。"""
    r = httpx.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
        },
        content=png_bytes,
        timeout=30.0,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"upload image failed: {r.status_code} {r.text}")


def main() -> None:
    settings = get_settings()
    cfg = Configuration(access_token=settings.line_channel_access_token)
    with ApiClient(cfg) as client:
        api = MessagingApi(client)

        # 清掉舊的同名選單
        for menu in api.get_rich_menu_list().richmenus or []:
            if menu.name == "sculinebot2026 default":
                print(f"deleting old menu: {menu.rich_menu_id}")
                api.delete_rich_menu(rich_menu_id=menu.rich_menu_id)

        req = build_request()
        created = api.create_rich_menu(rich_menu_request=req)
        rich_menu_id = created.rich_menu_id
        print(f"created rich menu: {rich_menu_id}")

        png_bytes = render_image()
        out = Path("richmenu_default.png")
        out.write_bytes(png_bytes)
        print(f"image saved -> {out} ({len(png_bytes)} bytes)")

        upload_image(settings.line_channel_access_token, rich_menu_id, png_bytes)
        print("image uploaded")

        api.set_default_rich_menu(rich_menu_id=rich_menu_id)
        print(f"set as default. rich_menu_id={rich_menu_id}")


if __name__ == "__main__":
    main()

"""說明 / 教學 Flex carousel。"""

ACCENT = "#4A90E2"


def _card(emoji: str, title: str, body: str, color: str, button_label: str, button_text: str) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": emoji, "size": "5xl", "align": "center"}],
            "paddingAll": "20px",
            "backgroundColor": color,
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True},
                {"type": "text", "text": body, "size": "sm", "color": "#555555", "wrap": True},
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": color,
                    "action": {"type": "message", "label": button_label, "text": button_text},
                }
            ],
        },
    }


def build() -> dict:
    return {
        "type": "carousel",
        "contents": [
            _card(
                "📍",
                "開始一趟旅程",
                "輸入「/開始 旅程名稱」就可以開始記錄。我會幫你畫一張水彩封面～",
                "#4A90E2",
                "立刻開始",
                "/開始 我的旅程",
            ),
            _card(
                "💬",
                "跟我聊天",
                "把你看到的、吃到的、想到的丟給我。我會像朋友一樣回應、給建議。",
                "#36B37E",
                "看歷史紀錄",
                "/我的旅程",
            ),
            _card(
                "📷",
                "傳照片",
                "我會幫你看圖、辨識景點，再回送一張隨機風格的重繪版本給你收藏 ✨",
                "#FFAB00",
                "我的旅程",
                "/我的旅程",
            ),
            _card(
                "🎙️",
                "傳語音",
                "按住麥克風錄下心情，我會自動轉文字、聊聊心得。適合走在路上時用。",
                "#7B61FF",
                "開始旅程",
                "/開始 我的旅程",
            ),
            _card(
                "📍",
                "傳位置",
                "在 + 選單選位置傳給我，我會反查地名、推薦附近景點，讓行程更豐富。",
                "#00B8D9",
                "看歷史",
                "/我的旅程",
            ),
            _card(
                "📖",
                "結束 → 收遊記",
                "點選單「結束旅程」，我會用 AI 整理整趟素材，產出一份精美的線上遊記網頁。",
                "#E2645B",
                "我的旅程",
                "/我的旅程",
            ),
        ],
    }

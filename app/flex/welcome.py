def build(display_name: str | None) -> dict:
    name = display_name or "旅人"
    return {
        "type": "bubble",
        "size": "kilo",
        "hero": {
            "type": "image",
            "url": "https://placehold.co/1040x520/4A90E2/FFFFFF/png?text=AI+Travel+Diary",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": f"嗨 {name}！", "weight": "bold", "size": "xl"},
                {
                    "type": "text",
                    "text": "我是你的 AI 旅伴。隨手把照片、心情、語音、地點丟給我，旅程結束後我會幫你寫成一篇遊記。",
                    "wrap": True,
                    "size": "sm",
                    "color": "#555555",
                },
                {
                    "type": "text",
                    "text": "輸入「/開始 旅程名稱」就能上路！",
                    "wrap": True,
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#4A90E2",
                    "action": {
                        "type": "message",
                        "label": "📍 開始一趟旅程",
                        "text": "/開始 我的新旅程",
                    },
                }
            ],
        },
    }

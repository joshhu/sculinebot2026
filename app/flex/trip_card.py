def trip_started(title: str) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "✈️ 旅程開始", "weight": "bold", "size": "lg"},
                {"type": "text", "text": title, "size": "xl", "weight": "bold", "color": "#4A90E2"},
                {
                    "type": "text",
                    "text": "現在開始所有訊息都會自動歸檔到這趟旅程。傳照片、心情、語音、位置都行。",
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#E2645B",
                    "action": {
                        "type": "postback",
                        "label": "🏁 結束旅程並產生遊記",
                        "data": "action=close_trip",
                        "displayText": "結束旅程",
                    },
                }
            ],
        },
    }


def entry_confirm(kind_emoji: str, summary: str, extra: str | None = None) -> dict:
    contents = [
        {"type": "text", "text": f"{kind_emoji} 已記錄", "weight": "bold", "size": "md"},
        {"type": "text", "text": summary, "wrap": True, "size": "sm", "color": "#333333"},
    ]
    if extra:
        contents.append(
            {"type": "text", "text": extra, "wrap": True, "size": "xs", "color": "#888888", "margin": "sm"}
        )
    return {
        "type": "bubble",
        "size": "nano",
        "body": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": contents},
    }


def trips_carousel(trips: list[dict]) -> dict:
    bubbles = []
    for t in trips:
        is_active = t.get("status") == "active"
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": ("🟢 進行中" if is_active else "✅ 已完成"),
                        "size": "xs",
                        "color": "#4A90E2" if is_active else "#888888",
                    },
                    {
                        "type": "text",
                        "text": t.get("title") or "未命名旅程",
                        "weight": "bold",
                        "size": "lg",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": (t.get("started_at") or "")[:10],
                        "size": "xs",
                        "color": "#888888",
                    },
                ],
            },
        }
        if t.get("summary_html_url"):
            bubble["footer"] = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#4A90E2",
                        "action": {
                            "type": "uri",
                            "label": "📖 閱讀遊記",
                            "uri": t["summary_html_url"],
                        },
                    }
                ],
            }
        bubbles.append(bubble)
    return {"type": "carousel", "contents": bubbles or [{"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "還沒有旅程紀錄"}]}}]}


def journal_cover(title: str, html_url: str, cover_url: str | None) -> dict:
    bubble = {
        "type": "bubble",
        "size": "giga",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "📖 遊記出爐！", "weight": "bold", "size": "lg", "color": "#4A90E2"},
                {"type": "text", "text": title, "weight": "bold", "size": "xxl", "wrap": True},
                {
                    "type": "text",
                    "text": "AI 已經幫你把整趟旅程整合成一篇遊記。點下面的按鈕閱讀完整內容，或重新生成。",
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
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
                    "action": {"type": "uri", "label": "📖 閱讀遊記", "uri": html_url},
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "postback",
                        "label": "🔁 重新生成",
                        "data": "action=regenerate_journal",
                        "displayText": "重新生成遊記",
                    },
                },
            ],
        },
    }
    if cover_url:
        bubble["hero"] = {
            "type": "image",
            "url": cover_url,
            "size": "full",
            "aspectRatio": "16:9",
            "aspectMode": "cover",
        }
    return bubble

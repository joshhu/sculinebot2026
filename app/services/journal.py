"""遊記產生：抓 entries → Gemini Pro → Markdown → HTML → 上傳 Storage → 回 URL。"""

from __future__ import annotations

from datetime import datetime

import markdown as md_lib

from .. import gemini_client, supabase_client as db


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --accent: #4A90E2; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "PingFang TC", "Noto Sans TC", "Helvetica Neue", Helvetica, Arial, sans-serif;
    line-height: 1.8; color: #1a1a1a; background: #f7f8fb;
    margin: 0; padding: 0;
  }}
  main {{ max-width: 720px; margin: 0 auto; padding: 32px 24px 80px; background: #fff; }}
  h1 {{ font-size: 2rem; border-bottom: 4px solid var(--accent); padding-bottom: .5rem; }}
  h2 {{ font-size: 1.4rem; color: var(--accent); margin-top: 2.5rem; }}
  h3 {{ font-size: 1.1rem; }}
  img {{ max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 18px rgba(0,0,0,.08); margin: 1rem 0; }}
  blockquote {{ border-left: 3px solid var(--accent); padding: .25rem 1rem; color: #555; background: #f1f6fc; }}
  .meta {{ color: #888; font-size: .85rem; margin-bottom: 2rem; }}
  hr {{ border: 0; border-top: 1px dashed #ccc; margin: 2rem 0; }}
  footer {{ text-align: center; color: #aaa; margin-top: 3rem; font-size: .8rem; }}
</style>
</head>
<body>
<main>
  <p class="meta">由 AI 旅遊日記 LINE Bot 自動生成 · {ts}</p>
  {body}
  <footer>— sculinebot2026 —</footer>
</main>
</body>
</html>
"""


def _render_html(title: str, markdown_text: str) -> str:
    body = md_lib.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "smarty"],
    )
    return HTML_TEMPLATE.format(title=title, body=body, ts=datetime.utcnow().strftime("%Y-%m-%d"))


def _entries_to_material(entries: list[dict]) -> list[dict]:
    """擷取 LLM 需要的欄位，去掉雜訊。"""
    out = []
    for e in entries:
        item: dict = {
            "ts": e.get("ts"),
            "kind": e.get("kind"),
        }
        if e.get("raw_text"):
            item["text"] = e["raw_text"]
        if e.get("photo_url"):
            item["photo_url"] = e["photo_url"]
        if e.get("ai_meta"):
            item["ai"] = e["ai_meta"]
        if e.get("lat") is not None:
            item["lat"] = e["lat"]
            item["lng"] = e["lng"]
        out.append(item)
    return out


async def generate_and_publish(trip_id: str) -> tuple[str, str, str | None]:
    """產生遊記並上傳；回傳 (markdown, public_html_url, cover_photo_url)。"""
    trip = await db.get_trip(trip_id)
    if not trip:
        raise ValueError(f"trip not found: {trip_id}")
    entries = await db.list_entries(trip_id)
    title = trip.get("title") or "未命名旅程"

    md_text = await gemini_client.generate_journal(title, _entries_to_material(entries))
    if not md_text.strip():
        md_text = f"# {title}\n\n（這趟旅程暫無素材）"

    html = _render_html(title, md_text)
    path = f"{trip['user_id']}/{trip_id}.html"
    public_url = await db.upload_to_bucket("journals", path, html.encode("utf-8"), "text/html; charset=utf-8")

    cover = next((e["photo_url"] for e in entries if e.get("photo_url")), None)
    return md_text, public_url, cover

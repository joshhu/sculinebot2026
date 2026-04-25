# sculinebot2026 — AI 旅遊日記 LINE Bot

把 LINE 變成隨身的旅伴：旅程中把照片、心情、語音、地點丟給 Bot，背後用 **Google Gemini** 做多模態理解（景點 / 食物 / 心情標籤、語音逐字稿、座標反查），把素材依時序歸檔到 **Supabase**；旅程結束時，Bot 自動把整趟旅程整合成一份**有圖有文有時序**的線上遊記網頁，回傳閱讀連結。

> 整套 webhook server 部署在 **Hugging Face Space (Docker SDK)**，免費方案 + cron 保溫即可運作。

---

## 功能

- 📍 **開始 / 結束旅程**：以 LINE 訊息或 Rich Menu 操作
- 📷 **照片**：自動描述、辨識景點/食物、抽取心情標籤
- 🎙️ **語音**：Gemini 直接轉繁體逐字稿
- 📍 **位置**：座標 → Gemini 反查地名 + 附近景點
- 📝 **文字**：直接歸檔當作心得
- 📖 **遊記生成**：旅程結束時用 Gemini 2.5 Pro 統整素材，產 Markdown → HTML，上傳 Supabase Storage 取 public URL
- 📚 **歷史回顧**：Flex carousel 列出所有旅程，點即可閱讀
- 🎨 **Rich Menu**：六宮格主選單常駐聊天視窗
- ⚡ **Loading animation**：AI 思考時顯示
- 🚀 **Push 補送**：AI 慢時走 Push Message，避開 reply token 30 秒限制

---

## 系統架構

```
LINE Platform
   │  (POST /callback, X-Line-Signature)
   ▼
┌──────────────────────────────────────────────────┐
│ Hugging Face Space (Docker, FastAPI + uvicorn)  │
│  /callback  → 驗簽 → handler 分流                │
│  /health    → 200，給 cron-job.org 保溫          │
└────────────┬──────────────────────┬──────────────┘
             ▼                      ▼
     Google Gemini API         Supabase
     vision/audio/text         Postgres + Storage
```

---

## 技術棧

- **Python 3.12 / FastAPI / uvicorn / line-bot-sdk v3**
- **google-genai** SDK（Gemini 2.5 Flash + 2.5 Pro）
- **supabase-py**（Postgres + Storage：private `media`、public `journals`）
- **uv** 管相依、**Docker** 部署、**ruff/pytest** for dev

---

## 目錄結構

```
sculinebot2026/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # pydantic-settings
│   ├── line_client.py          # LINE SDK wrapper
│   ├── supabase_client.py      # CRUD + Storage
│   ├── gemini_client.py        # vision / audio / text
│   ├── handlers/               # follow/text/image/audio/location/postback
│   ├── services/               # trip / entry / journal
│   └── flex/                   # Flex Message 卡片
├── scripts/
│   ├── init_supabase.sql       # schema
│   └── setup_richmenu.py       # 建立並上傳 Rich Menu
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 本機開發

```bash
# 1) 安裝相依
uv sync

# 2) 準備 .env（複製 .env.example 後填值；Supabase 相關欄位可由腳本自動產生）
cp .env.example .env
# 填上：LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET / GEMINI_API_KEY / SUPABASE_ACCESS_TOKEN
# 之後跑「建立 Supabase 專案」腳本會自動補完 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY

# 3) 跑 webhook server
uv run uvicorn app.main:app --reload --port 7860

# 4) 用 ngrok 暴露給 LINE
ngrok http 7860
# 把 https://xxxx.ngrok-free.app/callback 填到 LINE Console → Verify
```

## Rich Menu 建立 / 更新

```bash
uv run python scripts/setup_richmenu.py
```

腳本會清掉舊版同名選單、產生 2500x1686 的選單圖、上傳並設為預設。

---

## 部署到 Hugging Face Space

1. `hf auth login`（一次性）
2. `hf repo create <user>/sculinebot2026 --repo-type space --space_sdk docker`
3. 在 Space → Settings → **Variables and secrets** 填這些 secrets：
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
4. `git remote add space https://huggingface.co/spaces/<user>/sculinebot2026`
5. `git push space main`
6. 在 LINE Developer Console 把 Webhook URL 設為 `https://<user>-sculinebot2026.hf.space/callback` → 按「Verify」
7. 在 [cron-job.org](https://cron-job.org) 新增每 5 分鐘 GET `https://<user>-sculinebot2026.hf.space/health` 的 job 保溫

---

## 端到端測試清單

- [ ] `/health` 回 `{"ok":true}`
- [ ] LINE Console 「Verify」成功
- [ ] 加好友 → 收到歡迎卡 + Rich Menu 出現
- [ ] `/開始 測試` → 收到旅程開始卡
- [ ] 傳一張食物照 → 收到含 caption 的確認小卡
- [ ] 傳語音 → 收到逐字稿確認小卡
- [ ] 傳位置 → 收到地名確認小卡
- [ ] 點「結束旅程」postback → 數十秒後收到遊記封面 Push → 點開看 HTML 遊記
- [ ] `/我的旅程` → Flex carousel
- [ ] 重新整理 cron-job.org dashboard 看到綠燈

---

## 限制與後續

- 免費 HF Space 閒置 ~5 分鐘後睡眠，cron 每 5 分鐘 ping 保溫；首訊冷啟動可能 ~30 秒
- 影片訊息暫不處理（MVP）
- LIFF 前端 v2 再加（互動地圖 + 線上閱讀器）

---

## 授權

MIT

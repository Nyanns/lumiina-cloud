---
title: Lumiina Cloud
emoji: 👑
colorFrom: pink
colorTo: purple
sdk: gradio
app_file: app.py
pinned: false
---

# Lumiina Cloud (24/7 Telegram Companion Bot)

Autonomous Telegram companion bot powered by Lumiina's Soul and Token Harbor's free tier (`deepseek-v4-flash:free`, `mimo-v2.5:free`).

Designed for zero-cost, persistent 24/7 deployment on **Hugging Face Spaces** (Gradio SDK), **Botkeep**, or any container/cloud platform.

---

## Deploy to Hugging Face Spaces (100% Free 24/7 via Gradio)

1. Open [huggingface.co/new-space](https://huggingface.co/new-space)
2. Space name: `lumiina-cloud`
3. License: `mit`
4. Space SDK: Select **Gradio**
5. Space hardware: **Free (2 vCPU · 16 GB RAM)**
6. Visibility: **Public** or **Private**
7. Once created, go to **Settings** → **Variables and secrets**:
   - Add Secret: `TELEGRAM_BOT_TOKEN` = `8989105187:***`
   - Add Secret: `TOKENHARBOR_API_KEY` = `thk_live_uXrQzA2RAL0mvmefZ2_KDbffKeRebLiMacBgwj6f9Noz-7Dca5IEvWd7AfAb7g7y`
   - Add Variable: `ALLOWED_USER_ID` = `7003600665`
   - Add Variable: `MODEL` = `deepseek-v4-flash:free`
8. Push your code or sync with GitHub repo `Nyanns/lumiina-cloud`.

---

## Features
- Full Aristocratic & Tsundere personality defined in `SOUL.md`.
- Automatic fallback across 4 free frontier models.
- Whitelist protection (only responds to authorized Telegram user IDs).
- Built-in conversation memory per chat session.
- Web Dashboard + Web Playground on Hugging Face Spaces.

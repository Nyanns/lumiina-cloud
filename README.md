# Lumiina Cloud (24/7 Telegram Companion Bot)

Autonomous Telegram companion bot powered by Lumiina's Soul and Token Harbor's free tier (`deepseek-v4-flash:free`, `mimo-v2.5:free`).

Designed for zero-cost, persistent 24/7 deployment on **Botkeep Cloud**, Railway, or any Python container host.

---

## Deploy to Botkeep

1. Go to [Botkeep App](https://botkeep.cloud/app/create)
2. Select **Application** → **Python**
3. Under **02 / Identity & configuration**:
   - Server name: `lumiina-cloud`
   - Start command: `pip install -r requirements.txt && python bot.py` (or `python bot.py` if packages auto-install)
4. Under **03 / Source**:
   - Select **GitHub** and connect `Nyanns/lumiina-cloud`
5. Under **04 / Resources**:
   - Memory: `256 MB` (or whatever minimal portion)
   - CPU: `25%` (0.25 vCore)
   - Storage: `512 MB`
6. Set Environment Variables in Botkeep dashboard:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token
   - `TOKENHARBOR_API_KEY`: Your Token Harbor API Key
   - `ALLOWED_USER_ID`: `7003600665`
   - `MODEL`: `deepseek-v4-flash:free`

---

## Features
- Full Aristocratic & Tsundere personality defined in `SOUL.md`.
- Automatic fallback across 4 free frontier models.
- Whitelist protection (only responds to authorized Telegram user IDs).
- Built-in conversation memory per chat session.
- Light on resources (< 50MB RAM usage).

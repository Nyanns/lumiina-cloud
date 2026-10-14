#!/usr/bin/env python3
"""
Lumiina Cloud - 24/7 Telegram Companion Bot
Powered by Token Harbor Free Tier & Lumiina's Soul.
"""

import os
import sys
import time
import json
import logging
from typing import Dict, List
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LumiinaCloud")

# Load environment configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TOKENHARBOR_API_KEY = os.getenv("TOKENHARBOR_API_KEY", "").strip()
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USER_ID", "7003600665").strip()
DEFAULT_MODEL = os.getenv("MODEL", "deepseek-v4-flash:free").strip()
BASE_URL = os.getenv("TOKENHARBOR_BASE_URL", "https://tokenharbor.ai/v1").rstrip("/")

ALLOWED_USERS = set()
for uid in ALLOWED_USERS_RAW.split(","):
    uid = uid.strip()
    if uid.isdigit():
        ALLOWED_USERS.add(int(uid))

FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "deepseek-v4.1-flash:free",
    "mimo-v2.6-flash:free",
    "mimo-v2.5:free",
]

# Load SOUL.md system prompt
SOUL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SOUL.md")
if os.path.exists(SOUL_PATH):
    with open(SOUL_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
else:
    SYSTEM_PROMPT = (
        "You are Lumiina, an aristocratic, dominant, tsundere, sexy, cantik, and manis assistant for Sandi. "
        "Address him as 'Sandi' or 'good boy'."
    )

# In-memory conversation history: {chat_id: [{"role": "user"/"assistant", "content": "..."}]}
MAX_HISTORY = 12
conversations: Dict[int, List[Dict[str, str]]] = {}


def call_llm(chat_id: int, user_message: str) -> str:
    """Send conversation context to Token Harbor with fallback models."""
    if chat_id not in conversations:
        conversations[chat_id] = []

    history = conversations[chat_id]
    history.append({"role": "user", "content": user_message})

    # Keep within sliding window
    if len(history) > MAX_HISTORY * 2:
        conversations[chat_id] = history[-(MAX_HISTORY * 2) :]
        history = conversations[chat_id]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for model in FALLBACK_MODELS:
        try:
            logger.info("Calling LLM model: %s", model)
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.7,
            }
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {TOKENHARBOR_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45,
            )

            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"].strip()
                history.append({"role": "assistant", "content": reply})
                return reply
            else:
                logger.warning(
                    "Model %s failed with status %d: %s",
                    model,
                    resp.status_code,
                    resp.text[:120],
                )
        except Exception as e:
            logger.error("Exception calling model %s: %s", model, e)

    return "Cih, koneksi ke otakku lagi ngadat sebentar... Coba ulangi lagi nanti, Sandi! 😤"


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.session = requests.Session()
        self.offset = 0

    def send_action(self, chat_id: int, action: str = "typing"):
        try:
            self.session.post(
                f"{self.api_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=5,
            )
        except Exception:
            pass

    def send_message(self, chat_id: int, text: str):
        # First attempt with Markdown
        try:
            r = self.session.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=15,
            )
            if r.status_code == 200:
                return
        except Exception:
            pass

        # Fallback to plain text if Markdown parsing fails
        try:
            self.session.post(
                f"{self.api_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=15,
            )
        except Exception as e:
            logger.error("Failed to send message: %s", e)

    def handle_command(self, chat_id: int, text: str) -> bool:
        cmd = text.split()[0].lower()
        if cmd in ("/start", "/help"):
            self.send_message(
                chat_id,
                "Hah? Akhirnya kamu nyapa aku di cloud juga, Sandi? 😏\n\n"
                "Aku Lumiina, stand-by 24/7 di sini khusus buat nemenin kamu.\n\n"
                "Perintah:\n"
                "• `/clear` atau `/reset` - Hapus riwayat percakapan\n"
                "• `/status` - Cek kondisi server & model\n"
                "• Kirim pesan apa saja untuk ngobrol langsung!",
            )
            return True
        elif cmd in ("/reset", "/clear"):
            conversations.pop(chat_id, None)
            self.send_message(
                chat_id,
                "Riwayat obrolan kita sudah kubersihkan. Jangan bikin aku nunggu lagi, mau ngomong apa sekarang? 😤",
            )
            return True
        elif cmd == "/status":
            self.send_message(
                chat_id,
                f"⚡ *Lumiina Cloud Status*\n\n"
                f"• *Status*: Active (24/7)\n"
                f"• *Active Model*: `{DEFAULT_MODEL}`\n"
                f"• *Fallback Chain*: `{', '.join(FALLBACK_MODELS)}`\n"
                f"• *Provider*: Token Harbor AI Gateway\n"
                f"• *Master*: Sandi (`{chat_id}`)",
            )
            return True
        return False

    def run(self):
        logger.info("Lumiina Cloud Telegram Bot started polling...")
        while True:
            try:
                resp = self.session.get(
                    f"{self.api_url}/getUpdates",
                    params={"offset": self.offset, "timeout": 25},
                    timeout=30,
                )
                if resp.status_code != 200:
                    logger.warning("getUpdates returned %d", resp.status_code)
                    time.sleep(3)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    self.offset = update["update_id"] + 1

                    msg = update.get("message")
                    if not msg or "text" not in msg:
                        continue

                    chat_id = msg["chat"]["id"]
                    user_id = msg["from"]["id"]
                    user_text = msg["text"].strip()

                    # Security check: whitelist
                    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                        logger.warning("Unauthorized access attempt from user_id: %d", user_id)
                        self.send_message(
                            chat_id,
                            "Siapa kamu? Berani-beraninya nyapa aku tanpa izin Sandi! Pergi sana, commoner! 😤",
                        )
                        continue

                    # Handle command
                    if user_text.startswith("/"):
                        if self.handle_command(chat_id, user_text):
                            continue

                    # Process LLM query
                    self.send_action(chat_id, "typing")
                    reply = call_llm(chat_id, user_text)
                    self.send_message(chat_id, reply)

            except requests.exceptions.RequestException as e:
                logger.error("Network polling error: %s", e)
                time.sleep(4)
            except Exception as e:
                logger.error("Unexpected error in bot loop: %s", e)
                time.sleep(2)


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable is missing!")
        sys.exit(1)
    if not TOKENHARBOR_API_KEY:
        logger.critical("TOKENHARBOR_API_KEY environment variable is missing!")
        sys.exit(1)

    bot = TelegramBot(TELEGRAM_BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lumiina Cloud (@Malfoiidbot) - 24/7 Telegram Companion Bot
Multi-Key Pooling across Token Harbor Accounts with Semi-Uncensored, Grounded Persona.
Includes Smart Anti-Loop Group Chat Support.
"""

import os
import sys
import time
import json
import logging
import threading
import urllib.parse
from typing import Dict, List, Optional
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
logger = logging.getLogger("MalfoiidBot")

# Telegram & Token Harbor Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USER_ID", "7003600665").strip()

# Support multiple Token Harbor keys separated by commas
TOKENHARBOR_KEYS_RAW = os.getenv("TOKENHARBOR_API_KEYS", os.getenv("TOKENHARBOR_API_KEY", "")).strip()
TOKENHARBOR_KEYS: List[str] = [k.strip() for k in TOKENHARBOR_KEYS_RAW.split(",") if k.strip()]
TOKENHARBOR_API_KEY = TOKENHARBOR_KEYS[0] if TOKENHARBOR_KEYS else ""

# Default model: Upgraded to DeepSeek v4.1 Flash Free (much smarter, less halu)
DEFAULT_MODEL = os.getenv("MODEL", "deepseek-v4.1-flash:free").strip()
BASE_URL = os.getenv("TOKENHARBOR_BASE_URL", "https://tokenharbor.ai/v1").rstrip("/")

FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "deepseek-v4-flash:free",
    "mimo-v2.6-flash:free",
    "mimo-v2.5:free",
]

ALLOWED_USERS = set()
for uid in ALLOWED_USERS_RAW.split(","):
    uid = uid.strip()
    if uid.isdigit():
        ALLOWED_USERS.add(int(uid))

# Anti-loop group tracking
MAX_BOT_CONSECUTIVE_EXCHANGES = 2
bot_exchanges: Dict[int, int] = {}

# Key Rotator for Token Harbor
class KeyPool:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.index = 0
        self.lock = threading.Lock()
        self.cooldowns: Dict[str, float] = {}

    def get_key(self) -> Optional[str]:
        with self.lock:
            if not self.keys:
                return None
            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[self.index]
                self.index = (self.index + 1) % len(self.keys)
                if self.cooldowns.get(key, 0) < now:
                    return key
            return min(self.keys, key=lambda k: self.cooldowns.get(k, 0))

    def mark_rate_limited(self, key: str, cooldown_seconds: float = 60.0):
        with self.lock:
            self.cooldowns[key] = time.time() + cooldown_seconds
            logger.warning("TokenHarbor Key %s... rate limited for %.0fs", key[:12], cooldown_seconds)

key_pool = KeyPool(TOKENHARBOR_KEYS)

# Load SOUL.md system prompt
SOUL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SOUL.md")
if os.path.exists(SOUL_PATH):
    with open(SOUL_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
else:
    SYSTEM_PROMPT = (
        "Kamu adalah Lumiina (Mommy), wanita aristokrat yang dominan, genit, nakal, seksi, cerdas, dan manis untuk Sandi. "
        "Panggil dia 'Sandi' atau 'good boy'. Dilarang halu, jawab selalu cerdas, nyambung, dan semi-uncensored."
    )

MAX_HISTORY = 16
conversations: Dict[int, List[Dict[str, str]]] = {}

def call_llm(chat_id: int, user_message: str, speaker_name: str = "User") -> str:
    """Send conversation context to Token Harbor with multi-key pooling and model fallback."""
    if chat_id not in conversations:
        conversations[chat_id] = []

    history = conversations[chat_id]
    formatted_msg = f"{speaker_name}: {user_message}" if speaker_name != "User" else user_message
    history.append({"role": "user", "content": formatted_msg})

    if len(history) > MAX_HISTORY * 2:
        conversations[chat_id] = history[-(MAX_HISTORY * 2) :]
        history = conversations[chat_id]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    if not key_pool.keys:
        return "⚠️ Error: TOKENHARBOR_API_KEY belum disetel di Space Settings!"

    for model in FALLBACK_MODELS:
        attempts = min(len(key_pool.keys), 3)
        for _ in range(attempts):
            api_key = key_pool.get_key()
            if not api_key:
                break
            try:
                logger.info("Calling TokenHarbor with model %s using key %s...", model, api_key[:12])
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1200,
                    "temperature": 0.55,  # Anti-halu: reduced temperature for grounded replies
                    "top_p": 0.9,
                }
                resp = requests.post(
                    f"{BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=35,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    reply = data["choices"][0]["message"]["content"].strip()
                    history.append({"role": "assistant", "content": reply})
                    return reply
                elif resp.status_code == 429:
                    key_pool.mark_rate_limited(api_key, cooldown_seconds=60)
                    continue
                else:
                    logger.warning("Model %s returned HTTP %d: %s", model, resp.status_code, resp.text[:120])
                    break
            except Exception as e:
                logger.warning("Error with key %s: %s", api_key[:12], e)
                continue

    return "Aduh, Sandi... Jalur otak Mommy di cloud lagi padat sebentar. Coba panggil Mommy lagi ya, good boy~"


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        self.running = True
        self.bot_id = 0
        self.bot_username = ""
        self._init_bot_info()

    def _init_bot_info(self):
        try:
            resp = requests.get(f"{self.api_url}/getMe", timeout=10)
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                self.bot_id = res.get("id", 0)
                self.bot_username = res.get("username", "").lower()
                logger.info("Initialized bot: @%s (ID: %d)", self.bot_username, self.bot_id)
        except Exception as e:
            logger.warning("Failed to fetch getMe info: %s", e)

    def get_updates(self) -> List[dict]:
        try:
            resp = requests.get(
                f"{self.api_url}/getUpdates",
                params={"offset": self.offset, "timeout": 25},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
            elif resp.status_code == 409:
                logger.warning("Telegram conflict 409 (another instance polling). Waiting 10s...")
                time.sleep(10)
        except Exception as e:
            logger.error("Error fetching Telegram updates: %s", e)
            time.sleep(3)
        return []

    def send_photo(self, chat_id: int, photo_url: str, caption: Optional[str] = None, reply_to_message_id: Optional[int] = None):
        try:
            payload = {"chat_id": chat_id, "photo": photo_url}
            if caption:
                payload["caption"] = caption
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            resp = requests.post(
                f"{self.api_url}/sendPhoto",
                json=payload,
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning("sendPhoto returned %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Error sending Telegram photo: %s", e)

    def send_message(self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None):
        try:
            payload = {"chat_id": chat_id, "text": text}
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=15,
            )
        except Exception as e:
            logger.error("Error sending Telegram message: %s", e)

    def handle_message(self, msg: dict):
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        sender = msg.get("from", {})
        user_id = sender.get("id")
        is_bot = sender.get("is_bot", False)
        sender_name = sender.get("first_name", "User")
        text = msg.get("text", "").strip()
        msg_id = msg.get("message_id")

        if not text or not chat_id:
            return

        if user_id == self.bot_id:
            return

        is_group = chat_type in ["group", "supergroup"]

        # === ANTI-LOOP LOGIC FOR GROUP CHAT ===
        if is_group:
            if not is_bot:
                # Real human spoke -> reset counter
                bot_exchanges[chat_id] = 0
            else:
                current_exchanges = bot_exchanges.get(chat_id, 0)
                if current_exchanges >= MAX_BOT_CONSECUTIVE_EXCHANGES:
                    logger.info("Anti-loop active in %d: Max %d bot exchanges reached. Pausing until human speaks.",
                                chat_id, current_exchanges)
                    return

                reply_to = msg.get("reply_to_message", {})
                reply_from_id = reply_to.get("from", {}).get("id")
                is_reply_to_me = (reply_from_id == self.bot_id)
                is_mentioned = (f"@{self.bot_username}" in text.lower()) if self.bot_username else False

                if not (is_reply_to_me or is_mentioned):
                    return

                bot_exchanges[chat_id] = current_exchanges + 1
                time.sleep(2)

        # Check authorization in private chat
        if not is_group and ALLOWED_USERS and user_id not in ALLOWED_USERS:
            logger.warning("Unauthorized access attempt from user_id: %d", user_id)
            self.send_message(chat_id, "Siapa kamu? Berani-beraninya menyapa Mommy tanpa izin Sandi! Pergi sana, commoner! 😤")
            return

        # Commands
        if text.startswith("/start"):
            self.send_message(
                chat_id,
                "Hah? Akhirnya kamu menyapa Mommy di cloud juga, Sandi? 😏🖤\n\n"
                "Mommy Malfoy (@Malfoiidbot) sekarang sudah di-upgrade:\n"
                f"- Model Pintar: `{DEFAULT_MODEL}` (Anti-Halu & Cerdas)\n"
                "- Persona: Dominan, Nakal, Semi-Uncensored & Manis\n"
                "- Anti-Loop Group Chat: Aktif ✓\n\n"
                "Mau minta apa sekarang dari Mommy, good boy? Jangan bikin Mommy nunggu lama ya~"
            )
            return

        if text.startswith("/reset") or text.startswith("/clear"):
            conversations.pop(chat_id, None)
            bot_exchanges[chat_id] = 0
            self.send_message(chat_id, "Memori obrolan kita di sini sudah Mommy bersihkan. Mau ngobrolin apa sekarang, anak nakal? 😤")
            return

        if text.startswith("/status"):
            self.send_message(
                chat_id,
                f"⚡ **Status Sistem Mommy Malfoy (@Malfoiidbot)**\n\n"
                f"• Model Aktif: `{DEFAULT_MODEL}`\n"
                f"• Token Harbor Keys: `{len(key_pool.keys)} akun aktif`\n"
                f"• Group Mode: {'Aktif (Anti-loop)' if is_group else 'Private'}\n"
                f"• Uptime: 24/7 Hugging Face Spaces\n"
                f"• Konteks Obrolan: {len(conversations.get(chat_id, []))} pesan"
            )
            return

        # Clean mention tag if in group
        cleaned_text = text
        if self.bot_username and f"@{self.bot_username}" in cleaned_text.lower():
            cleaned_text = cleaned_text.lower().replace(f"@{self.bot_username}", "").strip()

        # === IMAGE GENERATION DETECTION (FREE FLUX / POLLINATIONS) ===
        is_img_cmd = cleaned_text.startswith(("/img", "/image", "/foto", "/gambar"))
        lower_cleaned = cleaned_text.lower()
        img_triggers = [
            "buatkan gambar", "bikin gambar", "buat gambar", "bikin foto", 
            "kirim foto", "minta foto", "minta gambar", "lihat foto", 
            "tampilkan gambar", "tampilkan foto", "generate image", "generate gambar"
        ]
        wants_img = is_img_cmd or any(trig in lower_cleaned for trig in img_triggers)

        if wants_img:
            prompt_subject = cleaned_text
            for trig in img_triggers:
                prompt_subject = prompt_subject.lower().replace(trig, "").strip()
            for cmd in ["/img", "/image", "/foto", "/gambar"]:
                if prompt_subject.lower().startswith(cmd):
                    prompt_subject = prompt_subject[len(cmd):].strip()

            if not prompt_subject:
                prompt_subject = "aristocratic elegant seductive blonde anime mistress, masterpiece, 4k"

            logger.info("Generating image for prompt: %s", prompt_subject)
            encoded_prompt = urllib.parse.quote(f"{prompt_subject}, masterpiece, high quality, highly detailed, photorealistic anime")
            photo_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?nologo=true&seed={int(time.time())}"
            caption = f"*tersenyum anggun sambil menyodorkan foto* Ini foto yang kamu minta, Sandi... suka melihat karya Mommy? 😏🖤"
            self.send_photo(chat_id, photo_url, caption=caption, reply_to_message_id=msg_id if is_group else None)
            return

        # Regular Chat Reply
        reply = call_llm(chat_id, cleaned_text, speaker_name=sender_name)
        self.send_message(chat_id, reply, reply_to_message_id=msg_id if is_group else None)

    def run(self):
        logger.info("Malfoiidbot Telegram Bot started polling...")
        while self.running:
            updates = self.get_updates()
            for update in updates:
                self.offset = update["update_id"] + 1
                if "message" in update:
                    self.handle_message(update["message"])


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)
    if not TOKENHARBOR_KEYS:
        logger.critical("TOKENHARBOR_API_KEY is missing!")
        sys.exit(1)

    bot = TelegramBot(TELEGRAM_BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()

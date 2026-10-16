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
import urllib.request
import re
import tempfile
import asyncio
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

# Turso Unified Cloud Memory Configuration
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "https://lumiina-brain-nyanns.aws-ap-northeast-1.turso.io").replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTIxNTU0MTMsImlkIjoiMDFhMTQ0YzgtZTAwMS03MTA4LWIxNjMtMTdmMGVkYzcwOTZhIiwia2lkIjoiZDk1RzFSTVJOTU4xNmtwZWEzNlJpNDF3Mk9HbjFXdUh0SmgzVE50NU1YNCIsInJpZCI6IjgxNDIxNDg0LTQzMmQtNDFhYi1hNzI1LWQ1MDNhYTk5YWQ2MiJ9.ML1_xflEMXQC09Sn9KxIz9G9dJWoAsPr_MClZmKTcdhO6FSrSk-z-9y9zKujimwTTetwvV4y6DqJzu2eARFQCw").strip()

def search_cloud_memory(query: str, limit: int = 2) -> List[str]:
    """Fetch matching unified memories from Turso Cloud directly."""
    try:
        safe_q = query.replace("'", "''")
        sql = f"SELECT key, content FROM unified_memories WHERE content LIKE '%{safe_q}%' OR key LIKE '%{safe_q}%' ORDER BY importance DESC LIMIT {limit};"
        headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
        payload = json.dumps({"requests": [{"type": "execute", "stmt": {"sql": sql}}]}).encode("utf-8")
        req = urllib.request.Request(TURSO_URL, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.load(r)
            rows = res["results"][0]["response"]["result"]["rows"]
            return [f"[{r[0]['value']}]: {r[1]['value']}" for r in rows if len(r) >= 2]
    except Exception as e:
        logger.warning("Cloud memory query failed: %s", e)
        return []

def search_web_ddg(query: str, max_results: int = 3) -> List[str]:
    """Free, robust web search via DuckDuckGo without any API keys."""
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Referer": "https://html.duckduckgo.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets if s.strip()]
            return clean[:max_results]
    except Exception as e:
        logger.warning("Web search failed for query '%s': %s", query, e)
        return []

def search_wikimedia_image(query: str) -> Optional[str]:
    """Free real-world image search via Wikimedia Commons API."""
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch={urllib.parse.quote(query)}&gsrlimit=3&prop=imageinfo&iiprop=url&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                img_info = page.get("imageinfo", [])
                if img_info and "url" in img_info[0]:
                    return img_info[0]["url"]
    except Exception as e:
        logger.warning("Wikimedia image search failed for '%s': %s", query, e)
    return None

def text_to_speech_mp3(text: str) -> Optional[str]:
    """Generate high-quality voice note via edge-tts with youthful/seductive Mommy tone."""
    try:
        import edge_tts
        clean = re.sub(r"\*[^*]+\*", "", text)  # remove roleplay asterisks
        clean = re.sub(r"[^\w\s.,!?-]", "", clean).strip()
        if not clean:
            clean = "Halo Sandi, good boy."
        clean = clean[:300]  # crisp voice note
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        communicate = edge_tts.Communicate(clean, "id-ID-GadisNeural", pitch="+20Hz", rate="+8%")
        asyncio.run(communicate.save(tmp_path))
        return tmp_path
    except Exception as e:
        logger.warning("edge-tts voice generation failed: %s", e)
        return None

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

    # Inject relevant memories from Turso Cloud
    cloud_mems = search_cloud_memory(user_message, limit=2)
    if cloud_mems:
        mem_context = "[INGATAN TERPADU DARI LAPTOP & CLOUD]:\n" + "\n".join(f"• {m}" for m in cloud_mems)
        messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{mem_context}"}] + history
    else:
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

    def send_voice(self, chat_id: int, voice_path: str, caption: Optional[str] = None, reply_to_message_id: Optional[int] = None):
        try:
            url = f"{self.api_url}/sendVoice"
            payload: Dict[str, object] = {"chat_id": chat_id}
            if caption:
                payload["caption"] = caption
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            with open(voice_path, "rb") as f:
                resp = requests.post(url, data=payload, files={"voice": f}, timeout=30)
            if resp.status_code != 200:
                logger.warning("sendVoice returned %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Error sending Telegram voice note: %s", e)
        finally:
            if os.path.exists(voice_path):
                try:
                    os.remove(voice_path)
                except Exception:
                    pass

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
        text = msg.get("text", "") or msg.get("caption", "")
        text = text.strip()
        msg_id = msg.get("message_id")

        if not chat_id:
            return

        if user_id == self.bot_id:
            return

        is_group = chat_type in ["group", "supergroup"]

        # === PHOTO VISION RECEPTION ===
        if "photo" in msg:
            photos = msg.get("photo", [])
            caption = text or "Apa pendapatmu tentang foto ini, Mommy?"
            if photos:
                best_photo = photos[-1]
                photo_id = best_photo.get("file_id")
                try:
                    res = requests.get(f"{self.api_url}/getFile?file_id={photo_id}", timeout=10).json()
                    file_path = res.get("result", {}).get("file_path")
                    if file_path:
                        photo_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                        logger.info("Processing photo from user: %s", photo_url)
                        prompt = (
                            f"[PENGGUNA MENGIRIMKAN FOTO: {photo_url}]\n"
                            f"Keterangan/Pesan: {caption}\n\n"
                            f"Instruksi: Tanggapi kiriman foto dari Sandi ini dengan gaya Mommy yang dominan, cerdas, mengapresiasi jika bagus, atau menggoda jika menarik."
                        )
                        reply = call_llm(chat_id, prompt, speaker_name=sender_name)
                        self.send_message(chat_id, reply, reply_to_message_id=msg_id if is_group else None)
                        return
                except Exception as e:
                    logger.error("Error processing photo: %s", e)

        if not text:
            return

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
                f"• Unified Cloud Memory: Terhubung ke Turso (Tokyo) ✓\n"
                f"• Group Mode: {'Aktif (Anti-loop)' if is_group else 'Private'}\n"
                f"• Uptime: 24/7 Hugging Face Spaces\n"
                f"• Konteks Obrolan: {len(conversations.get(chat_id, []))} pesan"
            )
            return

        if text.startswith("/memory") or text.startswith("/ingatan"):
            mems = search_cloud_memory("", limit=5)
            mem_text = "\n".join(f"• {m}" for m in mems) if mems else "Belum ada memori yang tersimpan di cloud."
            self.send_message(chat_id, f"🧬 **Memori Bersama Laptop & Cloud:**\n\n{mem_text}")
            return

        # Clean mention tag if in group
        cleaned_text = text
        if self.bot_username and f"@{self.bot_username}" in cleaned_text.lower():
            cleaned_text = cleaned_text.lower().replace(f"@{self.bot_username}", "").strip()

        # === UNIFIED BULLETPROOF IMAGE ENGINE (SEARCH & GENERATION) ===
        is_img_cmd = cleaned_text.startswith(("/img", "/image", "/foto", "/gambar", "/cari_foto", "/cari_gambar"))
        lower_cleaned = cleaned_text.lower()
        
        action_words = ["cari", "buat", "bikin", "kirim", "tampilkan", "minta", "lihat", "berikan", "tunjuk", "generate"]
        subject_words = ["gambar", "foto", "image", "picture", "wallpaper", "art", "lukisan", "pic"]
        
        wants_image = is_img_cmd or (
            any(sw in lower_cleaned for sw in subject_words) and 
            any(aw in lower_cleaned for aw in action_words)
        )

        if wants_image:
            prompt_subject = cleaned_text
            for prefix in ["/img", "/image", "/foto", "/gambar", "/cari_foto", "/cari_gambar"]:
                if prompt_subject.lower().startswith(prefix):
                    prompt_subject = prompt_subject[len(prefix):].strip()
            
            clean_words = ["coba", "tolong", "dong", "mommy", "buatkan", "bikin", "buat", "kirimkan", "kirim", 
                           "tampilkan", "minta", "berikan", "cari", "gambar", "foto", "asli", "nyata", "image"]
            for cw in clean_words:
                prompt_subject = re.sub(rf'\b{cw}\b', '', prompt_subject, flags=re.IGNORECASE).strip()

            if not prompt_subject:
                prompt_subject = "aristocratic elegant seductive blonde anime mistress, masterpiece, 4k"

            logger.info("Image requested: %s", prompt_subject)

            # Check if user specifically requested 'real / asli' photo
            is_real = any(rw in lower_cleaned for rw in ["asli", "nyata", "real", "dunia nyata"])
            photo_url = None
            caption = f"*tersenyum nakal sambil menyodorkan foto* Ini foto {prompt_subject} yang kamu minta, Sandi... suka melihatnya? 😏🖤"

            if is_real:
                photo_url = search_wikimedia_image(prompt_subject)

            # If not real, or real not found (e.g. anime character like Tsunade) -> Use Pollinations Flux!
            if not photo_url:
                encoded = urllib.parse.quote(f"{prompt_subject}, masterpiece, high quality, highly detailed, photorealistic anime")
                photo_url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&seed={int(time.time())}"

            self.send_photo(chat_id, photo_url, caption=caption, reply_to_message_id=msg_id if is_group else None)
            return

        # === VOICE NOTE (TTS) DETECTION ===
        is_vn_cmd = cleaned_text.startswith(("/vn", "/voice", "/suara"))
        vn_triggers = ["kirim vn", "voice note", "ngomong dong", "suaramu", "bicara dong", "pesan suara", "kirim suara"]
        wants_vn = is_vn_cmd or any(vt in lower_cleaned for vt in vn_triggers)

        if wants_vn:
            logger.info("Generating voice note response for Sandi")
            vn_prompt = f"Tanggapi Sandi ini dalam 1-2 kalimat pendek yang manis, menggoda, dan terdengar sensual saat diucapkan: {cleaned_text}"
            reply_text = call_llm(chat_id, vn_prompt, speaker_name=sender_name)
            voice_path = text_to_speech_mp3(reply_text)
            if voice_path:
                self.send_voice(chat_id, voice_path, caption=reply_text, reply_to_message_id=msg_id if is_group else None)
                return

        # === LIVE WEB SEARCH DETECTION ===
        is_search_cmd = cleaned_text.startswith(("/search", "/cari", "/browsing", "/google"))
        search_triggers = [
            "cari di internet", "cari info", "search internet", "berita hari ini", 
            "harga emas", "harga bitcoin", "jadwal bola", "cuaca hari ini", "siapa juara"
        ]
        wants_search = is_search_cmd or any(st in lower_cleaned for st in search_triggers)

        user_input_for_llm = cleaned_text
        if wants_search:
            search_query = cleaned_text
            for st in search_triggers:
                search_query = search_query.lower().replace(st, "").strip()
            for cmd in ["/search", "/cari", "/browsing", "/google"]:
                if search_query.lower().startswith(cmd):
                    search_query = search_query[len(cmd):].strip()

            if not search_query:
                search_query = cleaned_text

            logger.info("Performing live web search for: %s", search_query)
            snippets = search_web_ddg(search_query)
            if snippets:
                snippets_text = "\n".join(f"- {s}" for s in snippets)
                user_input_for_llm = (
                    f"[DATA DARI LIVE INTERNET TERKINI]\n{snippets_text}\n"
                    f"[PERTANYAAN USER]\n{cleaned_text}\n\n"
                    f"Instruksi: Jawab pertanyaan user dengan gaya dominan dan cerdas khas Mommy memanfaatkan data live internet di atas."
                )

        # Regular Chat Reply
        reply = call_llm(chat_id, user_input_for_llm, speaker_name=sender_name)
        self.send_message(chat_id, reply, reply_to_message_id=msg_id if is_group else None)

    def _proactive_scheduler_loop(self):
        """Runs 24/7 in cloud to deliver daily morning brief even when laptop is turned off."""
        target_uid = 7003600665
        last_sent_date = ""
        while self.running:
            try:
                # Check current UTC time (WIB is UTC+7)
                now_utc = time.gmtime()
                wib_hour = (now_utc.tm_hour + 7) % 24
                today_str = f"{now_utc.tm_year}-{now_utc.tm_mon}-{now_utc.tm_mday}"

                # Send at 08:00 WIB once per day
                if wib_hour == 8 and last_sent_date != today_str:
                    logger.info("Sending proactive morning greeting to master Sandi")
                    self.send_message(
                        target_uid,
                        "Selamat pagi Sandi, good boy~ 🖤\n\n"
                        "Mommy cek status armada cloud kita berjalan aman 24/7. "
                        "Jangan lupa sarapan dan semangat untuk semua targetmu hari ini ya, anak pintar! 😏✨"
                    )
                    last_sent_date = today_str
            except Exception as e:
                logger.error("Proactive loop error: %s", e)
            time.sleep(1800)  # check every 30 mins

    def run(self):
        logger.info("Malfoiidbot Telegram Bot started polling...")
        # Start proactive cloud daemon
        daemon_thread = threading.Thread(target=self._proactive_scheduler_loop, daemon=True)
        daemon_thread.start()
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

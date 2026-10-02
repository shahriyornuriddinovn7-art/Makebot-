"""Global konfiguratsiya (.env dan o'qiladi)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv ixtiyoriy
    pass

BASE_DIR = Path(__file__).resolve().parent

MAKER_TOKEN = os.getenv("MAKER_BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "maker.db"))
TEMP_DIR = Path(os.getenv("TEMP_DIR", str(BASE_DIR / "tmp")))
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip()

MAX_BOTS_PER_USER = int(os.getenv("MAX_BOTS_PER_USER", "5"))
MAX_PARALLEL_DOWNLOADS = int(os.getenv("MAX_PARALLEL_DOWNLOADS", "3"))
MAX_UPLOAD_BYTES = 49 * 1024 * 1024  # Bot API: 50 MB limit

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

# Yaratiladigan bot turlari: kalit -> sarlavha
BOT_TYPES = {
    "movie": "🎬 Kodli Kino Bot",
    "music": "🎵 Musiqa & Instagram Downloader",
    "gemini": "🤖 Gemini AI Chatbot",
    "image": "🎨 AI Logo & Tasvir Bot",
    "edu": "🎓 Talaba & O'qituvchi Boti",
    "downloader": "📥 Universal Downloader",
    "anon": "🕶 Anonim Chat Bot",
}

# Admin panelda ulanadigan API kalitlar: bot turi -> [(provider, nomi)]
API_PROVIDERS = {
    "maker": [("gemini", "Gemini"), ("openai", "OpenAI")],
    "gemini": [("gemini", "Gemini")],
    "edu": [("gemini", "Gemini")],
    "image": [("image", "Rasm API (Pollinations / OpenAI sk-...)")],
}

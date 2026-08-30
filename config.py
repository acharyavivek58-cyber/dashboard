import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or 0)

# Dashboard
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "changeme")

SETTINGS_FILE = "bot_settings.json"

# Default embed colors
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2
COLOR_WARNING = 0xFEE75C


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def get_guild_settings(guild_id: str) -> dict:
    settings = load_settings()
    defaults = {
        "prefix": BOT_PREFIX,
        "aliases": {},
        "welcome_enabled": False,
        "welcome_channel": "",
        "welcome_message": "Welcome {user} to {server}!",
        "logging_enabled": True,
        "autorole_enabled": False,
        "autorole_id": "",
    }
    return {**defaults, **settings.get(str(guild_id), {})}

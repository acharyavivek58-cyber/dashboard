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
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://dashboard-qyoy.onrender.com")

# Settings cache (avoid blocking HTTP calls on every message)
_settings_remote_cache = {}  # {guild_id: {"data": dict, "time": float}}
_REMOTE_CACHE_TTL = 300  # 5 minutes

# Default embed colors
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2
COLOR_WARNING = 0xFEE75C


DEFAULT_SETTINGS = {
    "prefix": BOT_PREFIX,
    "aliases": {},
    "welcome_enabled": False,
    "welcome_channel": "",
    "welcome_message": "Welcome {user} to {server}!",
    "logging_enabled": True,
    "autorole_enabled": False,
    "autorole_id": "",
    "permissions": {}
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def fetch_settings_from_dashboard(guild_id: str) -> dict:
    """Fetch settings from dashboard API — cached, non-blocking."""
    import time as _time
    now = _time.time()
    cached = _settings_remote_cache.get(guild_id)
    if cached and now - cached["time"] < _REMOTE_CACHE_TTL:
        return cached["data"]
    try:
        import requests
        resp = requests.get(f"{DASHBOARD_URL}/api/settings/{guild_id}", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            _settings_remote_cache[guild_id] = {"data": data, "time": now}
            return data
    except Exception:
        pass
    # Return cached even if stale, or empty
    return cached["data"] if cached else {}


def get_guild_settings(guild_id: str) -> dict:
    # Use local cache only — no blocking HTTP calls
    settings = load_settings()
    defaults = json.loads(json.dumps(DEFAULT_SETTINGS))
    stored = settings.get(str(guild_id), {})
    
    # Merge permissions
    if "permissions" not in stored:
        stored["permissions"] = defaults["permissions"]
    else:
        for cmd, data in defaults["permissions"].items():
            if cmd not in stored["permissions"]:
                stored["permissions"][cmd] = data
    
    defaults.update(stored)
    return defaults

import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_PREFIX = os.getenv("BOT_PREFIX", "$")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or 0)

# Dashboard
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
# Empty = not configured → dashboard.py derives the URI from the real
# request origin so local runs round-trip to whatever port is served.
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")
DISCORD_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def dashboard_port():
    """Deterministic web port for the dashboard.

    PORT is honored when it is a positive integer (Render sets its own);
    anything else — unset, non-numeric, or <= 0 (some launchers export
    PORT=0, which means "random port" to Flask) — falls back to 5000 so
    local runs are reproducible and the OAuth callback stays reachable.
    """
    raw = os.getenv("PORT") or ""
    try:
        port = int(raw)
    except (TypeError, ValueError):
        port = 0
    return port if port > 0 else 5000

SETTINGS_FILE = "bot_settings.json"

# File modification tracking for real-time sync
_settings_mtime = 0
_settings_cache_data = {}

# Default embed colors
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2
COLOR_WARNING = 0xFEE75C

# ── Single canonical DEFAULT_SETTINGS ───────────────────────────
DEFAULT_SETTINGS = {
    "prefix": BOT_PREFIX,
    "aliases": {},
    "welcome_enabled": False,
    "welcome_channel": "",
    "welcome_message": "Welcome {user} to {server}!",
    "logging_enabled": True,
    "autorole_enabled": False,
    "autorole_id": "",
    "permissions": {
        "ban": {"roles": [], "everyone": False},
        "kick": {"roles": [], "everyone": False},
        "mute": {"roles": [], "everyone": False},
        "unmute": {"roles": [], "everyone": False},
        "warn": {"roles": [], "everyone": False},
        "warnings": {"roles": [], "everyone": True},
        "purge": {"roles": [], "everyone": False},
        "lock": {"roles": [], "everyone": False},
        "unlock": {"roles": [], "everyone": False},
        "slowmode": {"roles": [], "everyone": False},
        "ticketsetup": {"roles": [], "everyone": False},
        "ticketrole": {"roles": [], "everyone": False},
        "tickettype": {"roles": [], "everyone": False},
        "closetype": {"roles": [], "everyone": False},
        "sendpanels": {"roles": [], "everyone": False},
        "movetickets": {"roles": [], "everyone": False},
        "close": {"roles": [], "everyone": False},
        "add": {"roles": [], "everyone": False},
        "remove": {"roles": [], "everyone": False},
        "afk": {"roles": [], "everyone": True},
        "invites": {"roles": [], "everyone": True},
        "inviteboard": {"roles": [], "everyone": True},
        "invitestats": {"roles": [], "everyone": True},
        "giveaway": {"roles": [], "everyone": False},
        "giveawayend": {"roles": [], "everyone": False},
        "giveawayreroll": {"roles": [], "everyone": False},
        "play": {"roles": [], "everyone": True},
        "pause": {"roles": [], "everyone": True},
        "resume": {"roles": [], "everyone": True},
        "skip": {"roles": [], "everyone": True},
        "stop": {"roles": [], "everyone": True},
        "queue": {"roles": [], "everyone": True},
        "nowplaying": {"roles": [], "everyone": True},
        "volume": {"roles": [], "everyone": True},
        "shuffle": {"roles": [], "everyone": True},
        "loop": {"roles": [], "everyone": True},
        "removesong": {"roles": [], "everyone": True},
        "clear": {"roles": [], "everyone": True},
        "join": {"roles": [], "everyone": True},
        "leave": {"roles": [], "everyone": True},
        "roulette": {"roles": [], "everyone": True},
        "dice": {"roles": [], "everyone": True},
        "rps": {"roles": [], "everyone": True},
        "xo": {"roles": [], "everyone": True},
        "hotxo": {"roles": [], "everyone": True},
        "deathwheel": {"roles": [], "everyone": True},
        "chairs": {"roles": [], "everyone": True},
        "truthordare": {"roles": [], "everyone": True},
        "hideandseek": {"roles": [], "everyone": True},
        "replica": {"roles": [], "everyone": True},
        "guesscountry": {"roles": [], "everyone": True},
        "mafia": {"roles": [], "everyone": True},
        "wyr": {"roles": [], "everyone": True},
        "fastclick": {"roles": [], "everyone": True},
        "fasttype": {"roles": [], "everyone": True},
        "textsplit": {"roles": [], "everyone": True},
        "textmerge": {"roles": [], "everyone": True},
        "ask": {"roles": [], "everyone": True},
        "flag": {"roles": [], "everyone": True},
        "textreverse": {"roles": [], "everyone": True},
        "findletter": {"roles": [], "everyone": True},
        "correctletter": {"roles": [], "everyone": True},
        "sortnumbers": {"roles": [], "everyone": True},
        "guesscolor": {"roles": [], "everyone": True},
        "emoji": {"roles": [], "everyone": True},
        "reveal": {"roles": [], "everyone": True},
        "trivia": {"roles": [], "everyone": True},
        "triviascore": {"roles": [], "everyone": True},
        "trivialeaderboard": {"roles": [], "everyone": True},
        "role": {"roles": [], "everyone": False},
        "createrole": {"roles": [], "everyone": False},
        "deleterole": {"roles": [], "everyone": False},
        "ping": {"roles": [], "everyone": True},
        "uptime": {"roles": [], "everyone": True},
        "userinfo": {"roles": [], "everyone": True},
        "serverinfo": {"roles": [], "everyone": True},
        "avatar": {"roles": [], "everyone": True},
        "servericon": {"roles": [], "everyone": True},
        "id": {"roles": [], "everyone": True},
        "say": {"roles": [], "everyone": False},
        "8ball": {"roles": [], "everyone": True},
        "coinflip": {"roles": [], "everyone": True},
        "reverse": {"roles": [], "everyone": True},
        "choose": {"roles": [], "everyone": True},
        "poll": {"roles": [], "everyone": True},
        "remind": {"roles": [], "everyone": True},
        "reminders": {"roles": [], "everyone": True},
        "count": {"roles": [], "everyone": True},
        "countreset": {"roles": [], "everyone": False},
        "countset": {"roles": [], "everyone": False},
        "countlb": {"roles": [], "everyone": True},
        "automod": {"roles": [], "everyone": False},
        "automodconfig": {"roles": [], "everyone": False},
        "clearwarns": {"roles": [], "everyone": False},
        "reactionrole": {"roles": [], "everyone": False},
        "reactionroleadd": {"roles": [], "everyone": False},
        "reactionroledel": {"roles": [], "everyone": False},
        "reactionroles": {"roles": [], "everyone": False},
    }
}


# ── Settings persistence ───────────────────────────────────────
def load_settings() -> dict:
    global _settings_mtime, _settings_cache_data
    try:
        mtime = os.path.getmtime(SETTINGS_FILE)
    except OSError:
        mtime = 0
    if mtime == _settings_mtime and _settings_cache_data:
        return _settings_cache_data
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            _settings_mtime = mtime
            _settings_cache_data = data
            return data
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_settings(data: dict):
    global _settings_mtime, _settings_cache_data
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    _settings_mtime = os.path.getmtime(SETTINGS_FILE)
    _settings_cache_data = data


def get_guild_settings(guild_id: str) -> dict:
    settings = load_settings()
    defaults = json.loads(json.dumps(DEFAULT_SETTINGS))
    stored = settings.get(str(guild_id), {})
    if "permissions" not in stored:
        stored["permissions"] = defaults["permissions"]
    else:
        for cmd, data in defaults["permissions"].items():
            if cmd not in stored["permissions"]:
                stored["permissions"][cmd] = data
    defaults.update(stored)
    return defaults


def set_guild_settings(guild_id: str, data: dict):
    settings = load_settings()
    settings[guild_id] = data
    save_settings(settings)


# ── Runtime state persistence ──────────────────────────────────
_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")


def _ensure_state_dir():
    os.makedirs(_STATE_DIR, exist_ok=True)


def load_state(filename: str) -> dict:
    """Load a state file from the state/ directory."""
    _ensure_state_dir()
    path = os.path.join(_STATE_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_state(filename: str, data: dict):
    """Save a state file to the state/ directory."""
    _ensure_state_dir()
    path = os.path.join(_STATE_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Unified permission check ──────────────────────────────────

# Commands that only Manage Server holders may run when nothing is
# configured on the dashboard (mirrors the dashboard's Co-Owner+ tier:
# ban/kick + lock family). Every other restricted command falls back to
# the wider mod trio (Manage Server / Manage Messages / Mute Members).
_ADMIN_FALLBACK_COMMANDS = {"ban", "kick", "lock", "unlock", "slowmode"}


def has_permission(command_name: str, member) -> bool:
    """Check if a member can use a command based on dashboard permissions.

    Returns True if:
    - Member is the server owner
    - Permission is set to everyone=True
    - No roles configured and member qualifies for the command's class:
      admin-class commands (ban/kick/lock/unlock/slowmode) require Manage
      Server; mod-class commands allow Manage Server / Manage Messages /
      Mute Members
    - Member has one of the configured roles
    """
    if member.id == member.guild.owner_id:
        return True
    settings = get_guild_settings(str(member.guild.id))
    permissions = settings.get("permissions", {})
    cmd_perm = permissions.get(command_name, {})
    # Nothing configured — fall back by command class so a low-privilege
    # mute-mod cannot run admin commands like $ban/$kick/$lock.
    if not cmd_perm or (not cmd_perm.get("roles") and not cmd_perm.get("everyone")):
        perms = member.guild_permissions
        if command_name in _ADMIN_FALLBACK_COMMANDS:
            return perms.manage_guild
        return perms.manage_guild or perms.manage_messages or perms.mute_members
    if cmd_perm.get("everyone", False):
        return True
    allowed_role_ids = cmd_perm.get("roles", [])
    if not allowed_role_ids:
        return False
    user_role_ids = [str(r.id) for r in member.roles]
    for role_id in allowed_role_ids:
        if role_id in user_role_ids:
            return True
    return False

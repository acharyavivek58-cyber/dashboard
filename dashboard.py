import os
import json
import secrets
import functools
from urllib.parse import urlencode

from dotenv import load_dotenv
load_dotenv()

import requests
from flask import (
    Flask, redirect, request, session, render_template, jsonify, url_for
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ── Discord OAuth2 Config ────────────────────────────────────────────────
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5000/callback")
DISCORD_BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Settings Storage ─────────────────────────────────────────────────────
SETTINGS_FILE = "bot_settings.json"


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_settings(guild_id: str) -> dict:
    settings = load_settings()
    return settings.get(guild_id, {
        "prefix": "$",
        "aliases": {},
        "welcome_enabled": False,
        "welcome_channel": "",
        "welcome_message": "Welcome {user} to {server}!",
        "logging_enabled": True,
        "autorole_enabled": False,
        "autorole_id": "",
    })


def set_guild_settings(guild_id: str, data: dict):
    settings = load_settings()
    settings[guild_id] = data
    save_settings(settings)


# ── Discord API Helpers ──────────────────────────────────────────────────
def get_user_guilds(token: str) -> list:
    resp = requests.get(
        "https://discord.com/api/v10/users/@me/guilds",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return []


def get_bot_guilds() -> list:
    resp = requests.get(
        "https://discord.com/api/v10/users/@me/guilds",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return []


def get_guild_info(guild_id: str) -> dict | None:
    resp = requests.get(
        f"https://discord.com/api/v10/guilds/{guild_id}",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def get_mutual_guilds(user_token: str) -> list:
    user_guilds = get_user_guilds(user_token)
    bot_guilds = get_bot_guilds()
    bot_guild_ids = {g["id"] for g in bot_guilds}
    # Only show guilds where user has ADMINISTRATE (0x8) and bot is also present
    return [
        g for g in user_guilds
        if g["id"] in bot_guild_ids and (int(g.get("permissions", "0")) & 0x8)
    ]


# ── Auth Decorator ───────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_token" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Check that the logged-in user has ADMINISTRATE permission in the guild."""
    @functools.wraps(f)
    def decorated(guild_id, *args, **kwargs):
        if "user_token" not in session:
            return redirect(url_for("login"))
        # Check user has admin perms in this guild
        user_guilds = get_user_guilds(session["user_token"])
        guild = next((g for g in user_guilds if g["id"] == guild_id), None)
        if not guild or not (int(guild.get("permissions", "0")) & 0x8):
            return redirect(url_for("dashboard"))
        return f(guild_id, *args, **kwargs)
    return decorated


# ── Routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_token" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login")
def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return redirect(f"https://discord.com/api/oauth2/authorize?{urlencode(params)}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data=data,
        headers=headers,
        auth=(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET)
    )
    if resp.status_code != 200:
        return redirect(url_for("index"))

    token_data = resp.json()
    session["user_token"] = token_data["access_token"]

    # Get user info
    user_resp = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {session['user_token']}"}
    )
    if user_resp.status_code == 200:
        session["user"] = user_resp.json()

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    guilds = get_mutual_guilds(session["user_token"])
    return render_template("dashboard.html", guilds=guilds, user=session.get("user"))


@app.route("/dashboard/<guild_id>")
@admin_required
def guild_settings(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    return render_template("settings.html", guild=guild, settings=settings, user=session.get("user"))


@app.route("/dashboard/<guild_id>/commands")
@admin_required
def guild_commands(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    return render_template("commands.html", guild=guild, settings=settings, user=session.get("user"))


@app.route("/dashboard/<guild_id>/moderation")
@admin_required
def guild_moderation(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    return render_template("moderation.html", guild=guild, settings=settings, user=session.get("user"))


@app.route("/dashboard/<guild_id>/counting")
@admin_required
def guild_counting(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    return render_template("counting.html", guild=guild, settings=settings, user=session.get("user"))


@app.route("/api/settings/<guild_id>", methods=["GET"])
@admin_required
def get_settings(guild_id):
    settings = get_guild_settings(guild_id)
    return jsonify(settings)


@app.route("/api/settings/<guild_id>", methods=["POST"])
@admin_required
def update_settings(guild_id):
    data = request.json
    current = get_guild_settings(guild_id)
    current.update(data)
    set_guild_settings(guild_id, current)
    return jsonify({"success": True, "settings": current})


@app.route("/api/aliases/<guild_id>", methods=["POST"])
@admin_required
def add_alias(guild_id):
    data = request.json
    alias = data.get("alias", "").strip()
    command = data.get("command", "").strip()
    if not alias or not command:
        return jsonify({"error": "Alias and command are required"}), 400

    settings = get_guild_settings(guild_id)
    settings["aliases"][alias] = command
    set_guild_settings(guild_id, settings)
    return jsonify({"success": True, "aliases": settings["aliases"]})


@app.route("/api/aliases/<guild_id>/<alias>", methods=["DELETE"])
@admin_required
def delete_alias(guild_id, alias):
    settings = get_guild_settings(guild_id)
    settings["aliases"].pop(alias, None)
    set_guild_settings(guild_id, settings)
    return jsonify({"success": True, "aliases": settings["aliases"]})


# ── API for the bot to read settings (internal use) ─────────────────────
@app.route("/api/bot/settings/<guild_id>", methods=["GET"])
def bot_get_settings(guild_id):
    # Simple token auth for bot-to-dashboard communication
    auth = request.headers.get("Authorization", "")
    if auth != f"Bot {os.getenv('DASHBOARD_API_KEY', 'changeme')}":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_guild_settings(guild_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

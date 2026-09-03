import os
import secrets
import functools
from urllib.parse import urlencode

from dotenv import load_dotenv
load_dotenv()

import requests
from flask import (
    Flask, redirect, request, session, render_template, jsonify, url_for
)

import config
from config import (
    load_settings, save_settings, get_guild_settings, set_guild_settings,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI,
    DISCORD_BOT_TOKEN,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(32))


# ── Discord API helpers ────────────────────────────────────────
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


def get_guild_roles(guild_id: str) -> list:
    resp = requests.get(
        f"https://discord.com/api/v10/guilds/{guild_id}/roles",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    )
    if resp.status_code == 200:
        roles = resp.json()
        return [r for r in sorted(roles, key=lambda x: x["position"], reverse=True) if r["name"] != "@everyone"]
    return []


def get_mutual_guilds(user_token: str) -> list:
    user_guilds = get_user_guilds(user_token)
    bot_guilds = get_bot_guilds()
    bot_guild_ids = {g["id"] for g in bot_guilds}
    return [
        g for g in user_guilds
        if g["id"] in bot_guild_ids and (int(g.get("permissions", "0")) & 0x8)
    ]


# ── Auth decorators ────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_token" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(guild_id, *args, **kwargs):
        if "user_token" not in session:
            return redirect(url_for("login"))
        user_guilds = get_user_guilds(session["user_token"])
        guild = next((g for g in user_guilds if g["id"] == guild_id), None)
        if not guild or not (int(guild.get("permissions", "0")) & 0x8):
            return redirect(url_for("dashboard"))
        return f(guild_id, *args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────

def oauth_redirect_uri():
    """The exact redirect URI for this request.

    Uses the configured DISCORD_REDIRECT_URI when set (Render and any
    deployment with a public hostname set it explicitly); otherwise it
    derives from the real request origin — scheme://host/callback — so
    a local login round-trips to the exact port being served instead of
    a hardcoded one.
    """
    if DISCORD_REDIRECT_URI:
        return DISCORD_REDIRECT_URI
    return request.url_root.rstrip("/") + "/callback"


@app.route("/")
def index():
    if "user_token" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login")
def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": oauth_redirect_uri(),
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
        "redirect_uri": oauth_redirect_uri(),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data=data, headers=headers,
        auth=(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET)
    )
    if resp.status_code != 200:
        return redirect(url_for("index"))
    token_data = resp.json()
    session["user_token"] = token_data["access_token"]
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


@app.route("/showcase")
@login_required
def showcase():
    return render_template("showcase.html", user=session.get("user"))


@app.route("/dashboard/<guild_id>")
@admin_required
def guild_settings(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    return render_template("settings.html", guild=guild, settings=settings, user=session.get("user"))


@app.route("/dashboard/<guild_id>/permissions")
@admin_required
def guild_permissions(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    roles = get_guild_roles(guild_id)
    return render_template("permissions.html", guild=guild, settings=settings, roles=roles, user=session.get("user"))


@app.route("/dashboard/<guild_id>/commands")
@admin_required
def guild_commands(guild_id):
    guild = get_guild_info(guild_id)
    if not guild:
        return redirect(url_for("dashboard"))
    settings = get_guild_settings(guild_id)
    roles = get_guild_roles(guild_id)
    return render_template("commands.html", guild=guild, settings=settings, roles=roles, user=session.get("user"))


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


# ── API routes ─────────────────────────────────────────────────
@app.route("/api/settings/<guild_id>", methods=["GET"])
@admin_required
def get_settings(guild_id):
    return jsonify(get_guild_settings(guild_id))


@app.route("/api/settings/<guild_id>", methods=["POST"])
@admin_required
def update_settings(guild_id):
    data = request.json
    current = get_guild_settings(guild_id)
    current.update(data)
    set_guild_settings(guild_id, current)
    return jsonify({"success": True, "settings": current})


@app.route("/api/permissions/<guild_id>", methods=["POST"])
@admin_required
def update_permissions(guild_id):
    data = request.json
    cmd = data.get("command")
    roles = data.get("roles", [])
    everyone = data.get("everyone", False)
    if not cmd:
        return jsonify({"error": "Command name required"}), 400
    current = get_guild_settings(guild_id)
    if "permissions" not in current:
        current["permissions"] = {}
    current["permissions"][cmd] = {"roles": roles, "everyone": everyone}
    set_guild_settings(guild_id, current)
    return jsonify({"success": True})


@app.route("/api/permissions/<guild_id>/bulk", methods=["POST"])
@admin_required
def bulk_update_permissions(guild_id):
    data = request.json
    current = get_guild_settings(guild_id)
    if "permissions" not in current:
        current["permissions"] = {}
    current["permissions"].update(data)
    set_guild_settings(guild_id, current)
    return jsonify({"success": True})


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


@app.route("/api/roles/<guild_id>", methods=["GET"])
@admin_required
def get_roles(guild_id):
    return jsonify(get_guild_roles(guild_id))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.dashboard_port(), debug=True)

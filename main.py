import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import threading
import time
import config
import utils

# ── Settings cache (avoid reading JSON/HTTP on every message) ──────
_settings_cache = {}
_CACHE_TTL = 2  # seconds (real-time sync via file mtime in config.py)


def get_prefix(bot_instance, message):
    """Dynamic prefix: check cached settings, fall back to default."""
    if not message.guild:
        return config.BOT_PREFIX
    gid = str(message.guild.id)
    now = time.time()
    cached = _settings_cache.get(gid)
    if cached and now - cached["time"] < _CACHE_TTL:
        return cached["prefix"]
    settings = config.get_guild_settings(gid)
    prefix = settings.get("prefix", config.BOT_PREFIX)
    _settings_cache[gid] = {"prefix": prefix, "time": now}
    return prefix


# ── Bot setup ──────────────────────────────────────────────────────
intents = discord.Intents.all()

COGS = [
    "cogs.moderation",
    "cogs.utility",
    "cogs.roles",
    "cogs.fun",
    "cogs.logging_cog",
    "cogs.counting",
    "cogs.giveaway",
    "cogs.invites",
    "cogs.reaction_roles",
    "cogs.automod",
    # "cogs.leveling",  # paused
    "cogs.reminders",
    "cogs.tickets",
    "cogs.afk",
    "cogs.music",
    "cogs.trivia",
    "cogs.games",
]

from cogs.help import CustomHelp

bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    description="An all-in-one Discord bot.",
    activity=discord.Activity(type=discord.ActivityType.watching, name="$help | Dashboard"),
    help_command=CustomHelp(),
)


# ── Events ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print("─" * 40)
    print(f"  Bot:    {bot.user} ({bot.user.id})")
    print(f"  Guilds: {len(bot.guilds)}")
    print(f"  Prefix: {config.BOT_PREFIX} (dynamic)")
    print("─" * 40)

    try:
        app_id = str(bot.user.id)
        old_names = {"ban", "kick", "mute", "unmute", "warn", "warnings", "purge"}
        # Delete old slash commands from Discord's API
        registered = await bot.http.get_global_commands(app_id)
        for cmd in registered:
            if cmd["name"] in old_names:
                await bot.http.delete_global_command(app_id, cmd["id"])
                print(f"  Removed: /{cmd['name']}")
        # Also delete guild-specific old slash commands
        for guild in bot.guilds:
            try:
                guild_cmds = await bot.http.get_guild_commands(app_id, str(guild.id))
                for cmd in guild_cmds:
                    if cmd["name"] in old_names:
                        await bot.http.delete_guild_command(app_id, str(guild.id), cmd["id"])
                        print(f"  Removed: /{cmd['name']} from {guild.name}")
            except Exception:
                pass
        synced = await bot.tree.sync()
        print(f"  Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"  Sync error: {e}")
    print("─" * 40)


_processed_messages = set()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    # Skip if already processed (prevents double replies)
    if message.id in _processed_messages:
        return
    _processed_messages.add(message.id)
    # Clean up old IDs (keep only last 1000)
    if len(_processed_messages) > 1000:
        oldest = list(_processed_messages)[:500]
        for mid in oldest:
            _processed_messages.discard(mid)

    # Check for custom aliases from dashboard
    content = message.content
    if content:
        prefix = get_prefix(bot, message)
        if content.startswith(prefix):
            args = content[len(prefix):].strip().split()
            if args:
                cmd_name = args[0].lower()
                settings = config.get_guild_settings(str(message.guild.id))
                aliases = settings.get("aliases", {})
                if cmd_name in aliases:
                    actual_cmd = aliases[cmd_name]
                    message._original_content = content
                    message.content = f"{prefix}{actual_cmd} {' '.join(args[1:])}"

    await bot.process_commands(message)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, commands.MissingRequiredArgument):
            return  # commands handle their own usage embeds
    return


@bot.event
async def on_command_error(ctx: commands.Context, error: discord.ext.commands.errors.CommandError):
    # Check wrapped errors first
    original = getattr(error, 'original', None)
    if isinstance(original, commands.MissingRequiredArgument):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        return
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=utils.warning("Cooldown", f"Try again in {error.retry_after:.1f}s."))
        return
    if isinstance(error, commands.MissingPermissions):
        return
    if isinstance(error, commands.CheckFailure):
        # Show permission denied message instead of silent ignore
        msg = str(getattr(error, 'original', error) or error)
        if 'No permission' in msg or msg in ('No permission', 'staff_role'):
            await ctx.send(embed=utils.error("Permission Denied", "You don't have permission to use this command."), delete_after=5)
        return
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send(embed=utils.error("Bot Missing Permissions", f"I need: **{', '.join(error.missing_permissions)}**"))
        return
    # Silently ignore everything else
    return


# ── Dashboard thread ───────────────────────────────────────────────
def start_dashboard():
    import os
    from dashboard import app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ── Main ───────────────────────────────────────────────────────────
async def main():
    dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
    dashboard_thread.start()
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"  Dashboard: http://localhost:{port}")

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"  Loaded: {cog}")

        if not config.BOT_TOKEN:
            print("ERROR: BOT_TOKEN not set. Copy .env.example to .env and add your token.")
            return

        await bot.start(config.BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

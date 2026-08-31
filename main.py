import discord
from discord.ext import commands
import asyncio
import threading
import config
import utils
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=config.BOT_PREFIX,
    intents=intents,
    description="An all-in-one Discord bot with moderation, utility, roles, fun, and logging.",
    activity=discord.Activity(type=discord.ActivityType.watching, name=f"{config.BOT_PREFIX}help"),
)


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
    "cogs.leveling",
    "cogs.reminders",
    "cogs.tickets",
]


def get_prefix(bot_instance, message):
    """Dynamic prefix: check dashboard settings, fall back to default."""
    if message.guild:
        settings = config.get_guild_settings(str(message.guild.id))
        guild_prefix = settings.get("prefix", config.BOT_PREFIX)
    else:
        guild_prefix = config.BOT_PREFIX
    return guild_prefix


# Re-create bot with dynamic prefix
from cogs.help import CustomHelp
bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    description="An all-in-one Discord bot with moderation, utility, roles, fun, and logging.",
    activity=discord.Activity(type=discord.ActivityType.watching, name="$help | Dashboard"),
    help_command=CustomHelp(),
)


@bot.event
async def on_ready():
    print("─" * 40)
    print(f"  Bot:    {bot.user} ({bot.user.id})")
    print(f"  Guilds: {len(bot.guilds)}")
    print(f"  Prefix: {config.BOT_PREFIX} (dynamic)")
    print("─" * 40)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"  Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"  Failed to sync slash commands: {e}")
    print("─" * 40)


@bot.event
async def on_message(message):
    """Check for alias commands before processing."""
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    # Check for custom aliases from dashboard
    settings = config.get_guild_settings(str(message.guild.id))
    aliases = settings.get("aliases", {})
    prefix = settings.get("prefix", config.BOT_PREFIX)

    content = message.content
    if content.startswith(prefix):
        args = content[len(prefix):].strip().split()
        if args:
            cmd_name = args[0].lower()
            if cmd_name in aliases:
                # Replace alias with actual command
                actual_cmd = aliases[cmd_name]
                message._original_content = content
                message.content = f"{prefix}{actual_cmd} {' '.join(args[1:])}"

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: discord.ext.commands.errors.CommandError):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=utils.error("Missing Argument", f"```\n{error}\n```"))
    elif isinstance(error, commands.CommandNotFound):
        pass  # silently ignore unknown commands
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=utils.warning("Cooldown", f"Try again in {error.retry_after:.1f}s."))
    elif isinstance(error, commands.MissingPermissions):
        pass  # silently ignore - no reply
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(embed=utils.error("Bot Missing Permissions", f"I need: **{', '.join(error.missing_permissions)}**"))
    elif isinstance(error, commands.CheckFailure):
        pass  # silently ignore - no reply
    else:
        raise error


def start_dashboard():
    """Run the Flask dashboard in a separate thread."""
    import os
    from dashboard import app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def main():
    # Start dashboard in background thread
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

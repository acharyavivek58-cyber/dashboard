import discord
import config


def success(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=config.COLOR_SUCCESS)


def error(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=config.COLOR_ERROR)


def info(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=config.COLOR_INFO)


def warning(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=config.COLOR_WARNING)


def member_embed(member: discord.Member) -> discord.Embed:
    """Build a rich embed for a member."""
    e = discord.Embed(title=str(member), color=member.color if member.color != discord.Color.default() else config.COLOR_INFO)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="ID", value=str(member.id), inline=True)
    e.add_field(name="Nickname", value=member.nick or "None", inline=True)
    e.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    e.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "Unknown", inline=True)
    roles = [r.mention for r in reversed(member.roles[1:])]
    e.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles) if roles else "None", inline=False)
    return e


def server_embed(guild: discord.Guild) -> discord.Embed:
    """Build a rich embed for a server."""
    e = discord.Embed(title=guild.name, color=config.COLOR_INFO)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    e.add_field(name="Members", value=guild.member_count, inline=True)
    e.add_field(name="Channels", value=len(guild.channels), inline=True)
    e.add_field(name="Roles", value=len(guild.roles), inline=True)
    e.add_field(name="Boost Level", value=guild.premium_tier.value, inline=True)
    e.add_field(name="Boosts", value=guild.premium_subscription_count or 0, inline=True)
    e.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"), inline=False)
    return e

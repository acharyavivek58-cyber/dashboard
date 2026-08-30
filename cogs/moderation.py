import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import config
from utils import success, error, info


# Role names for permission tiers (case-insensitive)
# The server owner always has access to everything.

# Staff Team: can warn, mute, unmute, warnings, purge
STAFF_ROLE_NAMES = [
    "staff team",
]

# Admin+ (Co Ownzzz and above): can ban, kick (everything staff can + more)
ADMIN_ROLE_NAMES = [
    "co ownzzz",
    "ownzzz",
    "founderzz",
    "$",
]

# Combined list for the broader check
ALL_TRUSTED_ROLES = STAFF_ROLE_NAMES + ADMIN_ROLE_NAMES


class Moderation(commands.Cog):
    """Moderation commands — ban, kick, mute, warn, purge."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings: dict[int, list[dict]] = {}  # guild_id -> [{user, reason, mod, time}]

    def _check_staff(self, member: discord.Member) -> bool:
        """Check if member has a Staff Team+ role or is the server owner."""
        if member.id == member.guild.owner_id:
            return True
        for role in member.roles:
            if role.name.lower() in ALL_TRUSTED_ROLES:
                return True
        return False

    def _check_admin(self, member: discord.Member) -> bool:
        """Check if member has an Admin+ role (Co Ownzzz+) or is the server owner."""
        if member.id == member.guild.owner_id:
            return True
        for role in member.roles:
            if role.name.lower() in ADMIN_ROLE_NAMES:
                return True
        return False

    async def _staff_before_invoke(self, ctx: commands.Context):
        """Pre-check for staff-level commands (warn, mute, unmute, purge)."""
        if not self._check_staff(ctx.author):
            await ctx.send(embed=error("Permission Denied", "You need a Staff Team+ role to use this command."))
            raise commands.CheckFailure("staff_role")

    async def _admin_before_invoke(self, ctx: commands.Context):
        """Pre-check for admin-level commands (ban, kick)."""
        if not self._check_admin(ctx.author):
            await ctx.send(embed=error("Permission Denied", "You need a Co-Owner+ role to use this command."))
            raise commands.CheckFailure("admin_role")

    async def _resolve_member(self, ctx: commands.Context, value: str) -> discord.Member | None:
        """Resolve a mention, username, or user ID to a Member."""
        # Try mention first
        if ctx.message.mentions:
            return ctx.message.mentions[0]
        # Try ID
        try:
            member_id = int(value)
            return ctx.guild.get_member(member_id) or await ctx.guild.fetch_member(member_id)
        except (ValueError, discord.NotFound, discord.HTTPException):
            return None

    async def _resolve_member_from_args(self, ctx: commands.Context, args: list[str]) -> discord.Member | None:
        """Resolve member from the first non-numeric arg or first arg if all args are checked."""
        if ctx.message.mentions:
            return ctx.message.mentions[0]
        if args:
            return await self._resolve_member(ctx, args[0])
        return None

    def _parse_duration(self, raw: str) -> tuple[datetime.timedelta, str] | None:
        """
        Parse a duration string like '5s', '10m', '1h', '2d', '1w'.
        Returns (timedelta, human_string) or None on failure.
        Max is 14 days (Discord limit).
        """
        raw = raw.strip().lower()
        units = {
            's': ('second', 'seconds'),
            'm': ('minute', 'minutes'),
            'h': ('hour', 'hours'),
            'd': ('day', 'days'),
            'w': ('week', 'weeks'),
        }
        if not raw[-1] in units:
            return None
        suffix = raw[-1]
        num_str = raw[:-1]
        try:
            num = int(num_str)
        except ValueError:
            return None
        if num <= 0:
            return None

        if suffix == 's':
            td = datetime.timedelta(seconds=num)
        elif suffix == 'm':
            td = datetime.timedelta(minutes=num)
        elif suffix == 'h':
            td = datetime.timedelta(hours=num)
        elif suffix == 'd':
            td = datetime.timedelta(days=num)
        elif suffix == 'w':
            td = datetime.timedelta(weeks=num)
        else:
            return None

        max_td = datetime.timedelta(days=14)
        if td > max_td:
            return None

        singular, plural = units[suffix]
        label = singular if num == 1 else plural
        return (td, f"{num} {label}")

    # ── Ban ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @commands.before_invoke(_admin_before_invoke)
    @app_commands.describe(member="Member to ban (mention or ID)", reason="Reason for ban", delete_days="Days of messages to delete (0-7)")
    async def ban(self, ctx: commands.Context, member: str, reason: str = "No reason provided", delete_days: int = 0):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member == ctx.author:
            return await ctx.send(embed=error("Error", "You cannot ban yourself."))
        if member.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot ban someone with a role equal or higher than mine."))
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=error("Error", "You cannot ban someone with an equal or higher role."))

        delete_days = max(0, min(7, delete_days))
        await member.ban(reason=f"{ctx.author}: {reason}", delete_message_days=delete_days)

        e = success("🔨 Banned", f"**{member}** has been banned.\n**Reason:** {reason}")
        await ctx.send(embed=e)

        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID) if config.LOG_CHANNEL_ID else None
        if log_channel:
            await log_channel.send(embed=success(
                "🔨 Member Banned",
                f"**User:** {member} ({member.id})\n**Moderator:** {ctx.author}\n**Reason:** {reason}"
            ))

    # ── Kick ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @commands.before_invoke(_admin_before_invoke)
    @app_commands.describe(member="Member to kick (mention or ID)", reason="Reason for kick")
    async def kick(self, ctx: commands.Context, member: str, reason: str = "No reason provided"):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member == ctx.author:
            return await ctx.send(embed=error("Error", "You cannot kick yourself."))
        if member.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot kick someone with a role equal or higher than mine."))
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=error("Error", "You cannot kick someone with an equal or higher role."))

        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=success("👢 Kicked", f"**{member}** has been kicked.\n**Reason:** {reason}"))

    # ── Mute (timeout) ───────────────────────────────────────────────────
    @commands.hybrid_command(name="mute", description="Timeout (mute) a member")
    @commands.before_invoke(_staff_before_invoke)
    @app_commands.describe(member="Member to mute (mention or ID)", duration="Duration (e.g. 30s, 10m, 1h, 2d, 1w) — max 14d", reason="Reason for mute")
    async def mute(self, ctx: commands.Context, member: str, duration: str = "10m", reason: str = "No reason provided"):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot mute someone with a role equal or higher than mine."))

        parsed = self._parse_duration(duration)
        if parsed is None:
            return await ctx.send(embed=error("Invalid Duration", "Use format: `30s`, `10m`, `1h`, `2d`, `1w`\nMax duration is **14 days**."))

        td, label = parsed
        await member.timeout(td, reason=f"{ctx.author}: {reason}")

        expires = discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc) + td, "R")
        await ctx.send(embed=success("🔇 Muted", f"**{member}** muted for **{label}**.\nExpires: {expires}\n**Reason:** {reason}"))

    # ── Unmute ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="unmute", description="Remove timeout from a member")
    @commands.before_invoke(_staff_before_invoke)
    @app_commands.describe(member="Member to unmute (mention or ID)")
    async def unmute(self, ctx: commands.Context, member: str):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        await member.timeout(None, reason=f"Unmuted by {ctx.author}")
        await ctx.send(embed=success("🔊 Unmuted", f"**{member}** has been unmuted."))

    # ── Warn ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.before_invoke(_staff_before_invoke)
    @app_commands.describe(member="Member to warn (mention or ID)", reason="Reason for warning")
    async def warn(self, ctx: commands.Context, member: str, reason: str = "No reason provided"):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member.bot:
            return await ctx.send(embed=error("Error", "You cannot warn a bot."))

        gid = ctx.guild.id
        self.warnings.setdefault(gid, []).append({
            "user": member.id,
            "reason": reason,
            "mod": ctx.author.id,
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        count = sum(1 for w in self.warnings[gid] if w["user"] == member.id)

        await ctx.send(embed=success("⚠️ Warned", f"**{member}** has been warned.\n**Total warnings:** {count}\n**Reason:** {reason}"))

    # ── Warnings ─────────────────────────────────────────────────────────
    @commands.hybrid_command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check (mention or ID)")
    async def warnings(self, ctx: commands.Context, member: str):
        member = await self._resolve_member(ctx, member)
        if member is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        gid = ctx.guild.id
        warns = [w for w in self.warnings.get(gid, []) if w["user"] == member.id]
        if not warns:
            return await ctx.send(embed=info("Warnings", f"**{member}** has no warnings."))

        lines = []
        for i, w in enumerate(warns, 1):
            mod = ctx.guild.get_member(w["mod"])
            lines.append(f"`{i}.` **Reason:** {w['reason']}\n    **Mod:** {mod or 'Unknown'} | **Time:** {w['time'][:10]}")

        e = info(f"Warnings for {member} ({len(warns)})", "\n".join(lines))
        await ctx.send(embed=e)

    # ── Purge ────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="purge", description="Bulk delete messages in a channel")
    @commands.before_invoke(_staff_before_invoke)
    @app_commands.describe(amount="Number of messages to delete (1-100)", member="Only delete messages from this member (mention or ID)")
    async def purge(self, ctx: commands.Context, amount: int = 10, member: str = None):
        if member:
            member = await self._resolve_member(ctx, member)
        if amount < 1 or amount > 100:
            return await ctx.send(embed=error("Error", "Amount must be between 1 and 100."))

        await ctx.defer(ephemeral=True)

        def check(m):
            return member is None or m.author == member

        deleted = await ctx.channel.purge(limit=amount, check=check)
        await ctx.send(embed=success("🗑️ Purged", f"Deleted **{len(deleted)}** messages{' from **' + str(member) + '**' if member else ''}."), delete_after=5)


import config

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
import datetime
import config
from utils import success, error, info


class Moderation(commands.Cog):
    """Moderation commands — ban, kick, mute, warn, purge."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings: dict[int, list[dict]] = {}
        self._load_warnings()

    def _load_warnings(self):
        data = config.load_state("mod_warnings.json")
        for gid_s, warns in data.items():
            self.warnings[int(gid_s)] = warns

    def _save_warnings(self):
        data = {str(gid): warns for gid, warns in self.warnings.items()}
        config.save_state("mod_warnings.json", data)

    def _check_permission(self, member: discord.Member, command: str) -> bool:
        return config.has_permission(command, member)

    async def _resolve_member(self, ctx: commands.Context, value: str) -> discord.Member | None:
        if ctx.message and ctx.message.mentions:
            return ctx.message.mentions[0]
        import re
        mention_match = re.match(r'<@!?([0-9]+)>', value)
        if mention_match:
            member_id = int(mention_match.group(1))
            member = ctx.guild.get_member(member_id)
            if member:
                return member
            try:
                return await ctx.guild.fetch_member(member_id)
            except (discord.NotFound, discord.HTTPException):
                return None
        try:
            member_id = int(value)
            member = ctx.guild.get_member(member_id)
            if member:
                return member
            try:
                return await ctx.guild.fetch_member(member_id)
            except (discord.NotFound, discord.HTTPException):
                return None
        except ValueError:
            pass
        value_lower = value.lower()
        for member in ctx.guild.members:
            if (member.name.lower() == value_lower or
                member.display_name.lower() == value_lower or
                (member.nick and member.nick.lower() == value_lower)):
                return member
        for member in ctx.guild.members:
            if value_lower in member.name.lower() or value_lower in member.display_name.lower():
                return member
        return None

    def _parse_duration(self, raw: str) -> tuple[datetime.timedelta, str] | None:
        raw = raw.strip().lower()
        units = {
            's': ('second', 'seconds'), 'm': ('minute', 'minutes'),
            'h': ('hour', 'hours'), 'd': ('day', 'days'), 'w': ('week', 'weeks'),
        }
        if not raw or raw[-1] not in units:
            return None
        suffix = raw[-1]
        try:
            num = int(raw[:-1])
        except ValueError:
            return None
        if num <= 0:
            return None
        td = datetime.timedelta(**{units[suffix][1]: num})
        if td > datetime.timedelta(days=14):
            return None
        label = units[suffix][0] if num == 1 else units[suffix][1]
        return (td, f"{num} {label}")

    def _usage_embed(self, ctx, cmd_name: str, description: str, cooldown: str, usage: str, examples: list[str]) -> discord.Embed:
        prefix = config.BOT_PREFIX
        e = discord.Embed(color=0x5865F2)
        e.set_author(name=f"Command: {prefix}{cmd_name}", icon_url=ctx.bot.user.display_avatar.url)
        e.add_field(name="Description", value=description, inline=False)
        e.add_field(name="Cooldown", value=cooldown, inline=True)
        e.add_field(name="Usage", value=f"`{prefix}{usage}`", inline=False)
        if examples:
            ex_lines = "\n".join(f"`{prefix}{ex}`" for ex in examples)
            e.add_field(name="Examples", value=ex_lines, inline=False)
        return e

    # ── Ban ──────────────────────────────────────────────────────────────
    @commands.command(name="ban", description="Ban a member from the server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ban(self, ctx: commands.Context, *, member: str = None):
        if not self._check_permission(ctx.author, "ban"):
            return
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "ban", "Ban a member from the server.", "5 seconds",
                "ban [user] [reason] [delete_days]",
                ["ban @NoobLance Spamming", "ban @User 3 Repeated warnings", "ban @NoobLance Raiding the server"]
            ))
        parts = member.split(None, 2)
        member_name = parts[0]
        reason = parts[1] if len(parts) > 1 else "No reason provided"
        delete_days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        member_obj = await self._resolve_member(ctx, member_name)
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member_obj == ctx.author:
            return await ctx.send(embed=error("Error", "You cannot ban yourself."))
        if member_obj.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot ban someone with a role equal or higher than mine."))
        if member_obj.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=error("Error", "You cannot ban someone with an equal or higher role."))

        delete_days = max(0, min(7, delete_days))
        await member_obj.ban(reason=f"{ctx.author}: {reason}", delete_message_days=delete_days)
        await ctx.send(embed=success("🔨 Banned", f"**{member_obj}** has been banned.\n**Reason:** {reason}"))

        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID) if config.LOG_CHANNEL_ID else None
        if log_channel:
            await log_channel.send(embed=success("🔨 Member Banned", f"**User:** {member_obj} ({member_obj.id})\n**Moderator:** {ctx.author}\n**Reason:** {reason}"))

    # ── Kick ─────────────────────────────────────────────────────────────
    @commands.command(name="kick", description="Kick a member from the server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def kick(self, ctx: commands.Context, *, member: str = None):
        if not self._check_permission(ctx.author, "ban"):
            return
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "kick", "Kick a member from the server.", "5 seconds",
                "kick [user] [reason]",
                ["kick @NoobLance Spamming", "kick @User Breaking rules", "kick @NoobLance Toxic behavior"]
            ))
        parts = member.split(None, 1)
        member_name = parts[0]
        reason = parts[1] if len(parts) > 1 else "No reason provided"

        member_obj = await self._resolve_member(ctx, member_name)
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member_obj == ctx.author:
            return await ctx.send(embed=error("Error", "You cannot kick yourself."))
        if member_obj.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot kick someone with a role equal or higher than mine."))
        if member_obj.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=error("Error", "You cannot kick someone with an equal or higher role."))

        await member_obj.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=success("👢 Kicked", f"**{member_obj}** has been kicked.\n**Reason:** {reason}"))

    # ── Mute (timeout) ───────────────────────────────────────────────────
    @commands.command(name="mute", description="Timeout (mute) a member")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mute(self, ctx: commands.Context, *, member: str = None):
        if not self._check_permission(ctx.author, "mute"):
            return
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "mute", "Mute a member so they cannot type.", "5 seconds",
                "mute [user] [duration] [reason]",
                ["mute @NoobLance 10 Shitposting", "mute @User 10m spamming", "mute @NoobLance 1d Too Cool", "mute @NoobLance 5h He asked for it"]
            ))
        parts = member.split(None, 2)
        member_name = parts[0]
        duration = parts[1] if len(parts) > 1 else "10m"
        reason = parts[2] if len(parts) > 2 else "No reason provided"

        member_obj = await self._resolve_member(ctx, member_name)
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member_obj.top_role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I cannot mute someone with a role equal or higher than mine."))

        parsed = self._parse_duration(duration)
        if parsed is None:
            return await ctx.send(embed=error("Invalid Duration", "Use format: `30s`, `10m`, `1h`, `2d`, `1w`\nMax duration is **14 days**."))

        td, label = parsed
        await member_obj.timeout(td, reason=f"{ctx.author}: {reason}")
        expires = discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc) + td, "R")
        await ctx.send(embed=success("🔇 Muted", f"**{member_obj}** muted for **{label}**.\nExpires: {expires}\n**Reason:** {reason}"))

    # ── Unmute ───────────────────────────────────────────────────────────
    @commands.command(name="unmute", description="Remove timeout from a member")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def unmute(self, ctx: commands.Context, *, member: str = None):
        if not self._check_permission(ctx.author, "mute"):
            return
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "unmute", "Remove timeout from a member.", "3 seconds",
                "unmute [user]",
                ["unmute @NoobLance", "unmute @User"]
            ))
        member_obj = await self._resolve_member(ctx, member.strip())
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        await member_obj.timeout(None, reason=f"Unmuted by {ctx.author}")
        await ctx.send(embed=success("🔊 Unmuted", f"**{member_obj}** has been unmuted."))

    # ── Warn ─────────────────────────────────────────────────────────────
    @commands.command(name="warn", description="Warn a member")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def warn(self, ctx: commands.Context, *, member: str = None):
        if not self._check_permission(ctx.author, "mute"):
            return
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "warn", "Warn a member for breaking rules.", "3 seconds",
                "warn [user] [reason]",
                ["warn @NoobLance Spamming", "warn @User Breaking rules", "warn @NoobLance Toxic behavior"]
            ))
        parts = member.split(None, 1)
        member_name = parts[0]
        reason = parts[1] if len(parts) > 1 else "No reason provided"

        member_obj = await self._resolve_member(ctx, member_name)
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        if member_obj.bot:
            return await ctx.send(embed=error("Error", "You cannot warn a bot."))

        gid = ctx.guild.id
        self.warnings.setdefault(gid, []).append({
            "user": member_obj.id, "reason": reason,
            "mod": ctx.author.id, "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        count = sum(1 for w in self.warnings[gid] if w["user"] == member_obj.id)
        self._save_warnings()
        await ctx.send(embed=success("⚠️ Warned", f"**{member_obj}** has been warned.\n**Total warnings:** {count}\n**Reason:** {reason}"))

    # ── Warnings ─────────────────────────────────────────────────────────
    @commands.command(name="warnings", description="View warnings for a member")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def warnings(self, ctx: commands.Context, *, member: str = None):
        if not member:
            return await ctx.send(embed=self._usage_embed(
                ctx, "warnings", "View warnings for a member.", "3 seconds",
                "warnings [user]",
                ["warnings @NoobLance", "warnings @User"]
            ))
        member_obj = await self._resolve_member(ctx, member.strip())
        if member_obj is None:
            return await ctx.send(embed=error("Error", "Could not find that member."))
        gid = ctx.guild.id
        warns = [w for w in self.warnings.get(gid, []) if w["user"] == member_obj.id]
        if not warns:
            return await ctx.send(embed=info("Warnings", f"**{member_obj}** has no warnings."))
        lines = []
        for i, w in enumerate(warns, 1):
            mod = ctx.guild.get_member(w["mod"])
            lines.append(f"`{i}.` **Reason:** {w['reason']}\n    **Mod:** {mod or 'Unknown'} | **Time:** {w['time'][:10]}")
        await ctx.send(embed=info(f"Warnings for {member_obj} ({len(warns)})", "\n".join(lines)))

    # ── Purge ────────────────────────────────────────────────────────────
    @commands.command(name="purge", description="Bulk delete messages in a channel")
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def purge(self, ctx: commands.Context, amount: int = None, member: discord.Member = None):
        if not self._check_permission(ctx.author, "mute"):
            return
        if amount is None:
            return await ctx.send(embed=self._usage_embed(
                ctx, "purge", "Bulk delete messages in a channel.", "10 seconds",
                "purge [amount] [user]",
                ["purge 50", "purge 20 @NoobLance", "purge 100 @User"]
            ))
        if amount < 1 or amount > 100:
            return await ctx.send(embed=error("Error", "Amount must be between 1 and 100."))
        await ctx.defer(ephemeral=True)
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: member is None or m.author == member)
        await ctx.send(embed=success("🗑️ Purged", f"Deleted **{len(deleted)}** messages{' from **' + str(member) + '**' if member else ''}."), delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))

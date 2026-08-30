import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from utils import success, error, info

DATA_FILE = "invite_data.json"


class InviteTracker(commands.Cog):
    """Invite tracker — track who invited whom, leaderboard, and stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self._load()
        # Cache invites on ready
        self.bot.loop.create_task(self._cache_invites())

    def _load(self) -> dict:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    async def _cache_invites(self):
        """Cache all invites on bot start."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.data[str(guild.id)] = {
                    "invites": {inv.code: inv.uses for inv in invites},
                    "members": self.data.get(str(guild.id), {}).get("members", {}),
                }
            except discord.Forbidden:
                pass
        self._save()

    def _get_guild_data(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {"invites": {}, "members": {}}
        if "invites" not in self.data[gid]:
            self.data[gid]["invites"] = {}
        if "members" not in self.data[gid]:
            self.data[gid]["members"] = {}
        return self.data[gid]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track which invite was used."""
        guild = member.guild
        gid = str(guild.id)
        guild_data = self._get_guild_data(guild.id)

        try:
            invites = await guild.invites()
        except discord.Forbidden:
            return

        # Find which invite was used (uses increased)
        old_uses = guild_data.get("invites", {})
        used_invite = None

        for inv in invites:
            old_count = old_uses.get(inv.code, 0)
            if inv.uses > old_count:
                used_invite = inv
                break

        if used_invite:
            inviter = used_invite.inviter
            if inviter:
                inviter_id = str(inviter.id)
                guild_data["members"].setdefault(inviter_id, {"total": 0, "joins": 0, "leaves": 0, "fake": 0})
                guild_data["members"][inviter_id]["total"] += 1
                guild_data["members"][inviter_id]["joins"] += 1

        # Update cached invite counts
        guild_data["invites"] = {inv.code: inv.uses for inv in invites}
        self._save()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Track leaves."""
        guild_data = self._get_guild_data(member.guild.id)

        # Find who invited this member
        for inviter_id, data in guild_data.get("members", {}).items():
            if data.get("joins", 0) > 0:
                data["leaves"] = data.get("leaves", 0) + 1
                break

        self._save()

    # ── Invite Info ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="invites", description="Check invite stats for a member")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def invites(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        guild_data = self._get_guild_data(ctx.guild.id)
        member_data = guild_data.get("members", {}).get(str(member.id), {})

        total = member_data.get("total", 0)
        joins = member_data.get("joins", 0)
        leaves = member_data.get("leaves", 0)
        fake = member_data.get("fake", 0)
        regular = total - fake

        e = info(
            f"📨 Invites — {member.display_name}",
            f"**Regular:** {regular}\n"
            f"**Joins:** {joins}\n"
            f"**Leaves:** {leaves}\n"
            f"**Fake:** {fake}\n"
            f"**Total:** {total}"
        )
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    # ── Invite Leaderboard ────────────────────────────────────────────────
    @commands.hybrid_command(name="inviteboard", description="Invite leaderboard for this server")
    @app_commands.describe(show="Number of entries to show (default 10)")
    async def inviteboard(self, ctx: commands.Context, show: int = 10):
        guild_data = self._get_guild_data(ctx.guild.id)
        members = guild_data.get("members", {})

        if not members:
            return await ctx.send(embed=info("📨 Invites", "No invite data yet."))

        # Sort by regular invites (total - fake)
        sorted_members = sorted(
            members.items(),
            key=lambda x: x[1].get("total", 0) - x[1].get("fake", 0),
            reverse=True
        )[:show]

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, data) in enumerate(sorted_members):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"Unknown ({uid})"
            total = data.get("total", 0)
            fake = data.get("fake", 0)
            regular = total - fake
            leaves = data.get("leaves", 0)
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{prefix} {name} — `{regular}` regular, `{leaves}` leaves")

        e = info(f"📨 Invite Leaderboard — {ctx.guild.name}", "\n".join(lines))
        await ctx.send(embed=e)

    # ── Server Invite Stats ───────────────────────────────────────────────
    @commands.hybrid_command(name="invitestats", description="Server-wide invite statistics")
    async def invitestats(self, ctx: commands.Context):
        guild_data = self._get_guild_data(ctx.guild.id)
        members = guild_data.get("members", {})

        total_invites = sum(d.get("total", 0) for d in members.values())
        total_joins = sum(d.get("joins", 0) for d in members.values())
        total_leaves = sum(d.get("leaves", 0) for d in members.values())
        active_inviters = len([d for d in members.values() if d.get("total", 0) > 0])

        # Top inviter
        top = max(members.items(), key=lambda x: x[1].get("total", 0)) if members else None
        top_name = "None"
        if top:
            member = ctx.guild.get_member(int(top[0]))
            top_name = member.display_name if member else "Unknown"

        e = info(
            f"📨 Invite Stats — {ctx.guild.name}",
            f"**Total Invites:** {total_invites}\n"
            f"**Total Joins:** {total_joins}\n"
            f"**Total Leaves:** {total_leaves}\n"
            f"**Active Inviters:** {active_inviters}\n"
            f"**Top Inviter:** {top_name}"
        )
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))

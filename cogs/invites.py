import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import config

DATA_FILE = "invite_data.json"


class InviteTracker(commands.Cog):
    """Invite tracker — track who invited whom, leaderboard, and stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self._load()

    async def cog_before_invoke(self, ctx: commands.Context):
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    def _load(self) -> dict:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except IOError:
            pass

    def _get_guild_data(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {"invites": {}, "members": {}}
        return self.data[gid]

    @commands.Cog.listener()
    async def on_ready(self):
        """Cache invites on startup."""
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                gid = str(guild.id)
                if gid not in self.data:
                    self.data[gid] = {"invites": {}, "members": {}}
                self.data[gid]["invites"] = {inv.code: inv.uses for inv in invites}
            except Exception:
                pass
        self._save()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            guild_data = self._get_guild_data(member.guild.id)
            invites = await member.guild.invites()
            old_uses = guild_data.get("invites", {})
            for inv in invites:
                old = old_uses.get(inv.code, 0)
                if inv.uses > old and inv.inviter:
                    inviter_id = str(inv.inviter.id)
                    if inviter_id not in guild_data.get("members", {}):
                        guild_data.setdefault("members", {})[inviter_id] = {"total": 0, "joins": 0, "leaves": 0, "fake": 0}
                    guild_data["members"][inviter_id]["total"] += 1
                    guild_data["members"][inviter_id]["joins"] += 1
                    break
            guild_data["invites"] = {inv.code: inv.uses for inv in invites}
            self._save()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            guild_data = self._get_guild_data(member.guild.id)
            for uid, data in guild_data.get("members", {}).items():
                if data.get("joins", 0) > data.get("leaves", 0):
                    data["leaves"] = data.get("leaves", 0) + 1
                    break
            self._save()
        except Exception:
            pass

    @commands.hybrid_command(name="invites", description="Check invite stats for a member")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def invites_cmd(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        guild_data = self._get_guild_data(ctx.guild.id)
        member_data = guild_data.get("members", {}).get(str(member.id), {})

        total = member_data.get("total", 0)
        joins = member_data.get("joins", 0)
        leaves = member_data.get("leaves", 0)
        fake = member_data.get("fake", 0)
        regular = total - fake

        e = discord.Embed(color=0x5865F2)
        e.set_author(name="Invite log")
        e.description = f"» **{member.display_name}** has **{regular}** invites"
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="Joins :", value=f"**{joins}**", inline=True)
        e.add_field(name="Left :", value=f"**{leaves}**", inline=True)
        e.add_field(name="Fake :", value=f"**{fake}**", inline=True)
        e.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="inviteboard", description="Invite leaderboard")
    async def inviteboard(self, ctx: commands.Context):
        guild_data = self._get_guild_data(ctx.guild.id)
        members = guild_data.get("members", {})
        if not members:
            return await ctx.send(embed=discord.Embed(description="No invite data yet.", color=0x5865F2))

        sorted_m = sorted(members.items(), key=lambda x: x[1].get("total", 0), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(sorted_m):
            m = ctx.guild.get_member(int(uid))
            name = m.display_name if m else "Unknown"
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{prefix} **{name}** — `{data.get('total', 0)}` invites")

        e = discord.Embed(title="📨 Invite Leaderboard", description="\n".join(lines), color=0x5865F2)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="invitestats", description="Server invite stats")
    async def invitestats(self, ctx: commands.Context):
        guild_data = self._get_guild_data(ctx.guild.id)
        members = guild_data.get("members", {})
        total = sum(d.get("total", 0) for d in members.values())
        joins = sum(d.get("joins", 0) for d in members.values())
        leaves = sum(d.get("leaves", 0) for d in members.values())

        e = discord.Embed(title="📨 Invite Stats", color=0x5865F2)
        e.add_field(name="Total Invites", value=f"**{total}**", inline=True)
        e.add_field(name="Joins", value=f"**{joins}**", inline=True)
        e.add_field(name="Leaves", value=f"**{leaves}**", inline=True)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))

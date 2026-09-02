import discord
from discord.ext import commands
from discord import app_commands
import datetime
import config
from utils import success, error, info, member_embed, server_embed


class Utility(commands.Cog):
    """Utility commands — info, avatar, ping, uptime, avatar."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    async def cog_before_invoke(self, ctx: commands.Context):
        """Check dashboard permissions for utility commands."""
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    # ── Ping ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ping", description="Check bot latency")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        e = success("🏓 Pong!", f"**Latency:** {latency}ms\n**API:** {latency}ms")
        await ctx.send(embed=e)

    # ── Uptime ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="uptime", description="Show bot uptime")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def uptime(self, ctx: commands.Context):
        delta = datetime.datetime.now(datetime.timezone.utc) - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        await ctx.send(embed=success("⏱️ Uptime", " ".join(parts)))

    # ── User Info ────────────────────────────────────────────────────────
    @commands.hybrid_command(name="userinfo", description="Get info about a member")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(member="Member to get info about (defaults to you)")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(embed=member_embed(member))

    # ── Server Info ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="serverinfo", description="Get info about this server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def serverinfo(self, ctx: commands.Context):
        await ctx.send(embed=server_embed(ctx.guild))

    # ── Avatar ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="avatar", description="Get a member's avatar")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(member="Member whose avatar to get")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        e = discord.Embed(title=f"{member.display_name}'s Avatar", color=member.color if member.color != discord.Color.default() else 0x5865F2)
        e.set_image(url=member.display_avatar.url)
        e.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=e)

    # ── Server Icon ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="servericon", description="Get the server's icon")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def servericon(self, ctx: commands.Context):
        if not ctx.guild.icon:
            return await ctx.send(embed=error("Error", "This server has no icon."))
        e = discord.Embed(title=f"{ctx.guild.name}'s Icon", color=0x5865F2)
        e.set_image(url=ctx.guild.icon.url)
        await ctx.send(embed=e)

    # ── Lookup ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="id", description="Get a member's user ID")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(member="Member to look up")
    async def user_id(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(embed=success("ID", f"**{member}** → `{member.id}`"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))

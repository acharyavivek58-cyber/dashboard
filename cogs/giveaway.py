import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
from utils import success, error, info, warning
import config


class Giveaway(commands.Cog):
    """Giveaway system — create, end, reroll giveaways with timed winners."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_giveaways: dict[int, dict] = {}  # message_id -> giveaway data
        self.giveaway_loop.start()

    def cog_unload(self):
        self.giveaway_loop.cancel()

    @tasks.loop(seconds=5)
    async def giveaway_loop(self):
        """Check for expired giveaways."""
        now = datetime.datetime.now(datetime.timezone.utc)
        ended = []

        for msg_id, data in self.active_giveaways.items():
            if now >= data["end_time"]:
                ended.append(msg_id)

        for msg_id in ended:
            data = self.active_giveaways.pop(msg_id)
            await self._end_giveaway(data)

    @giveaway_loop.before_loop
    async def before_giveaway_loop(self):
        await self.bot.wait_until_ready()

    async def _end_giveaway(self, data: dict):
        """End a giveaway and pick winner(s)."""
        channel = self.bot.get_channel(data["channel_id"])
        if not channel:
            return

        try:
            message = await channel.fetch_message(data["message_id"])
        except discord.NotFound:
            return

        # Get all users who reacted with 🎉
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction or reaction.count <= 1:
            e = warning("🎉 Giveaway Ended", f"**{data['prize']}**\nNo valid entries — nobody won!")
            await message.edit(embed=e, view=None)
            return

        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)

        if not users:
            e = warning("🎉 Giveaway Ended", f"**{data['prize']}**\nNo valid entries — nobody won!")
            await message.edit(embed=e, view=None)
            return

        # Pick winner(s)
        import random
        winners_count = min(data["winners"], len(users))
        winners = random.sample(users, winners_count)
        winner_mentions = ", ".join(w.mention for w in winners)

        e = success(
            "🎉 Giveaway Ended!",
            f"**Prize:** {data['prize']}\n**Winner(s):** {winner_mentions}\n**Entries:** {len(users)}"
        )
        e.set_footer(text=f"Hosted by {data['host']}")
        await message.edit(embed=e, view=None)

        await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{data['prize']}**!")

    def _parse_duration(self, raw: str) -> datetime.timedelta | None:
        """Parse duration like 30m, 1h, 2d."""
        raw = raw.strip().lower()
        if not raw:
            return None

        units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        if raw[-1] not in units:
            return None

        try:
            num = int(raw[:-1])
        except ValueError:
            return None

        if num <= 0:
            return None

        seconds = num * units[raw[-1]]
        max_seconds = 30 * 86400  # 30 days max
        if seconds > max_seconds:
            return None

        return datetime.timedelta(seconds=seconds)

    # ── Giveaway Command ──────────────────────────────────────────────────
    @commands.hybrid_command(name="giveaway", description="Start a giveaway")
    @app_commands.describe(
        duration="Duration (e.g. 30m, 1h, 2d)",
        winners="Number of winners (default 1)",
        prize="What are you giving away?"
    )
    @commands.before_invoke("_staff_check")
    async def giveaway(self, ctx: commands.Context, duration: str, winners: int = 1, *, prize: str = "No prize specified"):
        td = self._parse_duration(duration)
        if not td:
            return await ctx.send(embed=error("Invalid Duration", "Use format: `30m`, `1h`, `2d`, `1w`\nMax: 30 days"))

        if winners < 1 or winners > 20:
            return await ctx.send(embed=error("Error", "Winners must be between 1 and 20."))

        end_time = datetime.datetime.now(datetime.timezone.utc) + td

        # Build embed
        e = discord.Embed(
            title="🎉 Giveaway!",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winner(s):** {winners}\n"
                f"**Hosted by:** {ctx.author.mention}\n\n"
                f"React with 🎉 to enter!\n"
                f"Ends: {discord.utils.format_dt(end_time, 'R')}"
            ),
            color=0x57F287,
            timestamp=end_time,
        )
        e.set_footer(text=f"Ends at")
        e.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        msg = await ctx.send(embed=e)
        await msg.add_reaction("🎉")

        # Store giveaway data
        self.active_giveaways[msg.id] = {
            "message_id": msg.id,
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "prize": prize,
            "winners": winners,
            "host": str(ctx.author),
            "end_time": end_time,
        }

    async def _staff_check(self, ctx: commands.Context):
        """Pre-check for giveaway commands."""
        from cogs.moderation import Moderation
        cog = self.bot.get_cog("Moderation")
        if cog and not cog._check_staff(ctx.author):
            await ctx.send(embed=error("Permission Denied", "You need a Staff Team+ role to create giveaways."))
            raise commands.CheckFailure("staff_role")

    # ── End Giveaway ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="giveawayend", description="End a giveaway early")
    @app_commands.describe(message_id="The giveaway message ID")
    async def giveawayend(self, ctx: commands.Context, message_id: int):
        data = self.active_giveaways.get(message_id)
        if not data:
            return await ctx.send(embed=error("Error", "Giveaway not found or already ended."))

        if data["guild_id"] != ctx.guild.id:
            return await ctx.send(embed=error("Error", "That giveaway is in a different server."))

        self.active_giveaways.pop(message_id)
        await self._end_giveaway(data)
        await ctx.send(embed=success("✅ Ended", "Giveaway ended early!"))

    # ── Reroll Giveaway ───────────────────────────────────────────────────
    @commands.hybrid_command(name="giveawayreroll", description="Reroll a giveaway for new winners")
    @app_commands.describe(message_id="The giveaway message ID")
    async def reroll(self, ctx: commands.Context, message_id: int):
        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send(embed=error("Error", "Message not found in this channel."))

        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction or reaction.count <= 1:
            return await ctx.send(embed=error("Error", "No valid entries to reroll."))

        import random
        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)

        if not users:
            return await ctx.send(embed=error("Error", "No valid entries."))

        winner = random.choice(users)
        await ctx.send(embed=success("🎉 Rerolled!", f"New winner: {winner.mention}"))

    # ── List Active Giveaways ─────────────────────────────────────────────
    @commands.hybrid_command(name="giveaways", description="List all active giveaways")
    async def giveaways_list(self, ctx: commands.Context):
        server_giveaways = [
            data for data in self.active_giveaways.values()
            if data["guild_id"] == ctx.guild.id
        ]

        if not server_giveaways:
            return await ctx.send(embed=info("Giveaways", "No active giveaways in this server."))

        lines = []
        for i, data in enumerate(server_giveaways, 1):
            remaining = data["end_time"] - datetime.datetime.now(datetime.timezone.utc)
            minutes = int(remaining.total_seconds() / 60)
            if minutes > 1440:
                time_left = f"{minutes // 1440}d {(minutes % 1440) // 60}h"
            elif minutes > 60:
                time_left = f"{minutes // 60}h {minutes % 60}m"
            else:
                time_left = f"{minutes}m"
            lines.append(f"`{i}.` **{data['prize']}** — {data['winners']} winner(s) — Ends in {time_left}")

        e = info(f"🎉 Active Giveaways ({len(server_giveaways)})", "\n".join(lines))
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))

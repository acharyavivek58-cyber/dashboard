import discord
from discord.ext import commands
from discord import app_commands
from utils import success, error, info
import json
import os

DATA_FILE = "counting_data.json"

# Set to a channel ID to restrict counting to one channel.
# Set to 0 to allow counting in all channels.
COUNTING_CHANNEL_ID = 1543631917855805441


class Counting(commands.Cog):
    """Counting game — react ✅ for correct, ❌ for wrong."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _get_channel(self, channel_id: int) -> dict:
        cid = str(channel_id)
        if cid not in self.data:
            self.data[cid] = {"count": 0, "last_user": None}
        return self.data[cid]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Only work in the designated counting channel
        if COUNTING_CHANNEL_ID and message.channel.id != COUNTING_CHANNEL_ID:
            return

        content = message.content.strip()

        # Delete non-number messages in the counting channel
        if not content.isdigit():
            try:
                await message.delete()
            except discord.errors.NotFound:
                pass
            return

        number = int(content)
        channel_id = message.channel.id
        state = self._get_channel(channel_id)

        expected = state["count"] + 1

        # Check if same person counted last
        if state["last_user"] == message.author.id:
            await message.add_reaction("❌")
            e = error(
                "❌ Double Count!",
                f"**{message.author.mention}** counted twice in a row!\n"
                f"The count has been reset to **0**."
            )
            state["count"] = 0
            state["last_user"] = None
            self._save()
            await message.channel.send(embed=e, delete_after=8)
            return

        if number == expected:
            # Correct!
            state["count"] = number
            state["last_user"] = message.author.id
            self._save()
            await message.add_reaction("✅")
        else:
            # Wrong — reset to 0
            old_count = state["count"]
            state["count"] = 0
            state["last_user"] = None
            self._save()
            await message.add_reaction("❌")

            # Send embed showing the reset
            e = error(
                "❌ Count Reset!",
                f"**{message.author.mention}** said `{number}` but it was `{expected}`.\n"
                f"The count has been reset to **0**."
            )
            await message.channel.send(embed=e, delete_after=8)

    # ── Count Info ────────────────────────────────────────────────────────
    @commands.hybrid_command(name="count", description="Check the current count in this channel")
    async def count(self, ctx: commands.Context):
        state = self._get_channel(ctx.channel.id)
        count = state["count"]
        if count == 0:
            await ctx.send(embed=info("🔢 Count", "No count started yet. Be the first to type a number!"))
        else:
            last_user = ctx.guild.get_member(state["last_user"]) if state["last_user"] else None
            name = last_user.display_name if last_user else "Unknown"
            await ctx.send(embed=info("🔢 Count", f"Current count: **{count}**\nNext number: **{count + 1}**\nLast counter: {name}"))

    # ── Reset Count ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="countreset", description="Reset the count in this channel")
    async def countreset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Messages` permission."))
        state = self._get_channel(ctx.channel.id)
        old = state["count"]
        state["count"] = 0
        state["last_user"] = None
        self._save()
        await ctx.send(embed=success("🔄 Count Reset", f"Count was at **{old}**, now reset to **0**."))

    # ── Set Count ─────────────────────────────────────────────────────────
    @commands.hybrid_command(name="countset", description="Set the count to a specific number")
    @app_commands.describe(number="Number to set the count to")
    async def countset(self, ctx: commands.Context, number: int):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Messages` permission."))
        if number < 0:
            return await ctx.send(embed=error("Error", "Count can't be negative."))
        state = self._get_channel(ctx.channel.id)
        state["count"] = number
        state["last_user"] = None
        self._save()
        await ctx.send(embed=success("🔢 Count Set", f"Count is now **{number}**. Next number: **{number + 1}**"))

    # ── Leaderboard ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="countlb", description="Counting leaderboard for this server")
    async def countlb(self, ctx: commands.Context):
        # Tally all counts per user across all channels
        tallies: dict[int, int] = {}
        for cid, state in self.data.items():
            # We need to track per-channel top contributors
            # Since we only store last_user, count the highest number per channel
            uid = state.get("last_user")
            count = state.get("count", 0)
            if uid and count > 0:
                tallies[uid] = tallies.get(uid, 0) + count

        if not tallies:
            return await ctx.send(embed=info("🔢 Leaderboard", "No counts recorded yet."))

        sorted_users = sorted(tallies.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, total) in enumerate(sorted_users):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else "Unknown"
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{prefix} {name} — `{total}`")

        e = info(f"🔢 Counting Leaderboard — {ctx.guild.name}", "\n".join(lines))
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))

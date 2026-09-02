import discord
from discord.ext import commands
from discord import app_commands
from utils import success, error, info
import json
import os
import asyncio
import config

DATA_FILE = "counting_data.json"
COUNTING_CHANNEL_ID = 1543631917855805441


class Counting(commands.Cog):
    """Counting game — react ✅ for correct, ❌ for wrong."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self._load()
        self._processing = set()
        print(f"[Counting] Loaded. Channel: {COUNTING_CHANNEL_ID}")
        print(f"[Counting] Data: {self.data}")

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
                    data = json.load(f)
                    print(f"[Counting] Loaded data: {data}")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Counting] Load error: {e}")
                return {}
        print("[Counting] No data file found, starting fresh")
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
            print(f"[Counting] Saved: {self.data}")
        except IOError as e:
            print(f"[Counting] Save error: {e}")

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

        # Allow Co Owner+ to type anything (they manage the channel)
        co_owner_roles = ["co ownzzz", "co owner", "co-owner", "owner"]
        is_privileged = any(r.name.lower() in co_owner_roles for r in message.author.roles) or message.author.id == message.guild.owner_id

        if not content.isdigit():
            # Only delete non-numbers if not privileged
            if is_privileged:
                return  # Let them type freely
            try:
                await message.delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                pass
            return

        # Avoid processing same message twice
        msg_id = message.id
        if msg_id in self._processing:
            print(f"[Counting] Already processing msg {msg_id}, skipping")
            return
        self._processing.add(msg_id)

        try:
            number = int(content)
            channel_id = message.channel.id
            state = self._get_channel(channel_id)
            expected = state["count"] + 1

            print(f"[Counting] Got {number}, expected {expected}, current count: {state['count']}, last_user: {state['last_user']}")

            # Check if same person counted last
            if state["last_user"] == message.author.id:
                print(f"[Counting] Double count by {message.author}")
                try:
                    await message.add_reaction("\u274c")
                except discord.errors.Forbidden:
                    pass
                e = error(
                    "\u274c Double Count!",
                    f"**{message.author.mention}** counted twice in a row!\n"
                    f"The count has been reset to **0**."
                )
                state["count"] = 0
                state["last_user"] = None
                self._save()
                try:
                    await message.channel.send(embed=e, delete_after=8)
                except discord.errors.Forbidden:
                    pass
                return

            if number == expected:
                print(f"[Counting] CORRECT! {number} == {expected}")
                state["count"] = number
                state["last_user"] = message.author.id
                self._save()
                try:
                    await message.add_reaction("\u2705")
                except discord.errors.Forbidden:
                    pass
            else:
                print(f"[Counting] WRONG! {number} != {expected}")
                state["count"] = 0
                state["last_user"] = None
                self._save()
                try:
                    await message.add_reaction("\u274c")
                except discord.errors.Forbidden:
                    pass
                e = error(
                    "\u274c Count Reset!",
                    f"**{message.author.mention}** said `{number}` but it was `{expected}`.\n"
                    f"The count has been reset to **0**."
                )
                try:
                    await message.channel.send(embed=e, delete_after=8)
                except discord.errors.Forbidden:
                    pass
        finally:
            await asyncio.sleep(1)
            self._processing.discard(msg_id)

    @commands.hybrid_command(name="count", description="Check the current count")
    async def count(self, ctx: commands.Context):
        if COUNTING_CHANNEL_ID and ctx.channel.id != COUNTING_CHANNEL_ID:
            channel = self.bot.get_channel(COUNTING_CHANNEL_ID)
            if channel:
                return await ctx.send(embed=info("Count", f"Counting happens in {channel.mention}!"))
            return await ctx.send(embed=info("Count", "Counting channel not found."))

        state = self._get_channel(ctx.channel.id)
        count = state["count"]
        if count == 0:
            await ctx.send(embed=info("Count", "No count started yet. Be the first to type **1**!"))
        else:
            last_user = ctx.guild.get_member(state["last_user"]) if state["last_user"] else None
            name = last_user.display_name if last_user else "Unknown"
            await ctx.send(embed=info("Count", f"Current count: **{count}**\nNext number: **{count + 1}**\nLast counter: {name}"))

    @commands.hybrid_command(name="countreset", description="Reset the count")
    async def countreset(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Messages` permission."))
        state = self._get_channel(ctx.channel.id)
        old = state["count"]
        state["count"] = 0
        state["last_user"] = None
        self._save()
        await ctx.send(embed=success("Count Reset", f"Count was at **{old}**, now reset to **0**."))

    @commands.hybrid_command(name="countset", description="Set the count to a number")
    @app_commands.describe(number="Number to set")
    async def countset(self, ctx: commands.Context, number: int):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Messages` permission."))
        if number < 0:
            return await ctx.send(embed=error("Error", "Count can't be negative."))
        state = self._get_channel(ctx.channel.id)
        state["count"] = number
        state["last_user"] = None
        self._save()
        await ctx.send(embed=success("Count Set", f"Count is now **{number}**. Next number: **{number + 1}**"))

    @commands.hybrid_command(name="countlb", description="Counting leaderboard")
    async def countlb(self, ctx: commands.Context):
        tallies: dict[int, int] = {}
        for cid, state in self.data.items():
            uid = state.get("last_user")
            count = state.get("count", 0)
            if uid and count > 0:
                tallies[uid] = tallies.get(uid, 0) + count

        if not tallies:
            return await ctx.send(embed=info("Leaderboard", "No counts recorded yet."))

        sorted_users = sorted(tallies.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = []
        medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
        for i, (uid, total) in enumerate(sorted_users):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else "Unknown"
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{prefix} {name} — `{total}`")

        e = info(f"Leaderboard — {ctx.guild.name}", "\n".join(lines))
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))

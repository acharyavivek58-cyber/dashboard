import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import math
from utils import success, error, info


LEVELS_FILE = "levels.json"


def load_levels() -> dict:
    if os.path.exists(LEVELS_FILE):
        with open(LEVELS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_levels(data: dict):
    with open(LEVELS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def xp_for_level(level: int) -> int:
    """XP needed for a level."""
    return 5 * (level ** 2) + 50 * level + 100


def level_from_xp(xp: int) -> int:
    """Calculate level from total XP."""
    level = 0
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
    return level


class Leveling(commands.Cog):
    """XP and leveling system — chat to earn XP and level up!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_levels()
        self.cooldowns: dict[int, float] = {}  # user_id -> last message time

    def _get_user(self, guild_id: int, user_id: int) -> dict:
        gid = str(guild_id)
        uid = str(user_id)
        if gid not in self.data:
            self.data[gid] = {}
        if uid not in self.data[gid]:
            self.data[gid][uid] = {"xp": 0, "level": 0, "messages": 0}
        return self.data[gid][uid]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Cooldown: 1 XP gain per 60 seconds
        now = message.created_at.timestamp()
        uid = message.author.id
        if uid in self.cooldowns and now - self.cooldowns[uid] < 60:
            return
        self.cooldowns[uid] = now

        # Give random XP
        xp_gain = random.randint(5, 15)
        user = self._get_user(message.guild.id, uid)
        user["xp"] += xp_gain
        user["messages"] += 1

        # Check level up
        old_level = user["level"]
        new_level = level_from_xp(user["xp"])
        user["level"] = new_level

        save_levels(self.data)

        # Announce level up
        if new_level > old_level:
            channel = message.channel
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"**{message.author.mention}** reached **Level {new_level}**!",
                color=0x57F287
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await channel.send(embed=embed, delete_after=10)

    @commands.hybrid_command(name="rank", description="Check your or someone's rank")
    async def rank(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = self._get_user(ctx.guild.id, member.id)
        level = user["level"]
        xp = user["xp"]
        msgs = user["messages"]

        # XP progress
        xp_needed = xp_for_level(level)
        xp_in_level = xp
        for i in range(level):
            xp_in_level -= xp_for_level(i)

        bar_length = 20
        filled = int(bar_length * (xp_in_level / xp_needed)) if xp_needed > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        # Rank position
        all_users = self.data.get(str(ctx.guild.id), {})
        sorted_users = sorted(all_users.items(), key=lambda x: x[1].get("xp", 0), reverse=True)
        rank_pos = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == str(member.id)), "N/A")

        embed = discord.Embed(
            title=f"📊 {member.display_name}'s Rank",
            color=member.color if member.color != discord.Color.default() else 0x5865F2
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Rank", value=f"#{rank_pos}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Messages", value=str(msgs), inline=True)
        embed.add_field(name="XP Progress", value=f"`{bar}`\n**{xp_in_level}/{xp_needed}** XP", inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Server XP leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        all_users = self.data.get(str(ctx.guild.id), {})
        sorted_users = sorted(all_users.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:15]

        if not sorted_users:
            return await ctx.send(embed=info("Leaderboard", "No data yet. Start chatting to earn XP!"))

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(sorted_users):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{medal} **{name}** — Level {data.get('level', 0)} ({data.get('xp', 0)} XP)")

        e = discord.Embed(
            title="🏆 Leaderboard",
            description="\n".join(lines),
            color=0xFEE75C
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="resetlevels", description="Reset all levels in the server")
    @commands.has_permissions(administrator=True)
    async def resetlevels(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        if gid in self.data:
            del self.data[gid]
            save_levels(self.data)
        await ctx.send(embed=success("✅ Reset", "All levels have been reset."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))

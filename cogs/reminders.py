import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import re
import config
from utils import success, error, info


class Reminders(commands.Cog):
    """Set reminders — the bot will DM you when time's up!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_reminders: dict[int, asyncio.Task] = {}

    async def cog_before_invoke(self, ctx: commands.Context):
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    def _parse_time(self, text: str) -> datetime.timedelta | None:
        """Parse time strings like 30s, 10m, 2h, 1d."""
        match = re.match(r'(\d+)([smhdw])', text.lower().strip())
        if not match:
            return None
        num = int(match.group(1))
        unit = match.group(2)
        units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days', 'w': 'weeks'}
        return datetime.timedelta(**{units[unit]: num})

    @commands.hybrid_command(name="remind", description="Set a reminder")
    @app_commands.describe(time="Time (e.g. 30s, 10m, 2h, 1d)", message="What to remind you about")
    async def remind(self, ctx: commands.Context, time: str, *, message: str):
        delay = self._parse_time(time)
        if not delay:
            return await ctx.send(embed=error("Invalid Time", "Use format: `30s`, `10m`, `2h`, `1d`, `1w`"))

        total_seconds = int(delay.total_seconds())
        if total_seconds > 604800:  # 7 days max
            return await ctx.send(embed=error("Too Long", "Maximum reminder is **7 days**."))

        embed = success(
            "⏰ Reminder Set",
            f"I'll remind you about **{message}** in **{time}**."
        )
        await ctx.send(embed=embed)

        await asyncio.sleep(total_seconds)

        try:
            dm_embed = discord.Embed(
                title="⏰ Reminder!",
                description=f"You asked me to remind you about:\n**{message}**",
                color=0x5865F2,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            dm_embed.set_footer(text=f"From {ctx.guild.name}" if ctx.guild else "DM Reminder")
            await ctx.author.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="reminders", description="List your active reminders")
    async def reminders(self, ctx: commands.Context):
        active = [name for name, task in self.active_reminders.items() if not task.done()]
        if not active:
            return await ctx.send(embed=info("Reminders", "You have no active reminders.\nUse `$remind 10m do something` to set one!"))
        await ctx.send(embed=info("Reminders", f"You have **{len(active)}** active reminder(s)."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminders(bot))

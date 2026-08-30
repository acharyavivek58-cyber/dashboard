import discord
from discord.ext import commands
from utils import error, warning, info
import config


class Logging(commands.Cog):
    """Automatic logging — message edits, deletes, member joins/leaves, voice."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if config.LOG_CHANNEL_ID:
            return self.bot.get_channel(config.LOG_CHANNEL_ID)
        # Fallback: look for a channel named "log", "logs", "audit-log", or "mod-log"
        for ch in guild.text_channels:
            if ch.name in ("log", "logs", "audit-log", "mod-log", "bot-logs"):
                return ch
        return None

    # ── Message Delete ───────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        channel = self._get_log_channel(message.guild)
        if not channel:
            return

        e = error("🗑️ Message Deleted", "")
        e.add_field(name="Author", value=f"{message.author} ({message.author.id})", inline=True)
        e.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            content = message.content[:1000]
            e.add_field(name="Content", value=f"```\n{content}\n```", inline=False)
        if message.attachments:
            att = "\n".join(a.filename for a in message.attachments)
            e.add_field(name="Attachments", value=att, inline=False)
        e.set_footer(text=f"ID: {message.id}")
        e.timestamp = discord.utils.utcnow()
        await channel.send(embed=e)

    # ── Message Edit ─────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        channel = self._get_log_channel(before.guild)
        if not channel:
            return

        e = warning("✏️ Message Edited", "")
        e.add_field(name="Author", value=f"{before.author} ({before.author.id})", inline=True)
        e.add_field(name="Channel", value=before.channel.mention, inline=True)
        if before.content:
            e.add_field(name="Before", value=f"```\n{before.content[:500]}\n```", inline=False)
        if after.content:
            e.add_field(name="After", value=f"```\n{after.content[:500]}\n```", inline=False)
        e.add_field(name="Jump to Message", value=f"[Click]({after.jump_url})", inline=True)
        e.set_footer(text=f"ID: {before.id}")
        e.timestamp = discord.utils.utcnow()
        await channel.send(embed=e)

    # ── Member Join ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self._get_log_channel(member.guild)
        if not channel:
            return

        e = info("✅ Member Joined", "")
        e.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
        e.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        e.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.timestamp = discord.utils.utcnow()
        await channel.send(embed=e)

    # ── Member Leave ─────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = self._get_log_channel(member.guild)
        if not channel:
            return

        roles = [r.name for r in member.roles[1:]]
        e = error("❌ Member Left", "")
        e.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        e.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        if roles:
            e.add_field(name="Roles", value=", ".join(roles), inline=False)
        e.set_thumbnail(url=member.display_avatar.url)
        e.timestamp = discord.utils.utcnow()
        await channel.send(embed=e)

    # ── Voice State ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        channel = self._get_log_channel(member.guild)
        if not channel or member.bot:
            return

        e = None
        if before.channel is None and after.channel is not None:
            e = info("🔊 Joined Voice", f"{member.mention} joined **{after.channel.name}**")
        elif before.channel is not None and after.channel is None:
            e = error("🔇 Left Voice", f"{member.mention} left **{before.channel.name}**")
        elif before.channel != after.channel:
            e = info("🔄 Moved Voice", f"{member.mention} moved from **{before.channel.name}** to **{after.channel.name}**")

        if e:
            e.timestamp = discord.utils.utcnow()
            await channel.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))

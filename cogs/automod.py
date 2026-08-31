import discord
from discord.ext import commands
from discord import app_commands
import re
import time
from collections import defaultdict
from utils import success, error, info


class AutoMod(commands.Cog):
    """Auto-moderation: spam, links, caps, invite detection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam_tracker: dict[int, list[float]] = defaultdict(list)  # user_id -> [timestamps]
        self.warnings: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))  # guild_id -> user_id -> warn_count

    # ── Config ────────────────────────────────────────────────────────
    AUTO_MOD_CONFIG = {
        "max_caps_percent": 70,      # Max caps percentage before deleting
        "caps_min_length": 10,       # Min message length to check caps
        "max_mentions": 5,           # Max mentions before deleting
        "spam_window": 5,            # Seconds to track messages
        "max_spam": 5,               # Max messages in spam window
        "invite_links": True,        # Block discord invites
        "link_protection": False,    # Block all links (disabled by default)
    }

    def _is_invite(self, text: str) -> bool:
        """Check if text contains a Discord invite link."""
        patterns = [
            r'discord\.gg/\w+',
            r'discordapp\.com/invite/\w+',
            r'discord\.com/invite/\w+',
        ]
        return any(re.search(p, text.lower()) for p in patterns)

    def _is_caps(self, text: str) -> bool:
        """Check if message is mostly caps."""
        if len(text) < self.AUTO_MOD_CONFIG["caps_min_length"]:
            return False
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        caps = sum(1 for c in letters if c.isupper())
        return (caps / len(letters) * 100) > self.AUTO_MOD_CONFIG["max_caps_percent"]

    def _is_spam(self, user_id: int) -> bool:
        """Check if user is spamming."""
        now = time.time()
        window = self.AUTO_MOD_CONFIG["spam_window"]
        self.spam_tracker[user_id] = [t for t in self.spam_tracker[user_id] if now - t < window]
        self.spam_tracker[user_id].append(now)
        return len(self.spam_tracker[user_id]) > self.AUTO_MOD_CONFIG["max_spam"]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Skip if user is admin
        if message.author.guild_permissions.administrator:
            return

        content = message.content
        reasons = []

        # Check invites
        if self.AUTO_MOD_CONFIG["invite_links"] and self._is_invite(content):
            reasons.append("invite link")

        # Check caps
        if self._is_caps(content):
            reasons.append("excessive caps")

        # Check mentions
        if len(message.mentions) > self.AUTO_MOD_CONFIG["max_mentions"]:
            reasons.append("mass mentions")

        # Check spam
        if self._is_spam(message.author.id):
            reasons.append("spam")

        if reasons:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

            # Warn the user
            uid = message.author.id
            gid = message.guild.id
            self.warnings[gid][uid] += 1
            count = self.warnings[gid][uid]

            embed = discord.Embed(
                title="🛡️ AutoMod",
                description=f"**{message.author.mention}**, your message was removed for: **{', '.join(reasons)}**\n\nAuto-warn **{count}/3** — 3 warns = 10 min timeout.",
                color=0xED4245
            )
            await message.channel.send(embed=embed, delete_after=8)

            # Auto-timeout after 3 warns
            if count >= 3:
                try:
                    import datetime
                    await message.author.timeout(
                        datetime.timedelta(minutes=10),
                        reason="AutoMod: 3 auto-warns reached"
                    )
                    self.warnings[gid][uid] = 0

                    timeout_embed = discord.Embed(
                        title="🔇 AutoMod Timeout",
                        description=f"**{message.author}** has been timed out for 10 minutes (3 auto-warns).",
                        color=0xFEE75C
                    )
                    await message.channel.send(embed=timeout_embed, delete_after=15)
                except discord.HTTPException:
                    pass

    @commands.hybrid_command(name="automod", description="Toggle auto-moderation settings")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(setting="Setting to toggle", value="true/false")
    async def automod(self, ctx: commands.Context, setting: str, value: str = None):
        valid = list(self.AUTO_MOD_CONFIG.keys())
        if setting not in valid:
            return await ctx.send(embed=error("Error", f"Valid settings: `{'`, `'.join(valid)}`"))

        if value is None:
            current = self.AUTO_MOD_CONFIG[setting]
            return await ctx.send(embed=info("AutoMod", f"**{setting}** = `{current}`"))

        if isinstance(self.AUTO_MOD_CONFIG[setting], bool):
            self.AUTO_MOD_CONFIG[setting] = value.lower() in ("true", "1", "on", "yes")
        elif isinstance(self.AUTO_MOD_CONFIG[setting], int):
            try:
                self.AUTO_MOD_CONFIG[setting] = int(value)
            except ValueError:
                return await ctx.send(embed=error("Error", "Must be a number."))

        await ctx.send(embed=success("✅ Updated", f"**{setting}** = `{self.AUTO_MOD_CONFIG[setting]}`"))

    @commands.hybrid_command(name="automodconfig", description="View automod settings")
    async def automodconfig(self, ctx: commands.Context):
        lines = []
        for k, v in self.AUTO_MOD_CONFIG.items():
            emoji = "✅" if v else "❌" if isinstance(v, bool) else "🔢"
            lines.append(f"{emoji} **{k}**: `{v}`")
        await ctx.send(embed=info("AutoMod Config", "\n".join(lines)))

    @commands.hybrid_command(name="clearwarns", description="Clear automod warnings for a user")
    @commands.has_permissions(administrator=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        self.warnings[ctx.guild.id][member.id] = 0
        await ctx.send(embed=success("✅ Cleared", f"AutoMod warnings cleared for **{member}**."))


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))

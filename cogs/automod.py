import discord
from discord.ext import commands
from discord import app_commands
import re
import time
import datetime
from collections import defaultdict
import config
from utils import success, error, info, warning


# ── Profanity word list (use strict matches only) ────────────────
# These are matched as WHOLE WORDS using regex \b boundaries
CUSS_WORDS = [
    # Strong profanity
    "fuck", "fuk", "fck", "fucking", "fcking",
    "shit", "shitting",
    "bitch", "bitching",
    "asshole",
    "dickhead",
    "nigger", "nigga",
    "slut", "whore",
    "bastard",
    "retard", "retarded",
    # Short but strong (only match exact, no substrings)
    "stfu", "gtfo",
]

# Build regex pattern for strict whole-word matching
_CUSS_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in CUSS_WORDS) + r')\b',
    re.IGNORECASE
)

# Evasion patterns — check cleaned versions of words
_EVASION_WORDS = ["fuck", "shit", "bitch", "asshole", "dickhead", "fck", "sht", "btch"]


class AutoMod(commands.Cog):
    """Auto-moderation: spam, links, caps, invite detection, profanity."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam_tracker: dict[int, list[float]] = defaultdict(list)
        self.warnings: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.cuss_warnings: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._load_warnings()

    async def cog_before_invoke(self, ctx: commands.Context):
        """Check dashboard permissions for automod commands."""
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    def _load_warnings(self):
        data = config.load_state("automod_warnings.json")
        for gid_s, users in data.items():
            gid = int(gid_s)
            for uid_s, count in users.items():
                self.warnings[gid][int(uid_s)] = count
        data2 = config.load_state("automod_cuss_warnings.json")
        for gid_s, users in data2.items():
            gid = int(gid_s)
            for uid_s, count in users.items():
                self.cuss_warnings[gid][int(uid_s)] = count

    def _save_warnings(self):
        data = {str(gid): {str(uid): c for uid, c in users.items()}
                for gid, users in self.warnings.items()}
        config.save_state("automod_warnings.json", data)
        data2 = {str(gid): {str(uid): c for uid, c in users.items()}
                 for gid, users in self.cuss_warnings.items()}
        config.save_state("automod_cuss_warnings.json", data2)

    AUTO_MOD_CONFIG = {
        "max_caps_percent": 70,
        "caps_min_length": 200,
        "max_mentions": 5,
        "spam_window": 5,
        "max_spam": 5,
        "invite_links": True,
        "link_protection": False,
        "profanity_filter": True,
    }

    EXEMPT_CHANNELS = [1543631917855805441]  # counting channel

    def _is_cuss(self, text: str) -> bool:
        """Check if message contains profanity using strict word boundaries."""
        # Direct whole-word match
        if _CUSS_PATTERN.search(text):
            return True
        # Check evasion: strip ALL non-alpha and check substrings
        alpha_only = re.sub(r'[^a-z]', '', text.lower())
        for word in _EVASION_WORDS:
            if word in alpha_only:
                return True
        return False

    def _is_invite(self, text: str) -> bool:
        patterns = [
            r'discord\.gg/\w+',
            r'discordapp\.com/invite/\w+',
            r'discord\.com/invite/\w+',
        ]
        return any(re.search(p, text.lower()) for p in patterns)

    def _is_caps(self, text: str) -> bool:
        if len(text) < self.AUTO_MOD_CONFIG["caps_min_length"]:
            return False
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        caps = sum(1 for c in letters if c.isupper())
        return (caps / len(letters) * 100) > self.AUTO_MOD_CONFIG["max_caps_percent"]

    def _is_spam(self, user_id: int) -> bool:
        now = time.time()
        window = self.AUTO_MOD_CONFIG["spam_window"]
        self.spam_tracker[user_id] = [t for t in self.spam_tracker[user_id] if now - t < window]
        self.spam_tracker[user_id].append(now)
        return len(self.spam_tracker[user_id]) > self.AUTO_MOD_CONFIG["max_spam"]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Skip command messages to prevent double replies
        if message.content and message.content[0] in ['$', '!', '/', '?']:
            return

        if message.channel.id in self.EXEMPT_CHANNELS:
            return

        if message.author.guild_permissions.administrator:
            return

        content = message.content
        reasons = []

        # Check profanity
        if self.AUTO_MOD_CONFIG["profanity_filter"] and self._is_cuss(content):
            reasons.append("profanity")

        if self.AUTO_MOD_CONFIG["invite_links"] and self._is_invite(content):
            reasons.append("invite link")

        if self._is_caps(content):
            reasons.append("excessive caps")

        if len(message.mentions) > self.AUTO_MOD_CONFIG["max_mentions"]:
            reasons.append("mass mentions")

        if self._is_spam(message.author.id):
            reasons.append("spam")

        if not reasons:
            return

        # Delete message
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        uid = message.author.id
        gid = message.guild.id

        # ── Profanity has its own warn+mute system ──
        if "profanity" in reasons:
            self.cuss_warnings[gid][uid] += 1
            count = self.cuss_warnings[gid][uid]

            if count >= 2:
                # Mute for 2 minutes
                try:
                    await message.author.timeout(
                        datetime.timedelta(minutes=2),
                        reason="AutoMod: Profanity (2nd offense)"
                    )
                    self.cuss_warnings[gid][uid] = 0
                    embed = discord.Embed(
                        title="🔇 Profanity Mute",
                        description=f"**{message.author.mention}** has been muted for **2 minutes** for repeated profanity.",
                        color=0xED4245
                    )
                    await message.channel.send(embed=embed, delete_after=10)
                except discord.HTTPException:
                    pass
            else:
                embed = discord.Embed(
                    title="⚠️ Profanity Warning",
                    description=f"**{message.author.mention}**, watch your language!\n\nAuto-warn **{count}/2** — next cuss = **2 minute mute**.",
                    color=0xFEE75C
                )
                await message.channel.send(embed=embed, delete_after=8)
            self._save_warnings()
            return

        # ── Other automod violations (spam, caps, etc) ──
        other_reasons = [r for r in reasons if r != "profanity"]
        if other_reasons:
            self.warnings[gid][uid] += 1
            count = self.warnings[gid][uid]

            embed = discord.Embed(
                title="🛡️ AutoMod",
                description=f"**{message.author.mention}**, your message was removed for: **{', '.join(other_reasons)}**\n\nAuto-warn **{count}/3** — 3 warns = 10 min timeout.",
                color=0xED4245
            )
            await message.channel.send(embed=embed, delete_after=8)

            if count >= 3:
                try:
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
            self._save_warnings()

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
        self.cuss_warnings[ctx.guild.id][member.id] = 0
        self._save_warnings()
        await ctx.send(embed=success("✅ Cleared", f"AutoMod warnings cleared for **{member}**."))


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))

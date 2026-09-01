import discord
from discord.ext import commands
from datetime import datetime
import utils


class AFKButtonView(discord.ui.View):
    """Buttons shown when an AFK user is mentioned."""

    def __init__(self, afk_user, afk_data, bot):
        super().__init__(timeout=60)
        self.afk_user = afk_user
        self.afk_data = afk_data
        self.bot = bot

    @discord.ui.button(label="Leave a message", style=discord.ButtonStyle.primary, emoji="💬")
    async def leave_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AFKModal(self.afk_user, self.afk_data, self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Tell me when they are back", style=discord.ButtonStyle.secondary, emoji="🔔")
    async def notify_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = self.afk_user.guild.id
        user_id = self.afk_user.id
        requester_id = interaction.user.id

        cog = self.bot.get_cog("AFK")
        if not cog:
            await interaction.response.send_message("Error.", ephemeral=True)
            return

        if not cog._get_afk(guild_id, user_id):
            await interaction.response.send_message(
                f"**{self.afk_user.display_name}** is no longer AFK!", ephemeral=True
            )
            return

        if guild_id not in cog.notify_queue:
            cog.notify_queue[guild_id] = {}
        if user_id not in cog.notify_queue[guild_id]:
            cog.notify_queue[guild_id][user_id] = []
        if requester_id not in cog.notify_queue[guild_id][user_id]:
            cog.notify_queue[guild_id][user_id].append(requester_id)

        await interaction.response.send_message(
            f"✅ I'll DM you when **{self.afk_user.display_name}** comes back!", ephemeral=True
        )


class AFKModal(discord.ui.Modal, title="Leave a Message"):
    def __init__(self, afk_user, afk_data, bot):
        super().__init__()
        self.afk_user = afk_user
        self.afk_data = afk_data
        self.bot = bot

    message_input = discord.ui.TextInput(
        label="Your message",
        placeholder="Type your message here...",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = self.afk_user.guild.id
        user_id = self.afk_user.id

        cog = self.bot.get_cog("AFK")
        if not cog:
            await interaction.response.send_message("Error.", ephemeral=True)
            return

        if guild_id not in cog.pending_messages:
            cog.pending_messages[guild_id] = {}
        if user_id not in cog.pending_messages[guild_id]:
            cog.pending_messages[guild_id][user_id] = []
        cog.pending_messages[guild_id][user_id].append({
            "from": interaction.user,
            "message": self.message_input.value,
        })

        await interaction.response.send_message(
            f"✅ Message saved! I'll deliver it to **{self.afk_user.display_name}** when they're back.",
            ephemeral=True
        )


class AFK(commands.Cog):
    """AFK system — lightweight, auto-remove, mention notifications."""

    def __init__(self, bot):
        self.bot = bot
        self.afk_users = {}       # {guild_id: {user_id: {"reason": str, "since": datetime}}}
        self.pending_messages = {} # {guild_id: {user_id: [{"from": user, "message": str}]}}
        self.notify_queue = {}     # {guild_id: {user_id: [requester_ids]}}

    def _set_afk(self, guild_id, user_id, reason="AFK"):
        if guild_id not in self.afk_users:
            self.afk_users[guild_id] = {}
        self.afk_users[guild_id][user_id] = {
            "reason": reason,
            "since": datetime.utcnow(),
        }

    def _remove_afk(self, guild_id, user_id):
        if guild_id in self.afk_users:
            return self.afk_users[guild_id].pop(user_id, None)
        return None

    def _get_afk(self, guild_id, user_id):
        return self.afk_users.get(guild_id, {}).get(user_id)

    def _format_duration(self, since):
        seconds = int((datetime.utcnow() - since).total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

    @commands.hybrid_command(name="afk", description="Set your AFK status")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afk_command(self, ctx, *, reason: str = "AFK"):
        guild_id = ctx.guild.id
        user_id = ctx.author.id

        if self._get_afk(guild_id, user_id):
            return  # Already AFK, stay silent

        self._set_afk(guild_id, user_id, reason)

        # Change nickname to [AFK] (name)
        try:
            original_name = ctx.author.display_name
            if not original_name.startswith("[AFK]"):
                new_nick = f"[AFK] {original_name}"
                await ctx.author.edit(nick=new_nick[:32])
        except discord.Forbidden:
            pass

        # Simple one-line response (not a big embed)
        await ctx.send(
            embed=utils.warning("AFK", f"**{ctx.author.display_name}** is now AFK: {reason}"),
            delete_after=10
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # ── Check if SENDER is AFK → remove it ──
        afk_data = self._get_afk(guild_id, user_id)
        if afk_data:
            self._remove_afk(guild_id, user_id)

            # Restore nickname - remove [AFK] prefix
            nick = message.author.display_name
            if nick.startswith("[AFK]"):
                original = nick[6:].strip()  # Remove '[AFK] ' prefix
                try:
                    await message.author.edit(nick=original if original else None)
                except discord.Forbidden:
                    pass

            # Deliver pending DMs only (no channel spam)
            pending = self.pending_messages.get(guild_id, {}).pop(user_id, [])
            for msg_data in pending:
                try:
                    dm_embed = utils.info(
                        "📬 Message While AFK",
                        f"**{msg_data['from'].display_name}** said:\n> {msg_data['message']}"
                    )
                    await message.author.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

            # Notify people waiting (DM only, no channel spam)
            notify_list = self.notify_queue.get(guild_id, {}).pop(user_id, [])
            for requester_id in notify_list:
                requester = message.guild.get_member(requester_id)
                if requester:
                    try:
                        await requester.send(
                            embed=utils.success("🔔 They're Back!", f"**{message.author.display_name}** is back!")
                        )
                    except discord.Forbidden:
                        pass

            return  # Don't check mentions for this message

        # ── Check if MENTIONED users are AFK → show notification ──
        if not message.mentions:
            return  # No mentions, skip entirely (saves processing)

        for user in message.mentions:
            if user.bot or user.id == user_id:
                continue

            afk_data = self._get_afk(guild_id, user.id)
            if afk_data:
                duration = self._format_duration(afk_data["since"])
                embed = utils.warning(
                    "AFK",
                    f"**{user.display_name}** is AFK: {afk_data['reason']} — {duration}"
                )
                view = AFKButtonView(user, afk_data, self.bot)
                try:
                    await message.channel.send(embed=embed, view=view, delete_after=30)
                except discord.Forbidden:
                    pass


async def setup(bot):
    await bot.add_cog(AFK(bot))

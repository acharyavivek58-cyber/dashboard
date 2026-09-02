import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import config
from utils import success, error, info


REACTIONS_FILE = "reaction_roles.json"


def load_reaction_roles() -> dict:
    if os.path.exists(REACTIONS_FILE):
        with open(REACTIONS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_reaction_roles(data: dict):
    with open(REACTIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class ReactionRoles(commands.Cog):
    """Self-assign roles by reacting to messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_reaction_roles()

    async def cog_before_invoke(self, ctx: commands.Context):
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    def _get_config(self, guild_id: int) -> dict:
        return self.data.get(str(guild_id), {})

    def _save(self):
        save_reaction_roles(self.data)

    @commands.hybrid_command(name="reactionrole", description="Set up a reaction role message")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        channel="Channel to send the message in",
        emoji="Emoji for the role",
        role="Role to assign"
    )
    async def reactionrole(self, ctx: commands.Context, channel: discord.TextChannel, emoji: str, role: discord.Role):
        gid = str(ctx.guild.id)

        embed = discord.Embed(
            title="🎖️ Reaction Roles",
            description=f"React with {emoji} to get the **{role.name}** role!\nReact again to remove it.",
            color=0x5865F2
        )
        embed.set_footer(text="Remove your reaction to lose the role")

        msg = await channel.send(embed=embed)
        await msg.add_reaction(emoji)

        if gid not in self.data:
            self.data[gid] = {}
        if str(msg.id) not in self.data[gid]:
            self.data[gid][str(msg.id)] = {}

        self.data[gid][str(msg.id)][emoji] = role.id
        self._save()

        await ctx.send(embed=success("✅ Reaction Role Created", f"Message sent to {channel.mention}\n{emoji} → **{role.name}**"))

    @commands.hybrid_command(name="reactionroleadd", description="Add another role to an existing reaction role message")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        message_id="ID of the reaction role message",
        emoji="Emoji for the new role",
        role="Role to assign"
    )
    async def reactionroleadd(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role):
        gid = str(ctx.guild.id)
        config = self._get_config(ctx.guild.id)

        if message_id not in config:
            return await ctx.send(embed=error("Error", "No reaction role found with that message ID."))

        try:
            channel = ctx.channel
            msg = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            return await ctx.send(embed=error("Error", "Could not find that message in this channel."))

        await msg.add_reaction(emoji)
        config[message_id][emoji] = role.id
        self._save()

        await ctx.send(embed=success("✅ Added", f"{emoji} → **{role.name}**"))

    @commands.hybrid_command(name="reactionroledel", description="Delete a reaction role message")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(message_id="ID of the reaction role message to delete")
    async def reactionroledel(self, ctx: commands.Context, message_id: str):
        gid = str(ctx.guild.id)
        config = self._get_config(ctx.guild.id)

        if message_id in config:
            del config[message_id]
            self._save()
            await ctx.send(embed=success("✅ Deleted", "Reaction role removed."))
        else:
            await ctx.send(embed=error("Error", "Not found."))

    @commands.hybrid_command(name="reactionroles", description="List all reaction roles in this server")
    async def reactionroles(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        config = self._get_config(ctx.guild.id)

        if not config:
            return await ctx.send(embed=info("Reaction Roles", "No reaction roles set up yet.\nUse `$reactionrole` to create one."))

        lines = []
        for msg_id, roles in config.items():
            for emoji, role_id in roles.items():
                role = ctx.guild.get_role(int(role_id))
                lines.append(f"{emoji} → **{role.name if role else 'Deleted Role'}** (Msg: `{msg_id}`)")

        e = info("Reaction Roles", "\n".join(lines))
        await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return

        gid = str(payload.guild_id)
        config = self._get_config(payload.guild_id)
        msg_config = config.get(str(payload.message_id), {})

        emoji_str = str(payload.emoji)
        if emoji_str in msg_config:
            role_id = msg_config[emoji_str]
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(int(role_id))
            if role:
                await payload.member.add_roles(role, reason="Self-assign via reaction role")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        gid = str(payload.guild_id)
        config = self._get_config(payload.guild_id)
        msg_config = config.get(str(payload.message_id), {})

        emoji_str = str(payload.emoji)
        if emoji_str in msg_config:
            role_id = msg_config[emoji_str]
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(int(role_id))
            if member and role:
                await member.remove_roles(role, reason="Self-remove via reaction role")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))

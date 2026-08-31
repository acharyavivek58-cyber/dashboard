import discord
from discord.ext import commands
from discord import app_commands


class CustomHelp(commands.HelpCommand):
    """Dyno-style help command with command cards."""

    def __init__(self):
        super().__init__(command_attrs={
            "cooldown": commands.CooldownMapping.from_cooldown(2, 5, commands.BucketType.user)
        })

    def get_command_signature(self, command):
        prefix = self.context.prefix
        if command.usage:
            return f"{prefix}{command.qualified_name} {command.usage}"
        return f"{prefix}{command.qualified_name}"

    async def send_bot_help(self, mapping):
        prefix = self.context.prefix
        embed = discord.Embed(
            title="📋 Command List",
            description=f"Use `{prefix}help <command>` for details on a command.",
            color=0x5865F2
        )

        categories = {
            "🛡️ Moderation": ["ban", "kick", "mute", "unmute", "warn", "warnings", "purge"],
            "🔧 Utility": ["ping", "uptime", "userinfo", "serverinfo", "avatar", "servericon", "id", "help"],
            "🏷️ Roles": ["role", "createrole", "deleterole", "roles"],
            "🎮 Fun": ["8ball", "coinflip", "dice", "reverse", "choose", "poll", "say"],
            "🔢 Counting": ["count", "countreset", "countset", "countlb"],
            "🎉 Giveaways": ["giveaway", "giveawayend", "giveawayreroll"],
            "📨 Invites": ["invites", "inviteboard", "invitestats"],
            "🎭 Reaction Roles": ["reactionrole", "reactionroleadd", "reactionroledel", "reactionroles"],
            "🛡️ AutoMod": ["automod", "automodconfig", "clearwarns"],
            "📊 Leveling": ["rank", "leaderboard", "resetlevels"],
            "⏰ Reminders": ["remind", "reminders"],
            "🎫 Tickets": ["ticketsetup", "close", "add", "remove"],
        }

        for cat_name, cmds in categories.items():
            available = []
            for cmd_name in cmds:
                cmd = self.context.bot.get_command(cmd_name)
                if cmd:
                    available.append(f"`{prefix}{cmd_name}`")
            if available:
                embed.add_field(name=cat_name, value=" · ".join(available), inline=False)

        embed.set_footer(text=f"Total: {len(self.context.bot.commands)} commands")
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog):
        embed = discord.Embed(
            title=f"{cog.qualified_name}",
            description=cog.description or "No description.",
            color=0x5865F2
        )
        for cmd in cog.get_commands():
            embed.add_field(
                name=f"`{self.context.prefix}{cmd.qualified_name}`",
                value=cmd.description or "No description.",
                inline=False
            )
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        prefix = self.context.prefix
        embed = discord.Embed(
            title=f"Command: {prefix}{command.qualified_name}",
            color=0x5865F2
        )

        if command.description:
            embed.add_field(name="Description", value=command.description, inline=False)

        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in command.aliases), inline=True)

        # Cooldown
        if command._buckets and command._buckets._cooldown:
            cd = command._buckets._cooldown
            embed.add_field(name="Cooldown", value=f"{cd.rate} per {cd.per}s", inline=True)

        # Usage
        usage = self.get_command_signature(command)
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)

        # Permissions
        if hasattr(command, 'requires'):
            perms = []
            for perm, value in command.requires.get('permissions', {}).items():
                if value:
                    perms.append(perm.replace('_', ' ').title())
            if perms:
                embed.add_field(name="Permissions", value=", ".join(perms), inline=True)

        # Example
        examples = {
            "ban": f"`{prefix}ban @user Spamming`",
            "kick": f"`{prefix}kick @user Rule break`",
            "mute": f"`{prefix}mute @user 2h Being toxic`",
            "unmute": f"`{prefix}unmute @user`",
            "warn": f"`{prefix}warn @user Stop posting images`",
            "warnings": f"`{prefix}warnings @user`",
            "purge": f"`{prefix}purge 50`",
            "role": f"`{prefix}role @user add @Member`",
            "createrole": f"`{prefix}createrole NewRole #FF0000`",
            "deleterole": f"`{prefix}deleterole OldRole`",
            "giveaway": f"`{prefix}giveaway 1h 1 Nitro`",
            "giveawayend": f"`{prefix}giveawayend {prefix}giveaway`",
            "giveawayreroll": f"`{prefix}giveawayreroll {prefix}giveaway`",
            "poll": f"`{prefix}poll Favorite color? Red, Blue, Green`",
            "say": f"`{prefix}say Hello everyone!`",
            "8ball": f"`{prefix}8ball Will I win?`",
            "coinflip": f"`{prefix}coinflip`",
            "dice": f"`{prefix}dice 20`",
            "reverse": f"`{prefix}reverse hello world`",
            "choose": f"`{prefix}choose pizza, pasta, burger`",
            "rank": f"`{prefix}rank` or `{prefix}rank @user`",
            "leaderboard": f"`{prefix}leaderboard`",
            "remind": f"`{prefix}remind 30m check oven`",
            "reactionrole": f"`{prefix}reactionrole #roles 🎮 @Role`",
            "ticketsetup": f"`{prefix}ticketsetup #tickets #logs`",
            "automod": f"`{prefix}automod invite_links true`",
            "count": f"`{prefix}count`",
            "countset": f"`{prefix}countset 50`",
            "invites": f"`{prefix}invites @user`",
        }

        if command.qualified_name in examples:
            embed.add_field(name="Example", value=examples[command.qualified_name], inline=False)
        elif command.qualified_name in ["userinfo", "avatar", "id"]:
            embed.add_field(name="Example", value=f"`{prefix}{command.qualified_name} @user`", inline=False)
        elif command.qualified_name in ["ping", "uptime", "serverinfo", "servericon", "countlb", "invitestats", "inviteboard", "reactionroles", "automodconfig", "reminders"]:
            embed.add_field(name="Example", value=f"`{prefix}{command.qualified_name}`", inline=False)

        embed.set_footer(text="[] = optional · <> = required")
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        pass  # Silently ignore help errors

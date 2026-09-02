import discord
from discord.ext import commands


class CustomHelp(commands.HelpCommand):
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
            title="Command List",
            description=f"Use `{prefix}help <command>` for details.\nAll commands also work as slash commands.",
            color=0x5865F2
        )

        categories = {
            "\U0001f6e1\ufe0f Moderation": ["ban", "kick", "mute", "unmute", "warn", "warnings", "purge", "lock", "unlock", "slowmode"],
            "\U0001f4a8 AutoMod": ["automod", "automodconfig", "clearwarns"],
            "\U0001f3ab Tickets": ["ticketsetup", "ticketrole", "tickettype", "closetype", "sendpanels", "movetickets", "close", "add", "remove"],
            "\U0001f4e4 Invites": ["invites", "inviteboard", "invitestats"],
            "\U0001f389 Giveaways": ["giveaway", "giveawayend", "giveawayreroll"],
            "\U0001f3b2 Counting": ["count", "countreset", "countset", "countlb"],
            "\U0001f3ae Games": ["roulette", "dice", "rps", "xo", "hotxo", "deathwheel", "chairs", "hideandseek", "replica", "guesscountry", "mafia", "wyr", "fastclick", "fasttype", "textsplit", "textmerge", "flag", "textreverse", "findletter", "correctletter", "sortnumbers", "guesscolor", "emoji", "reveal"],
            "\U0001f9e0 Trivia": ["trivia", "triviascore", "trivialeaderboard"],
            "\U0001f3b5 Music": ["join", "leave", "play", "pause", "resume", "skip", "stop", "queue", "nowplaying", "volume", "shuffle", "loop", "removesong", "clear"],
            "\U0001f4a4 AFK": ["afk"],
            "\U0001f399\ufe0f Roles": ["role", "createrole", "deleterole"],
            "\U0001f514 Reaction Roles": ["reactionrole", "reactionroleadd", "reactionroledel", "reactionroles"],
            "\U0001f4ac Fun": ["8ball", "coinflip", "reverse", "choose", "say", "poll"],
            "\U0001f514 Utility": ["ping", "uptime", "userinfo", "serverinfo", "avatar", "servericon", "id"],
            "\u23f0 Reminders": ["remind", "reminders"],
        }

        for cat_name, cmds in categories.items():
            available = []
            for cmd_name in cmds:
                cmd = self.context.bot.get_command(cmd_name)
                if cmd:
                    available.append(f"`{prefix}{cmd_name}`")
            if available:
                embed.add_field(name=cat_name, value=" \u00b7 ".join(available), inline=False)

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
        if command._buckets and command._buckets._cooldown:
            cd = command._buckets._cooldown
            embed.add_field(name="Cooldown", value=f"{cd.rate} per {cd.per}s", inline=True)
        usage = self.get_command_signature(command)
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)

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
            "giveawayend": f"`{prefix}giveawayend <message_id>`",
            "giveawayreroll": f"`{prefix}giveawayreroll <message_id>`",
            "poll": f"`{prefix}poll Favorite color? Red, Blue, Green`",
            "say": f"`{prefix}say Hello everyone!`",
            "8ball": f"`{prefix}8ball Will I win?`",
            "coinflip": f"`{prefix}coinflip`",
            "dice": f"`{prefix}dice 2 20`",
            "reverse": f"`{prefix}reverse hello world`",
            "choose": f"`{prefix}choose pizza, pasta, burger`",
            "rps": f"`{prefix}rps rock`",
            "xo": f"`{prefix}xo @user`",
            "remind": f"`{prefix}remind 30m check oven`",
            "reactionrole": f"`{prefix}reactionrole #roles \U0001f3ae @Role`",
            "ticketsetup": f"`{prefix}ticketsetup`",
            "ticketrole": f"`{prefix}ticketrole @Staff`",
            "tickettype": f"`{prefix}tickettype General Help \u2753 general-help`",
            "automod": f"`{prefix}automod profanity_filter true`",
            "count": f"`{prefix}count`",
            "countset": f"`{prefix}countset 50`",
            "invites": f"`{prefix}invites @user`",
            "afk": f"`{prefix}afk eating lunch`",
            "play": f"`{prefix}play Never Gonna Give You Up`",
            "trivia": f"`{prefix}trivia`",
            "fastclick": f"`{prefix}fastclick`",
            "roulette": f"`{prefix}roulette`",
            "wyr": f"`{prefix}wyr`",
        }

        name = command.qualified_name
        if name in examples:
            embed.add_field(name="Example", value=examples[name], inline=False)
        elif name in ["userinfo", "avatar", "id"]:
            embed.add_field(name="Example", value=f"`{prefix}{name} @user`", inline=False)
        elif name in ["ping", "uptime", "serverinfo", "servericon", "countlb", "invitestats", "inviteboard", "reactionroles", "automodconfig", "reminders", "triviascore", "trivialeaderboard", "queue", "nowplaying", "stop", "leave", "join"]:
            embed.add_field(name="Example", value=f"`{prefix}{name}`", inline=False)

        embed.set_footer(text="[] = optional \u00b7 <> = required")
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        pass

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import config
from utils import success, error, info


TICKETS_FILE = "tickets.json"


def load_tickets() -> dict:
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_tickets(data: dict):
    try:
        with open(TICKETS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


DEFAULT_TYPES = {
    "support": {"emoji": "\U0001f48e", "label": "Request Support", "channel_prefix": "request-support"},
    "reward": {"emoji": "\U0001f381", "label": "Reward Claim", "channel_prefix": "reward-claim"},
    "mm": {"emoji": "\U0001f91d", "label": "Request MM", "channel_prefix": "request-mm"},
}


class TicketCreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Create ticket", style=discord.ButtonStyle.primary, emoji="\U0001f3ab", custom_id="ticket_create_btn")

    async def callback(self, interaction: discord.Interaction):
        if not config.has_permission("ticketsetup", interaction.user):
            return await interaction.response.send_message(embed=error("Permission Denied", "You don't have permission to create tickets."), ephemeral=True)
        cog = interaction.client.get_cog("Tickets")
        guild, user = interaction.guild, interaction.user
        ticket_config = load_tickets().get(str(guild.id), {})
        channel, err = await cog._create_ticket_channel(
            guild, user, ticket_config,
            channel_name=f"ticket-{user.name.lower().replace('.', '')}",
            topic=f"Support ticket \u2014 opened by {user} ({user.id})",
            log_message="**Opened by:** {user}\n**Channel:** {channel}"
        )
        if err:
            return await interaction.response.send_message(embed=error("Error", err), ephemeral=True)
        await interaction.response.send_message(embed=success("\u2705 Ticket Opened", f"Your ticket: {channel.mention}"), ephemeral=True)


class TicketTypeSelect(discord.ui.Select):
    def __init__(self, guild_id: str):
        data = load_tickets()
        cfg = data.get(guild_id, {})
        ticket_types = cfg.get("types", DEFAULT_TYPES)
        options = [discord.SelectOption(label=t["label"], value=k, emoji=t["emoji"], description=f"Open a {t['label'].lower()} ticket") for k, t in ticket_types.items()]
        super().__init__(placeholder="Select a category...", options=options, custom_id="ticket_type_select")

    async def callback(self, interaction: discord.Interaction):
        if not config.has_permission("ticketsetup", interaction.user):
            return await interaction.response.send_message(embed=error("Permission Denied", "You don't have permission to create tickets."), ephemeral=True)
        cog = interaction.client.get_cog("Tickets")
        guild, user = interaction.guild, interaction.user
        data = load_tickets()
        ticket_config = data.get(str(guild.id), {})
        ticket_types = ticket_config.get("types", DEFAULT_TYPES)
        ttype = ticket_types.get(self.values[0], DEFAULT_TYPES["support"])
        prefix = ttype.get("channel_prefix", "ticket")
        channel, err = await cog._create_ticket_channel(
            guild, user, ticket_config,
            channel_name=f"{prefix}-{user.name.lower().replace('.', '')}",
            topic=f"{ttype['label']} \u2014 opened by {user} ({user.id})",
            log_message="**Type:** " + ttype["emoji"] + " " + ttype["label"] + "\n**Opened by:** {user}\n**Channel:** {channel}"
        )
        if err:
            return await interaction.response.send_message(embed=error("Error", err), ephemeral=True)
        await interaction.response.send_message(embed=success("\u2705 Ticket Opened", f"Your ticket: {channel.mention}"), ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self, guild_id: str = None, with_dropdown: bool = False):
        super().__init__(timeout=None)
        self.add_item(TicketCreateButton())
        if with_dropdown and guild_id:
            self.add_item(TicketTypeSelect(guild_id))


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self._register_views())

    async def _register_views(self):
        await self.bot.wait_until_ready()
        data = load_tickets()
        for gid in data:
            try:
                self.bot.add_view(TicketView(gid, with_dropdown=True))
            except Exception:
                pass

    async def _create_ticket_channel(self, guild, user, ticket_config, channel_name, topic, log_message):
        category_id = ticket_config.get("category_id", 0)
        category = guild.get_channel(category_id)
        if not category:
            return None, "Ticket system not set up. Run `$ticketsetup`."
        for ch in category.text_channels:
            if ch.name.endswith(user.name.lower().replace(".", "")):
                return None, f"You already have an open ticket: {ch.mention}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
        }
        staff_role_id = ticket_config.get("staff_role_id", 0)
        if staff_role_id:
            role = guild.get_role(int(staff_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role_name in ["Staff Team", "staff team", "Staff", "Moderator", "Co Ownzzz", "founderzz"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role.id not in [r.id for r in overwrites]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites, topic=topic)
        embed = discord.Embed(description="Support will be with you shortly.\nTo close this press the close button", color=0x2F3136)
        embed.set_footer(text=f"{guild.name} \u00b7 Ticketing without clutter")
        view = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger, emoji="\U0001f512", custom_id=f"ticket_close_{channel.id}")

        async def close_callback(interaction: discord.Interaction):
            cfg = load_tickets().get(str(guild.id), {})
            staff_rid = cfg.get("staff_role_id", 0)
            is_staff = False
            if staff_rid:
                sr = guild.get_role(staff_rid)
                if sr and sr in interaction.user.roles:
                    is_staff = True
            if interaction.user.id != user.id and not is_staff and not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(embed=error("Error", "Only the ticket opener or staff can close this ticket."), ephemeral=True)
            log_ch = guild.get_channel(cfg.get("log_channel", 0))
            if log_ch:
                msgs = []
                async for msg in channel.history(limit=100):
                    msgs.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content[:200]}")
                transcript = "\n".join(reversed(msgs))
                log_embed = discord.Embed(title=f"\U0001f4cb Ticket Closed \u2014 {channel.name}", description=f"Closed by {interaction.user.mention}\n\n```\n{transcript[:1900]}\n```", color=0xED4245)
                try:
                    await log_ch.send(embed=log_embed)
                except discord.Forbidden:
                    pass
            await interaction.response.send_message(embed=info("\U0001f512 Closing", "This ticket will be deleted in 5 seconds..."))
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket closed by {interaction.user}")

        close_btn.callback = close_callback
        view.add_item(close_btn)
        await channel.send(embed=embed, view=view)
        staff_role = None
        if staff_role_id:
            staff_role = guild.get_role(int(staff_role_id))
        if not staff_role:
            for rn in ["Staff Team", "staff team", "Staff", "Moderator", "staff"]:
                staff_role = discord.utils.get(guild.roles, name=rn)
                if staff_role:
                    break
        ping_text = f"New ticket from {user.mention}!"
        if staff_role:
            try:
                await guild.chunk()
            except Exception:
                pass
            staff_members = [m for m in guild.members if staff_role in m.roles and not m.bot]
            if staff_members:
                ping_text = f"{' '.join(m.mention for m in staff_members)} \u2014 New ticket from {user.mention}!"
            else:
                ping_text = f"{staff_role.mention} \u2014 New ticket from {user.mention}!"
        await channel.send(ping_text)
        log_channel = guild.get_channel(ticket_config.get("log_channel", 0))
        if log_channel:
            try:
                await log_channel.send(embed=info("\U0001f3ab Ticket Opened", log_message.format(user=user.mention, channel=channel.mention)))
            except discord.Forbidden:
                pass
        return channel, None

    async def cog_before_invoke(self, ctx: commands.Context):
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    @commands.hybrid_command(name="ticketsetup", description="Set up the ticket system")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(category_name="Category for ticket channels", log_channel="Channel for ticket logs", with_dropdown="Include a type dropdown (default: no)")
    async def ticketsetup(self, ctx: commands.Context, category_name: str = "Support Zone", log_channel: discord.TextChannel = None, with_dropdown: bool = False):
        guild = ctx.guild
        gid = str(guild.id)
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                category = await guild.create_category(category_name)
            except discord.Forbidden:
                return await ctx.send(embed=error("Error", "I need `Manage Channels` permission."))
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
            if not log_channel:
                try:
                    overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
                    log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites, category=category)
                except discord.Forbidden:
                    pass
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        data[gid]["category_id"] = category.id
        data[gid]["log_channel"] = log_channel.id if log_channel else 0
        data[gid]["types"] = data[gid].get("types", DEFAULT_TYPES)
        data[gid]["tickets"] = {}
        save_tickets(data)
        embed = discord.Embed(title="Request Support", description="To create a ticket use the Create ticket button", color=0x5865F2)
        embed.set_footer(text=f"{guild.name} \u00b7 Ticketing without clutter")
        view = TicketView(gid, with_dropdown=with_dropdown)
        await ctx.send(embed=embed, view=view)
        types_list = ', '.join(t['emoji'] + ' ' + t['label'] for t in data[gid]['types'].values()) if with_dropdown else "None (using Create ticket button)"
        await ctx.send(embed=success("\u2705 Setup Complete", f"**Category:** {category.name}\n**Log Channel:** {log_channel.mention if log_channel else 'None'}\n**Types:** {types_list}\n**Panel:** Sent above \u261d\ufe0f"), ephemeral=True)

    @commands.hybrid_command(name="tickettype", description="Add a new ticket type (requires dropdown)")
    @commands.has_permissions(administrator=True)
    async def tickettype(self, ctx: commands.Context, name: str, emoji: str, channel_prefix: str):
        gid = str(ctx.guild.id)
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        if "types" not in data[gid]:
            data[gid]["types"] = DEFAULT_TYPES
        key = name.lower().replace(" ", "_")
        data[gid]["types"][key] = {"emoji": emoji, "label": name, "channel_prefix": channel_prefix.lower().replace(" ", "-")}
        save_tickets(data)
        await ctx.send(embed=success("\u2705 Type Added", f"**{emoji} {name}** \u2192 `{channel_prefix}`\n\nRun `$ticketsetup` with dropdown to update the panel."))

    @commands.hybrid_command(name="closetype", description="Remove a ticket type")
    @commands.has_permissions(administrator=True)
    async def closetype(self, ctx: commands.Context, name: str):
        gid = str(ctx.guild.id)
        data = load_tickets()
        types = data.get(gid, {}).get("types", {})
        key = name.lower().replace(" ", "_")
        if key in types:
            removed = types.pop(key)
            save_tickets(data)
            await ctx.send(embed=success("\u2705 Removed", f"**{removed['emoji']} {removed['label']}** removed."))
        else:
            await ctx.send(embed=error("Error", f"Type `{name}` not found."))

    @commands.hybrid_command(name="ticketrole", description="Set which role gets pinged when a ticket is opened")
    @commands.has_permissions(administrator=True)
    async def ticketrole(self, ctx: commands.Context, role: discord.Role):
        gid = str(ctx.guild.id)
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        data[gid]["staff_role_id"] = role.id
        save_tickets(data)
        await ctx.send(embed=success("\u2705 Role Set", f"{role.mention} will be pinged for new tickets."))

    @commands.hybrid_command(name="sendpanels", description="Send the ticket panel to each type channel")
    @commands.has_permissions(administrator=True)
    async def sendpanels(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        cfg = load_tickets().get(gid, {})
        ticket_types = cfg.get("types", DEFAULT_TYPES)
        sent = 0
        for key, ttype in ticket_types.items():
            prefix = ttype.get("channel_prefix", "ticket")
            channel = discord.utils.get(ctx.guild.text_channels, name=prefix)
            if not channel:
                for ch in ctx.guild.text_channels:
                    if prefix in ch.name:
                        channel = ch
                        break
            if not channel:
                continue
            embed = discord.Embed(title=f"{ttype['emoji']} {ttype['label']}", description="To create a ticket use the Create ticket button", color=0x5865F2)
            embed.set_footer(text=f"{ctx.guild.name} \u00b7 Ticketing without clutter")
            try:
                await channel.send(embed=embed, view=TicketView(gid))
                sent += 1
            except discord.Forbidden:
                pass
        if sent == 0:
            await ctx.send(embed=error("Error", "No matching channels found."))
        else:
            await ctx.send(embed=success("\u2705 Panels Sent", f"Sent **{sent}** ticket panel(s)."))

    @commands.hybrid_command(name="movetickets", description="Move all ticket channels to the configured category")
    @commands.has_permissions(administrator=True)
    async def movetickets(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        cfg = load_tickets().get(gid, {})
        category_id = cfg.get("category_id", 0)
        category = ctx.guild.get_channel(category_id)
        if not category:
            return await ctx.send(embed=error("Error", f"Category not found. ID: {category_id}"))
        moved = 0
        for ch in ctx.guild.text_channels:
            if ch.name.startswith(("ticket-", "request-", "reward-")):
                if ch.category_id != category_id:
                    try:
                        await ch.edit(category=category, reason=f"Moved by {ctx.author}")
                        moved += 1
                    except discord.Forbidden:
                        pass
                try:
                    await ch.send(embed=discord.Embed(title="\U0001f3ab Ticket Notice", description="This ticket has been moved.", color=0x5865F2))
                except discord.Forbidden:
                    pass
        if moved == 0:
            await ctx.send(embed=info("Tickets", "No ticket channels needed moving."))
        else:
            await ctx.send(embed=success("\u2705 Moved", f"Moved **{moved}** ticket(s) to **{category.name}**."))

    @commands.hybrid_command(name="close", description="Close the current ticket")
    async def close(self, ctx: commands.Context):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        cfg = load_tickets().get(str(ctx.guild.id), {})
        log_channel = ctx.guild.get_channel(cfg.get("log_channel", 0))
        if log_channel:
            messages = []
            async for msg in ctx.channel.history(limit=100):
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content[:200]}")
            transcript = "\n".join(reversed(messages))
            embed = discord.Embed(title=f"\U0001f4cb Ticket Closed \u2014 {ctx.channel.name}", description=f"Closed by {ctx.author.mention}\n\n```\n{transcript[:1900]}\n```", color=0xED4245)
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass
        await ctx.send(embed=info("\U0001f512 Closing", "This ticket will be deleted in 5 seconds..."))
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")

    @commands.hybrid_command(name="add", description="Add a user to this ticket")
    async def add(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(embed=success("\u2705 Added", f"{member.mention} has been added to this ticket."))

    @commands.hybrid_command(name="remove", description="Remove a user from this ticket")
    async def remove(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=False)
        await ctx.send(embed=success("\u2705 Removed", f"{member.mention} has been removed from this ticket."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
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


# ── Default ticket types ──────────────────────────────────────────
DEFAULT_TYPES = {
    "support": {"emoji": "💎", "label": "Request Support", "channel_prefix": "request-support"},
    "reward": {"emoji": "🎁", "label": "Reward Claim", "channel_prefix": "reward-claim"},
    "mm": {"emoji": "🤝", "label": "Request MM", "channel_prefix": "request-mm"},
}


class TicketCreateButton(discord.ui.Button):
    """Create ticket button — instantly creates a support ticket."""

    def __init__(self):
        super().__init__(
            label="Create ticket",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="ticket_create_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        data = load_tickets()
        gid = str(guild.id)
        config = data.get(gid, {})

        category_id = config.get("category_id", 0)
        category = guild.get_channel(category_id)

        if not category:
            return await interaction.response.send_message(
                embed=error("Error", "Ticket system not set up. Run `$ticketsetup`."),
                ephemeral=True
            )

        # Check if user already has an open ticket
        for ch in category.text_channels:
            if ch.name.endswith(user.name.lower().replace(".", "")):
                return await interaction.response.send_message(
                    embed=error("Error", f"You already have an open ticket: {ch.mention}"),
                    ephemeral=True
                )

        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
        }

        # Add configured staff role + fallback names
        staff_role_id = config.get("staff_role_id", 0)
        if staff_role_id:
            role = guild.get_role(staff_role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role_name in ["Staff Team", "staff team", "Staff", "Moderator", "Co Ownzzz", "founderzz"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role.id not in [r.id for r in overwrites]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            f"ticket-{user.name.lower().replace('.', '')}",
            category=category,
            overwrites=overwrites,
            topic=f"Support ticket — opened by {user} ({user.id})"
        )

        # Find staff role to ping
        staff_role = None
        saved_role_id = config.get("staff_role_id", 0)
        print(f"[Tickets] staff_role_id from config: {saved_role_id}")
        if saved_role_id:
            staff_role = guild.get_role(saved_role_id)
            print(f"[Tickets] Found role by ID: {staff_role}")
        if not staff_role:
            for role_name in ["Staff Team", "staff team", "Staff", "Moderator", "staff"]:
                staff_role = discord.utils.get(guild.roles, name=role_name)
                if staff_role:
                    print(f"[Tickets] Found role by name: {staff_role}")
                    break
        print(f"[Tickets] Final staff_role: {staff_role}")

        # Welcome embed — clean TicketTool style
        embed = discord.Embed(
            description=f"Support will be with you shortly.\nTo close this press the close button",
            color=0x2F3136
        )
        embed.set_footer(text=f"{guild.name} · Ticketing without clutter")

        view = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"ticket_close_{channel.id}"
        )

        async def close_callback(interaction: discord.Interaction):
            # Only ticket opener, staff, or admin can close
            config2 = load_tickets().get(str(guild.id), {})
            staff_role_id2 = config2.get("staff_role_id", 0)
            is_staff = False
            if staff_role_id2:
                staff_role2 = guild.get_role(staff_role_id2)
                if staff_role2 and staff_role2 in interaction.user.roles:
                    is_staff = True
            if interaction.user.id != user.id and not is_staff and not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(embed=error("Error", "Only the ticket opener or staff can close this ticket."), ephemeral=True)

            # Save transcript to log
            log_id2 = config2.get("log_channel", 0)
            log_ch2 = guild.get_channel(log_id2)
            if log_ch2:
                msgs = []
                async for msg in channel.history(limit=100):
                    msgs.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content[:200]}")
                transcript = "\n".join(reversed(msgs))
                log_embed = discord.Embed(
                    title=f"📋 Ticket Closed — {channel.name}",
                    description=f"Closed by {interaction.user.mention}\n\n```\n{transcript[:1900]}\n```",
                    color=0xED4245
                )
                try:
                    await log_ch2.send(embed=log_embed)
                except discord.Forbidden:
                    pass

            await interaction.response.send_message(embed=info("🔒 Closing", "This ticket will be deleted in 5 seconds..."))
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket closed by {interaction.user}")

        close_btn.callback = close_callback
        view.add_item(close_btn)

        await channel.send(embed=embed, view=view)

        # Log
        log_id = config.get("log_channel", 0)
        log_channel = guild.get_channel(log_id)
        if log_channel:
            log_embed = info("🎫 Ticket Opened", f"**Opened by:** {user.mention}\n**Channel:** {channel.mention}")
            try:
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            embed=success("✅ Ticket Opened", f"Your ticket: {channel.mention}"),
            ephemeral=True
        )


class TicketTypeSelect(discord.ui.Select):
    """Dropdown to pick ticket type."""

    def __init__(self, guild_id: str):
        data = load_tickets()
        config = data.get(guild_id, {})
        ticket_types = config.get("types", DEFAULT_TYPES)

        options = []
        for key, ttype in ticket_types.items():
            options.append(discord.SelectOption(
                label=ttype["label"],
                value=key,
                emoji=ttype["emoji"],
                description=f"Open a {ttype['label'].lower()} ticket"
            ))

        super().__init__(
            placeholder="Select a category...",
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        ticket_type = self.values[0]

        data = load_tickets()
        gid = str(guild.id)
        config = data.get(gid, {})
        ticket_types = config.get("types", DEFAULT_TYPES)
        ttype = ticket_types.get(ticket_type, DEFAULT_TYPES["support"])

        category_id = config.get("category_id", 0)
        category = guild.get_channel(category_id)

        if not category:
            return await interaction.response.send_message(
                embed=error("Error", "Ticket system not set up. Run `$ticketsetup`."),
                ephemeral=True
            )

        # Check if user already has an open ticket
        prefix = ttype.get("channel_prefix", "ticket")
        for ch in category.text_channels:
            if ch.name.startswith(prefix) and ch.name.endswith(user.name.lower().replace(".", "")):
                return await interaction.response.send_message(
                    embed=error("Error", f"You already have an open ticket: {ch.mention}"),
                    ephemeral=True
                )

        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
        }

        staff_role_id = config.get("staff_role_id", 0)
        if staff_role_id:
            role = guild.get_role(staff_role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role_name in ["Staff Team", "staff team", "Staff", "Moderator", "Co Ownzzz", "founderzz"]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role.id not in [r.id for r in overwrites]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"{prefix}-{user.name.lower().replace('.', '')}"
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"{ttype['label']} — opened by {user} ({user.id})"
        )

        staff_role = None
        saved_role_id = config.get("staff_role_id", 0)
        if saved_role_id:
            staff_role = guild.get_role(saved_role_id)
        if not staff_role:
            for role_name in ["Staff Team", "staff team", "Staff", "Moderator", "staff"]:
                staff_role = discord.utils.get(guild.roles, name=role_name)
                if staff_role:
                    break

        # Welcome embed — clean TicketTool style
        embed = discord.Embed(
            description=f"Support will be with you shortly.\nTo close this press the close button",
            color=0x2F3136
        )
        embed.set_footer(text=f"{guild.name} · Ticketing without clutter")

        view = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"ticket_close_{channel.id}"
        )

        async def close_callback(interaction: discord.Interaction):
            config2 = load_tickets().get(str(guild.id), {})
            staff_role_id2 = config2.get("staff_role_id", 0)
            is_staff = False
            if staff_role_id2:
                staff_role2 = guild.get_role(staff_role_id2)
                if staff_role2 and staff_role2 in interaction.user.roles:
                    is_staff = True
            if interaction.user.id != user.id and not is_staff and not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(embed=error("Error", "Only the ticket opener or staff can close this ticket."), ephemeral=True)

            log_id2 = config2.get("log_channel", 0)
            log_ch2 = guild.get_channel(log_id2)
            if log_ch2:
                msgs = []
                async for msg in channel.history(limit=100):
                    msgs.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content[:200]}")
                transcript = "\n".join(reversed(msgs))
                log_embed = discord.Embed(
                    title=f"📋 Ticket Closed — {channel.name}",
                    description=f"Closed by {interaction.user.mention}\n\n```\n{transcript[:1900]}\n```",
                    color=0xED4245
                )
                try:
                    await log_ch2.send(embed=log_embed)
                except discord.Forbidden:
                    pass

            await interaction.response.send_message(embed=info("🔒 Closing", "This ticket will be deleted in 5 seconds..."))
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket closed by {interaction.user}")

        close_btn.callback = close_callback
        view.add_item(close_btn)

        await channel.send(embed=embed, view=view)

        log_id = config.get("log_channel", 0)
        log_channel = guild.get_channel(log_id)
        if log_channel:
            log_embed = info(
                "🎫 Ticket Opened",
                f"**Type:** {ttype['emoji']} {ttype['label']}\n"
                f"**Opened by:** {user.mention}\n"
                f"**Channel:** {channel.mention}"
            )
            try:
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            embed=success("✅ Ticket Opened", f"Your ticket: {channel.mention}"),
            ephemeral=True
        )


class TicketView(discord.ui.View):
    def __init__(self, guild_id: str = None, with_dropdown: bool = False):
        super().__init__(timeout=None)
        self.add_item(TicketCreateButton())
        if with_dropdown and guild_id:
            self.add_item(TicketTypeSelect(guild_id))


class Tickets(commands.Cog):
    """Support ticket system."""

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

    @commands.hybrid_command(name="ticketsetup", description="Set up the ticket system")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        category_name="Category for ticket channels",
        log_channel="Channel for ticket logs",
        with_dropdown="Include a type dropdown (default: no)"
    )
    async def ticketsetup(self, ctx: commands.Context, category_name: str = "Support Zone", log_channel: discord.TextChannel = None, with_dropdown: bool = False):
        guild = ctx.guild
        gid = str(guild.id)

        # Create category
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                category = await guild.create_category(category_name)
            except discord.Forbidden:
                return await ctx.send(embed=error("Error", "I need `Manage Channels` permission."))

        # Create log channel
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
            if not log_channel:
                try:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    }
                    log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites, category=category)
                except discord.Forbidden:
                    pass

        # Save config
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        data[gid]["category_id"] = category.id
        data[gid]["log_channel"] = log_channel.id if log_channel else 0
        data[gid]["types"] = data[gid].get("types", DEFAULT_TYPES)
        data[gid]["tickets"] = {}
        save_tickets(data)

        # Send ticket panel
        embed = discord.Embed(
            title="Request Support",
            description="To create a ticket use the Create ticket button",
            color=0x5865F2
        )
        embed.set_footer(text=f"{guild.name} · Ticketing without clutter")

        view = TicketView(gid, with_dropdown=with_dropdown)
        await ctx.send(embed=embed, view=view)

        # Confirmation
        types_list = ', '.join(t['emoji'] + ' ' + t['label'] for t in data[gid]['types'].values()) if with_dropdown else "None (using Create ticket button)"
        confirm = success(
            "✅ Setup Complete",
            f"**Category:** {category.name}\n"
            f"**Log Channel:** {log_channel.mention if log_channel else 'None'}\n"
            f"**Types:** {types_list}\n"
            f"**Panel:** Sent above ☝️"
        )
        await ctx.send(embed=confirm, ephemeral=True)

    @commands.hybrid_command(name="tickettype", description="Add a new ticket type (requires dropdown)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Type name", emoji="Emoji for the type", channel_prefix="Channel name prefix")
    async def tickettype(self, ctx: commands.Context, name: str, emoji: str, channel_prefix: str):
        gid = str(ctx.guild.id)
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        if "types" not in data[gid]:
            data[gid]["types"] = DEFAULT_TYPES

        key = name.lower().replace(" ", "_")
        data[gid]["types"][key] = {
            "emoji": emoji,
            "label": name,
            "channel_prefix": channel_prefix.lower().replace(" ", "-"),
        }
        save_tickets(data)

        await ctx.send(embed=success("✅ Type Added", f"**{emoji} {name}** → `{channel_prefix}`\n\nRun `$ticketsetup` with dropdown to update the panel."))

    @commands.hybrid_command(name="closetype", description="Remove a ticket type")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Type name to remove")
    async def closetype(self, ctx: commands.Context, name: str):
        gid = str(ctx.guild.id)
        data = load_tickets()
        types = data.get(gid, {}).get("types", {})
        key = name.lower().replace(" ", "_")

        if key in types:
            removed = types.pop(key)
            save_tickets(data)
            await ctx.send(embed=success("✅ Removed", f"**{removed['emoji']} {removed['label']}** removed."))
        else:
            await ctx.send(embed=error("Error", f"Type `{name}` not found."))

    @commands.hybrid_command(name="ticketrole", description="Set which role gets pinged when a ticket is opened")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to ping for new tickets")
    async def ticketrole(self, ctx: commands.Context, role: discord.Role):
        gid = str(ctx.guild.id)
        data = load_tickets()
        if gid not in data:
            data[gid] = {}
        data[gid]["staff_role_id"] = role.id
        save_tickets(data)
        await ctx.send(embed=success("✅ Role Set", f"{role.mention} will be pinged for new tickets."))

    @commands.hybrid_command(name="sendpanels", description="Send the ticket panel with Create ticket button to each type channel")
    @commands.has_permissions(administrator=True)
    async def sendpanels(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        config = load_tickets().get(gid, {})
        ticket_types = config.get("types", DEFAULT_TYPES)

        sent = 0
        for key, ttype in ticket_types.items():
            prefix = ttype.get("channel_prefix", "ticket")
            # Find the channel by name
            channel = discord.utils.get(ctx.guild.text_channels, name=prefix)
            if not channel:
                # Try partial match
                for ch in ctx.guild.text_channels:
                    if prefix in ch.name:
                        channel = ch
                        break
            if not channel:
                continue

            embed = discord.Embed(
                title=f"{ttype['emoji']} {ttype['label']}",
                description="To create a ticket use the Create ticket button",
                color=0x5865F2
            )
            embed.set_footer(text=f"{ctx.guild.name} · Ticketing without clutter")

            view = TicketView(gid)
            try:
                await channel.send(embed=embed, view=view)
                sent += 1
            except discord.Forbidden:
                pass

        if sent == 0:
            await ctx.send(embed=error("Error", "No matching channels found. Create channels like `request-support`, `reward-claim`, `request-mm` first."))
        else:
            await ctx.send(embed=success("✅ Panels Sent", f"Sent **{sent}** ticket panel(s) with Create ticket button."))

    @commands.hybrid_command(name="movetickets", description="Move all ticket channels to the configured category")
    @commands.has_permissions(administrator=True)
    async def movetickets(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        config = load_tickets().get(gid, {})
        category_id = config.get("category_id", 0)
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

                # Send notice in each ticket channel
                try:
                    notice = discord.Embed(
                        title="🎫 Ticket Notice",
                        description="This ticket has been moved. If you need further assistance, please open a new ticket.",
                        color=0x5865F2
                    )
                    await ch.send(embed=notice)
                except discord.Forbidden:
                    pass

        if moved == 0:
            await ctx.send(embed=info("Tickets", "No ticket channels needed moving."))
        else:
            await ctx.send(embed=success("✅ Moved", f"Moved **{moved}** ticket(s) to **{category.name}**."))

    @commands.hybrid_command(name="close", description="Close the current ticket")
    async def close(self, ctx: commands.Context):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))

        config = load_tickets().get(str(ctx.guild.id), {})
        log_channel = ctx.guild.get_channel(config.get("log_channel", 0))

        if log_channel:
            messages = []
            async for msg in ctx.channel.history(limit=100):
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content[:200]}")
            transcript = "\n".join(reversed(messages))

            embed = discord.Embed(
                title=f"📋 Ticket Closed — {ctx.channel.name}",
                description=f"Closed by {ctx.author.mention}\n\n```\n{transcript[:1900]}\n```",
                color=0xED4245
            )
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass

        await ctx.send(embed=info("🔒 Closing", "This ticket will be deleted in 5 seconds..."))
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")

    @commands.hybrid_command(name="add", description="Add a user to this ticket")
    async def add(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(embed=success("✅ Added", f"{member.mention} has been added to this ticket."))

    @commands.hybrid_command(name="remove", description="Remove a user from this ticket")
    async def remove(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith(("ticket-", "request-", "reward-")):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=False)
        await ctx.send(embed=success("✅ Removed", f"{member.mention} has been removed from this ticket."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

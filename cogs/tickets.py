import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from utils import success, error, info


TICKETS_FILE = "tickets.json"


def load_tickets() -> dict:
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tickets(data: dict):
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class Tickets(commands.Cog):
    """Support ticket system — users open tickets, staff responds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_tickets()

    def _get_config(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {"category_id": 0, "log_channel": 0, "tickets": {}}
        return self.data[gid]

    @commands.hybrid_command(name="ticketsetup", description="Set up the ticket system")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(category="Category for ticket channels", log_channel="Channel to log ticket transcripts")
    async def ticketsetup(self, ctx: commands.Context, category: discord.CategoryChannel, log_channel: discord.TextChannel):
        gid = str(ctx.guild.id)
        config = self._get_config(ctx.guild.id)
        config["category_id"] = category.id
        config["log_channel"] = log_channel.id
        save_tickets(self.data)

        # Send ticket panel
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Need help? Open a ticket by clicking the button below!\n\nOur staff team will assist you as soon as possible.",
            color=0x5865F2
        )
        embed.set_footer(text="Click the button to open a ticket")

        view = TicketView(self.bot)
        await ctx.send(embed=embed, view=view)
        await ctx.send(embed=success("✅ Setup Complete", f"Category: {category.name}\nLog Channel: {log_channel.mention}"))

    @commands.hybrid_command(name="close", description="Close the current ticket")
    async def close(self, ctx: commands.Context):
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))

        config = self._get_config(ctx.guild.id)
        log_channel = ctx.guild.get_channel(config.get("log_channel", 0))

        # Send transcript
        if log_channel:
            messages = []
            async for msg in ctx.channel.history(limit=100):
                messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
            transcript = "\n".join(reversed(messages))

            embed = discord.Embed(
                title=f"📋 Ticket Closed — {ctx.channel.name}",
                description=f"Closed by {ctx.author.mention}\n\n```\n{transcript[:1900]}\n```",
                color=0xED4245
            )
            await log_channel.send(embed=embed)

        await ctx.send(embed=info("🔒 Closing", "This ticket will be deleted in 5 seconds..."))
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")

    @commands.hybrid_command(name="add", description="Add a user to this ticket")
    async def add(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(embed=success("✅ Added", f"{member.mention} has been added to this ticket."))

    @commands.hybrid_command(name="remove", description="Remove a user from this ticket")
    async def remove(self, ctx: commands.Context, member: discord.Member):
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send(embed=error("Error", "This isn't a ticket channel."))
        await ctx.channel.set_permissions(member, read_messages=False)
        await ctx.send(embed=success("✅ Removed", f"{member.mention} has been removed from this ticket."))


class TicketView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        # Check if user already has an open ticket
        for channel in guild.text_channels:
            if channel.name == f"ticket-{user.name.lower()}":
                return await interaction.response.send_message(
                    embed=error("Error", f"You already have an open ticket: {channel.mention}"),
                    ephemeral=True
                )

        # Create ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        # Find support role if exists
        support_role = discord.utils.get(guild.roles, name="Staff Team")
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            f"ticket-{user.name.lower()}",
            category=guild.get_channel(0) if not guild.categories else guild.categories[0],
            overwrites=overwrites,
            topic=f"Ticket opened by {user}"
        )

        embed = discord.Embed(
            title=f"🎫 Ticket — {user.name}",
            description=f"Welcome {user.mention}! Describe your issue and our staff will assist you.\n\nType `$close` when resolved.",
            color=0x5865F2
        )
        await channel.send(embed=embed)
        await interaction.response.send_message(
            embed=success("✅ Ticket Opened", f"Your ticket: {channel.mention}"),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

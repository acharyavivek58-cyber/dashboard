import discord
from discord.ext import commands
from discord import app_commands
from utils import success, error, info


class Roles(commands.Cog):
    """Role management — add, remove, create, list roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Add Role ─────────────────────────────────────────────────────────
    @commands.hybrid_command(name="role", description="Add or remove a role from a member")
    @app_commands.describe(member="Member to modify", role="Role to add or remove")
    async def role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Roles` permission."))
        if role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I can't manage a role equal to or higher than my highest role."))
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=error("Error", "You can't manage a role equal to or higher than your highest role."))

        if role in member.roles:
            await member.remove_roles(role, reason=f"Removed by {ctx.author}")
            await ctx.send(embed=success("🔄 Role Removed", f"Removed **{role.name}** from **{member}**."))
        else:
            await member.add_roles(role, reason=f"Added by {ctx.author}")
            await ctx.send(embed=success("✅ Role Added", f"Added **{role.name}** to **{member}**."))

    # ── Create Role ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="createrole", description="Create a new role")
    @app_commands.describe(name="Role name", color="Hex color (e.g. #FF5733)", hoist="Show separately in member list")
    async def createrole(self, ctx: commands.Context, name: str, color: str = "#99AAB5", hoist: bool = False):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Roles` permission."))

        try:
            color_int = int(color.strip("#"), 16)
        except ValueError:
            return await ctx.send(embed=error("Error", "Invalid hex color. Use format `#FF5733`."))

        role = await ctx.guild.create_role(name=name, color=discord.Color(color_int), hoist=hoist, reason=f"Created by {ctx.author}")
        await ctx.send(embed=success("✅ Role Created", f"Created **{role.mention}** (color: `{color}`)."))

    # ── Delete Role ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="deleterole", description="Delete a role")
    @app_commands.describe(role="Role to delete")
    async def deleterole(self, ctx: commands.Context, role: discord.Role):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.send(embed=error("Permission Denied", "You need `Manage Roles` permission."))
        if role >= ctx.me.top_role:
            return await ctx.send(embed=error("Error", "I can't delete a role equal to or higher than my highest role."))

        name = role.name
        await role.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send(embed=success("🗑️ Role Deleted", f"Deleted **{name}**."))

    # ── Role List ────────────────────────────────────────────────────────
    @commands.hybrid_command(name="roles", description="List all roles in this server")
    async def roles_list(self, ctx: commands.Context):
        roles = [r for r in ctx.guild.roles if r != ctx.guild.default_role]
        if not roles:
            return await ctx.send(embed=info("Roles", "This server has no roles."))

        lines = [f"{r.mention} — `{len(r.members)} members`" for r in reversed(roles)]
        # Paginate if too long
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 1024:
                chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks):
            title = f"Roles ({len(roles)})" if i == 0 else f"Roles (continued {i + 1}/{len(chunks)})"
            await ctx.send(embed=info(title, chunk))


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))

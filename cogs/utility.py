import discord
from discord.ext import commands
from discord import app_commands
import datetime
import aiohttp
import config
from utils import success, error, info, member_embed, server_embed


class Utility(commands.Cog):
    """Utility commands — info, avatar, ping, uptime, avatar."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    async def cog_before_invoke(self, ctx: commands.Context):
        """Check dashboard permissions for utility commands."""
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    # ── Ping ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ping", description="Check bot latency")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        e = success("🏓 Pong!", f"**Latency:** {latency}ms\n**API:** {latency}ms")
        await ctx.send(embed=e)

    # ── Uptime ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="uptime", description="Show bot uptime")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def uptime(self, ctx: commands.Context):
        delta = datetime.datetime.now(datetime.timezone.utc) - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        await ctx.send(embed=success("⏱️ Uptime", " ".join(parts)))

    # ── User Info ────────────────────────────────────────────────────────
    @commands.hybrid_command(name="userinfo", description="Get info about a member")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(member="Member to get info about (defaults to you)")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(embed=member_embed(member))

    # ── Server Info ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="serverinfo", description="Get info about this server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def serverinfo(self, ctx: commands.Context):
        await ctx.send(embed=server_embed(ctx.guild))

    # ── Avatar ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="avatar", description="Get a member's avatar")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(member="Member whose avatar to get")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        e = discord.Embed(title=f"{member.display_name}'s Avatar", color=member.color if member.color != discord.Color.default() else 0x5865F2)
        e.set_image(url=member.display_avatar.url)
        e.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=e)

    # ── Server Icon ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="servericon", description="Get the server's icon")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def servericon(self, ctx: commands.Context):
        if not ctx.guild.icon:
            return await ctx.send(embed=error("Error", "This server has no icon."))
        e = discord.Embed(title=f"{ctx.guild.name}'s Icon", color=0x5865F2)
        e.set_image(url=ctx.guild.icon.url)
        await ctx.send(embed=e)

    # ── Lookup ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="id", description="Get a member's user ID")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @app_commands.describe(member="Member to look up")
    async def user_id(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(embed=success("ID", f"**{member}** → `{member.id}`"))

    # ── ChatGPT ──────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ask", description="Ask ChatGPT anything")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(question="Your question for the AI")
    async def ask(self, ctx: commands.Context, *, question: str):
        async with ctx.typing():
            try:
                answer = await self._ask_ai(question)
            except Exception as e:
                return await ctx.send(embed=error("🤖 AI Error", f"Couldn't reach the AI right now.\n```{e}```"))
        if not answer:
            return await ctx.send(embed=error("🤖 AI Error", "The AI returned an empty response — try rephrasing."))
        chunks = [answer[i:i + 3900] for i in range(0, len(answer), 3900)]
        await ctx.send(embed=success("🤖 ChatGPT", chunks[0]))
        for chunk in chunks[1:]:
            await ctx.send(chunk[:2000])

    async def _ask_ai(self, prompt: str) -> str:
        """Answer via local Ollama (free, no key) or the OpenAI API if a key is set."""
        timeout = aiohttp.ClientTimeout(total=120)
        # 1. Local Ollama — free, runs on this machine.
        try:
            payload = {
                "model": "llama3.2",
                "messages": [
                    {"role": "system", "content": "You are a friendly Discord assistant. Keep answers clear, concise and well-formatted."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 500},
            }
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post("http://localhost:11434/api/chat", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answer = data.get("message", {}).get("content", "").strip()
                        if answer:
                            return answer
        except Exception:
            pass  # Ollama not running — fall through to OpenAI.
        # 2. OpenAI API — needs a key with credits.
        if config.OPENAI_API_KEY:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a friendly Discord assistant. Keep answers clear, concise and well-formatted."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 800,
            }
            headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise RuntimeError(data.get("error", {}).get("message", f"HTTP {resp.status}"))
                    return data["choices"][0]["message"]["content"].strip()
        raise RuntimeError("No AI backend available — start Ollama (free, local) or add OpenAI credits.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))

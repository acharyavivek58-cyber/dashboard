import discord
from discord.ext import commands
from discord import app_commands
import random
from utils import success, info


class Fun(commands.Cog):
    """Fun commands — 8ball, coinflip, dice, reverse, say, choose."""

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question")
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes — definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful.",
        ]
        e = info("🎱 Magic 8-Ball", f"**Q:** {question}\n**A:** {random.choice(responses)}")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="coinflip", description="Flip a coin")
    async def coinflip(self, ctx: commands.Context):
        result = random.choice(["🪙 Heads!", "🪙 Tails!"])
        await ctx.send(embed=success("Coin Flip", result))

    @commands.hybrid_command(name="reverse", description="Reverse a string")
    @app_commands.describe(text="Text to reverse")
    async def reverse(self, ctx: commands.Context, *, text: str):
        await ctx.send(embed=success("🔄 Reversed", f"```\n{text[::-1]}\n```"))

    @commands.hybrid_command(name="choose", description="Choose from a list of options")
    @app_commands.describe(options="Options separated by commas")
    async def choose(self, ctx: commands.Context, *, options: str):
        choices = [c.strip() for c in options.split(",") if c.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=info("Choose", "Provide at least 2 options separated by commas."))
        pick = random.choice(choices)
        await ctx.send(embed=success("🎯 I choose...", f"**{pick}**\n\n*From: {', '.join(choices)}*"))

    @commands.hybrid_command(name="say", description="Make the bot say something")
    @app_commands.describe(text="What the bot should say")
    async def say(self, ctx: commands.Context, *, text: str):
        await ctx.message.delete()
        await ctx.send(text)

    @commands.hybrid_command(name="poll", description="Create a quick poll")
    @app_commands.describe(question="Poll question", options="Options separated by commas (max 10)")
    async def poll(self, ctx: commands.Context, question: str, *, options: str = ""):
        if not options:
            # Yes/No poll
            e = discord.Embed(title="📊 Poll", description=f"**{question}**", color=0x5865F2)
            msg = await ctx.send(embed=e)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            return

        choices = [c.strip() for c in options.split(",") if c.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=info("Poll", "Provide at least 2 options."))
        if len(choices) > 10:
            return await ctx.send(embed=info("Poll", "Maximum 10 options."))

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        desc_lines = [f"{number_emojis[i]} {c}" for i, c in enumerate(choices)]
        e = discord.Embed(title="📊 Poll", description=f"**{question}**\n\n" + "\n".join(desc_lines), color=0x5865F2)
        e.set_footer(text=f"Poll by {ctx.author.display_name}")
        msg = await ctx.send(embed=e)
        for i in range(len(choices)):
            await msg.add_reaction(number_emojis[i])


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))

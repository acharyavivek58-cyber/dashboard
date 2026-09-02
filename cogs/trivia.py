import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import html
import random
import config
from utils import success, error, info


def load_scores() -> dict:
    return config.load_state("trivia_scores.json")


def save_scores(data: dict):
    config.save_state("trivia_scores.json", data)


# ── Built-in fallback questions ────────────────────────────────────
FALLBACK_QUESTIONS = [
    {"question": "What planet is known as the Red Planet?", "correct": "Mars", "incorrect": ["Venus", "Jupiter", "Saturn"]},
    {"question": "How many continents are there?", "correct": "7", "incorrect": ["5", "6", "8"]},
    {"question": "What is the capital of Japan?", "correct": "Tokyo", "incorrect": ["Seoul", "Beijing", "Bangkok"]},
    {"question": "What is the largest ocean?", "correct": "Pacific Ocean", "incorrect": ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean"]},
    {"question": "How many bones are in the human body?", "correct": "206", "incorrect": ["195", "210", "180"]},
    {"question": "What gas do plants absorb?", "correct": "Carbon dioxide", "incorrect": ["Oxygen", "Nitrogen", "Helium"]},
    {"question": "What is the hardest natural substance?", "correct": "Diamond", "incorrect": ["Gold", "Iron", "Quartz"]},
    {"question": "How many days in a leap year?", "correct": "366", "incorrect": ["365", "364", "367"]},
    {"question": "What is the speed of light?", "correct": "300,000 km/s", "incorrect": ["150,000 km/s", "500,000 km/s", "100,000 km/s"]},
    {"question": "What is the largest planet?", "correct": "Jupiter", "incorrect": ["Saturn", "Neptune", "Earth"]},
    {"question": "What year did World War II end?", "correct": "1945", "incorrect": ["1943", "1944", "1946"]},
    {"question": "What is the chemical symbol for water?", "correct": "H2O", "incorrect": ["CO2", "O2", "NaCl"]},
    {"question": "How many players in a soccer team?", "correct": "11", "incorrect": ["9", "10", "12"]},
    {"question": "What is the tallest mountain?", "correct": "Mount Everest", "incorrect": ["K2", "Kangchenjunga", "Mount Kilimanjaro"]},
    {"question": "What language has the most speakers?", "correct": "English", "incorrect": ["Mandarin", "Spanish", "Hindi"]},
    {"question": "What is the smallest country?", "correct": "Vatican City", "incorrect": ["Monaco", "Liechtenstein", "San Marino"]},
    {"question": "How many colors in a rainbow?", "correct": "7", "incorrect": ["5", "6", "8"]},
    {"question": "What animal is known as the King of the Jungle?", "correct": "Lion", "incorrect": ["Tiger", "Elephant", "Bear"]},
    {"question": "What is the boiling point of water?", "correct": "100°C", "incorrect": ["90°C", "110°C", "80°C"]},
    {"question": "How many sides does a hexagon have?", "correct": "6", "incorrect": ["5", "7", "8"]},
]


class TriviaView(discord.ui.View):
    """View with 4 answer buttons for trivia."""

    def __init__(self, correct_answer: str, question_text: str, user_id: int, timeoutSec: int = 15):
        super().__init__(timeout=timeoutSec)
        self.correct = correct_answer
        self.question_text = question_text
        self.user_id = user_id
        self.answered = False

    async def on_timeout(self):
        # Disable all buttons on timeout
        for child in self.children:
            child.disabled = True
        if not self.answered:
            try:
                await self.message.edit(
                    embed=discord.Embed(
                        title="⏱️ Time's Up!",
                        description=f"**{self.question_text}**\n\nThe answer was: **{self.correct}**",
                        color=0xFEE75C
                    ),
                    view=self
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(label="A", style=discord.ButtonStyle.secondary)
    async def button_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, button.label)

    @discord.ui.button(label="B", style=discord.ButtonStyle.secondary)
    async def button_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, button.label)

    @discord.ui.button(label="C", style=discord.ButtonStyle.secondary)
    async def button_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, button.label)

    @discord.ui.button(label="D", style=discord.ButtonStyle.secondary)
    async def button_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._answer(interaction, button.label)

    async def _answer(self, interaction: discord.Interaction, choice: str):
        if not config.has_permission("trivia", interaction.user):
            return await interaction.response.send_message(embed=error("Permission Denied", "You don't have permission to play trivia."), ephemeral=True)
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your question!", ephemeral=True)

        if self.answered:
            return await interaction.response.send_message("You already answered!", ephemeral=True)

        self.answered = True
        for child in self.children:
            child.disabled = True

        # Find which answer was selected
        answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        # The correct answer index is stored from the shuffle
        selected_index = answer_map[choice]
        is_correct = (self.answers[selected_index] == self.correct)

        if is_correct:
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"**{self.question_text}**\n\nThe answer was: **{self.correct}**\n\n**+10 points!**",
                color=0x57F287
            )
        else:
            embed = discord.Embed(
                title="❌ Wrong!",
                description=f"**{self.question_text}**\n\nThe answer was: **{self.correct}**\n\nYou selected: {self.answers[selected_index]}",
                color=0xED4245
            )

        await interaction.response.edit_message(embed=embed, view=self)
        self._result = is_correct

    def set_answers(self, answers: list):
        self.answers = answers


class Trivia(commands.Cog):
    """Trivia game — test your knowledge!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context):
        """Check dashboard permissions for trivia commands."""
        if ctx.author.id == ctx.guild.owner_id:
            return
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            raise commands.CommandError('No permission')

    async def _fetch_question(self) -> dict | None:
        """Fetch a random question from Open Trivia DB."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://opentdb.com/api.php?amount=1&type=multiple&encode=url3986",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("response_code") == 0 and data.get("results"):
                            q = data["results"][0]
                            return {
                                "question": html.unescape(q["question"]),
                                "correct": html.unescape(q["correct_answer"]),
                                "incorrect": [html.unescape(a) for a in q["incorrect_answers"]],
                            }
        except Exception:
            pass
        return None

    def _get_question(self, q: dict) -> tuple[str, list, str]:
        """Shuffle answers and return (question, answers_list, correct)."""
        answers = q["incorrect"] + [q["correct"]]
        random.shuffle(answers)
        return q["question"], answers, q["correct"]

    @commands.hybrid_command(name="trivia", description="Play a round of trivia")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def trivia(self, ctx: commands.Context):
        # Try API first, fallback to built-in
        q = await self._fetch_question()
        if not q:
            q = random.choice(FALLBACK_QUESTIONS)

        question_text, answers, correct = self._get_question(q)
        labels = ["A", "B", "C", "D"]

        # Build embed
        desc = ""
        for i, ans in enumerate(answers):
            desc += f"**{labels[i]}.** {ans}\n"

        embed = discord.Embed(
            title="🧠 Trivia",
            description=f"**{question_text}**\n\n{desc}",
            color=0x5865F2
        )
        embed.set_footer(text=f"Asked by {ctx.author.display_name} · 15s to answer")

        view = TriviaView(correct, question_text, ctx.author.id)
        view.set_answers(answers)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

        # Wait for view to finish
        await view.wait()

        # Update scores
        if hasattr(view, '_result') and view._result:
            gid = str(ctx.guild.id)
            uid = str(ctx.author.id)
            scores = load_scores()
            if gid not in scores:
                scores[gid] = {}
            if uid not in scores[gid]:
                scores[gid][uid] = {"name": ctx.author.display_name, "score": 0, "correct": 0, "played": 0}
            scores[gid][uid]["score"] += 10
            scores[gid][uid]["correct"] += 1
            scores[gid][uid]["played"] += 1
            scores[gid][uid]["name"] = ctx.author.display_name
            save_scores(scores)
        elif hasattr(view, '_result') and not view._result:
            gid = str(ctx.guild.id)
            uid = str(ctx.author.id)
            scores = load_scores()
            if gid not in scores:
                scores[gid] = {}
            if uid not in scores[gid]:
                scores[gid][uid] = {"name": ctx.author.display_name, "score": 0, "correct": 0, "played": 0}
            scores[gid][uid]["played"] += 1
            scores[gid][uid]["name"] = ctx.author.display_name
            save_scores(scores)

    @commands.hybrid_command(name="triviascore", description="Check your trivia score")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def triviascore(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        gid = str(ctx.guild.id)
        uid = str(member.id)
        scores = load_scores()
        user = scores.get(gid, {}).get(uid)

        if not user:
            return await ctx.send(embed=info("🧠 Trivia", f"**{member.display_name}** hasn't played yet."))

        accuracy = round(user["correct"] / user["played"] * 100) if user["played"] > 0 else 0

        embed = discord.Embed(title=f"🧠 Trivia Score — {member.display_name}", color=0x5865F2)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Score", value=f"**{user['score']}** pts", inline=True)
        embed.add_field(name="Correct", value=f"**{user['correct']}**/{user['played']}", inline=True)
        embed.add_field(name="Accuracy", value=f"**{accuracy}%**", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trivialeaderboard", aliases=["tlb"], description="Trivia leaderboard")
    async def trivialeaderboard(self, ctx: commands.Context):
        gid = str(ctx.guild.id)
        scores = load_scores().get(gid, {})

        if not scores:
            return await ctx.send(embed=info("🧠 Trivia Leaderboard", "No scores yet. Play with `$trivia`!"))

        sorted_users = sorted(scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(sorted_users):
            prefix = medals[i] if i < 3 else f"**{i+1}.**"
            accuracy = round(data["correct"] / data["played"] * 100) if data.get("played", 0) > 0 else 0
            lines.append(f"{prefix} **{data['name']}** — `{data['score']}pts` ({data['correct']}/{data.get('played', 0)} · {accuracy}%)")

        embed = discord.Embed(title="🧠 Trivia Leaderboard", description="\n".join(lines), color=0x5865F2)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))

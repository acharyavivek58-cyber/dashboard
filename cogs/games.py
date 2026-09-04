import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import config
from utils import success, error, info, warning


GAMES_CHANNEL_ID = 1534228053163511879


class Games(commands.Cog):
    """Server Games — play with friends!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context):
        """Lock all game commands to the designated channel and check permissions."""
        if ctx.channel.id != GAMES_CHANNEL_ID:
            channel = ctx.guild.get_channel(GAMES_CHANNEL_ID)
            if channel:
                await ctx.send(embed=error("Wrong Channel", f"Games can only be played in {channel.mention}!"), delete_after=5)
            else:
                await ctx.send(embed=error("Wrong Channel", "Games can only be played in the designated games channel!"), delete_after=5)
            raise commands.CommandError('Not in games channel')
        # Check dashboard permissions
        cmd_name = ctx.command.qualified_name.split()[0]
        if not config.has_permission(cmd_name, ctx.author):
            await ctx.send(embed=error("Permission Denied", "You don't have permission to use this command."), delete_after=5)
            raise commands.CommandError('No permission')

    # Roulette (Fizbo-style interactive)
    @commands.hybrid_command(name="roulette", description="Interactive roulette \u2014 join, pick a number, survive!")
    async def roulette(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 20

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Pick a number that will represent you",
                "2\u20e3 A random number (the gunshot) will be chosen",
                "3\u20e3 If your number matches the gunshot, you\u2019re out!",
                "4\u20e3 Last player standing wins",
                "",
                f"**Participating players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                lines.append(f"{i}\u20e3 {p.mention}")
            lines.append("")
            lines.append(f"The game will start in **15 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            grid = ""
            for n in range(1, max_players + 1):
                grid += f"`{n:2d}` "
                if n % 5 == 0:
                    grid += "\n"
            lines.append(grid)
            return discord.Embed(title="\U0001f52b Roulette", description="\n".join(lines), color=0x2F3136)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=20)
                self.game_started = False

            @discord.ui.button(label="Random join", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave the game", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You\u2019re not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can\u2019t leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(15)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < 2:
            return await msg.edit(embed=discord.Embed(title="\U0001f52b Roulette", description="Not enough players! Need at least 2.", color=0xED4245), view=view)
        random.shuffle(players)
        number_map = {i + 1: p for i, p in enumerate(players)}
        gunshot = random.randint(1, len(players))
        eliminated = number_map[gunshot]
        grid_lines = []
        for n in range(1, len(players) + 1):
            p = number_map[n]
            marker = "\U0001f4a5" if n == gunshot else "\u2b1c"
            grid_lines.append(f"{marker} **{n}** \u2014 {p.mention}")
        result_embed = discord.Embed(
            title="\U0001f52b Roulette \u2014 Results",
            description="\n".join(grid_lines) + f"\n\n**Gunshot number: {gunshot}**\n\n{eliminated.mention} has been eliminated! \U0001f480",
            color=0xED4245
        )
        await msg.edit(embed=result_embed, view=None)


    # ── Dice ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="dice", description="Roll dice")
    @app_commands.describe(dice="Number of dice (1-10)", sides="Sides per die (2-100)")
    async def dice(self, ctx: commands.Context, dice: int = 1, sides: int = 6):
        dice = max(1, min(10, dice))
        sides = max(2, min(100, sides))
        rolls = [random.randint(1, sides) for _ in range(dice)]
        total = sum(rolls)
        roll_str = ", ".join(str(r) for r in rolls)
        embed = success("🎲 Dice Roll", f"**{dice}d{sides}:** {roll_str}\n**Total:** {total}")
        await ctx.send(embed=embed)
    # Truth or Dare — reference-style: categorized prompts, Truth/Dare/Random buttons,
    # "Requested by" footer, keeps playing round after round on one message.
    @commands.hybrid_command(name="truthordare", aliases=["tod"], description="Truth or Dare — pick a poison!")
    @app_commands.describe(target="Who's it for? (optional)")
    async def truthordare(self, ctx: commands.Context, target: discord.Member = None):
        truths = {
            "Friendship": [
                "Have you ever shared a friend's secret with someone else?",
                "What's the nicest thing a friend has ever done for you?",
                "Who in this server would you swap lives with for a day?",
                "What's something you've never told your best friend?",
                "Have you ever ended a friendship over something small?",
                "What's the pettiest thing you've ever done to a friend?",
            ],
            "Confessions": [
                "What's the last lie you told?",
                "What's a secret you've never told anyone in this server?",
                "What's the biggest lie you've told to get out of trouble?",
                "Have you ever snooped through someone's phone?",
                "What's something you've done that your parents still don't know about?",
                "What's something you do when you're alone that you'd never do publicly?",
            ],
            "Embarrassing": [
                "What's the most embarrassing thing you've done in public?",
                "What's the worst haircut you've ever had?",
                "What was your most embarrassing crush?",
                "What's the most embarrassing thing in your search history?",
                "What's the most awkward message you've ever sent?",
                "What's your most embarrassing moment from school or work?",
            ],
            "Love & Dating": [
                "Who's your celebrity crush?",
                "What's the worst date you've ever been on?",
                "Have you ever sent a text to the wrong person? What happened?",
                "Have you ever had a crush on a friend?",
                "What's the most romantic thing you've ever done?",
                "What's the cringiest thing you've ever posted online?",
            ],
            "Life": [
                "What's your most controversial opinion?",
                "What's the biggest risk you've ever taken?",
                "What's the most money you've wasted on something useless?",
                "What's the strangest dream you remember?",
                "What's an irrational fear you have?",
                "What's the most childish thing you still do?",
            ],
        }
        dares = {
            "Social": [
                "Send a compliment to every person who messaged in the last 10 minutes.",
                "Let the server pick your nickname for 1 hour.",
                "Send 'I love this server more than life itself' in the chat.",
                "Make your status say 'currently losing at Truth or Dare' for 1 hour.",
                "Praise the last person who sent a message here.",
                "Send your most-used sticker or emoji.",
            ],
            "Embarrassing": [
                "Send your current camera roll's last photo.",
                "Send a voice message singing your favorite song's chorus.",
                "Describe your morning routine in the most dramatic way possible.",
                "Do an impression of someone in this server until they guess who it is.",
                "Send the worst joke you know.",
                "Act out your favorite emoji using only text.",
            ],
            "Fun": [
                "Send a message using only emojis to describe your last meal.",
                "Talk like a pirate for your next 5 messages.",
                "Speak in lowercase and no punctuation for the next 10 messages.",
                "Make a haiku about the last message sent in this channel.",
                "Recite the alphabet backwards in chat.",
                "Type with your elbows for the next 3 messages.",
            ],
            "Challenge": [
                "Do 10 pushups right now and tell us when you're done.",
                "Send a selfie-style description of your current outfit.",
                "Share your screen for 30 seconds (if you can).",
                "Reveal your phone's battery percentage right now.",
                "Send the first result when you Google your own username.",
                "Turn your phone brightness to max and stare at it for 10 seconds.",
            ],
        }
        player = ctx.author
        subject = target if (target and not target.bot and target.id != player.id) else player

        def footer():
            return {"text": f"Requested by {player.display_name}", "icon_url": player.display_avatar.url}

        class TordView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=600)

            async def _reveal(self, interaction: discord.Interaction, kind: str):
                if kind == "random":
                    kind = random.choice(("truth", "dare"))
                if kind == "truth":
                    cat = random.choice(list(truths))
                    prompt = random.choice(truths[cat])
                    embed = discord.Embed(title=f"💙 Truth — {cat} 💕", description=f"*{prompt}*", color=0x00B0F4)
                else:
                    cat = random.choice(list(dares))
                    prompt = random.choice(dares[cat])
                    embed = discord.Embed(title=f"💖 Dare — {cat} 😈", description=f"*{prompt}*", color=0xEB459E)
                if subject != player:
                    embed.description += f"\n\n🎯 {subject.mention} — your turn!"
                embed.set_footer(**footer())
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Truth", style=discord.ButtonStyle.primary, emoji="💙")
            async def b_truth(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self._reveal(interaction, "truth")

            @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger, emoji="💖")
            async def b_dare(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self._reveal(interaction, "dare")

            @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="🎲")
            async def b_random(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self._reveal(interaction, "random")

        view = TordView()
        intro = discord.Embed(
            title="🎯 Truth or Dare",
            description=f"{'🎯 ' + subject.mention + ' — ' if subject != player else ''}pick your poison:",
            color=0x2F3136,
        )
        intro.set_footer(**footer())
        await ctx.send(embed=intro, view=view)
    # Rock Paper Scissors (Fizbo-style interactive)
    @commands.hybrid_command(name="rps", description="Interactive RPS \u2014 join, pick, battle!")
    async def rps(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 2

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Join the game",
                "2\u20e3 Pick rock, paper, or scissors",
                "3\u20e3 Beat your opponent to win!",
                "",
                f"**Players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                lines.append(f"{i}\u20e3 {p.mention}")
            lines.append("")
            lines.append(f"The game will start in **10 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            return discord.Embed(title="\U0001faa9\U0001f4f0\u2702\ufe0f Rock Paper Scissors", description="\n".join(lines), color=0x5865F2)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=15)
                self.game_started = False

            @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave Game", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You\u2019re not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can\u2019t leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(10)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < 2:
            return await msg.edit(embed=discord.Embed(title="\U0001faa9\U0001f4f0\u2702\ufe0f RPS", description="Not enough players! Need 2.", color=0xED4245), view=view)

        # Ask both players for their choice
        emojis = {"rock": "\U0001faa8", "paper": "\U0001f4f0", "scissors": "\u2702\ufe0f"}
        choices = {}

        class ChoiceView(discord.ui.View):
            def __init__(self, player):
                super().__init__(timeout=30)
                self.player = player

            @discord.ui.button(label="Rock", emoji="\U0001faa8", style=discord.ButtonStyle.secondary)
            async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != self.player:
                    return await interaction.response.send_message("Not your turn!", ephemeral=True)
                choices[self.player.id] = "rock"
                await interaction.response.edit_message(content=f"{self.player.mention} chose **Rock** \U0001faa8", view=None)

            @discord.ui.button(label="Paper", emoji="\U0001f4f0", style=discord.ButtonStyle.secondary)
            async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != self.player:
                    return await interaction.response.send_message("Not your turn!", ephemeral=True)
                choices[self.player.id] = "paper"
                await interaction.response.edit_message(content=f"{self.player.mention} chose **Paper** \U0001f4f0", view=None)

            @discord.ui.button(label="Scissors", emoji="\u2702\ufe0f", style=discord.ButtonStyle.secondary)
            async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != self.player:
                    return await interaction.response.send_message("Not your turn!", ephemeral=True)
                choices[self.player.id] = "scissors"
                await interaction.response.edit_message(content=f"{self.player.mention} chose **Scissors** \u2702\ufe0f", view=None)

        # Send choice prompts
        for p in players:
            await ctx.send(f"{p.mention}, pick your move!", view=ChoiceView(p))

        # Wait for both choices
        for _ in range(30):
            if len(choices) == 2:
                break
            await asyncio.sleep(1)

        if len(choices) < 2:
            return await ctx.send(embed=discord.Embed(title="RPS", description="Not everyone picked in time!", color=0xED4245))

        p1, p2 = players[0], players[1]
        c1, c2 = choices[p1.id], choices[p2.id]

        if c1 == c2:
            result, color = "It\u2019s a **tie**! \U0001f91d", 0xFEE75C
            winner = None
        elif (c1 == "rock" and c2 == "scissors") or (c1 == "paper" and c2 == "rock") or (c1 == "scissors" and c2 == "paper"):
            result, color = f"**{p1.display_name}** wins! \U0001f389", 0x57F287
            winner = p1
        else:
            result, color = f"**{p2.display_name}** wins! \U0001f389", 0x57F287
            winner = p2

        result_embed = discord.Embed(
            title="\U0001faa9\U0001f4f0\u2702\ufe0f RPS \u2014 Results",
            description=f"{p1.mention}: **{emojis[c1]} {c1.title()}**\n{p2.mention}: **{emojis[c2]} {c2.title()}**\n\n{result}",
            color=color
        )
        await ctx.send(embed=result_embed)

    # XO (Tic Tac Toe) (Fizbo-style interactive)
    @commands.hybrid_command(name="xo", description="Interactive Tic Tac Toe \u2014 join, battle!")
    async def xo(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 2

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Join the game",
                "2\u20e3 Take turns placing X or O",
                "3\u20e3 Get 3 in a row to win!",
                "",
                f"**Players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                marker = "\u274c" if i == 1 else "\u2b55"
                lines.append(f"{i}\u20e3 {p.mention} ({marker})")
            lines.append("")
            lines.append(f"The game will start in **10 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            return discord.Embed(title="\u274c\u2b55 Tic Tac Toe", description="\n".join(lines), color=0x5865F2)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=15)
                self.game_started = False

            @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave Game", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You\u2019re not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can\u2019t leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(10)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < 2:
            return await msg.edit(embed=discord.Embed(title="XO", description="Not enough players! Need 2.", color=0xED4245), view=view)

        board = ["\u20e3"] * 9
        player_marks = {players[0].id: "\u274c", players[1].id: "\u2b55"}
        current_idx = [0]  # mutable container for closure

        def render_board():
            return f"{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}"

        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

        class BoardView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, row=0)
            async def b1(self, interaction, button): await self._move(interaction, 0)
            @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, row=0)
            async def b2(self, interaction, button): await self._move(interaction, 1)
            @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, row=0)
            async def b3(self, interaction, button): await self._move(interaction, 2)
            @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, row=1)
            async def b4(self, interaction, button): await self._move(interaction, 3)
            @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, row=1)
            async def b5(self, interaction, button): await self._move(interaction, 4)
            @discord.ui.button(label="6", style=discord.ButtonStyle.secondary, row=1)
            async def b6(self, interaction, button): await self._move(interaction, 5)
            @discord.ui.button(label="7", style=discord.ButtonStyle.secondary, row=2)
            async def b7(self, interaction, button): await self._move(interaction, 6)
            @discord.ui.button(label="8", style=discord.ButtonStyle.secondary, row=2)
            async def b8(self, interaction, button): await self._move(interaction, 7)
            @discord.ui.button(label="9", style=discord.ButtonStyle.secondary, row=2)
            async def b9(self, interaction, button): await self._move(interaction, 8)

            async def _move(self, interaction, pos):
                cur = players[current_idx[0]]
                if interaction.user != cur:
                    return await interaction.response.send_message("Not your turn!", ephemeral=True)
                if board[pos] != "\u20e3":
                    return await interaction.response.send_message("That spot is taken!", ephemeral=True)
                mark = player_marks[interaction.user.id]
                board[pos] = mark
                for a, b, c in wins:
                    if board[a] == board[b] == board[c] == mark:
                        embed = discord.Embed(title="\u274c\u2b55 Game Over", description=f"{render_board()}\n\n{cur.mention} **wins!** \U0001f389", color=0x57F287)
                        for child in self.children:
                            child.disabled = True
                        return await interaction.response.edit_message(embed=embed, view=self)
                if all(b != "\u20e3" for b in board):
                    embed = discord.Embed(title="\u274c\u2b55 Game Over", description=f"{render_board()}\n\n**It\u2019s a draw!** \U0001f91d", color=0xFEE75C)
                    for child in self.children:
                        child.disabled = True
                    return await interaction.response.edit_message(embed=embed, view=self)
                current_idx[0] = 1 - current_idx[0]
                nxt = players[current_idx[0]]
                embed = discord.Embed(title="\u274c\u2b55 Tic Tac Toe", description=f"**{player_marks[nxt.id]}** {nxt.mention}\u2019s turn\n\n{render_board()}", color=0x5865F2)
                await interaction.response.edit_message(embed=embed, view=self)

        board_view = BoardView()
        cur = players[0]
        embed = discord.Embed(title="\u274c\u2b55 Tic Tac Toe", description=f"**{player_marks[cur.id]}** {cur.mention}\u2019s turn\n\n{render_board()}", color=0x5865F2)
        await ctx.send(embed=embed, view=board_view)

    # ── Hot XO ─────────────────────────────────────────────────────
    @commands.hybrid_command(name="hotxo", description="Hot or Cold XO — react to the right tile!")
    async def hotxo(self, ctx: commands.Context):
        board = ["⬜"] * 9
        hot_pos = random.randint(0, 8)
        board[hot_pos] = "🔥"

        embed = discord.Embed(
            title="🔥 Hot XO",
            description=f"Find the **fire** in the grid!\n\n{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}\n\nReact with 1️⃣-9️⃣ to guess!",
            color=0xED4245
        )
        msg = await ctx.send(embed=embed)
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        for e in emojis:
            await msg.add_reaction(e)

        tried = set()
        for _ in range(3):
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in emojis and str(reaction.emoji) not in tried
            try:
                reaction, _ = await self.bot.wait_for("reaction_add", check=check, timeout=30)
            except asyncio.TimeoutError:
                board[hot_pos] = "✅"
                return await msg.edit(embed=discord.Embed(title="🔥 Hot XO — Time's Up!", description=f"The fire was at position **{hot_pos+1}**!\n\n{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}", color=0xFEE75C))

            idx = emojis.index(str(reaction.emoji))
            tried.add(str(reaction.emoji))

            if idx == hot_pos:
                board[idx] = "✅"
                return await msg.edit(embed=discord.Embed(title="🔥 Hot XO — You Found It!", description=f"**{ctx.author.mention}** found the fire! 🎉\n\n{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}", color=0x57F287))
            else:
                board[idx] = "❄️"

            await msg.edit(embed=discord.Embed(
                title="🔥 Hot XO",
                description=f"{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}\n\n**{3 - len(tried)}** guesses left!",
                color=0xED4245
            ))

        board[hot_pos] = "✅"
        await msg.edit(embed=discord.Embed(title="🔥 Hot XO — Game Over!", description=f"The fire was at position **{hot_pos+1}**!\n\n{board[0]} {board[1]} {board[2]}\n{board[3]} {board[4]} {board[5]}\n{board[6]} {board[7]} {board[8]}", color=0xED4245))

    # Death Wheel (Fizbo-style interactive)
    @commands.hybrid_command(name="deathwheel", description="Interactive death wheel \u2014 join, spin, survive!")
    async def deathwheel(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 20

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Join the game",
                "2\u20e3 The wheel spins and eliminates someone",
                "3\u20e3 Last player standing wins!",
                "",
                f"**Players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                lines.append(f"{i}\u20e3 {p.mention}")
            lines.append("")
            lines.append(f"The game will start in **15 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            return discord.Embed(title="\U0001f480 Death Wheel", description="\n".join(lines), color=0xED4245)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=20)
                self.game_started = False

            @discord.ui.button(label="Join Wheel", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave Wheel", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You\u2019re not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can\u2019t leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(15)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < 2:
            return await msg.edit(embed=discord.Embed(title="Death Wheel", description="Not enough players! Need at least 2.", color=0xED4245), view=view)

        # Spin animation
        remaining = players.copy()
        while len(remaining) > 1:
            random.shuffle(remaining)
            spin_embed = discord.Embed(
                title="\U0001f480 Death Wheel",
                description=f"**{len(remaining)}** players remaining...\n\nSpinning...\n\n" + " \u2022 ".join(p.mention for p in remaining),
                color=0xED4245
            )
            await msg.edit(embed=spin_embed)
            await asyncio.sleep(2)
            eliminated = remaining.pop(random.randint(0, len(remaining) - 1))
            result_embed = discord.Embed(
                title="\U0001f480 Death Wheel",
                description=f"**{eliminated.mention}** has been eliminated! \U0001f480\n\n**{len(remaining)}** players remaining...",
                color=0xED4245
            )
            await msg.edit(embed=result_embed)
            await asyncio.sleep(2)

        winner = remaining[0]
        win_embed = discord.Embed(
            title="\U0001f480 Death Wheel \u2014 Winner!",
            description=f"**{winner.mention}** is the last one standing! \U0001f3c6",
            color=0x57F287
        )
    # ── Chairs (Fizbo-style interactive) ────────────────────────────
    @commands.hybrid_command(name="chairs", description="Interactive musical chairs \u2014 join, grab a chair, survive!")
    async def chairs(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 20

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Join the game",
                "2\u20e3 When music stops, grab a chair!",
                "3\u20e3 Last player without a chair is out!",
                "",
                f"**Players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                lines.append(f"{i}\u20e3 {p.mention}")
            lines.append("")
            lines.append(f"The game will start in **15 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            return discord.Embed(title="\U0001fa91 Musical Chairs", description="\n".join(lines), color=0x5865F2)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=20)
                self.game_started = False

            @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave Game", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You're not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can't leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(15)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < 3:
            return await msg.edit(embed=discord.Embed(title="Musical Chairs", description="Not enough players! Need at least 3.", color=0xED4245), view=view)

        # Game loop
        remaining = players.copy()
        eliminated = []
        round_num = 1

        while len(remaining) > 1:
            chairs_count = len(remaining) - 1

            # Show round info
            round_embed = discord.Embed(
                title="\U0001fa91 Musical Chairs \u2014 Round " + str(round_num),
                description=f"**{chairs_count}** chairs for **{len(remaining)}** players\n\n" + " ".join(["\U0001fa91"] * min(chairs_count, 10)) + "\n\n**Grab a chair when the music stops!**",
                color=0x5865F2
            )
            await msg.edit(embed=round_embed)

            # "Music playing" phase
            await asyncio.sleep(random.randint(3, 8))

            # Grab chair phase with button
            class ChairView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=10)
                    self.grabbed = []

                @discord.ui.button(label="Grab Chair!", style=discord.ButtonStyle.success, emoji="\U0001fa91")
                async def grab_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user not in remaining:
                        return await interaction.response.send_message("You're not in the game!", ephemeral=True)
                    if interaction.user.id in self.grabbed:
                        return await interaction.response.send_message("You already grabbed a chair!", ephemeral=True)
                    if len(self.grabbed) >= chairs_count:
                        return await interaction.response.send_message("No more chairs!", ephemeral=True)
                    self.grabbed.append(interaction.user.id)
                    await interaction.response.send_message(f"\u2705 **{interaction.user.display_name}** grabbed a chair!", ephemeral=True)

                async def on_timeout(self):
                    for child in self.children:
                        child.disabled = True

            chair_view = ChairView()
            stop_embed = discord.Embed(
                title="\U0001fa91 Musical Chairs \u2014 GRAB!",
                description=f"**{chairs_count}** chairs available!\n\n**CLICK THE BUTTON TO GRAB A CHAIR!**\n\nTime remaining: **10 seconds**",
                color=0xED4245
            )
            await msg.edit(embed=stop_embed, view=chair_view)
            await asyncio.sleep(10)

            # Find losers
            safe = set(chair_view.grabbed[:chairs_count])
            losers = [p for p in remaining if p.id not in safe]

            if losers:
                loser = random.choice(losers)
                eliminated.append(loser)
                remaining.remove(loser)

                result_embed = discord.Embed(
                    title="\U0001fa91 Musical Chairs",
                    description=f"**{loser.mention}** didn't grab a chair in time! \U0001f480\n\nEliminated: {', '.join(e.mention for e in eliminated)}\n\n**{len(remaining)}** players remaining!",
                    color=0xED4245
                )
                await msg.edit(embed=result_embed, view=None)
                await asyncio.sleep(2)
            else:
                # Everyone got a chair
                safe_embed = discord.Embed(
                    title="\U0001fa91 Musical Chairs",
                    description=f"Everyone grabbed a chair! \u2705\n\n**{len(remaining)}** players remaining!",
                    color=0x57F287
                )
                await msg.edit(embed=safe_embed, view=None)
                await asyncio.sleep(2)

            round_num += 1

        # Winner
        winner = remaining[0]
        win_embed = discord.Embed(
            title="\U0001fa91 Musical Chairs \u2014 Winner!",
            description=f"**{winner.mention}** is the last one standing! \U0001f3c6\n\nEliminated: {', '.join(e.mention for e in eliminated)}",
            color=0x57F287
        )
        await ctx.send(embed=win_embed)

    # ── Hide and Seek ──────────────────────────────────────────────
    @commands.hybrid_command(name="hideandseek", description="Hide in a channel — others have to find you!")
    async def hideandseek(self, ctx: commands.Context):
        channels = [ch for ch in ctx.guild.text_channels if ch != ctx.channel and ch.permissions_for(ctx.guild.me).send_messages]
        if not channels:
            return await ctx.send(embed=error("Error", "No other channels to hide in!"))

        hiding_spot = random.choice(channels)
        embed = discord.Embed(title="🫣 Hide and Seek", description=f"{ctx.author.mention} is hiding!\n\nUse `$find @user` in a channel to find them!\nYou have **60 seconds**!", color=0x5865F2)
        await ctx.send(embed=embed)

        found = False
        start = asyncio.get_event_loop().time()

        def check(m):
            return m.content.lower().startswith("$find") and m.author != ctx.author

        while not found and asyncio.get_event_loop().time() - start < 60:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=10)
                if hiding_spot.id == msg.channel.id:
                    found = True
                    embed = discord.Embed(title="🫣 Found!", description=f"**{msg.author.mention}** found **{ctx.author.mention}** in {hiding_spot.mention}! 🎉", color=0x57F287)
                    return await ctx.send(embed=embed)
                else:
                    await msg.reply(f"❌ **{ctx.author.display_name}** is not here!", delete_after=3)
            except asyncio.TimeoutError:
                pass

        if not found:
            embed = discord.Embed(title="🫣 Time's Up!", description=f"Nobody found **{ctx.author.mention}**! They were hiding in {hiding_spot.mention}!", color=0xFEE75C)
            await ctx.send(embed=embed)

    # ── Replica ────────────────────────────────────────────────────
    @commands.hybrid_command(name="replica", description="Type the same emoji chain as fast as you can!")
    async def replica(self, ctx: commands.Context):
        emojis_list = ["🔴", "🔵", "🟢", "🟡", "🟣", "🟠", "⚫", "⚪", "🟤"]
        chain = "".join(random.choice(emojis_list) for _ in range(random.randint(5, 10)))

        embed = discord.Embed(title="🧩 Replica", description=f"Type this chain as fast as you can:\n\n**{chain}**\n\nGo!", color=0x5865F2)
        await ctx.send(embed=embed)
        start = asyncio.get_event_loop().time()

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", "Too slow!"))

        elapsed = round(asyncio.get_event_loop().time() - start, 2)
        if msg.content.strip() == chain:
            embed = success("✅ Perfect Replica!", f"Speed: **{elapsed}s** 🏆\nAccuracy: **100%**")
        else:
            correct = sum(1 for a, b in zip(msg.content.strip(), chain) if a == b)
            accuracy = round(correct / len(chain) * 100)
            embed = error("❌ Wrong!", f"Speed: **{elapsed}s**\nAccuracy: **{accuracy}%**\nExpected: {chain}\nGot: {msg.content[:30]}")
        await ctx.send(embed=embed)

    # ── Guess the Country ──────────────────────────────────────────
    @commands.hybrid_command(name="guesscountry", description="Guess the country from the flag!")
    async def guesscountry(self, ctx: commands.Context):
        countries = {
            "🇺🇸": "United States", "🇬🇧": "United Kingdom", "🇫🇷": "France", "🇩🇪": "Germany",
            "🇮🇳": "India", "🇯🇵": "Japan", "🇧🇷": "Brazil", "🇦🇺": "Australia",
            "🇨🇦": "Canada", "🇮🇹": "Italy", "🇪🇸": "Spain", "🇲🇽": "Mexico",
            "🇷🇺": "Russia", "🇨🇳": "China", "🇰🇷": "South Korea", "🇳🇬": "Nigeria",
            "🇿🇦": "South Africa", "🇦🇷": "Argentina", "🇹🇷": "Turkey", "🇸🇦": "Saudi Arabia",
            "🇪🇬": "Egypt", "🇹🇭": "Thailand", "🇻🇳": "Vietnam", "🇮🇩": "Indonesia",
            "🇵🇰": "Pakistan", "🇧🇩": "Bangladesh", "🇵🇭": "Philippines", "🇲🇾": "Malaysia",
            "🇸🇬": "Singapore", "🇳🇿": "New Zealand", "🇸🇪": "Sweden", "🇳🇴": "Norway",
            "🇫🇮": "Finland", "🇩🇰": "Denmark", "🇳🇱": "Netherlands", "🇧🇪": "Belgium",
            "🇨🇭": "Switzerland", "🇦🇹": "Austria", "🇵🇱": "Poland", "🇺🇦": "Ukraine",
            "🇬🇷": "Greece", "🇵🇹": "Portugal", "🇮🇪": "Ireland", "🇮🇸": "Iceland",
            "🇨🇴": "Colombia", "🇨🇱": "Chile", "🇵🇪": "Peru", "🇪🇨": "Ecuador",
        }

        flag, country = random.choice(list(countries.items()))
        # Scramble the options
        options = [country]
        while len(options) < 4:
            pick = random.choice(list(countries.values()))
            if pick not in options:
                options.append(pick)
        random.shuffle(options)

        option_letters = ["A", "B", "C", "D"]
        desc = ""
        for i, opt in enumerate(options):
            desc += f"**{option_letters[i]}.** {opt}\n"

        embed = discord.Embed(title=f"🌍 Guess the Country", description=f"What country does this flag belong to?\n\n{flag}\n\n{desc}", color=0x5865F2)
        embed.set_footer(text="Type A, B, C, or D!")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.upper().strip() in ["A", "B", "C", "D"]

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The answer was **{country}**!"))

        chosen = options[option_letters.index(msg.content.upper().strip())]
        if chosen == country:
            await ctx.send(embed=success("🎉 Correct!", f"{flag} **{country}** — you know your flags! 🏆"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The answer was {flag} **{country}**. You chose: {chosen}"))

    # Mafia (Fizbo-style interactive)
    @commands.hybrid_command(name="mafia", description="Interactive mafia \u2014 join, vote, survive!")
    async def mafia(self, ctx: commands.Context):
        players = [ctx.author]
        max_players = 10
        min_players = 4

        def build_embed():
            lines = [
                "**How to play:**",
                "1\u20e3 Join the game",
                "2\u20e3 Mafia are assigned secretly via DM",
                "3\u20e3 Vote to eliminate suspects",
                "4\u20e3 Mafia tries to eliminate civilians",
                "5\u20e3 Last team standing wins!",
                "",
                f"**Players: ({len(players)}/{max_players})**",
            ]
            for i, p in enumerate(players, 1):
                lines.append(f"{i}\u20e3 {p.mention}")
            lines.append("")
            lines.append(f"The game will start in **15 seconds** \u2022 Today at {ctx.created_at.strftime('%H:%M')}")
            return discord.Embed(title="\U0001f3ad Mafia", description="\n".join(lines), color=0xED4245)

        class JoinView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=20)
                self.game_started = False

            @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="\U0001f3ae")
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user in players:
                    return await interaction.response.send_message("You already joined!", ephemeral=True)
                if len(players) >= max_players:
                    return await interaction.response.send_message("Game is full!", ephemeral=True)
                players.append(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            @discord.ui.button(label="Leave Game", style=discord.ButtonStyle.danger, emoji="\U0001f6ab")
            async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.game_started:
                    return await interaction.response.send_message("Game already started!", ephemeral=True)
                if interaction.user not in players:
                    return await interaction.response.send_message("You\u2019re not in the game!", ephemeral=True)
                if interaction.user == ctx.author:
                    return await interaction.response.send_message("You can\u2019t leave your own game!", ephemeral=True)
                players.remove(interaction.user)
                await interaction.response.edit_message(embed=build_embed(), view=self)

            async def on_timeout(self):
                self.game_started = True
                for child in self.children:
                    child.disabled = True

        view = JoinView()
        msg = await ctx.send(embed=build_embed(), view=view)
        await asyncio.sleep(15)
        view.game_started = True
        for child in view.children:
            child.disabled = True
        if len(players) < min_players:
            return await msg.edit(embed=discord.Embed(title="Mafia", description=f"Need at least {min_players} players!", color=0xED4245), view=view)

        # Assign roles
        num_mafia = max(1, len(players) // 3)
        shuffled = players.copy()
        random.shuffle(shuffled)
        mafia_players = set(p.id for p in shuffled[:num_mafia])
        civilian_players = set(p.id for p in shuffled[num_mafia:])

        # DM roles
        for p in shuffled[:num_mafia]:
            try:
                await p.send(embed=discord.Embed(title="\U0001f3ad Mafia Game", description="Your role: **\U0001f52a Mafia**\n\nYou are a **mafia**! Try to eliminate civilians without getting caught.", color=0xED4245))
            except discord.Forbidden:
                pass
        for p in shuffled[num_mafia:]:
            try:
                await p.send(embed=discord.Embed(title="\U0001f3ad Mafia Game", description="Your role: **\U0001f464 Civilian**\n\nYou are a **civilian**! Vote wisely to eliminate suspects.", color=0x57F287))
            except discord.Forbidden:
                pass

        # Game loop
        alive = set(p.id for p in players)
        round_num = 1

        while len(alive) > 2:
            # Night phase - mafia kills
            mafia_alive = [p for p in players if p.id in alive and p.id in mafia_players]
            civilian_alive = [p for p in players if p.id in alive and p.id in civilian_players]

            if not mafia_alive:
                break  # Civilians win
            if not civilian_alive:
                break  # Mafia wins

            # Mafia vote
            night_embed = discord.Embed(
                title=f"\U0001f3ad Mafia \u2014 Round {round_num}",
                description="**Night phase:** Mafia are selecting a target...\n\nThis will take 30 seconds.",
                color=0x2F3136
            )
            await ctx.send(embed=night_embed)
            await asyncio.sleep(30)

            # Kill a random civilian
            victim = random.choice(civilian_alive)
            alive.discard(victim.id)
            await ctx.send(embed=discord.Embed(
                title="\U0001f480 Night Results",
                description=f"**{victim.mention}** was found dead this morning... \U0001f480",
                color=0xED4245
            ))

            # Check win
            mafia_alive = [p for p in players if p.id in alive and p.id in mafia_players]
            civilian_alive = [p for p in players if p.id in alive and p.id in civilian_players]
            if len(mafia_alive) >= len(civilian_alive):
                await ctx.send(embed=discord.Embed(title="\U0001f3ad Mafia \u2014 Game Over", description="**Mafia wins!** \U0001f52a\nThe mafia have overtaken the town!", color=0xED4245))
                return
            if not mafia_alive:
                await ctx.send(embed=discord.Embed(title="\U0001f3ad Mafia \u2014 Game Over", description="**Civilians win!** \U0001f389\nThe mafia have been eliminated!", color=0x57F287))
                return

            # Day phase - vote
            alive_players = [p for p in players if p.id in alive]
            votes = {}
            vote_embed = discord.Embed(
                title=f"\U0001f3ad Mafia \u2014 Round {round_num} (Day)",
                description=f"**{len(alive)}** players remaining\n\nVote to eliminate a suspect! Type `$vote @user`",
                color=0xFEE75C
            )
            await ctx.send(embed=vote_embed)

            # Wait for votes
            def check(m):
                return m.author.id in alive and m.content.lower().startswith("$vote") and m.guild

            for _ in range(60):
                try:
                    msg2 = await self.bot.wait_for("message", check=check, timeout=10)
                    parts = msg2.content.split()
                    if len(parts) >= 2:
                        # Parse vote target
                        target = None
                        if msg2.mentions:
                            target = msg2.mentions[0]
                        else:
                            try:
                                target_id = int(parts[1].replace("<@", "").replace(">", ""))
                                target = ctx.guild.get_member(target_id)
                            except ValueError:
                                pass
                        if target and target.id in alive:
                            votes[msg2.author.id] = target.id
                            await ctx.send(f"{msg2.author.mention} voted for {target.mention}", delete_after=3)
                except:
                    pass

            # Count votes
            if votes:
                vote_counts = {}
                for voter, target in votes.items():
                    vote_counts[target] = vote_counts.get(target, 0) + 1
                eliminated_id = max(vote_counts, key=vote_counts.get)
                eliminated = ctx.guild.get_member(eliminated_id)
                alive.discard(eliminated_id)
                await ctx.send(embed=discord.Embed(
                    title=f"\U0001f3ad Round {round_num} Results",
                    description=f"**{eliminated.mention}** was voted out! ({vote_counts[eliminated_id]} votes)\n\nThey were a **{'mafia' if eliminated_id in mafia_players else 'civilian'}**!",
                    color=0xFEE75C
                ))
            else:
                await ctx.send(embed=discord.Embed(title=f"Round {round_num}", description="No votes! No one was eliminated.", color=0xFEE75C))

            round_num += 1

        # Game end
        if len([p for p in players if p.id in alive and p.id in mafia_players]) > 0:
            await ctx.send(embed=discord.Embed(title="\U0001f3ad Mafia \u2014 Game Over", description="**Mafia wins!** \U0001f52a", color=0xED4245))
        else:
            await ctx.send(embed=discord.Embed(title="\U0001f3ad Mafia \u2014 Game Over", description="**Civilians win!** \U0001f389", color=0x57F287))

    @commands.hybrid_command(name="wyr", aliases=["wouldyourather"], description="Would you rather?")
    async def wyr(self, ctx: commands.Context):
        questions = [
            ("Be able to fly 🦅", "Be invisible 👻"),
            ("Live without music 🎵", "Live without movies 🎬"),
            ("Have unlimited money 💰", "Have unlimited time ⏰"),
            ("Read minds 🧠", "See the future 🔮"),
            ("Have super strength 💪", "Have super speed ⚡"),
            ("Live in Harry Potter world 🧙", "Live in Star Wars universe 🚀"),
            ("Be a pirate 🏴‍☠️", "Be an astronaut 🧑‍🚀"),
            ("Fight 1 horse-sized duck 🦆", "Fight 100 duck-sized horses 🐴"),
            ("Have a time machine ⏰", "Have a teleportation device 🌀"),
            ("Never use WiFi 📶", "Never play games 🎮"),
        ]
        q = random.choice(questions)

        embed = discord.Embed(title="🤔 Would You Rather?", color=0x5865F2)
        embed.add_field(name="Option A", value=q[0], inline=True)
        embed.add_field(name="Option B", value=q[1], inline=True)
        embed.set_footer(text="React with 1️⃣ for A or 2️⃣ for B!")

        msg = await ctx.send(embed=embed)
        await msg.add_reaction("1️⃣")
        await msg.add_reaction("2️⃣")


    # ══════════════════════════════════════════════════════════════
    # QUICK GAMES
    # ══════════════════════════════════════════════════════════════

    # ── Fast Click ─────────────────────────────────────────────────
    @commands.hybrid_command(name="fastclick", description="Click the reaction as fast as you can!")
    async def fastclick(self, ctx: commands.Context):
        delay = random.uniform(3, 8)
        embed = discord.Embed(title="⚡ Fast Click", description="Get ready... ⏳", color=0xFEE75C)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(delay)
        embed = discord.Embed(title="⚡ Fast Click", description="**CLICK ⚡ NOW!**", color=0x57F287)
        await msg.edit(embed=embed)
        await msg.add_reaction("⚡")
        start = asyncio.get_event_loop().time()

        def check(reaction, user):
            return str(reaction.emoji) == "⚡" and user == ctx.author
        try:
            await self.bot.wait_for("reaction_add", check=check, timeout=5)
            elapsed = round((asyncio.get_event_loop().time() - start) * 1000)
            embed = success("⚡ Fast Click", f"Reaction time: **{elapsed}ms** 🏆")
            await msg.edit(embed=embed)
        except asyncio.TimeoutError:
            await msg.edit(embed=error("⏱️ Too Slow!", "You didn't click in time!"))

    # ── Fast Type ──────────────────────────────────────────────────
    @commands.hybrid_command(name="fasttype", description="Type the word as fast as you can!")
    async def fasttype(self, ctx: commands.Context):
        words = ["python", "discord", "banana", "castle", "rocket", "shadow", "wizard", "jungle", "galaxy", "legend", "phantom", "mystic", "adventure", "thunder", "lightning"]
        word = random.choice(words)
        embed = info("⌨️ Fast Type", f"Type this word as fast as you can:\n\n**{word}**\n\nGO!")
        await ctx.send(embed=embed)
        start = asyncio.get_event_loop().time()

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", "Too slow!"))

        elapsed = round(asyncio.get_event_loop().time() - start, 2)
        if msg.content.strip().lower() == word:
            await ctx.send(embed=success("✅ Correct!", f"Speed: **{elapsed}s** 🏆\nWord: **{word}**"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"Speed: **{elapsed}s**\nYou typed: `{msg.content[:30]}`\nWord: **{word}**"))

    # ── Text Split ─────────────────────────────────────────────────
    @commands.hybrid_command(name="textsplit", description="Put the letters back in order!")
    async def textsplit(self, ctx: commands.Context):
        words = ["python", "discord", "rocket", "galaxy", "legend", "shadow", "wizard", "jungle", "thunder", "phantom"]
        word = random.choice(words)
        letters = list(word)
        random.shuffle(letters)
        scrambled = " ".join(letters).upper()

        embed = info("🔤 Text Split", f"""Put these letters back in order:

**{scrambled}**\n\nType the word!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The word was **{word.upper()}**!"))

        if msg.content.lower().strip() == word:
            await ctx.send(embed=success("✅ Correct!", f"The word was **{word.upper()}**! 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The word was **{word.upper()}**!"))

    # ── Text Merge ─────────────────────────────────────────────────
    @commands.hybrid_command(name="textmerge", description="Merge the words back into a sentence!")
    async def textmerge(self, ctx: commands.Context):
        sentences = [
            "the cat sat on the mat", "i love discord bot", "python is awesome",
            "have a great day", "the sky is blue today", "lets play a game",
            "this is so much fun", "i am a coding genius", "the bot is very fast",
            "we love playing games"
        ]
        sentence = random.choice(sentences)
        words = sentence.split()
        random.shuffle(words)
        merged = " | ".join(words)

        embed = info("🔀 Text Merge", f"""Unmerge these words into a sentence:

**{merged}**\n\nType the sentence!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The sentence was: **{sentence}**"))

        if msg.content.lower().strip() == sentence:
            await ctx.send(embed=success("✅ Correct!", f"**{sentence}** 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The sentence was: **{sentence}**"))

    # ── Text Reverse ───────────────────────────────────────────────
    @commands.hybrid_command(name="textreverse", description="Reverse the text!")
    async def textreverse(self, ctx: commands.Context):
        words = ["python", "discord", "rocket", "galaxy", "shadow", "wizard", "thunder", "phantom", "legend", "mystic"]
        word = random.choice(words)
        reversed_word = word[::-1]

        embed = info("🔄 Text Reverse", f"""Reverse this word:

**{reversed_word}**\n\nType the original word!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The word was **{word}**!"))

        if msg.content.lower().strip() == word:
            await ctx.send(embed=success("✅ Correct!", f"**{word}** → **{reversed_word}** 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The word was **{word}**!"))

    # ── Find Letter ────────────────────────────────────────────────
    @commands.hybrid_command(name="findletter", description="Find the hidden letter!")
    async def findletter(self, ctx: commands.Context):
        letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        hidden = random.choice(letters)
        blank = "⬜" * 26
        positions = list(range(26))
        random.shuffle(positions)
        hidden_pos = positions[0]

        display = list(blank)
        display[hidden_pos] = "❓"

        embed = info("🔍 Find Letter", f"""Which letter is hidden?

**{" ".join(display)}**\n\nType a letter A-Z!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content.strip()) == 1
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The letter was **{hidden}** at position **{hidden_pos+1}**!"))

        if msg.content.upper().strip() == hidden:
            await ctx.send(embed=success("✅ Found It!", f"The letter was **{hidden}**! 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The letter was **{hidden}**!"))

    # ── Correct Letter ─────────────────────────────────────────────
    @commands.hybrid_command(name="correctletter", description="Fix the scrambled word!")
    async def correctletter(self, ctx: commands.Context):
        words = ["python", "discord", "rocket", "galaxy", "shadow", "wizard", "thunder", "phantom", "legend", "mystic", "adventure", "lightning"]
        word = random.choice(words)
        letters = list(word)
        # Swap a few letters
        for _ in range(max(2, len(word) // 3)):
            i, j = random.sample(range(len(letters)), 2)
            letters[i], letters[j] = letters[j], letters[i]
        scrambled = "".join(letters)

        embed = info("✏️ Correct Letter", f"""Fix this scrambled word:

**{scrambled.upper()}**\n\nType the correct word!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The word was **{word}**!"))

        if msg.content.lower().strip() == word:
            await ctx.send(embed=success("✅ Correct!", f"**{scrambled}** → **{word}** 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The word was **{word}**!"))

    # ── Sort Numbers ───────────────────────────────────────────────
    @commands.hybrid_command(name="sortnumbers", description="Sort the numbers fast!")
    async def sortnumbers(self, ctx: commands.Context):
        count = random.randint(5, 8)
        numbers = random.sample(range(1, 50), count)
        correct = ", ".join(str(n) for n in sorted(numbers))
        scrambled = ", ".join(str(n) for n in numbers)

        embed = info("🔢 Sort Numbers", f"""Sort these numbers from smallest to largest:

**{scrambled}**\n\nType the sorted numbers (comma separated)!""")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The answer was: **{correct}**"))

        user_answer = msg.content.strip().replace(" ", "")
        if user_answer == correct.replace(" ", ""):
            await ctx.send(embed=success("✅ Correct!", f"**{correct}** 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The answer was: **{correct}**"))

    # ── Guess Color ────────────────────────────────────────────────
    @commands.hybrid_command(name="guesscolor", description="Guess the color!")
    async def guesscolor(self, ctx: commands.Context):
        colors = {
            "🔴": "red", "🔵": "blue", "🟢": "green", "🟡": "yellow",
            "🟣": "purple", "🟠": "orange", "⚫": "black", "⚪": "white",
            "🟤": "brown", "🩷": "pink", "🩵": "light blue", "💚": "lime",
        }
        emoji, color_name = random.choice(list(colors.items()))
        options = [color_name]
        while len(options) < 4:
            pick = random.choice(list(colors.values()))
            if pick not in options:
                options.append(pick)
        random.shuffle(options)

        letters = ["A", "B", "C", "D"]
        desc = ""
        for i, opt in enumerate(options):
            desc += f"**{letters[i]}.** {opt}\n"

        embed = discord.Embed(title="🎨 Guess the Color", description=f"""What color is this?

{emoji}\n
{desc}""", color=0x5865F2)
        embed.set_footer(text="Type A, B, C, or D!")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.upper().strip() in ["A", "B", "C", "D"]
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The answer was **{color_name}**!"))

        chosen = options[letters.index(msg.content.upper().strip())]
        if chosen == color_name:
            await ctx.send(embed=success("✅ Correct!", f"The color was **{color_name}**! {emoji} 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The answer was **{color_name}** {emoji}. You chose: {chosen}"))

    # ── Flag ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="flag", description="Guess the country from the flag!")
    async def flag(self, ctx: commands.Context):
        countries = {
            "🇺🇸": "United States", "🇬🇧": "United Kingdom", "🇫🇷": "France", "🇩🇪": "Germany",
            "🇮🇳": "India", "🇯🇵": "Japan", "🇧🇷": "Brazil", "🇦🇺": "Australia",
            "🇨🇦": "Canada", "🇮🇹": "Italy", "🇪🇸": "Spain", "🇲🇽": "Mexico",
            "🇷🇺": "Russia", "🇨🇳": "China", "🇰🇷": "South Korea", "🇳🇬": "Nigeria",
            "🇿🇦": "South Africa", "🇦🇷": "Argentina", "🇹🇷": "Turkey", "🇸🇦": "Saudi Arabia",
            "🇪🇬": "Egypt", "🇹🇭": "Thailand", "🇻🇳": "Vietnam", "🇮🇩": "Indonesia",
            "🇵🇰": "Pakistan", "🇧🇩": "Bangladesh", "🇵🇭": "Philippines", "🇲🇾": "Malaysia",
            "🇸🇬": "Singapore", "🇳🇿": "New Zealand", "🇸🇪": "Sweden", "🇳🇴": "Norway",
            "🇫🇮": "Finland", "🇩🇰": "Denmark", "🇳🇱": "Netherlands", "🇧🇪": "Belgium",
            "🇨🇭": "Switzerland", "🇦🇹": "Austria", "🇵🇱": "Poland", "🇺🇦": "Ukraine",
            "🇬🇷": "Greece", "🇵🇹": "Portugal", "🇮🇪": "Ireland", "🇮🇸": "Iceland",
        }
        flag_emoji, country = random.choice(list(countries.items()))
        options = [country]
        while len(options) < 4:
            pick = random.choice(list(countries.values()))
            if pick not in options:
                options.append(pick)
        random.shuffle(options)

        letters = ["A", "B", "C", "D"]
        desc_lines = []
        for i, opt in enumerate(options):
            desc_lines.append(f"**{letters[i]}.** {opt}")
        desc = "\n".join(desc_lines)

        embed = discord.Embed(
            title="🏁 Flag",
            description=f"What country does this flag belong to?\n\n{flag_emoji}\n\n{desc}",
            color=0x5865F2
        )
        embed.set_footer(text="Type A, B, C, or D!")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.upper().strip() in ["A", "B", "C", "D"]
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The answer was **{country}**!"))

        chosen = options[letters.index(msg.content.upper().strip())]
        if chosen == country:
            await ctx.send(embed=success("🎉 Correct!", f"{flag_emoji} **{country}** — you know your flags!"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The answer was {flag_emoji} **{country}**. You chose: {chosen}"))

    # ── Emoji ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="emoji", description="Guess what the emoji combo means!")
    async def emoji(self, ctx: commands.Context):
        combos = [
            ("🍕🍔🌮", "food", ["fast food", "snacks", "dessert"]),
            ("⚽🏀🏈", "sports", ["games", "hobbies", "fitness"]),
            ("🎬🎵🎨", "arts", ["music", "sports", "science"]),
            ("🌍🌎🌏", "earth", ["space", "planets", "weather"]),
            ("🐱🐶🐰", "pets", ["animals", "zoo", "farm"]),
            ("💻📱⌨️", "tech", ["office", "gaming", "school"]),
            ("✈️🚗🚂", "travel", ["transport", "vacation", "commute"]),
            ("🌙⭐☀️", "sky", ["weather", "time", "space"]),
            ("🎄🎃🎃", "holidays", ["birthday", "party", "celebration"]),
            ("💎👑🏆", "winning", ["wealth", "royalty", "treasure"]),
        ]
        emoji_str, answer, wrong_options = random.choice(combos)
        options = [answer] + wrong_options[:3]
        random.shuffle(options)

        letters = ["A", "B", "C", "D"]
        desc = ""
        for i, opt in enumerate(options):
            desc += f"**{letters[i]}.** {opt}\n"

        embed = discord.Embed(title="😀 Emoji", description=f"""What do these emojis represent?

{emoji_str}

{desc}""", color=0x5865F2)
        embed.set_footer(text="Type A, B, C, or D!")
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.upper().strip() in ["A", "B", "C", "D"]
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warning("⏱️ Time's Up", f"The answer was **{answer}**!"))

        chosen = options[letters.index(msg.content.upper().strip())]
        if chosen == answer:
            await ctx.send(embed=success("✅ Correct!", f"**{emoji_str}** = **{answer}** 🎉"))
        else:
            await ctx.send(embed=error("❌ Wrong!", f"The answer was **{answer}**. You chose: {chosen}"))

    # ── Reveal ─────────────────────────────────────────────────────
    @commands.hybrid_command(name="reveal", description="Guess the hidden word before time runs out!")
    async def reveal(self, ctx: commands.Context):
        words = ["python", "discord", "rocket", "galaxy", "shadow", "wizard", "thunder", "phantom", "legend", "mystic", "adventure", "lightning", "treasure", "mystery"]
        word = random.choice(words)
        revealed = ["_"] * len(word)

        embed = discord.Embed(
            title="🔮 Reveal",
            description=f"Guess the word!\n\n**{" ".join(revealed)}** ({len(word)} letters)\n\nType a letter!",
            color=0x5865F2
        )
        msg = await ctx.send(embed=embed)

        guessed = set()
        lives = 6

        for _ in range(lives):
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and len(m.content.strip()) == 1 and m.content.isalpha()
            try:
                msg2 = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await msg.edit(embed=warning("⏱️ Time's Up", f"The word was **{word}**!"))

            letter = msg2.content.lower().strip()
            if letter in guessed:
                await ctx.send(f"You already guessed **{letter}**!", delete_after=3)
                continue
            guessed.add(letter)

            if letter in word:
                for i, c in enumerate(word):
                    if c == letter:
                        revealed[i] = letter
                status = "✅"
            else:
                lives -= 1
                status = "❌"

            display = " ".join(revealed)
            hearts = "❤️" * lives + "🖤" * (6 - lives)

            if "_" not in revealed:
                return await msg.edit(embed=success("🎉 You Won!", f"The word was **{word}**!\n{hearts}"))

            embed = discord.Embed(
                title="🔮 Reveal",
                description=f"{status} Guessed: **{letter}**\n\n**{display}** ({len(word)} letters)\n\nLives: {hearts}\nGuessed: {', '.join(sorted(guessed))}",
                color=0x5865F2 if lives > 2 else 0xED4245
            )
            await msg.edit(embed=embed)

        await msg.edit(embed=error("💀 Game Over", f"The word was **{word}**!"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))

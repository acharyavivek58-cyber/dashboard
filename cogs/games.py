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
            raise commands.CommandError('No permission')

    # ── Roulette ───────────────────────────────────────────────────
    @commands.hybrid_command(name="roulette", description="Spin the wheel of fate — will you survive?")
    async def roulette(self, ctx: commands.Context):
        alive = random.randint(1, 6)
        if alive == 1:
            embed = discord.Embed(title="🔫 Roulette", description=f"**BANG!** 💀\n{ctx.author.mention} didn't make it...", color=0xED4245)
        else:
            embed = discord.Embed(title="🔫 Roulette", description=f"*click*\n{ctx.author.mention} survived! 😮‍💨 ({alive-1}/5 shots left)", color=0x57F287)
        await ctx.send(embed=embed)

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

    # ── Rock Paper Scissors ────────────────────────────────────────
    @commands.hybrid_command(name="rps", description="Play Rock Paper Scissors")
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(self, ctx: commands.Context, choice: str):
        choice = choice.lower().strip()
        if choice not in ["rock", "paper", "scissors", "r", "p", "s"]:
            return await ctx.send(embed=error("Error", "Pick `rock`, `paper`, or `scissors`!"))
        if choice in ["r"]: choice = "rock"
        elif choice in ["p"]: choice = "paper"
        elif choice in ["s"]: choice = "scissors"

        bot_choice = random.choice(["rock", "paper", "scissors"])
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if choice == bot_choice:
            result, color = "It's a **tie**! 🤝", 0xFEE75C
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result, color = "You **win**! 🎉", 0x57F287
        else:
            result, color = "You **lose**! 💀", 0xED4245

        embed = discord.Embed(title="🪨📄✂️ Rock Paper Scissors", color=color)
        embed.add_field(name="You", value=f"{emojis[choice]} {choice.title()}", inline=True)
        embed.add_field(name="Bot", value=f"{emojis[bot_choice]} {bot_choice.title()}", inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        await ctx.send(embed=embed)

    # ── XO (Tic Tac Toe) ──────────────────────────────────────────
    @commands.hybrid_command(name="xo", description="Play Tic Tac Toe against someone")
    @app_commands.describe(opponent="Who do you want to play against?")
    async def xo(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.bot:
            return await ctx.send(embed=error("Error", "You can't play against a bot!"))
        if opponent == ctx.author:
            return await ctx.send(embed=error("Error", "You can't play against yourself!"))

        board = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        players = {ctx.author.id: "❌", opponent.id: "⭕"}
        current = ctx.author.id

        def render(b):
            return f"{b[0]} {b[1]} {b[2]}\n{b[3]} {b[4]} {b[5]}\n{b[6]} {b[7]} {b[8]}"

        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

        embed = discord.Embed(
            title="❌⭕ Tic Tac Toe",
            description=f"{ctx.author.mention} (❌) vs {opponent.mention} (⭕)\n\n{render(board)}",
            color=0x5865F2
        )
        msg = await ctx.send(embed=embed)

        for i in range(9):
            # Add reactions
            for e in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]:
                if e in board:
                    await msg.add_reaction(e)

            def check(reaction, user):
                return user.id == current and str(reaction.emoji) in board

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", check=check, timeout=60)
            except asyncio.TimeoutError:
                return await ctx.send(embed=warning("⏱️ Game Over", "No move in 60s — game cancelled."))

            idx = board.index(str(reaction.emoji))
            board[idx] = players[current]

            # Check win
            for a, b, c in wins:
                if board[a] == board[b] == board[c]:
                    winner = ctx.author if current == ctx.author.id else opponent
                    embed = discord.Embed(
                        title="❌⭕ Game Over",
                        description=f"{winner.mention} **wins!** 🎉\n\n{render(board)}",
                        color=0x57F287
                    )
                    return await msg.edit(embed=embed)

            # Check draw
            if all(x in ["❌", "⭕"] for x in board):
                embed = discord.Embed(title="❌⭕ Game Over", description=f"**It's a draw!** 🤝\n\n{render(board)}", color=0xFEE75C)
                return await msg.edit(embed=embed)

            current = opponent.id if current == ctx.author.id else ctx.author.id
            embed = discord.Embed(
                title="❌⭕ Tic Tac Toe",
                description=f"**{players[current]}**'s turn\n\n{render(board)}",
                color=0x5865F2
            )
            await msg.edit(embed=embed)

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

    # ── Death Wheel ────────────────────────────────────────────────
    @commands.hybrid_command(name="deathwheel", description="Spin the death wheel — who survives?")
    async def deathwheel(self, ctx: commands.Context):
        members = [m.mention for m in ctx.channel.members if not m.bot and m.status != discord.Status.offline]
        if len(members) < 2:
            return await ctx.send(embed=error("Error", "Need at least 2 people in the channel!"))

        embed = discord.Embed(title="💀 Death Wheel", description=f"**{len(members)}** victims...\n\nSpinning...", color=0xED4245)
        msg = await ctx.send(embed=embed)

        for _ in range(5):
            random.shuffle(members)
            embed.description = f"**{len(members)}** victims...\n\n🎲 {', '.join(members[:5])}..."
            await msg.edit(embed=embed)
            await asyncio.sleep(1)

        victim = random.choice(members)
        embed = discord.Embed(title="💀 Death Wheel", description=f"**{victim}** has been eliminated! 💀", color=0xED4245)
        await msg.edit(embed=embed)

    # ── Chairs ─────────────────────────────────────────────────────
    @commands.hybrid_command(name="chairs", description="Musical chairs — last one standing loses!")
    async def chairs(self, ctx: commands.Context):
        members = [m for m in ctx.channel.members if not m.bot and m.status != discord.Status.offline]
        if len(members) < 3:
            return await ctx.send(embed=error("Error", "Need at least 3 people!"))

        embed = discord.Embed(title="🪑 Musical Chairs", description=f"**{len(members)}** players — **{len(members)-1}** chairs\n\nWhen I say GO, react with 🪑 fastest!", color=0x5865F2)
        await ctx.send(embed=embed)
        await asyncio.sleep(3)

        eliminated = []
        while len(members) > 1:
            chairs_count = len(members) - 1
            embed = discord.Embed(title="🪑 Musical Chairs", description=f"**{chairs_count}** chairs for **{len(members)}** players\n\n🪑🪑" * min(chairs_count, 5) + f"\n\nReact with 🪑 NOW!", color=0xED4245)
            msg = await ctx.send(embed=embed)
            await msg.add_reaction("🪑")

            reactors = set()
            def check(reaction, user):
                return str(reaction.emoji) == "🪑" and user in members and user.id not in reactors
            start = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start < 5:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=5 - (asyncio.get_event_loop().time() - start))
                    reactors.add(user.id)
                except asyncio.TimeoutError:
                    break

            safe = list(reactors)[:chairs_count]
            losers = [m for m in members if m.id not in safe]

            if losers:
                loser = random.choice(losers)
                eliminated.append(loser)
                members.remove(loser)
                embed = discord.Embed(title="🪑 Musical Chairs", description=f"**{loser.mention}** is OUT! 💀\n\nEliminated: {', '.join(e.mention for e in eliminated)}\n\n**{len(members)}** players left!", color=0xED4245)
                await ctx.send(embed=embed)
                await asyncio.sleep(2)

        winner = members[0]
        embed = discord.Embed(title="🪑 Musical Chairs — Winner!", description=f"**{winner.mention}** is the last one standing! 🏆🎉", color=0x57F287)
        await ctx.send(embed=embed)

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

    # ── Mafia ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="mafia", description="Start a mini mafia game (3-10 players)")
    async def mafia(self, ctx: commands.Context):
        members = [m for m in ctx.channel.members if not m.bot and m.status != discord.Status.offline]
        if len(members) < 3:
            return await ctx.send(embed=error("Error", "Need at least 3 players!"))
        if len(members) > 10:
            members = members[:10]

        # Assign roles
        num_mafia = max(1, len(members) // 3)
        shuffled = members.copy()
        random.shuffle(shuffled)

        roles = {}
        for m in shuffled[:num_mafia]:
            roles[m.id] = "🔪 Mafia"
        for m in shuffled[num_mafia:]:
            roles[m.id] = "👤 Civilian"

        # DM roles
        for m in members:
            try:
                await m.send(embed=info("🎭 Mafia Game", f"Your role: **{roles[m.id]}**\n\nGame starts in chat!"))
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="🎭 Mafia Game Started!",
            description=f"**{len(members)}** players | **{num_mafia}** mafia\n\nRoles have been sent via DM!\n\n**Gameplay:**\n• Mafia tries to eliminate civilians\n• Civilians vote to eliminate suspects\n• Type `$vote @user` to vote\n• Most votes = eliminated!",
            color=0xED4245
        )
        await ctx.send(embed=embed)

    # ── Would You Rather ───────────────────────────────────────────
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

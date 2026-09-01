import discord
from discord.ext import commands
import asyncio
import utils

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


# ── YT-DLP options ──────────────────────────────────────────────────
YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class Song:
    """Represents a single song in the queue."""

    def __init__(self, url, title, duration, requester, webpage_url=None, thumbnail=None):
        self.url = url
        self.title = title
        self.duration = duration
        self.requester = requester
        self.webpage_url = webpage_url or url
        self.thumbnail = thumbnail

    def format_duration(self):
        if not self.duration or self.duration == "Live":
            return "🔴 Live"
        try:
            total = int(self.duration)
            mins, secs = divmod(total, 60)
            hours, mins = divmod(mins, 60)
            if hours:
                return f"{hours}:{mins:02d}:{secs:02d}"
            return f"{mins}:{secs:02d}"
        except (ValueError, TypeError):
            return "??:??"


class MusicPlayer:
    """Per-guild music state."""

    def __init__(self):
        self.queue = []
        self.current = None
        self.playing = False
        self.paused = False
        self.volume = 0.5
        self.loop = False
        self.vc = None


class Music(commands.Cog):
    """Music commands — play, queue, skip, and more."""

    def __init__(self, bot):
        self.bot = bot
        self.players = {}  # guild_id -> MusicPlayer

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer()
        return self.players[guild_id]

    # ── Helpers ──────────────────────────────────────────────────────

    async def search_youtube(self, query):
        """Search YouTube and return (url, title, duration, webpage_url, thumbnail)."""
        if not yt_dlp:
            return None

        loop = asyncio.get_event_loop()

        def _search():
            opts = {**YDL_OPTS, "default_search": "ytsearch1"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if "entries" in info:
                    info = info["entries"][0]
                return info

        try:
            info = await loop.run_in_executor(None, _search)
            url = info.get("url") or info.get("webpage_url")
            if not info.get("url") and info.get("webpage_url"):
                # Need to extract actual stream URL
                def _extract():
                    opts = {**YDL_OPTS}
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        full = ydl.extract_info(info["webpage_url"], download=False)
                        if "entries" in full:
                            full = full["entries"][0]
                        return full
                info2 = await loop.run_in_executor(None, _extract)
                url = info2.get("url")

            return (
                url,
                info.get("title", "Unknown"),
                info.get("duration"),
                info.get("webpage_url", url),
                info.get("thumbnail"),
            )
        except Exception as e:
            print(f"[Music] Search error: {e}")
            return None

    async def play_next(self, guild_id):
        """Play the next song in queue or stop."""
        player = self.get_player(guild_id)

        if player.loop and player.current:
            # Re-queue current song
            player.queue.append(player.current)

        if not player.queue:
            player.current = None
            player.playing = False
            # Auto-disconnect after 60s idle
            await asyncio.sleep(60)
            if not player.playing and player.vc and player.vc.is_connected():
                try:
                    await player.vc.disconnect()
                except:
                    pass
            return

        song = player.queue.pop(0)
        player.current = song
        player.playing = True
        player.paused = False

        if not player.vc or not player.vc.is_connected():
            return

        def _after_playing(error):
            if error:
                print(f"[Music] Player error: {error}")
            coro = self.play_next(guild_id)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        try:
            source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTS)
            source = discord.PCMVolumeTransformer(source, volume=player.volume)
            player.vc.play(source, after=_after_playing)
        except Exception as e:
            print(f"[Music] Play error: {e}")
            await self.play_next(guild_id)

    # ── Commands ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="join", description="Join your voice channel")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def join(self, ctx):
        """Join your voice channel."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=utils.error("Not in Voice", "Join a voice channel first!"))
            return

        channel = ctx.author.voice.channel
        player = self.get_player(ctx.guild.id)

        if player.vc and player.vc.is_connected():
            await player.vc.move_to(channel)
        else:
            player.vc = await channel.connect(self_deaf=True)

        await ctx.send(embed=utils.success("Joined", f"Joined **{channel.name}** 🎵"))

    @commands.hybrid_command(name="leave", description="Leave voice channel")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def leave(self, ctx):
        """Leave voice channel and clear queue."""
        player = self.get_player(ctx.guild.id)

        if not player.vc or not player.vc.is_connected():
            await ctx.send(embed=utils.error("Not Connected", "I'm not in a voice channel!"))
            return

        player.queue.clear()
        player.current = None
        player.playing = False
        player.paused = False
        player.vc.stop()
        await player.vc.disconnect()
        player.vc = None

        await ctx.send(embed=utils.success("Disconnected", "Left the voice channel. 👋"))

    @commands.hybrid_command(name="play", description="Play a song from YouTube")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def play(self, ctx, *, query: str):
        """Play a song. Use a URL or search term."""
        if not yt_dlp:
            await ctx.send(embed=utils.error("Missing Dependency", "`yt-dlp` is not installed."))
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=utils.error("Not in Voice", "Join a voice channel first!"))
            return

        player = self.get_player(ctx.guild.id)

        # Join channel if not connected
        if not player.vc or not player.vc.is_connected():
            player.vc = await ctx.author.voice.channel.connect(self_deaf=True)

        # Search YouTube
        async with ctx.typing():
            result = await self.search_youtube(query)

        if not result:
            await ctx.send(embed=utils.error("Not Found", f"Couldn't find: **{query}**"))
            return

        url, title, duration, webpage_url, thumbnail = result
        song = Song(url, title, duration, ctx.author, webpage_url, thumbnail)

        if player.playing and player.current:
            player.queue.append(song)
            embed = utils.info(
                "Added to Queue",
                f"**{title}** ({song.format_duration()})\n"
                f"Position: #{len(player.queue)}"
            )
            embed.set_thumbnail(url=thumbnail or "")
            await ctx.send(embed=embed)
        else:
            player.queue.append(song)
            await self.play_next(ctx.guild.id)
            embed = utils.success("Now Playing", f"**{title}** ({song.format_duration()})")
            embed.set_thumbnail(url=thumbnail or "")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", description="Pause the current song")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pause(self, ctx):
        """Pause playback."""
        player = self.get_player(ctx.guild.id)
        if player.vc and player.vc.is_paused():
            await ctx.send(embed=utils.warning("Already Paused", "Music is already paused."))
            return
        if player.vc and player.playing:
            player.vc.pause()
            player.paused = True
            await ctx.send(embed=utils.info("Paused", "⏸️ Paused the current song."))
        else:
            await ctx.send(embed=utils.error("Nothing Playing", "Nothing to pause."))

    @commands.hybrid_command(name="resume", description="Resume paused music")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def resume(self, ctx):
        """Resume paused music."""
        player = self.get_player(ctx.guild.id)
        if player.vc and player.vc.is_paused():
            player.vc.resume()
            player.paused = False
            await ctx.send(embed=utils.success("Resumed", "▶️ Resumed playback."))
        else:
            await ctx.send(embed=utils.error("Not Paused", "Music isn't paused right now."))

    @commands.hybrid_command(name="skip", description="Skip the current song")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def skip(self, ctx):
        """Skip the current song."""
        player = self.get_player(ctx.guild.id)
        if player.vc and player.playing:
            player.vc.stop()  # triggers after -> play_next
            await ctx.send(embed=utils.info("Skipped", "⏭️ Skipped the current song."))
        else:
            await ctx.send(embed=utils.error("Nothing Playing", "Nothing to skip."))

    @commands.hybrid_command(name="stop", description="Stop music and clear queue")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def stop(self, ctx):
        """Stop music and clear the queue."""
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        player.current = None
        player.playing = False
        player.paused = False
        if player.vc and player.vc.is_playing():
            player.vc.stop()
        await ctx.send(embed=utils.success("Stopped", "⏹️ Stopped music and cleared queue."))

    @commands.hybrid_command(name="queue", description="Show the music queue")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def queue(self, ctx):
        """Display the current music queue."""
        player = self.get_player(ctx.guild.id)

        if not player.current and not player.queue:
            await ctx.send(embed=utils.info("Empty Queue", "The queue is empty. Use `$play` to add songs!"))
            return

        embed = discord.Embed(title="🎵 Music Queue", color=0x5865F2)

        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"**{player.current.title}** ({player.current.format_duration()})\n"
                      f"Requested by {player.current.requester.mention}",
                inline=False
            )

        if player.queue:
            lines = []
            for i, song in enumerate(player.queue[:10], 1):
                lines.append(f"`{i}.` **{song.title}** ({song.format_duration()}) — {song.requester.mention}")
            embed.add_field(
                name=f"Up Next ({len(player.queue)} songs)",
                value="\n".join(lines),
                inline=False
            )
            if len(player.queue) > 10:
                embed.set_footer(text=f"...and {len(player.queue) - 10} more songs")

        if player.loop:
            embed.set_footer(text="🔁 Loop is ON")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show what's playing")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def nowplaying(self, ctx):
        """Show the currently playing song."""
        player = self.get_player(ctx.guild.id)

        if not player.current:
            await ctx.send(embed=utils.info("Nothing Playing", "Nothing is playing right now."))
            return

        song = player.current
        status = "⏸️ Paused" if player.paused else "▶️ Playing"

        embed = utils.info(
            "Now Playing",
            f"**{song.title}**\n"
            f"Duration: {song.format_duration()}\n"
            f"Requested by: {song.requester.mention}\n"
            f"Status: {status}"
        )
        embed.set_thumbnail(url=song.thumbnail or "")
        if song.webpage_url:
            embed.url = song.webpage_url
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="volume", description="Set volume (0-100)")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def volume(self, ctx, volume: int = None):
        """Set the playback volume (0-100)."""
        player = self.get_player(ctx.guild.id)

        if volume is None:
            current = int(player.volume * 100)
            await ctx.send(embed=utils.info("Volume", f"Current volume: **{current}%**"))
            return

        if volume < 0 or volume > 100:
            await ctx.send(embed=utils.error("Invalid Volume", "Volume must be 0-100."))
            return

        player.volume = volume / 100
        if player.vc and player.vc.source:
            player.vc.source.volume = player.volume

        await ctx.send(embed=utils.success("Volume", f"Volume set to **{volume}%** 🔊"))

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def shuffle(self, ctx):
        """Shuffle the music queue."""
        import random
        player = self.get_player(ctx.guild.id)

        if not player.queue:
            await ctx.send(embed=utils.error("Empty Queue", "Nothing to shuffle."))
            return

        random.shuffle(player.queue)
        await ctx.send(embed=utils.success("Shuffled", f"🔀 Shuffled **{len(player.queue)}** songs."))

    @commands.hybrid_command(name="loop", description="Toggle loop for current song")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def loop(self, ctx):
        """Toggle loop mode for the current song."""
        player = self.get_player(ctx.guild.id)
        player.loop = not player.loop
        status = "ON 🔁" if player.loop else "OFF 🔂"
        await ctx.send(embed=utils.success("Loop", f"Loop: **{status}**"))

    @commands.hybrid_command(name="removesong", description="Remove a song from queue by position")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def remove(self, ctx, position: int):
        """Remove a song from queue by its position number."""
        player = self.get_player(ctx.guild.id)

        if position < 1 or position > len(player.queue):
            await ctx.send(embed=utils.error("Invalid Position", f"Queue has {len(player.queue)} songs."))
            return

        removed = player.queue.pop(position - 1)
        await ctx.send(embed=utils.success("Removed", f"Removed **{removed.title}** from queue."))

    @commands.hybrid_command(name="clear", description="Clear the entire queue")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clear(self, ctx):
        """Clear the entire music queue."""
        player = self.get_player(ctx.guild.id)
        count = len(player.queue)
        player.queue.clear()
        await ctx.send(embed=utils.success("Cleared", f"Cleared **{count}** songs from queue. 🗑️"))


async def setup(bot):
    await bot.add_cog(Music(bot))

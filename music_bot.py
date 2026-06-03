import discord
import os
import yt_dlp as youtube_dl
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )

        # Music storage
        self.queues = {}
        self.current_song = None

        # YouTube DL options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'noplaylist': True,  # Don't extract playlists, just single videos
            'nocheckcertificate': True,  # Bypass SSL certificate checks
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',  # Fake browser user agent
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'web'],  # Try multiple clients
                }
            }
        }

        # FFmpeg options
        self.ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        # FFmpeg executable path (bundled with project)
        ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg-8.1.1-essentials_build', 'bin', 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            self.ffmpeg_opts['executable'] = ffmpeg_path

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def _search_youtube_sync(self, query):
        """Synchronous wrapper for YouTube search (runs in thread)"""
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            # Check if query is a YouTube URL
            is_url = query.startswith('http') and ('youtube.com' in query or 'youtu.be' in query)

            if is_url:
                # Direct URL - extract info directly
                info = ydl.extract_info(query, download=False)
                if info:
                    # Use webpage_url for the YouTube URL (what we need for playback)
                    youtube_url = info.get('webpage_url') or query
                    return {
                        'title': info.get('title', 'Unknown'),
                        'url': youtube_url,
                        'duration': info.get('duration', 0)
                    }
            else:
                # Search term - use ytsearch
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    result = info['entries'][0]
                    # Use webpage_url for the YouTube URL
                    youtube_url = result.get('webpage_url') or result.get('url')
                    return {
                        'title': result['title'],
                        'url': youtube_url,
                        'duration': result.get('duration', 0)
                    }
        return None

    async def search_youtube(self, query):
        """Async wrapper that runs YouTube search in a thread"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._search_youtube_sync, query)
        except Exception as e:
            print(f"Search error: {e}")
            return None

    def _get_audio_url_sync(self, song):
        """Synchronous wrapper for getting audio URL (runs in thread)"""
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(song['url'], download=False)
            return info['url']

    async def play_song(self, ctx, song):
        try:
            # Run the blocking yt-dlp operation in a thread
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(None, self._get_audio_url_sync, song)

            voice_client = ctx.voice_client
            if voice_client.is_playing():
                voice_client.stop()

            player = discord.FFmpegPCMAudio(url, **self.ffmpeg_opts)
            voice_client.play(player, after=lambda e: self.play_next(ctx))

            await ctx.send(f"Now playing: {song['title']}")

        except Exception as e:
            print(f"Play error: {e}")
            await ctx.send(f"Error playing song: {e}")
            self.play_next(ctx)

    def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if queue:
            next_song = queue.pop(0)
            asyncio.run_coroutine_threadsafe(self.play_song(ctx, next_song), self.loop)

    def format_time(self, seconds):
        if seconds:
            mins, secs = divmod(int(seconds), 60)
            return f"{mins:02d}:{secs:02d}"
        return "00:00"

# Create bot instance
bot = MusicBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Servers: {len(bot.guilds)}')
    print('Commands: !play, !skip, !queue, !stop, !join, !leave')

@bot.command()
async def test(ctx):
    """Test if bot is working"""
    await ctx.send("Bot is working! Try !join")

@bot.command()
async def join(ctx):
    """Join voice channel"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("Join a voice channel first!")

@bot.command()
async def leave(ctx):
    """Leave voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left voice channel")

@bot.command()
async def play(ctx, *, search):
    """Play music from YouTube"""
    # Auto-join if not in voice channel
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send(f"Joined {channel.name}")
        else:
            await ctx.send("You need to be in a voice channel first!")
            return

    song = await bot.search_youtube(search)
    if not song:
        await ctx.send("Song not found")
        return

    queue = bot.get_queue(ctx.guild.id)

    if not ctx.voice_client.is_playing():
        # Nothing playing - play immediately, don't add to queue
        await bot.play_song(ctx, song)
    else:
        # Something playing - add to queue
        queue.append(song)
        await ctx.send(f"Added to queue: {song['title']}")

@bot.command()
async def skip(ctx):
    """Skip current song"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped")

@bot.command()
async def queue(ctx):
    """Show music queue"""
    queue = bot.get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("Queue is empty")
        return

    songs = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(queue)])
    await ctx.send(f"Queue:\n{songs}")

@bot.command()
async def stop(ctx):
    """Stop music and clear queue"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    bot.get_queue(ctx.guild.id).clear()
    await ctx.send("Stopped and queue cleared")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("No DISCORD_TOKEN found in .env")
    else:
        bot.run(token)
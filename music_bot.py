import discord
import os
import yt_dlp as youtube_dl
import asyncio
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
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
            'format': 'best',  # Best quality available
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'noplaylist': True,  # Don't extract playlists, just single videos
        }

        # FFmpeg options
        self.ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -err_detect ignore_err',
            'options': '-vn -b:a 128k -ar 48000 -bufsize 256k'
        }

        # FFmpeg executable path (bundled with project)
        ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg-8.1.1-essentials_build', 'bin', 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            self.ffmpeg_opts['executable'] = ffmpeg_path

        # Spotify client
        try:
            spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
            spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

            if spotify_client_id and spotify_client_secret:
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret
                )
                self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            else:
                self.spotify = None
        except Exception as e:
            print(f"Spotify initialization error: {e}")
            self.spotify = None

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def _extract_from_spotify(self, url):
        """Extract track info from Spotify URL"""
        if not self.spotify:
            return None

        try:
            # Extract track/playlist/album ID from URL
            track_match = re.search(r'track/([a-zA-Z0-9]+)', url)
            playlist_match = re.search(r'playlist/([a-zA-Z0-9]+)', url)
            album_match = re.search(r'album/([a-zA-Z0-9]+)', url)

            if track_match:
                # Single track
                track_id = track_match.group(1)
                track = self.spotify.track(track_id)
                artist_name = track['artists'][0]['name']
                track_name = track['name']
                duration_ms = track['duration_ms']
                # Better search query with keywords
                search_query = f"{track_name} {artist_name} official audio"
                return [{
                    'query': search_query,
                    'title': track_name,
                    'artist': artist_name,
                    'duration_ms': duration_ms
                }]

            elif playlist_match:
                # Playlist
                playlist_id = playlist_match.group(1)
                playlist = self.spotify.playlist(playlist_id)
                tracks = []
                for item in playlist['tracks']['items']:
                    track = item['track']
                    if track:
                        artist_name = track['artists'][0]['name']
                        track_name = track['name']
                        duration_ms = track['duration_ms']
                        search_query = f"{track_name} {artist_name} official audio"
                        tracks.append({
                            'query': search_query,
                            'title': track_name,
                            'artist': artist_name,
                            'duration_ms': duration_ms
                        })
                return tracks

            elif album_match:
                # Album
                album_id = album_match.group(1)
                album = self.spotify.album(album_id)
                tracks = []
                for track in album['tracks']['items']:
                    artist_name = track['artists'][0]['name']
                    track_name = track['name']
                    duration_ms = track['duration_ms']
                    search_query = f"{track_name} {artist_name} official audio"
                    tracks.append({
                        'query': search_query,
                        'title': track_name,
                        'artist': artist_name,
                        'duration_ms': duration_ms
                    })
                return tracks

        except Exception as e:
            print(f"Spotify extraction error: {e}")

        return None

    def _search_youtube_sync(self, query, duration_ms=None):
        """Synchronous wrapper for YouTube search (runs in thread)"""
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            # Check if query is a YouTube URL
            is_url = query.startswith('http') and ('youtube.com' in query or 'youtu.be' in query)

            if is_url:
                # Direct URL - extract info directly
                info = ydl.extract_info(query, download=False)
                if info:
                    youtube_url = info.get('webpage_url') or query
                    return {
                        'title': info.get('title', 'Unknown'),
                        'url': youtube_url,
                        'duration': info.get('duration', 0)
                    }
            else:
                # Search term - use ytsearch with multiple results
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    # If we have duration info, find the best match
                    if duration_ms:
                        target_duration = duration_ms / 1000  # Convert to seconds
                        best_match = None
                        best_diff = float('inf')

                        for entry in info['entries'][:10]:  # Check top 10 results
                            if entry:
                                entry_duration = entry.get('duration', 0)
                                duration_diff = abs(entry_duration - target_duration)

                                # Prefer results within 10 seconds
                                if duration_diff < 10 and duration_diff < best_diff:
                                    best_match = entry
                                    best_diff = duration_diff

                        # Use best match if found, otherwise use first result
                        result = best_match if best_match else info['entries'][0]
                    else:
                        result = info['entries'][0]

                    youtube_url = result.get('webpage_url') or result.get('url')
                    return {
                        'title': result['title'],
                        'url': youtube_url,
                        'duration': result.get('duration', 0)
                    }
        return None

    async def search_youtube(self, query, duration_ms=None):
        """Async wrapper that runs YouTube search in a thread"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._search_youtube_sync, query, duration_ms)
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
    """Play music from YouTube or Spotify"""
    # Auto-join if not in voice channel
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send(f"Joined {channel.name}")
        else:
            await ctx.send("You need to be in a voice channel first!")
            return

    # Check if it's a Spotify URL
    is_spotify = 'spotify.com' in search

    if is_spotify:
        # Extract tracks from Spotify
        track_infos = bot._extract_from_spotify(search)
        if not track_infos:
            await ctx.send("Could not extract tracks from Spotify. Make sure you've set up Spotify credentials.")
            return

        queue = bot.get_queue(ctx.guild.id)
        found_count = 0
        songs_to_queue = []

        # First, find all songs
        for track_info in track_infos:
            song = await bot.search_youtube(track_info['query'], track_info.get('duration_ms'))
            if song:
                songs_to_queue.append(song)
                found_count += 1

        # Then, handle playback
        if not ctx.voice_client.is_playing() and songs_to_queue:
            # Play first song immediately
            first_song = songs_to_queue.pop(0)
            await bot.play_song(ctx, first_song)

        # Add remaining songs to queue
        for song in songs_to_queue:
            queue.append(song)

        queued_count = len(songs_to_queue)

        if found_count == 0:
            await ctx.send("Could not find any songs from Spotify on YouTube")
        elif found_count == 1 and queued_count == 0:
            await ctx.send(f"Now playing: {first_song['title']}")
        else:
            await ctx.send(f"Found {found_count} song(s)! {queued_count} added to queue.")
    else:
        # Regular YouTube search
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
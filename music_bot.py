import discord
import os
import yt_dlp as youtube_dl
import asyncio
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
from dotenv import load_dotenv
from lyricsgenius import Genius

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
        self.search_results = {}  # Store search results per guild
        self.song_history = {}  # Store recently played songs per server (max 20 per server)
        self.is_paused = {}  # Store pause state per server

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

        # Genius client for lyrics
        try:
            genius_token = os.getenv('GENIUS_ACCESS_TOKEN')
            if genius_token:
                self.genius = Genius(genius_token)
                self.genius.remove_section_headers = True  # Clean up lyrics
            else:
                self.genius = None
        except Exception as e:
            print(f"Genius initialization error: {e}")
            self.genius = None

    async def setup_hook(self):
        """Sync slash commands with Discord on startup"""
        try:
            print("Syncing slash commands...")
            await self.tree.sync()
            print("Slash commands synced!")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    def add_to_history(self, guild_id, song):
        """Add song to play history (max 20 per server)"""
        if guild_id not in self.song_history:
            self.song_history[guild_id] = []

        # Add song if not already in recent history
        song_title = song.get('title', '')
        if song_title:
            # Remove if already exists (to move to top)
            self.song_history[guild_id] = [s for s in self.song_history[guild_id] if s.get('title') != song_title]

            # Add to beginning
            self.song_history[guild_id].insert(0, song)

            # Keep only last 20
            if len(self.song_history[guild_id]) > 20:
                self.song_history[guild_id] = self.song_history[guild_id][:20]

    def get_history(self, guild_id):
        """Get play history for a server"""
        if guild_id not in self.song_history:
            self.song_history[guild_id] = []
        return self.song_history[guild_id]

    async def send_auto_delete_message(self, ctx, content, delete_after=30):
        """Send a message that will be automatically deleted after specified seconds"""
        message = await ctx.send(content)
        # Schedule deletion
        asyncio.create_task(self._delete_message_later(message, delete_after))
        return message

    async def send_auto_delete_followup(self, interaction, content, delete_after=30):
        """Send a followup message that will be automatically deleted"""
        message = await interaction.followup.send(content)
        # Schedule deletion
        asyncio.create_task(self._delete_message_later(message, delete_after))
        return message

    async def _delete_message_later(self, message, delay):
        """Delete a message after a delay"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass  # Message might already be deleted

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

    def _search_multiple_results_sync(self, query, duration_ms=None):
        """Search for multiple results (runs in thread)"""
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            # Search term - get multiple results
            info = ydl.extract_info(f"ytsearch:{query}", download=False)

            if 'entries' in info and len(info['entries']) > 0:
                results = []
                for entry in info['entries'][:5]:  # Get top 5 results
                    if entry:
                        youtube_url = entry.get('webpage_url') or entry.get('url')
                        results.append({
                            'title': entry['title'],
                            'url': youtube_url,
                            'duration': entry.get('duration', 0)
                        })
                return results
        return None

    async def search_multiple_results(self, query, duration_ms=None):
        """Async wrapper for multiple results search"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._search_multiple_results_sync, query, duration_ms)
        except Exception as e:
            print(f"Search error: {e}")
            return None

    def format_time(self, seconds):
        if seconds:
            mins, secs = divmod(int(seconds), 60)
            return f"{mins:02d}:{secs:02d}"
        return "00:00"

    def _get_audio_url_sync(self, song):
        """Synchronous wrapper for getting audio URL (runs in thread)"""
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(song['url'], download=False)
            return info['url']

    async def play_song(self, ctx, song):
        try:
            # Add to history when song starts playing
            self.add_to_history(ctx.guild.id, song)

            # Run the blocking yt-dlp operation in a thread
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(None, self._get_audio_url_sync, song)

            voice_client = ctx.voice_client
            if voice_client.is_playing():
                voice_client.stop()

            player = discord.FFmpegPCMAudio(url, **self.ffmpeg_opts)
            voice_client.play(player, after=lambda e: self.play_next(ctx))

            await bot.send_auto_delete_message(ctx, f"Now playing: {song['title']}", delete_after=30)

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

# Select Menu for Song Selection
class SongSelect(Select):
    def __init__(self, results, bot_instance, ctx):
        self.results = results
        self.bot = bot_instance
        self.ctx = ctx

        options = []
        for i, result in enumerate(results[:5]):  # Top 5 results
            duration = bot_instance.format_time(result['duration'])
            label = f"{result['title'][:80]}..." if len(result['title']) > 80 else result['title']
            options.append(discord.SelectOption(
                label=label,
                value=str(i),
                description=f"Duration: {duration}"
            ))

        super().__init__(
            placeholder="Choose a song to play...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        selected_index = int(self.values[0])
        selected = self.results[selected_index]

        # Auto-join if not in voice channel
        if not self.ctx.voice_client:
            if self.ctx.author.voice:
                channel = self.ctx.author.voice.channel
                await channel.connect()
            else:
                await interaction.followup.send("You need to be in a voice channel first!")
                return

        queue = self.bot.get_queue(self.ctx.guild.id)

        if not self.ctx.voice_client.is_playing():
            # Play immediately
            await self.bot.play_song(self.ctx, selected)
            self.bot.add_to_history(self.ctx.guild.id, selected)  # Add to history
            await self.bot.send_auto_delete_followup(interaction, f"Now playing: {selected['title']}", delete_after=30)
        else:
            # Add to queue
            queue.append(selected)
            self.bot.add_to_history(self.ctx.guild.id, selected)  # Add to history
            await self.bot.send_auto_delete_followup(interaction, f"Added to queue: {selected['title']}", delete_after=20)

class SongSelectView(View):
    def __init__(self, results, bot_instance, ctx):
        super().__init__(timeout=60)  # 60 second timeout
        self.add_item(SongSelect(results, bot_instance, ctx))

# Create bot instance
bot = MusicBot()

# Autocomplete function for /play command
async def play_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice]:
    """Autocomplete handler for /play command - shows recent songs"""
    if not interaction.guild:
        return []

    guild_id = interaction.guild.id
    history = bot.get_history(guild_id)

    if not history:
        return []

    # Filter songs by what user is typing
    current_lower = current.lower()
    matching = []

    for song in history:
        title = song.get('title', '')
        if current_lower in title.lower():
            # Add to matching results (limit to 25 for Discord)
            matching.append(app_commands.Choice(
                name=title[:80] + "..." if len(title) > 80 else title,
                value=title
            ))

            if len(matching) >= 25:
                break

    return matching

# Slash Command: /play
@bot.tree.command(name="play", description="Play music from YouTube or Spotify")
@app_commands.describe(query="Song name or URL to play")
@app_commands.autocomplete(query=play_autocomplete)
async def play_slash(interaction: discord.Interaction, query: str):
    """Play music with dropdown selection"""

    # Defer the response (searching takes time)
    await interaction.response.defer(thinking=True)

    # Check if it's a URL
    is_spotify = 'spotify.com' in query
    is_youtube = query.startswith('http') and ('youtube.com' in query or 'youtu.be' in query)

    try:
        if is_spotify:
            # Handle Spotify
            track_infos = bot._extract_from_spotify(query)
            if not track_infos:
                await interaction.followup.send("Could not extract tracks from Spotify. Check your credentials.")
                return

            # Search for first track and show results
            results = []
            for track_info in track_infos[:5]:  # Get up to 5 tracks
                song = await bot.search_youtube(track_info['query'], track_info.get('duration_ms'))
                if song:
                    results.append(song)

            if not results:
                await interaction.followup.send("Could not find songs on YouTube")
                return

        elif is_youtube:
            # Direct YouTube URL - get info
            song = await bot.search_youtube(query)
            if not song:
                await interaction.followup.send("Could not find video")
                return

            # Auto-join and play
            if not interaction.user.voice:
                await interaction.followup.send("You need to be in a voice channel first!")
                return

            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()

            queue = bot.get_queue(interaction.guild.id)

            if not interaction.guild.voice_client.is_playing():
                await bot.play_song(interaction, song)
                bot.add_to_history(interaction.guild.id, song)  # Add to history
                await bot.send_auto_delete_followup(interaction, f"Now playing: {song['title']}", delete_after=30)
            else:
                queue.append(song)
                bot.add_to_history(interaction.guild.id, song)  # Add to history
                await bot.send_auto_delete_followup(interaction, f"Added to queue: {song['title']}", delete_after=20)
            return

        else:
            # Search query - get multiple results
            results = await bot.search_multiple_results(query)
            if not results:
                await interaction.followup.send("No results found")
                return

        # Show dropdown menu
        view = SongSelectView(results, bot, interaction)
        await interaction.followup.send("Choose a song:", view=view)

    except Exception as e:
        print(f"Error in /play: {e}")
        await interaction.followup.send(f"Error: {str(e)}")

@bot.tree.command(name="pause", description="Pause the current song")
async def pause_slash(interaction: discord.Interaction):
    """Pause the currently playing song"""
    if not interaction.guild.voice_client:
        await interaction.response.send_message("Bot is not in a voice channel", ephemeral=True)
        return

    if not interaction.guild.voice_client.is_playing():
        await interaction.response.send_message("Nothing is playing", ephemeral=True)
        return

    voice_client = interaction.guild.voice_client
    voice_client.pause()
    bot.is_paused[interaction.guild.id] = True

    # Send ephemeral message (only visible to user) and delete after 10 seconds
    await interaction.response.send_message("⏸️ Paused the music", ephemeral=True)
    # Schedule deletion of the ephemeral message
    original_message = await interaction.original_response()
    asyncio.create_task(bot._delete_message_later(original_message, 10))

@bot.tree.command(name="resume", description="Resume the paused song")
async def resume_slash(interaction: discord.Interaction):
    """Resume the paused song"""
    if not interaction.guild.voice_client:
        await interaction.response.send_message("Bot is not in a voice channel", ephemeral=True)
        return

    voice_client = interaction.guild.voice_client

    if not voice_client.is_paused():
        await interaction.response.send_message("Music is not paused", ephemeral=True)
        return

    voice_client.resume()
    bot.is_paused[interaction.guild.id] = False

    # Send ephemeral message (only visible to user) and delete after 10 seconds
    await interaction.response.send_message("▶️ Resumed the music", ephemeral=True)
    # Schedule deletion of the ephemeral message
    original_message = await interaction.original_response()
    asyncio.create_task(bot._delete_message_later(original_message, 10))

@bot.tree.command(name="lyrics", description="Show lyrics for the current song")
async def lyrics_slash(interaction: discord.Interaction):
    """Show lyrics for the currently playing song"""
    await interaction.response.defer(thinking=True)

    if not bot.genius:
        await interaction.followup.send("Lyrics feature is not configured. Please add GENIUS_ACCESS_TOKEN to .env")
        return

    # Get current song from history
    history = bot.get_history(interaction.guild.id)
    if not history:
        await interaction.followup.send("No song has been played yet")
        return

    current_song = history[0]  # Most recent song
    song_title = current_song.get('title', 'Unknown')

    try:
        # Search for lyrics on Genius
        song = bot.genius.search_song(song_title, get_lyrics=True)

        if not song:
            await interaction.followup.send(f"Could not find lyrics for: {song_title}")
            return

        lyrics = song.lyrics

        # Clean up and format lyrics
        if not lyrics or len(lyrics) < 50:
            await interaction.followup.send(f"Lyrics not available for: {song_title}")
            return

        # Truncate if too long (Discord message limit is 2000 chars)
        if len(lyrics) > 1900:
            lyrics = lyrics[:1900] + "\n... (truncated)"

        # Create embed for lyrics
        embed = discord.Embed(
            title=f"🎵 {song.title}",
            description=lyrics,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Lyrics provided by Genius.com")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Lyrics error: {e}")
        await interaction.followup.send(f"Error fetching lyrics: {str(e)}")

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
        await bot.send_auto_delete_message(ctx, f"Joined {channel.name}", delete_after=10)
    else:
        await ctx.send("Join a voice channel first!")

@bot.command()
async def leave(ctx):
    """Leave voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await bot.send_auto_delete_message(ctx, "Left voice channel", delete_after=10)
    else:
        await ctx.send("Bot is not in a voice channel")

@bot.command()
async def play(ctx, *, search):
    """Play music from YouTube or Spotify"""
    # Auto-join if not in voice channel
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await bot.send_auto_delete_message(ctx, f"Joined {channel.name}", delete_after=10)
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
            # Handled by play_song which already has auto-delete
            pass
        else:
            await bot.send_auto_delete_message(ctx, f"Found {found_count} song(s)! {queued_count} added to queue.", delete_after=25)
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
            await bot.send_auto_delete_message(ctx, f"Added to queue: {song['title']}", delete_after=20)

@bot.command()
async def skip(ctx):
    """Skip current song"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await bot.send_auto_delete_message(ctx, "Skipped", delete_after=10)

@bot.command()
async def queue(ctx):
    """Show music queue"""
    queue = bot.get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("Queue is empty")
        return

    songs = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(queue)])
    await bot.send_auto_delete_message(ctx, f"Queue:\n{songs}", delete_after=45)

@bot.command()
async def search(ctx, *, query):
    """Search for music and show multiple results"""
    results = await bot.search_multiple_results(query)
    if not results:
        await ctx.send("No results found")
        return

    # Store results for this guild
    bot.search_results[ctx.guild.id] = results

    # Display results
    message = "Search results:\n\n"
    for i, result in enumerate(results):
        duration = bot.format_time(result['duration'])
        message += f"{i+1}. **{result['title']}** ({duration})\n"

    message += "\nUse `!choose <number>` to play a song"
    await ctx.send(message)

@bot.command()
async def choose(ctx, *, choice: int):
    """Choose a song from search results"""
    if ctx.guild.id not in bot.search_results:
        await ctx.send("No search results available. Use `!search <query>` first")
        return

    results = bot.search_results[ctx.guild.id]
    if choice < 1 or choice > len(results):
        await ctx.send(f"Invalid choice. Please choose between 1 and {len(results)}")
        return

    selected = results[choice - 1]

    # Auto-join if not in voice channel
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await bot.send_auto_delete_message(ctx, f"Joined {channel.name}", delete_after=10)
        else:
            await ctx.send("You need to be in a voice channel first!")
            return

    queue = bot.get_queue(ctx.guild.id)

    if not ctx.voice_client.is_playing():
        # Nothing playing - play immediately
        await bot.play_song(ctx, selected)
    else:
        # Something playing - add to queue
        queue.append(selected)
        await ctx.send(f"Added to queue: {selected['title']}")

    # Clear search results after choosing
    del bot.search_results[ctx.guild.id]

@bot.command()
async def stop(ctx):
    """Stop music and clear queue"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    bot.get_queue(ctx.guild.id).clear()
        await bot.send_auto_delete_message(ctx, "Stopped and queue cleared", delete_after=15)
    else:
        await ctx.send("Nothing is playing")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("No DISCORD_TOKEN found in .env")
    else:
        bot.run(token)
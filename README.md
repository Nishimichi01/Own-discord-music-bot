# Discord Music Bot

A simple Discord bot for playing music from YouTube.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Bot Token
Edit `.env` file:
```
DISCORD_TOKEN=your_actual_bot_token_here
```

### 3. Start Bot
Double-click `start.bat` or run:
```bash
python music_bot.py
```

## 🎵 Commands

- `!test` - Test if bot is working
- `!join` - Join your voice channel
- `!leave` - Leave voice channel
- `!play <song>` - Play music from YouTube
- `!skip` - Skip current song
- `!queue` - Show music queue
- `!stop` - Stop and clear queue

## ⚙️ Requirements

- Python 3.6+
- Discord Bot Token (from Discord Developer Portal)
- Message Content Intent enabled in Discord Developer Portal
- FFmpeg (for audio playback)

## 🔧 Troubleshooting

### Bot not responding:
- Check bot is green (online) in Discord
- Ensure Message Content Intent is enabled
- Verify bot has Send Messages permission

### Music not playing:
- Install FFmpeg: https://ffmpeg.org/download.html
- Add FFmpeg to system PATH
- Restart bot

### Can't connect:
- Check internet connection
- Verify bot token is correct
- Make sure bot is invited to server

## 📋 Setup Steps

1. Create bot at Discord Developer Portal
2. Enable Message Content Intent
3. Copy bot token to `.env` file
4. Invite bot to server
5. Start bot with `start.bat`

## 🎮 Usage

1. Start bot (`start.bat`)
2. Join a voice channel in Discord
3. Type `!join`
4. Type `!play never gonna give you up`
5. Enjoy music!

## 🛠️ Technical Details

- Uses discord.py for Discord API
- Uses youtube-dl for music search
- Uses FFmpeg for audio playback
- Supports queue management
- Auto-advance through songs
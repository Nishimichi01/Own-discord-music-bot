# How to Start the Music Bot Properly

## Manual Start Method (Most Reliable)

1. **Open Command Prompt** (search for "cmd" in Windows)
2. **Navigate to bot folder:**
   ```
   cd "C:\Own Project\Discord Bot"
   ```
3. **Start the bot:**
   ```
   python music_bot_nocogs.py
   ```
4. **You should see:**
   ```
   Starting Music Bot (No Cogs Version)...
   Logged in as [YourBotName]
   Bot ID: [numbers]
   --------------------------
   Bot is in [number] guild(s)
   Music commands: !play, !skip, !queue, !stop, !join, !leave
   ```

5. **Keep this window open** - Bot stops when you close it

## What If Bot Doesn't Start?

### Check for Errors:
1. **"Module not found"** - Install dependencies:
   ```
   pip install youtube-dl PyNaCl
   ```

2. **"DISCORD_TOKEN not found"** - Check .env file has your token

3. **"Privileged intents required"** - Enable Message Content Intent in Discord Developer Portal

## Test Commands (Once Bot is Running):

1. **Test bot is working:**
   ```
   !test
   ```

2. **Join voice channel:**
   ```
   !join
   ```

3. **Play music:**
   ```
   !play never gonna give you up
   ```

## Important Notes:

- **Bot must stay running** - Keep the command window open
- **Discord status** - Bot should appear green (online) when running
- **Permissions** - Bot needs "Connect" and "Speak" permissions in voice channels
- **Restart if needed** - If bot stops working, close and restart

## Quick Restart:

1. **Close the command window** (or press Ctrl+C)
2. **Repeat the start process above**

The bot will respond to commands once it shows "Logged in as [YourBotName]" in the console!
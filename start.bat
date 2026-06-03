@echo off
title Discord Music Bot
cls
echo ================================================
echo           DISCORD MUSIC BOT
echo ================================================
echo.
echo Music Commands:
echo - !join / !leave (voice channels)
echo - !play (search term)
echo - !skip / !queue / !stop
echo - !test (test bot)
echo.
echo Press any key to start...
pause >nul
echo.
cd /d "C:\Own_Project\Discord Bot"
echo Starting bot...
echo.
python music_bot.py
echo.
echo Bot stopped.
pause
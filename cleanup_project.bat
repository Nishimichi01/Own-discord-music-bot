@echo off
title Clean Up Project
cls
echo ================================================
echo           CLEAN UP DISCORD BOT PROJECT
echo ================================================
echo.
echo This will delete unnecessary files and keep only:
echo - music_bot.py (main bot)
echo - start.bat (launcher)
echo - README.md (instructions)
echo - requirements.txt (dependencies)
echo - .env (your token)
echo - .gitignore (git settings)
echo.
echo Files to delete (40+ files):
echo - Old bot versions
echo - Test scripts
echo - Debug files
echo - Multiple batch files
echo - Old guides
echo.
echo Press any key to continue...
pause >nul
echo.

cd /d "C:\Own_Project\Discord Bot"

echo Deleting old bot files...
del /Q bot.py 2>nul
del /Q bot_config.py 2>nul
del /Q bot_manager.py 2>nul
del /Q working_bot.py 2>nul
del /Q simple_bot.py 2>nul
del /Q music_bot_simple.py 2>nul
del /Q music_bot_nocogs.py 2>nul

echo Deleting test and debug files...
del /Q test_bot.py 2>nul
del /Q debug_*.py 2>nul
del /Q check_*.py 2>nul
del /Q verify_*.py 2>nul
del /Q find_*.py 2>nul
del /Q generate_*.py 2>nul
del /Q *test*.py 2>nul
del /Q diagnostic.py 2>nul
del /Q minimal_*.py 2>nul
del /Q simple_*.py 2>nul
del /Q connection_test.py 2>nul
del /Q stop_bot_now.py 2>nul
del /Q working_bot_test.py 2>nul
del /Q final_status_check.py 2>nul

echo Deleting old batch files...
del /Q setup*.bat 2>nul
del /Q invite.bat 2>nul
del /Q restart_*.bat 2>nul
del /Q start_*.bat 2>nul
del /Q stop_*.bat 2>nul
del /Q run_*.bat 2>nul

echo Deleting old guide files...
del /Q *_GUIDE.md 2>nul
del /Q *GUIDE.md 2>nul
del /Q manual_invite_guide.md 2>nul

echo Deleting cogs folder...
if exist cogs rmdir /S /Q cogs

echo.
echo ================================================
echo              CLEANUP COMPLETE!
echo ================================================
echo.
echo Project now contains only essential files:
echo - music_bot.py (main bot)
echo - start.bat (launcher)
echo - README.md (instructions)
echo - requirements.txt (dependencies)
echo - .env (your token)
echo - .gitignore (git settings)
echo.
echo You can now start fresh with: start.bat
echo.
pause
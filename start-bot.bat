@echo off
chcp 65001 >nul
title MyFlowMusic - Telegram Bot
color 0B

echo.
echo ==========================================
echo   🤖 MyFlowMusic - Telegram Bot
echo ==========================================
echo.

:: Check if running from correct directory
if not exist "agent.py" (
    echo ❌ ERROR: Please run this file from the project folder!
    echo    Make sure you are in the same folder as agent.py
    pause
    exit /b 1
)

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ⚠️  Virtual environment not found!
    echo    Please run music-agent-first-run.bat first
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

echo ✅ Virtual environment activated
echo.

:: Check .env
if not exist ".env" (
    echo ⚠️  Configuration file ^(.env^) not found!
    echo    Please create .env file from .env.example
    pause
    exit /b 1
)

:: Check if bot token is configured
echo 🔍 Checking bot configuration...
python -c "from music_agent.config import settings; exit(0 if settings.telegram_bot_token else 1)"
if errorlevel 1 (
    echo ❌ ERROR: Telegram Bot Token not configured!
    echo.
    echo    Please add to .env file:
    echo    MUSIC_AGENT_TELEGRAM_BOT_TOKEN=your_token_here
    echo.
    echo    Get token from @BotFather:
    echo    1. Open Telegram
    echo    2. Find @BotFather
    echo    3. Send /newbot
    echo    4. Copy the token
    echo.
    notepad .env
    pause
    exit /b 1
)

echo ✅ Bot token found
echo.
echo 🤖 Starting Telegram Bot...
echo    Press Ctrl+C to stop
echo.
echo ==========================================
echo.

:: Start Bot
python run_bot.py

:: If crashed
echo.
echo ❌ Bot stopped or crashed
echo.
pause

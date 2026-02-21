@echo off
chcp 65001 >nul
title MyFlowMusic - All Services
color 0E

echo.
echo ==========================================
echo   🚀 MyFlowMusic - All Services
echo ==========================================
echo.

:: Check if running from correct directory
if not exist "agent.py" (
    echo ❌ ERROR: Please run this file from the project folder!
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

:: Check .env
if not exist ".env" (
    echo ⚠️  Configuration file ^(.env^) not found!
    echo    Please create .env file from .env.example
    pause
    exit /b 1
)

echo Starting all services...
echo.

:: Start Web UI in new window
echo 🌐 Starting Web UI (http://localhost:8000)...
start "MyFlowMusic Web UI" cmd /k "cd /d "%CD%" && call venv\Scripts\activate.bat && color 0A && python agent.py web"

timeout /t 2 >nul

:: Start Bot in new window (if token configured)
echo 🤖 Starting Telegram Bot...
python -c "from music_agent.config import settings; exit(0 if settings.telegram_bot_token else 1)" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Bot token not configured - skipping bot
    echo    Add MUSIC_AGENT_TELEGRAM_BOT_TOKEN to .env to enable bot
) else (
    start "MyFlowMusic Bot" cmd /k "cd /d "%CD%" && call venv\Scripts\activate.bat && color 0B && python run_bot.py"
)

echo.
echo ==========================================
echo ✅ Services started!
echo.
echo 🌐 Web UI:   http://localhost:8000
echo 🤖 Bot:      Check Telegram
echo.
echo Close this window to keep services running
echo (they run in separate windows)
echo ==========================================
echo.
pause

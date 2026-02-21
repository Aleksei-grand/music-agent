@echo off
chcp 65001 >nul
title MyFlowMusic - Web UI
color 0A

echo.
echo ==========================================
echo   🌊 MyFlowMusic - Web UI
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

echo 🌐 Starting Web UI...
echo    URL: http://localhost:8000
echo    Press Ctrl+C to stop
echo.
echo ==========================================
echo.

:: Start Web UI
python agent.py web

:: If crashed
echo.
echo ❌ Web UI stopped or crashed
echo.
pause

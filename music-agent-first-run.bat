@echo off
chcp 65001 >nul
title MyFlowMusic - First Run Setup
echo.
echo ==========================================
echo   🌊 MyFlowMusic (MFM) - First Run
echo   Setup and Installation
echo ==========================================
echo.

:: Check if running from correct directory
if not exist "agent.py" (
    echo ❌ ERROR: Please run this file from the project folder!
    echo    Make sure you are in the same folder as agent.py
    pause
    exit /b 1
)

echo 📁 Project directory: %CD%
echo.

:: Check Python version
echo 🔍 Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python not found!
    echo    Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ❌ ERROR: Python 3.10+ required!
    echo    Current version:
    python --version
    pause
    exit /b 1
)

echo ✅ Python version OK
echo.

:: Create virtual environment
echo 📦 Creating virtual environment...
if exist "venv" (
    echo ⚠️  Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ❌ ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
)
echo.

:: Activate and install dependencies
echo 📥 Installing dependencies...
call venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo ❌ ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo ✅ Dependencies installed successfully
echo.

:: Check .env file
echo ⚙️  Checking configuration...
if not exist ".env" (
    echo 📄 Creating .env file from template...
    copy .env.example .env
    echo.
    echo ⚠️  IMPORTANT: You need to configure .env file!
    echo.
    echo    Please open .env in Notepad and add:
    echo.
    echo    MUSIC_AGENT_SUNO_COOKIE=your_suno_cookie_here
    echo    MUSIC_AGENT_POE_API_KEY=your_poe_api_key_here
    echo.
    echo    Instructions:
    echo    1. Suno Cookie: Login to suno.com → F12 → Network → Copy cookie
    echo    2. Poe API Key: Visit https://poe.com/api_key
    echo.
    notepad .env
    echo.
    echo 📝 After editing .env, run music-agent.bat to start
) else (
    echo ✅ .env file exists
    echo.
    echo 🎉 Setup complete! Run music-agent.bat to start using MyFlowMusic
)

echo.
echo ==========================================
echo   Setup finished!
echo ==========================================
echo.
pause

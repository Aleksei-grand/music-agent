@echo off
chcp 65001 >nul
:: Quick launcher - runs command directly
:: Usage: music-agent-quick.bat [command] [args...]

:: Check if running from correct directory
if not exist "agent.py" (
    echo ❌ ERROR: Please run this file from the project folder!
    pause
    exit /b 1
)

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ⚠️  First run detected! Running setup...
    call music-agent-first-run.bat
    exit /b
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: If no arguments, show help
if "%~1"=="" (
    echo.
    echo 🌊 MyFlowMusic Quick Launcher
    echo.
    echo Usage: music-agent-quick.bat [command] [options]
    echo.
    echo Examples:
    echo    music-agent-quick.bat sync
    echo    music-agent-quick.bat process --album-id xxx
    echo    music-agent-quick.bat cover --album-id xxx
    echo    music-agent-quick.bat web
    echo.
    echo For interactive menu, use: music-agent.bat
    echo.
    echo Available commands:
    python agent.py --help
    pause
    exit /b 0
)

:: Run the command
python agent.py %*

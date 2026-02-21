@echo off
chcp 65001 >nul
title MyFlowMusic (MFM)
echo.
echo 🌊 Welcome to MyFlowMusic (MFM)
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

:: Check .env file
if not exist ".env" (
    echo ⚠️  Configuration file (.env) not found!
    echo    Please run music-agent-first-run.bat first
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Main menu
:menu
cls
echo.
echo ==========================================
echo   🌊 MyFlowMusic (MFM) - Main Menu
echo ==========================================
echo.
echo 📥 DOWNLOAD:
echo    [1] Sync with Suno (download new tracks)
echo.
echo 🌐 PROCESS:
echo    [2] Translate lyrics
echo    [3] Generate cover art
echo    [4] Process audio (mastering)
echo.
echo 📤 PUBLISH:
echo    [5] Publish to distributor
echo    [6] Check publish status
echo.
echo 📊 INFO:
echo    [7] Process status
echo    [8] Audio info
echo    [9] Album list
echo.
echo 🌐 WEB:
echo    [10] Start Web UI (http://localhost:8000)
echo.
echo 🤖 BOT:
echo    [11] Start Telegram Bot
echo.
echo 📁 OTHER:
echo    [12] Import local files
echo    [13] Open storage folder
echo.
echo    [0] Exit
echo.
echo ==========================================
echo.
set /p choice="👉 Enter your choice (0-13): "

if "%choice%"=="1" goto sync
if "%choice%"=="2" goto translate
if "%choice%"=="3" goto cover
if "%choice%"=="4" goto process
if "%choice%"=="5" goto publish
if "%choice%"=="6" goto publish_status
if "%choice%"=="7" goto process_status
if "%choice%"=="8" goto audio_info
if "%choice%"=="9" goto album_list
if "%choice%"=="10" goto web
if "%choice%"=="11" goto bot
if "%choice%"=="12" goto import_local
if "%choice%"=="13" goto open_storage
if "%choice%"=="0" goto exit

echo ❌ Invalid choice, please try again
timeout /t 2 >nul
goto menu

:sync
cls
echo.
echo 🔄 Syncing with Suno...
echo.
python agent.py sync
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:translate
cls
echo.
echo 🌐 Translate lyrics
echo.
set /p album_id="Enter Album ID (or press Enter for all): "
if "%album_id%"=="" (
    python agent.py translate
) else (
    python agent.py translate --album-id %album_id%
)
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:cover
cls
echo.
echo 🎨 Generate cover art
echo.
set /p album_id="Enter Album ID (or press Enter for all without cover): "
if "%album_id%"=="" (
    python agent.py cover --all
) else (
    python agent.py cover --album-id %album_id%
)
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:process
cls
echo.
echo 🎚️ Process audio (mastering)
echo.
echo This will:
echo   - Apply fade-out (3 seconds)
echo   - Normalize to -14 LUFS
echo   - Trim silence
echo   - Add ID3 tags
echo   - Generate international filenames
echo.
set /p album_id="Enter Album ID (or press Enter for all): "
if "%album_id%"=="" (
    python agent.py process --all
) else (
    python agent.py process --album-id %album_id%
)
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:publish
cls
echo.
echo 📤 Publish to distributor
echo.
echo Available distributors:
echo   1. RouteNote
echo   2. Sferoom
echo.
set /p album_id="Enter Album ID: "
set /p dist="Enter distributor (routenote/sferoom): "
if "%dist%"=="" set dist=routenote
python agent.py publish --distributor %dist% --album-id %album_id%
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:publish_status
cls
echo.
echo 📊 Check publish status
echo.
set /p dist="Enter distributor (routenote/sferoom) or press Enter for all: "
if "%dist%"=="" (
    python agent.py publish-status
) else (
    python agent.py publish-status --distributor %dist%
)
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:process_status
cls
echo.
echo 📊 Process status
echo.
python agent.py process-status
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:audio_info
cls
echo.
echo 🎵 Audio info
echo.
set /p path="Enter path to audio file: "
if not "%path%"=="" python agent.py audio-info --file "%path%"
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:album_list
cls
echo.
echo 💿 Album list
echo.
python -c "from music_agent.models import Database; from music_agent.config import settings; db = Database(settings.db_type, settings.db_conn).connect(); session = db.session(); [print(f'{a.id} | {a.title} | {a.artist or \"Unknown\"}') for a in session.query(db.Album).all()]; session.close()"
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:web
cls
echo.
echo 🌐 Starting Web UI...
echo.
echo Open browser: http://localhost:8000
echo Press Ctrl+C to stop
echo.
python agent.py web
echo.
echo Web UI stopped
echo Press any key to return to menu...
pause >nul
goto menu

:bot
cls
echo.
echo 🤖 Starting Telegram Bot...
echo.
echo Press Ctrl+C to stop
echo.
python run_bot.py
echo.
echo Bot stopped
echo Press any key to return to menu...
pause >nul
goto menu

:import_local
cls
echo.
echo 📁 Import local files
echo.
echo Example: C:\Users\Music\*.mp3
echo.
set /p files="Enter path to files (with wildcards): "
set /p create_album="Create new album? (y/n): "
if /i "%create_album%"=="y" (
    set /p album_title="Enter album title: "
    python agent.py import-files "%files%" --create-album --album-title "%album_title%"
) else (
    python agent.py import-files "%files%"
)
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:open_storage
cls
echo.
echo 📂 Opening storage folder...
start storage
goto menu

:exit
cls
echo.
echo 👋 Thank you for using MyFlowMusic!
echo    Have a great day! 🎵
echo.
timeout /t 2 >nul
exit /b 0

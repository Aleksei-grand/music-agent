"""
Web UI - FastAPI приложение
Dashboard для управления MyFlowMusic (MFM) - GrandEmotions / VOLNAI
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from ..config import settings
from ..models import Database, Album, Song, Generation, Cover
from ..vault.manager import VaultManager
from ..utils.security import setup_security_logging
from .api import api_router
from .middleware import RateLimitMiddleware, SecurityHeadersMiddleware, RequestValidationMiddleware

logger = logging.getLogger(__name__)

# Настраиваем безопасное логирование
setup_security_logging()

# Создаём приложение
app = FastAPI(
    title="MyFlowMusic Dashboard",
    description="Web interface for MyFlowMusic by GrandEmotions / VOLNAI",
    version="0.2.0"
)

# Добавляем middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst_size=10)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestValidationMiddleware)

# Подключаем API
app.include_router(api_router)

# Статические файлы
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Шаблоны
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Глобальные объекты
db: Optional[Database] = None
vault: Optional[VaultManager] = None


@app.on_event("startup")
async def startup_event():
    """Инициализация при старте"""
    global db, vault
    
    logger.info("Starting Web UI...")
    
    db = Database(settings.db_type, settings.db_conn).connect()
    vault = VaultManager()
    
    # Создаём шаблоны если их нет
    _create_default_templates()
    
    logger.info("Web UI ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    logger.info("Shutting down Web UI...")


# ============ Pages ============

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница - Dashboard"""
    session = db.session()
    
    # Статистика
    stats = {
        "albums": session.query(Album).count(),
        "songs": session.query(Song).count(),
        "processed": session.query(Generation).filter_by(processed=True).count(),
        "pending": session.query(Generation).filter_by(processed=False).count(),
        "covers": session.query(Cover).filter_by(state=2).count(),
        "published": session.query(Album).filter_by(published=True).count(),
    }
    
    # Последние альбомы
    recent_albums = session.query(Album).order_by(Album.created_at.desc()).limit(5).all()
    
    # Активность из vault
    activity = vault.get_user_preferences(days=7) if vault else {}
    
    session.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "recent_albums": recent_albums,
        "activity": activity
    })


@app.get("/albums", response_class=HTMLResponse)
async def albums_list(request: Request, page: int = 1, per_page: int = 20):
    """Список альбомов"""
    session = db.session()
    
    total = session.query(Album).count()
    albums = session.query(Album).order_by(Album.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    session.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("albums.html", {
        "request": request,
        "albums": albums,
        "page": page,
        "total_pages": total_pages,
        "total": total
    })


@app.get("/albums/{album_id}", response_class=HTMLResponse)
async def album_detail(request: Request, album_id: str):
    """Детальная страница альбома"""
    session = db.session()
    
    album = session.query(Album).get(album_id)
    if not album:
        session.close()
        raise HTTPException(status_code=404, detail="Album not found")
    
    # Получаем треки
    songs = session.query(Song).filter_by(album_id=album_id).order_by(Song.order).all()
    
    session.close()
    
    # Проверяем наличие обложки
    cover_url = None
    if album.cover and album.cover.local_path:
        cover_path = Path(album.cover.local_path)
        if cover_path.exists():
            cover_url = f"/covers/{album.cover.id}"
    
    return templates.TemplateResponse("album_detail.html", {
        "request": request,
        "album": album,
        "songs": songs,
        "cover_url": cover_url
    })


@app.get("/songs", response_class=HTMLResponse)
async def songs_list(request: Request, status: str = "all"):
    """Список песен"""
    session = db.session()
    
    query = session.query(Song).join(Generation)
    
    if status == "processed":
        query = query.filter(Generation.processed == True)
    elif status == "pending":
        query = query.filter(Generation.processed == False)
    
    songs = query.order_by(Song.created_at.desc()).limit(100).all()
    
    session.close()
    
    return templates.TemplateResponse("songs.html", {
        "request": request,
        "songs": songs,
        "status": status
    })


@app.get("/covers", response_class=HTMLResponse)
async def covers_list(request: Request):
    """Управление обложками"""
    session = db.session()
    
    covers = session.query(Cover).order_by(Cover.created_at.desc()).all()
    albums_without = session.query(Album).filter(
        (Album.cover_id == None) | (Album.cover_id == '')
    ).all()
    
    session.close()
    
    return templates.TemplateResponse("covers.html", {
        "request": request,
        "covers": covers,
        "albums_without": albums_without
    })


@app.get("/publish", response_class=HTMLResponse)
async def publish_page(request: Request):
    """Страница публикации"""
    session = db.session()
    
    # Готовые к публикации альбомы
    ready_albums = []
    for album in session.query(Album).all():
        if album.cover_id and hasattr(album, 'songs') and album.songs:
            if not album.routenote_id or not album.sferoom_id:
                ready_albums.append(album)
    
    # Опубликованные
    published = session.query(Album).filter_by(published=True).all()
    
    session.close()
    
    return templates.TemplateResponse("publish.html", {
        "request": request,
        "ready_albums": ready_albums,
        "published": published
    })


@app.get("/vault", response_class=HTMLResponse)
async def vault_page(request: Request, days: int = 7):
    """Страница истории"""
    prefs = vault.get_user_preferences(days) if vault else {}
    
    # Получаем последние записи
    recent = []
    if vault:
        from datetime import date
        recent = vault._get_entries_for_date(date.today())
    
    return templates.TemplateResponse("vault.html", {
        "request": request,
        "preferences": prefs,
        "recent_entries": recent[-20:],  # Последние 20
        "days": days
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Страница настроек"""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": {
            "db_type": settings.db_type,
            "poe_model_translate": settings.poe_translation_model,
            "poe_model_cover": settings.poe_cover_model,
        }
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Страница загрузки с drag-and-drop"""
    return templates.TemplateResponse("upload.html", {
        "request": request
    })


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """Страница задач с real-time прогрессом"""
    # Получаем последние задачи из vault
    recent_tasks = []
    if vault:
        from datetime import date, timedelta
        for i in range(7):  # Последние 7 дней
            day = date.today() - timedelta(days=i)
            entries = vault._get_entries_for_date(day)
            for entry in entries[-5:]:  # Последние 5 записей дня
                recent_tasks.append({
                    "id": entry.get('id', ''),
                    "name": entry.get('command', 'Unknown'),
                    "album_title": entry.get('album', 'Unknown'),
                    "status": entry.get('status', 'completed'),
                    "status_label": "Готово" if entry.get('status') == 'completed' else entry.get('status', 'Unknown'),
                    "created_at": day.strftime('%d.%m.%Y'),
                    "icon": get_task_icon(entry.get('command', ''))
                })
    
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "recent_tasks": recent_tasks[:20]  # Последние 20 задач
    })


def get_task_icon(command: str) -> str:
    """Получить иконку для команды"""
    icons = {
        'translate': '🌐',
        'cover': '🎨',
        'process': '🎚️',
        'publish': '📤',
        'sync': '🔄'
    }
    for key, icon in icons.items():
        if key in command.lower():
            return icon
    return '⚙️'


# ============ API Endpoints ============

@app.get("/api/stats")
async def api_stats():
    """API: Статистика"""
    session = db.session()
    
    stats = {
        "albums": session.query(Album).count(),
        "songs": session.query(Song).count(),
        "processed": session.query(Generation).filter_by(processed=True).count(),
        "pending": session.query(Generation).filter_by(processed=False).count(),
        "covers_done": session.query(Cover).filter_by(state=2).count(),
        "covers_pending": session.query(Cover).filter_by(state=0).count(),
        "published": session.query(Album).filter_by(published=True).count(),
    }
    
    session.close()
    
    return JSONResponse(stats)


@app.post("/api/sync")
async def api_sync():
    """API: Запуск синхронизации"""
    # Запускаем в фоне
    from ..workflow.sync_suno import SunoSyncWorkflow
    from ..integrations.poe_client import PoeClient
    
    poe = PoeClient(settings.poe_api_key) if settings.poe_api_key else None
    workflow = SunoSyncWorkflow(db, poe)
    
    import asyncio
    stats = await asyncio.to_thread(workflow.sync, settings.suno_cookie, dry_run=False)
    
    return JSONResponse({"success": True, "stats": stats})


@app.post("/api/albums/{album_id}/translate")
async def api_translate_album(album_id: str, background_tasks: BackgroundTasks):
    """API: Перевод альбома"""
    from .api import translate_album
    return await translate_album(album_id, background_tasks)


@app.post("/api/albums/{album_id}/cover")
async def api_generate_cover(album_id: str, background_tasks: BackgroundTasks):
    """API: Генерация обложки"""
    from .api import generate_cover
    return await generate_cover(album_id, background_tasks)


@app.post("/api/albums/{album_id}/process")
async def api_process_album(album_id: str, background_tasks: BackgroundTasks):
    """API: Обработка аудио"""
    from .api import process_album
    return await process_album(album_id, background_tasks)


@app.post("/api/albums/{album_id}/publish")
async def api_publish_album(album_id: str, distributor: str, background_tasks: BackgroundTasks):
    """API: Публикация альбома"""
    from .api import publish_album
    return await publish_album(album_id, distributor, background_tasks)


@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """API: Загрузка аудио файла"""
    from ..utils.file_manager import FileManager
    
    try:
        file_manager = FileManager(settings.fs_conn)
        upload_dir = file_manager.raw_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем безопасное имя файла
        import uuid
        safe_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = upload_dir / safe_filename
        
        # Сохраняем файл
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Uploaded file: {file.filename} -> {file_path}")
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path)
        })
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks")
async def api_tasks():
    """API: Список активных задач"""
    from .api import task_progress
    
    # Фильтруем только активные
    active = {
        k: v for k, v in task_progress.items()
        if v.get('status') == 'running'
    }
    
    return JSONResponse({
        "active": active,
        "count": len(active)
    })


@app.get("/api/tasks/{task_id}")
async def api_task_detail(task_id: str):
    """API: Детали задачи"""
    from .api import task_progress
    
    task = task_progress.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(task)


@app.post("/api/tasks/{task_id}/cancel")
async def api_cancel_task(task_id: str):
    """API: Отмена задачи"""
    from ..utils.process_manager import process_manager
    
    cancelled = await process_manager.cancel_task(task_id)
    
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task not found or already completed")
    
    return JSONResponse({"success": True, "message": "Task cancelled"})


@app.get("/albums/bulk", response_class=HTMLResponse)
async def albums_bulk_page(request: Request):
    """Страница массовых операций"""
    session = db.session()
    albums = session.query(Album).order_by(Album.created_at.desc()).all()
    
    # Добавляем счётчики песен
    for album in albums:
        album.songs_count = session.query(Song).filter_by(album_id=album.id).count()
    
    session.close()
    
    return templates.TemplateResponse("albums_bulk.html", {
        "request": request,
        "albums": albums
    })


@app.get("/albums/{album_id}/edit", response_class=HTMLResponse)
async def album_edit_page(request: Request, album_id: str):
    """Страница редактирования альбома"""
    session = db.session()
    
    album = session.query(Album).get(album_id)
    if not album:
        session.close()
        raise HTTPException(status_code=404, detail="Album not found")
    
    songs = session.query(Song).filter_by(album_id=album_id).order_by(Song.order).all()
    session.close()
    
    return templates.TemplateResponse("album_edit.html", {
        "request": request,
        "album": album,
        "songs": songs
    })


@app.patch("/api/albums/{album_id}")
async def api_update_album(album_id: str, data: dict):
    """API: Обновление метаданных альбома"""
    session = db.session()
    
    album = session.query(Album).get(album_id)
    if not album:
        session.close()
        raise HTTPException(status_code=404, detail="Album not found")
    
    # Обновляем разрешённые поля
    allowed_fields = ['title', 'artist', 'description', 'primary_genre', 'type']
    for field, value in data.items():
        if field in allowed_fields and hasattr(album, field):
            setattr(album, field, value)
    
    session.commit()
    session.close()
    
    return JSONResponse({"success": True})


@app.patch("/api/songs/{song_id}")
async def api_update_song(song_id: str, data: dict):
    """API: Обновление метаданных песни"""
    session = db.session()
    
    song = session.query(Song).get(song_id)
    if not song:
        session.close()
        raise HTTPException(status_code=404, detail="Song not found")
    
    allowed_fields = ['title', 'type', 'description', 'intl_title']
    for field, value in data.items():
        if field in allowed_fields and hasattr(song, field):
            setattr(song, field, value)
    
    session.commit()
    session.close()
    
    return JSONResponse({"success": True})


@app.delete("/api/songs/{song_id}")
async def api_delete_song(song_id: str):
    """API: Удаление песни"""
    session = db.session()
    
    song = session.query(Song).get(song_id)
    if not song:
        session.close()
        raise HTTPException(status_code=404, detail="Song not found")
    
    session.delete(song)
    session.commit()
    session.close()
    
    return JSONResponse({"success": True})


# WebSocket endpoint для real-time прогресса
@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket: Real-time прогресс задач"""
    from .api import manager
    await manager.connect(websocket)
    try:
        while True:
            # Ждём сообщения от клиента (ping/keepalive)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/covers/{cover_id}")
async def get_cover(cover_id: str):
    """Получить файл обложки"""
    session = db.session()
    cover = session.query(Cover).get(cover_id)
    session.close()
    
    if not cover or not cover.local_path:
        raise HTTPException(status_code=404, detail="Cover not found")
    
    cover_path = Path(cover.local_path).resolve()
    
    # Security: validate path is within storage directory
    base_path = Path(settings.fs_conn).resolve() / "covers"
    try:
        cover_path.relative_to(base_path)
    except ValueError:
        logger.warning(f"Path traversal attempt: {cover_path} not in {base_path}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found")
    
    return FileResponse(cover_path)


# ============ Helpers ============

def _create_default_templates():
    """Создать шаблоны по умолчанию если их нет"""
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Базовый шаблон
    base_template = templates_dir / "base.html"
    if not base_template.exists():
        base_template.write_text(BASE_TEMPLATE, encoding='utf-8')
    
    # Dashboard
    dashboard_template = templates_dir / "dashboard.html"
    if not dashboard_template.exists():
        dashboard_template.write_text(DASHBOARD_TEMPLATE, encoding='utf-8')


# Простые шаблоны (в реальном проекте лучше отдельные файлы)
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Music Agent{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-900 text-white">
    <nav class="bg-gray-800 p-4">
        <div class="container mx-auto flex items-center justify-between">
            <a href="/" class="text-xl font-bold text-green-400">🎵 Music Agent</a>
            <div class="space-x-4">
                <a href="/" class="hover:text-green-400">Dashboard</a>
                <a href="/albums" class="hover:text-green-400">Альбомы</a>
                <a href="/songs" class="hover:text-green-400">Треки</a>
                <a href="/covers" class="hover:text-green-400">Обложки</a>
                <a href="/publish" class="hover:text-green-400">Публикация</a>
                <a href="/vault" class="hover:text-green-400">История</a>
            </div>
        </div>
    </nav>
    
    <main class="container mx-auto p-6">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
{% extends "base.html" %}

{% block title %}Dashboard - Music Agent{% endblock %}

{% block content %}
<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <!-- Stats Cards -->
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-lg font-semibold text-gray-400">Альбомов</h3>
        <p class="text-3xl font-bold text-green-400">{{ stats.albums }}</p>
    </div>
    
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-lg font-semibold text-gray-400">Песен</h3>
        <p class="text-3xl font-bold text-blue-400">{{ stats.songs }}</p>
    </div>
    
    <div class="bg-gray-800 p-6 rounded-lg">
        <h3 class="text-lg font-semibold text-gray-400">Обработано</h3>
        <p class="text-3xl font-bold text-purple-400">{{ stats.processed }}</p>
    </div>
</div>

<!-- Quick Actions -->
<div class="mt-8 bg-gray-800 p-6 rounded-lg">
    <h2 class="text-xl font-bold mb-4">Быстрые действия</h2>
    <div class="flex flex-wrap gap-4">
        <button @click="sync()" class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
            🔄 Синхронизировать
        </button>
        <a href="/covers" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
            🎨 Обложки
        </a>
        <a href="/publish" class="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded">
            📤 Публиковать
        </a>
    </div>
</div>

<!-- Recent Albums -->
<div class="mt-8 bg-gray-800 p-6 rounded-lg">
    <h2 class="text-xl font-bold mb-4">Последние альбомы</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {% for album in recent_albums %}
        <a href="/albums/{{ album.id }}" class="bg-gray-700 p-4 rounded hover:bg-gray-600">
            <div class="aspect-square bg-gray-600 rounded mb-2 flex items-center justify-center">
                {% if album.cover %}
                <img src="/covers/{{ album.cover.id }}" class="w-full h-full object-cover rounded">
                {% else %}
                <span class="text-4xl">💿</span>
                {% endif %}
            </div>
            <h3 class="font-semibold truncate">{{ album.title }}</h3>
            <p class="text-sm text-gray-400">{{ album.artist or 'Unknown' }}</p>
        </a>
        {% endfor %}
    </div>
</div>

<script>
function sync() {
    fetch('/api/sync', {method: 'POST'})
        .then(r => r.json())
        .then(data => alert('Синхронизация запущена!'))
}
</script>
{% endblock %}
"""


# Запуск
def run_web(host: str = "0.0.0.0", port: int = 8080, reload: bool = False):
    """Запустить Web UI"""
    uvicorn.run(
        "music_agent.web.app:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    run_web()

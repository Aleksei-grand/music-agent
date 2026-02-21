"""
API Endpoints для Web UI
REST API + WebSocket для real-time прогресса
"""
import asyncio
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse

from ..config import settings
from ..models import Database, Album, Song, Generation, Cover
from ..integrations.poe_client import PoeClient
from ..workflow.sync_suno import SunoSyncWorkflow
from ..audio.processor import AudioProcessor
from ..utils.file_manager import FileManager

logger = logging.getLogger(__name__)

# Router
api_router = APIRouter(prefix="/api")

# Хранилище для прогресса задач
task_progress: Dict[str, Dict] = {}


# ============ WebSocket для прогресса ============

class ConnectionManager:
    """Управление WebSocket соединениями"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Отправить сообщение всем клиентам"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass
    
    async def send_progress(self, task_id: str, progress: dict):
        """Отправить прогресс по задаче"""
        message = {
            "type": "progress",
            "task_id": task_id,
            "data": progress,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)


manager = ConnectionManager()


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для real-time обновлений"""
    await manager.connect(websocket)
    try:
        while True:
            # Ждём сообщения от клиента
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Обработка команд от клиента
            if message.get("action") == "subscribe_task":
                task_id = message.get("task_id")
                if task_id in task_progress:
                    await websocket.send_json({
                        "type": "task_status",
                        "task_id": task_id,
                        "data": task_progress[task_id]
                    })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============ Stats & Status ============

@api_router.get("/stats")
async def get_stats():
    """Полная статистика"""
    from ..web.app import db
    session = db.session()
    
    stats = {
        "albums": {
            "total": session.query(Album).count(),
            "published": session.query(Album).filter_by(published=True).count(),
            "ready": 0  # Посчитаем ниже
        },
        "songs": {
            "total": session.query(Song).count(),
            "translated": session.query(Song).filter(Song.translated_lyrics != "").count()
        },
        "generations": {
            "total": session.query(Generation).count(),
            "processed": session.query(Generation).filter_by(processed=True).count(),
            "pending": session.query(Generation).filter_by(processed=False).count()
        },
        "covers": {
            "total": session.query(Cover).count(),
            "approved": session.query(Cover).filter_by(state=2).count(),
            "pending": session.query(Cover).filter_by(state=0).count()
        }
    }
    
    # Считаем готовые к публикации альбомы
    for album in session.query(Album).all():
        if album.cover_id and hasattr(album, 'songs') and album.songs:
            if not album.routenote_id or not album.sferoom_id:
                stats["albums"]["ready"] += 1
    
    session.close()
    return stats


@api_router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Статус фоновой задачи"""
    if task_id not in task_progress:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_progress[task_id]


# ============ Actions API ============

@api_router.post("/sync")
async def start_sync(background_tasks: BackgroundTasks):
    """Запуск синхронизации с Suno"""
    task_id = f"sync_{datetime.utcnow().timestamp()}"
    
    task_progress[task_id] = {
        "status": "running",
        "progress": 0,
        "message": "Starting sync...",
        "started_at": datetime.utcnow().isoformat()
    }
    
    background_tasks.add_task(_run_sync_task, task_id)
    
    return {"task_id": task_id, "status": "started"}


async def _run_sync_task(task_id: str):
    """Фоновая задача синхронизации"""
    from ..web.app import db
    
    try:
        task_progress[task_id]["message"] = "Connecting to Suno..."
        await manager.send_progress(task_id, task_progress[task_id])
        
        poe = PoeClient(settings.poe_api_key) if settings.poe_api_key else None
        workflow = SunoSyncWorkflow(db, poe)
        
        # Запускаем синхронизацию
        task_progress[task_id]["message"] = "Fetching library..."
        await manager.send_progress(task_id, task_progress[task_id])
        
        stats = workflow.sync(settings.suno_cookie, dry_run=False)
        
        task_progress[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": f"Downloaded {stats.get('downloaded', 0)} tracks",
            "stats": stats,
            "completed_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Sync task failed: {e}")
        task_progress[task_id].update({
            "status": "error",
            "message": str(e),
            "error": str(e)
        })
    
    await manager.send_progress(task_id, task_progress[task_id])


@api_router.post("/albums/{album_id}/translate")
async def translate_album(album_id: str, background_tasks: BackgroundTasks):
    """Перевод всех песен альбома"""
    from ..web.app import db
    session = db.session()
    
    album = session.query(Album).get(album_id)
    if not album:
        session.close()
        raise HTTPException(status_code=404, detail="Album not found")
    
    task_id = f"translate_{album_id}_{datetime.utcnow().timestamp()}"
    task_progress[task_id] = {
        "status": "running",
        "album_id": album_id,
        "message": "Starting translation..."
    }
    
    songs_count = session.query(Song).filter_by(album_id=album_id).count()
    session.close()
    
    background_tasks.add_task(_run_translate_task, task_id, album_id)
    
    return {"task_id": task_id, "status": "started", "songs_count": songs_count}


async def _run_translate_task(task_id: str, album_id: str):
    """Фоновая задача перевода"""
    from ..web.app import db
    
    session = db.session()
    
    try:
        if not settings.poe_api_key:
            raise ValueError("Poe API key not configured")
        
        poe = PoeClient(settings.poe_api_key)
        
        # Получаем песни внутри задачи
        songs = session.query(Song).filter_by(album_id=album_id).all()
        total = len(songs)
        translated = 0
        
        for i, song in enumerate(songs):
            if not song.original_lyrics:
                continue
            
            task_progress[task_id]["message"] = f"Translating: {song.title}"
            task_progress[task_id]["progress"] = int((i / total) * 100)
            await manager.send_progress(task_id, task_progress[task_id])
            
            try:
                translated_text = poe.translate_lyrics(
                    song.original_lyrics,
                    target_language="english"
                )
                song.translated_lyrics = translated_text
                song.translated_to = "english"
                translated += 1
            except Exception as e:
                logger.error(f"Failed to translate {song.id}: {e}")
        
        session.commit()
        
        task_progress[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": f"Translated {translated}/{total} songs",
            "translated": translated
        })
        
    except Exception as e:
        logger.error(f"Translation task failed: {e}")
        task_progress[task_id].update({
            "status": "error",
            "message": str(e)
        })
    finally:
        session.close()
    
    await manager.send_progress(task_id, task_progress[task_id])


@api_router.post("/albums/{album_id}/cover")
async def generate_cover(album_id: str, background_tasks: BackgroundTasks):
    """Генерация обложки для альбома"""
    task_id = f"cover_{album_id}_{datetime.utcnow().timestamp()}"
    task_progress[task_id] = {
        "status": "running",
        "album_id": album_id,
        "message": "Starting cover generation..."
    }
    
    background_tasks.add_task(_run_cover_task, task_id, album_id)
    
    return {"task_id": task_id, "status": "started"}


async def _run_cover_task(task_id: str, album_id: str):
    """Фоновая задача генерации обложки"""
    from ..web.app import db
    from ..utils.image_processor import ImageProcessor
    from ..utils.id_generator import generate_ulid
    
    session = db.session()
    
    try:
        album = session.query(Album).get(album_id)
        if not album:
            raise ValueError("Album not found")
        
        if not settings.poe_api_key:
            raise ValueError("Poe API key not configured")
        
        poe = PoeClient(settings.poe_api_key)
        processor = ImageProcessor()
        file_manager = FileManager(settings.fs_conn)
        
        # Получаем основную песню
        main_song = session.query(Song).filter_by(album_id=album_id).first()
        
        task_progress[task_id]["message"] = "Analyzing song..."
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Анализ
        analysis = poe.analyze_song_for_cover(
            lyrics=main_song.original_lyrics if main_song else "",
            title=album.title,
            style=album.type
        )
        
        task_progress[task_id]["message"] = "Generating prompt..."
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Промпт
        prompt = poe.generate_cover_prompt(
            album_title=album.title,
            song_lyrics=main_song.original_lyrics if main_song else "",
            style=analysis.get('style', ''),
            mood=analysis.get('mood', '')
        )
        
        task_progress[task_id]["message"] = "Generating image..."
        task_progress[task_id]["progress"] = 50
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Генерация
        cover_id = generate_ulid()
        cover_dir = Path(settings.fs_conn) / "covers" / cover_id
        cover_dir.mkdir(parents=True, exist_ok=True)
        
        source_path = poe.generate_cover_image(
            prompt=prompt,
            output_path=cover_dir / "source.jpg"
        )
        
        task_progress[task_id]["message"] = "Processing image..."
        task_progress[task_id]["progress"] = 80
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Обработка
        processed_path = cover_dir / "cover_3000.jpg"
        processor.process_for_distribution(
            input_path=Path(source_path),
            output_path=processed_path,
            target_size=3000
        )
        
        # Сохраняем в БД
        cover = Cover(
            id=cover_id,
            album_id=album_id,
            prompt=prompt,
            local_path=str(processed_path),
            state=2  # Approved
        )
        session.add(cover)
        album.cover_id = cover_id
        session.commit()
        
        task_progress[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Cover generated successfully",
            "cover_id": cover_id
        })
        
    except Exception as e:
        logger.error(f"Cover generation failed: {e}")
        task_progress[task_id].update({
            "status": "error",
            "message": str(e)
        })
    finally:
        session.close()
    
    await manager.send_progress(task_id, task_progress[task_id])


@api_router.get("/albums/{album_id}/preview/process")
async def preview_process_album(album_id: str):
    """Превью перед обработкой альбома"""
    from ..utils.preview_helper import preview_helper
    from ..utils.file_manager import FileManager
    from ..web.app import db
    
    session = db.session()
    file_manager = FileManager(settings.fs_conn)
    
    try:
        preview = preview_helper.generate_process_preview(
            album_id=album_id,
            session=session,
            file_manager=file_manager
        )
        
        if not preview:
            raise HTTPException(status_code=404, detail="No tracks found for processing")
        
        return preview.to_dict()
        
    finally:
        session.close()


@api_router.post("/albums/{album_id}/process")
async def process_album(album_id: str, background_tasks: BackgroundTasks, confirmed: bool = False):
    """Обработка аудио альбома (требует confirmed=True после превью)"""
    task_id = f"process_{album_id}_{datetime.utcnow().timestamp()}"
    task_progress[task_id] = {
        "status": "running",
        "album_id": album_id,
        "message": "Starting audio processing..."
    }
    
    background_tasks.add_task(_run_process_task, task_id, album_id)
    
    return {"task_id": task_id, "status": "started", "confirmed": confirmed}


async def _run_process_task(task_id: str, album_id: str):
    """Фоновая задача обработки аудио"""
    from ..web.app import db
    
    session = db.session()
    
    try:
        album = session.query(Album).get(album_id)
        if not album:
            raise ValueError("Album not found")
        
        processor = AudioProcessor(settings.ffmpeg_path)
        file_manager = FileManager(settings.fs_conn)
        
        songs = session.query(Song).filter_by(album_id=album_id).all()
        total = len(songs)
        processed = 0
        
        for i, song in enumerate(songs):
            if not song.generation:
                continue
            
            task_progress[task_id]["message"] = f"Processing: {song.title}"
            task_progress[task_id]["progress"] = int((i / total) * 100)
            await manager.send_progress(task_id, task_progress[task_id])
            
            # Пути
            input_path = file_manager.raw_dir / song.generation.external_id / "audio.mp3"
            album_dir = file_manager.get_album_dir(album_id)
            # Sanitize filename to prevent path traversal
            safe_title = file_manager._sanitize_filename(song.title) or "untitled"
            output_path = album_dir / f"{song.order:02d}-{safe_title}.mp3"
            
            if not input_path.exists():
                continue
            
            # Обработка
            metadata = {
                'title': song.title,
                'artist': album.artist or 'Unknown',
                'album': album.title,
                'genre': song.type or 'Pop',
                'track': str(song.order)
            }
            
            result = processor.process_track(
                input_path=input_path,
                output_path=output_path,
                format='mp3',
                fade_out=3.0,
                normalize_lufs=True,
                trim_silence=True,
                metadata=metadata
            )
            
            if result['success']:
                song.generation.processed = True
                processed += 1
        
        session.commit()
        
        task_progress[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": f"Processed {processed}/{total} tracks",
            "processed": processed
        })
        
    except Exception as e:
        task_progress[task_id].update({
            "status": "error",
            "message": str(e)
        })
    finally:
        session.close()
    
    await manager.send_progress(task_id, task_progress[task_id])


@api_router.post("/albums/{album_id}/publish")
async def publish_album(album_id: str, distributor: str, background_tasks: BackgroundTasks):
    """Публикация альбома"""
    task_id = f"publish_{album_id}_{datetime.utcnow().timestamp()}"
    task_progress[task_id] = {
        "status": "running",
        "album_id": album_id,
        "distributor": distributor,
        "message": "Starting publication..."
    }
    
    background_tasks.add_task(_run_publish_task, task_id, album_id, distributor)
    
    return {"task_id": task_id, "status": "started"}


async def _run_publish_task(task_id: str, album_id: str, distributor: str):
    """Фоновая задача публикации"""
    from ..web.app import db
    from ..distributors.factory import DistributorFactory
    from ..distributors.base import AlbumInfo, TrackInfo
    
    session = db.session()
    
    try:
        album = session.query(Album).get(album_id)
        if not album:
            raise ValueError("Album not found")
        
        # Получаем cookie
        cookie = settings.routenote_cookie if distributor == 'routenote' else settings.sferoom_cookie
        if not cookie:
            raise ValueError(f"Cookie for {distributor} not configured")
        
        task_progress[task_id]["message"] = "Connecting to distributor..."
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Создаём дистрибьютор
        dist = DistributorFactory.create(distributor, cookie=cookie)
        
        # Собираем треки
        tracks = []
        file_manager = FileManager(settings.fs_conn)
        album_dir = file_manager.get_album_dir(album_id)
        
        for song in session.query(Song).filter_by(album_id=album_id).order_by(Song.order):
            if not song.generation:
                continue
            
            track_file = album_dir / f"{song.order:02d}-{song.title}.mp3"
            if track_file.exists():
                tracks.append(TrackInfo(
                    title=song.title,
                    file_path=track_file,
                    order=song.order
                ))
        
        # Создаём альбом
        album_info = AlbumInfo(
            title=album.title,
            artist=album.artist or "Unknown Artist",
            tracks=tracks,
            cover_path=Path(album.cover.local_path) if album.cover else None,
            primary_genre=album.primary_genre or "Pop"
        )
        
        task_progress[task_id]["message"] = "Uploading..."
        task_progress[task_id]["progress"] = 50
        await manager.send_progress(task_id, task_progress[task_id])
        
        # Публикуем
        result = dist.upload_album(album_info, auto_submit=False)
        
        if result.success:
            # Сохраняем ID
            if distributor == 'routenote':
                album.routenote_id = result.distributor_id
            else:
                album.sferoom_id = result.distributor_id
            
            album.published = True
            session.commit()
            
            task_progress[task_id].update({
                "status": "completed",
                "progress": 100,
                "message": "Published successfully",
                "distributor_id": result.distributor_id
            })
        else:
            task_progress[task_id].update({
                "status": "error",
                "message": result.message,
                "errors": result.errors
            })
        
    except Exception as e:
        task_progress[task_id].update({
            "status": "error",
            "message": str(e)
        })
    finally:
        session.close()
    
    await manager.send_progress(task_id, task_progress[task_id])

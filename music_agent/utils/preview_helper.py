"""
Preview Helper - генерация превью перед операциями
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

from .transliterator import auto_transliterate, generate_filename

logger = logging.getLogger(__name__)


@dataclass
class TrackPreview:
    """Превью трека для обработки"""
    order: int
    original_title: str
    output_filename: str
    version_type: str  # "original" или "english"
    input_path: str
    output_path: str
    will_be_processed: bool


@dataclass
class ProcessPreview:
    """Полное превью операции обработки"""
    album_id: str
    album_title: str
    artist: str
    total_tracks: int
    tracks: List[TrackPreview]
    output_format: str
    settings: Dict
    
    def to_dict(self) -> dict:
        return {
            "album_id": self.album_id,
            "album_title": self.album_title,
            "artist": self.artist,
            "total_tracks": self.total_tracks,
            "tracks": [
                {
                    "order": t.order,
                    "original_title": t.original_title,
                    "output_filename": t.output_filename,
                    "version_type": t.version_type,
                    "will_be_processed": t.will_be_processed
                }
                for t in self.tracks
            ],
            "output_format": self.output_format,
            "settings": self.settings
        }


class PreviewHelper:
    """Генератор превью для операций"""
    
    @staticmethod
    def generate_process_preview(
        album_id: str,
        session,
        file_manager,
        output_format: str = "mp3"
    ) -> Optional[ProcessPreview]:
        """
        Сгенерировать превью перед обработкой альбома
        
        Returns:
            ProcessPreview или None если нет треков для обработки
        """
        from ..models import Album, Song
        
        album = session.query(Album).get(album_id)
        if not album:
            return None
        
        songs = session.query(Song).filter_by(album_id=album_id).order_by(Song.order).all()
        if not songs:
            return None
        
        tracks_preview = []
        
        for song in songs:
            if not song.generation:
                continue
            
            # Определяем тип версии
            if song.translated_to and song.translated_lyrics:
                version_type = song.translated_to.lower()
            else:
                version_type = "original"
            
            # Получаем международное название
            if song.intl_title:
                # Используем ручной ввод
                intl_title = song.intl_title
            else:
                # Автоматическая транслитерация
                intl_title = auto_transliterate(song.title)
            
            # Формируем имя файла
            safe_name = generate_filename(intl_title, version_type)
            output_filename = f"{song.order:02d}-{safe_name}.{output_format}"
            
            input_path = str(file_manager.raw_dir / song.generation.external_id / "audio.mp3")
            album_dir = file_manager.get_album_dir(album_id)
            output_path = str(album_dir / output_filename)
            
            tracks_preview.append(TrackPreview(
                order=song.order,
                original_title=song.title,
                output_filename=output_filename,
                version_type=version_type,
                input_path=input_path,
                output_path=output_path,
                will_be_processed=song.generation and not song.generation.processed
            ))
        
        if not tracks_preview:
            return None
        
        return ProcessPreview(
            album_id=album_id,
            album_title=album.title,
            artist=album.artist or "Unknown Artist",
            total_tracks=len(tracks_preview),
            tracks=tracks_preview,
            output_format=output_format,
            settings={
                "fade_out": 3.0,
                "normalize_lufs": True,
                "trim_silence": True,
                "target_lufs": -14
            }
        )
    
    @staticmethod
    def format_preview_for_telegram(preview: ProcessPreview) -> str:
        """Форматировать превью для Telegram"""
        text = f"📋 <b>Предпросмотр обработки</b>\n\n"
        text += f"📀 <b>{preview.album_title}</b>\n"
        text += f"👤 {preview.artist}\n"
        text += f"🎵 Треков: {preview.total_tracks}\n\n"
        
        text += "<b>Будут созданы файлы:</b>\n"
        for track in preview.tracks[:10]:  # Показываем первые 10
            status = "✓" if track.will_be_processed else "⏭"
            text += f"{status} <code>{track.output_filename}</code>\n"
        
        if len(preview.tracks) > 10:
            text += f"<i>... и ещё {len(preview.tracks) - 10} треков</i>\n"
        
        text += f"\n<b>Настройки:</b>\n"
        text += f"• Fade-out: {preview.settings['fade_out']}с\n"
        text += f"• Нормализация: {preview.settings['target_lufs']} LUFS\n"
        text += f"• Формат: {preview.output_format.upper()}"
        
        return text
    
    @staticmethod
    def format_preview_for_web(preview: ProcessPreview) -> dict:
        """Форматировать превью для Web UI"""
        return preview.to_dict()


# Глобальный экземпляр
preview_helper = PreviewHelper()

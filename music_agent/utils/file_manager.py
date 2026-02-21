"""
Управление файловой структурой проекта
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class FileManager:
    """
    Менеджер файловой структуры:
    - raw/ - скачанное с Suno
    - versions/ - копии с разными названиями
    - albums/ - сгруппированные релизы
    """
    
    def __init__(self, base_path: str = "./storage"):
        self.base_path = Path(base_path)
        self.raw_dir = self.base_path / "raw"
        self.versions_dir = self.base_path / "versions"
        self.albums_dir = self.base_path / "albums"
        self.covers_dir = self.base_path / "covers"
        
        # Создаём папки
        for dir_path in [self.raw_dir, self.versions_dir, self.albums_dir, self.covers_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_raw_track_dir(self, track_id: str) -> Path:
        """Путь к папке сырых данных трека"""
        return self.raw_dir / track_id
    
    def get_version_path(self, track_id: str, version_name: str, ext: str = "mp3") -> Path:
        """
        Путь к версии трека
        version_name: "original version" или "english version"
        """
        safe_name = self._sanitize_filename(version_name)
        return self.versions_dir / f"{track_id}_{safe_name}.{ext}"
    
    def get_album_dir(self, album_id: str) -> Path:
        """Путь к папке альбома"""
        return self.albums_dir / album_id
    
    def track_exists(self, track_id: str) -> bool:
        """Проверить скачан ли уже трек"""
        track_dir = self.get_raw_track_dir(track_id)
        audio_file = track_dir / "audio.mp3"
        metadata_file = track_dir / "metadata.json"
        return audio_file.exists() and metadata_file.exists()
    
    def load_track_metadata(self, track_id: str) -> Optional[Dict]:
        """Загрузить metadata.json трека"""
        metadata_path = self.get_raw_track_dir(track_id) / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_track_metadata(self, track_id: str, metadata: Dict):
        """Сохранить metadata.json"""
        metadata_path = self.get_raw_track_dir(track_id) / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def list_downloaded_tracks(self) -> List[str]:
        """Получить список ID уже скачанных треков"""
        tracks = []
        if self.raw_dir.exists():
            for track_dir in self.raw_dir.iterdir():
                if track_dir.is_dir() and (track_dir / "metadata.json").exists():
                    tracks.append(track_dir.name)
        return tracks
    
    def get_track_created_date(self, track_id: str) -> Optional[datetime]:
        """Получить дату создания трека из метаданных"""
        metadata = self.load_track_metadata(track_id)
        if metadata and 'created_at' in metadata:
            try:
                # Suno формат: 2024-01-20T10:00:00.000Z
                return datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
            except:
                pass
        return None
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Очистить строку для использования в имени файла"""
        # Убираем недопустимые символы
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        # Убираем лишние пробелы
        name = re.sub(r'\s+', " ", name).strip()
        return name
    
    @staticmethod
    def create_version_filename(original_title: str, version_type: str, language: str) -> str:
        """
        Создать имя файла для версии
        
        Args:
            original_title: Оригинальное название
            version_type: "original" или "english"
            language: язык для скобок
            
        Returns:
            "Название (original version).mp3" или "Name (english version).mp3"
        """
        # Для английской версии переводим название
        if version_type == "english":
            # Здесь будет перевод названия через Poe
            # Пока используем транслитерацию или оригинал
            title = original_title
        else:
            title = original_title
        
        suffix = f"({version_type} version)"
        return f"{title} {suffix}"

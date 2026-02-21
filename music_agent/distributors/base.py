"""
Базовый класс для дистрибьюторов
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrackInfo:
    """Информация о треке для загрузки"""
    title: str
    file_path: Path
    order: int = 1
    isrc: str = ""
    instrumental: bool = False
    lyrics: str = ""


@dataclass
class AlbumInfo:
    """Информация об альбоме для загрузки"""
    title: str
    artist: str
    tracks: List[TrackInfo]
    cover_path: Optional[Path] = None
    primary_genre: str = "Pop"
    secondary_genre: str = ""
    upc: str = ""
    record_label: str = ""
    first_name: str = ""
    last_name: str = ""
    
    @property
    def track_count(self) -> int:
        return len(self.tracks)


@dataclass
class UploadResult:
    """Результат загрузки"""
    success: bool
    distributor_id: Optional[str] = None  # ID в системе дистрибьютора
    message: str = ""
    errors: List[str] = None
    url: str = ""  # Ссылка на релиз
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BaseDistributor(ABC):
    """Базовый класс для всех дистрибьюторов"""
    
    NAME: str = "base"
    DISPLAY_NAME: str = "Base Distributor"
    
    # Требования к файлам
    MIN_COVER_SIZE: int = 3000
    REQUIRED_COVER_RATIO: str = "1:1"
    ACCEPTED_FORMATS: List[str] = ["mp3", "wav", "flac"]
    MIN_BITRATE: int = 192  # kbps
    
    def __init__(self, cookie: str, proxy: Optional[str] = None):
        self.cookie = cookie
        self.proxy = proxy
        self.session = None
        
    @abstractmethod
    def authenticate(self) -> bool:
        """Проверить/обновить аутентификацию"""
        pass
    
    @abstractmethod
    def upload_album(self, album: AlbumInfo, auto_submit: bool = False) -> UploadResult:
        """Загрузить альбом"""
        pass
    
    @abstractmethod
    def check_status(self, distributor_id: str) -> Dict:
        """Проверить статус релиза"""
        pass
    
    def validate_album(self, album: AlbumInfo) -> List[str]:
        """Проверить альбом перед загрузкой"""
        errors = []
        
        # Проверка обложки
        if not album.cover_path or not album.cover_path.exists():
            errors.append("Cover image required")
        else:
            from PIL import Image
            try:
                with Image.open(album.cover_path) as img:
                    w, h = img.size
                    if w < self.MIN_COVER_SIZE or h < self.MIN_COVER_SIZE:
                        errors.append(f"Cover too small: {w}x{h}, min {self.MIN_COVER_SIZE}x{self.MIN_COVER_SIZE}")
                    if w != h:
                        errors.append(f"Cover must be square, got {w}x{h}")
            except Exception as e:
                errors.append(f"Cannot read cover: {e}")
        
        # Проверка треков
        if not album.tracks:
            errors.append("No tracks")
        
        for track in album.tracks:
            if not track.file_path.exists():
                errors.append(f"Track file not found: {track.file_path}")
            else:
                # Проверка формата
                ext = track.file_path.suffix.lower().replace('.', '')
                if ext not in self.ACCEPTED_FORMATS:
                    errors.append(f"Format not accepted: {ext}")
        
        # Проверка метаданных
        if not album.title:
            errors.append("Album title required")
        if not album.artist:
            errors.append("Artist name required")
        if not album.primary_genre:
            errors.append("Genre required")
        
        return errors
    
    def prepare_for_upload(self, album: AlbumInfo, temp_dir: Path) -> AlbumInfo:
        """Подготовить файлы для загрузки (конвертация, копирование)"""
        # По умолчанию возвращаем как есть
        return album


class DistributorError(Exception):
    """Ошибка дистрибьютора"""
    pass


class AuthenticationError(DistributorError):
    """Ошибка аутентификации"""
    pass


class ValidationError(DistributorError):
    """Ошибка валидации"""
    pass

"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Database
    db_type: str = "sqlite"  # sqlite, postgres, mysql
    db_conn: str = "myflowmusic.db"
    
    # File Storage
    fs_type: str = "local"  # local, s3, telegram
    fs_conn: str = "./storage"
    
    # Poe API (для переводов и обложек)
    poe_api_key: str = ""
    poe_translation_model: str = "Claude-Opus-4.6"  # Для переводов
    poe_cover_model: str = "Nano-Banana-Pro"  # Для обложек
    
    # Suno API
    suno_cookie: str = ""
    suno_account: str = "main"
    
    # Voice Commands (Deepgram или другой API)
    voice_api_key: str = ""
    voice_model: str = "nova-2"  # Deepgram model
    
    # RouteNote / Sferoom
    routenote_cookie: str = ""
    sferoom_cookie: str = ""
    
    # Processing
    concurrency: int = 1
    debug: bool = False
    proxy: Optional[str] = None
    
    # Paths
    ffmpeg_path: str = "ffmpeg"
    aubio_path: str = "aubio"
    
    class Config:
        env_prefix = "MUSIC_AGENT_"
        env_file = ".env"


settings = Settings()

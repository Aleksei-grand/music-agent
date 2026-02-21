"""
SQLAlchemy модели данных (аналог storage в musikai)
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


class State(enum.IntEnum):
    """Статусы записей"""
    PENDING = 0
    REJECTED = 1
    APPROVED = 2
    USED = 3


class Song(Base):
    """Модель песни"""
    __tablename__ = "songs"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    type = Column(String, default="")  # Жанр/категория
    notes = Column(Text, default="")  # Заметки
    
    prompt = Column(Text, default="")  # Промпт для генерации
    manual = Column(Boolean, default=False)
    style = Column(String, default="")  # Стиль музыки
    instrumental = Column(Boolean, default=False)
    
    generation_id = Column(String, ForeignKey("generations.id"), nullable=True)
    generation = relationship("Generation", back_populates="song")
    
    provider = Column(String, default="")  # suno, udio
    account = Column(String, default="")  # Аккаунт
    
    title = Column(String, default="")  # Название
    album_id = Column(String, ForeignKey("albums.id"), default="")
    order = Column(Integer, default=0)  # Порядок в альбоме
    
    isrc = Column(String, default="")  # International Standard Recording Code
    youtube_id = Column(String, default="")
    spotify_id = Column(String, default="")
    spotify_analysis = Column(Text, default="")
    jamendo_id = Column(String, default="")
    
    disabled = Column(Boolean, default=False)
    classification = Column(String, default="")
    classified = Column(Boolean, default=False)
    description = Column(Text, default="")
    described = Column(Boolean, default=False)
    
    likes = Column(Integer, default=0)
    state = Column(Integer, default=State.PENDING)
    
    # Переводы
    original_lyrics = Column(Text, default="")  # Оригинал на русском
    translated_lyrics = Column(Text, default="")  # Перевод
    translated_to = Column(String, default="")  # Язык перевода
    
    # Международное название (латиница)
    intl_title = Column(String, default="")  # Авто-транслит или ручной ввод


class Generation(Base):
    """Модель генерации (результат от Suno/Udio)"""
    __tablename__ = "generations"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    song_id = Column(String, ForeignKey("songs.id"), nullable=True)
    song = relationship("Song", back_populates="generation")
    
    external_id = Column(String, default="")  # ID в Suno/Udio
    audio_url = Column(String, default="")  # URL аудио
    image_url = Column(String, default="")  # URL изображения
    title = Column(String, default="")  # Название от генератора
    history = Column(Text, default="")  # История генерации (JSON)
    duration = Column(Float, default=0.0)  # Длительность в секундах
    lyrics = Column(Text, default="")  # Текст песни
    
    # Обработка
    mastered = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    tempo = Column(Float, default=0.0)  # BPM
    ends = Column(Boolean, default=False)  # Заканчивается ли корректно
    flags = Column(Text, default="")  # JSON с флагами (silences, BPM changes)
    flagged = Column(Boolean, default=False)


class Album(Base):
    """Модель альбома"""
    __tablename__ = "albums"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    type = Column(String, default="")
    title = Column(String, default="")
    subtitle = Column(String, default="")
    volume = Column(Integer, default=1)
    
    artist = Column(String, default="")
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    record_label = Column(String, default="")
    
    primary_genre = Column(String, default="")
    secondary_genre = Column(String, default="")
    
    cover_id = Column(String, ForeignKey("covers.id"), nullable=True)
    cover = relationship("Cover", back_populates="album")
    
    upc = Column(String, default="")  # Universal Product Code
    
    # Публикация
    published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    distrokid_id = Column(String, default="")
    routenote_id = Column(String, default="")
    sferoom_id = Column(String, default="")


class Cover(Base):
    """Модель обложки"""
    __tablename__ = "covers"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    album_id = Column(String, ForeignKey("albums.id"), nullable=True)
    album = relationship("Album", back_populates="cover")
    
    prompt = Column(Text, default="")  # Промпт для генерации
    image_url = Column(String, default="")  # URL изображения
    local_path = Column(String, default="")  # Локальный путь
    
    state = Column(Integer, default=State.PENDING)
    
    # Для апскейла
    upscaled = Column(Boolean, default=False)
    upscaled_path = Column(String, default="")


class Title(Base):
    """Названия треков для импорта"""
    __tablename__ = "titles"
    
    id = Column(String, primary_key=True)
    type = Column(String, default="")
    style = Column(String, default="")
    title = Column(String, default="")
    used = Column(Boolean, default=False)


class Draft(Base):
    """Черновики альбомов"""
    __tablename__ = "drafts"
    
    id = Column(String, primary_key=True)
    type = Column(String, default="")
    title = Column(String, default="")
    subtitle = Column(String, default="")
    volumes = Column(Integer, default=1)
    used = Column(Boolean, default=False)


class Setting(Base):
    """Настройки (куки, API ключи)"""
    __tablename__ = "settings"
    
    id = Column(String, primary_key=True)
    service = Column(String, default="")  # suno, distrokid, routenote, etc.
    account = Column(String, default="")
    value = Column(Text, default="")  # Cookie или API ключ
    type = Column(String, default="cookie")  # cookie, api_key


class Database:
    """Класс для работы с БД"""
    
    def __init__(self, db_type: str, db_conn: str, debug: bool = False):
        self.db_type = db_type
        self.db_conn = db_conn
        self.debug = debug
        self.engine = None
        self.Session = None
        
    def connect(self):
        """Подключение к БД"""
        if self.db_type == "sqlite":
            self.engine = create_engine(f"sqlite:///{self.db_conn}", echo=self.debug)
        elif self.db_type == "postgres":
            self.engine = create_engine(self.db_conn, echo=self.debug)
        elif self.db_type == "mysql":
            self.engine = create_engine(self.db_conn, echo=self.debug)
        else:
            raise ValueError(f"Unknown db type: {self.db_type}")
        
        self.Session = sessionmaker(bind=self.engine)
        return self
    
    def migrate(self):
        """Создание таблиц"""
        Base.metadata.create_all(self.engine)
        return self
    
    def session(self):
        """Получение сессии"""
        return self.Session()

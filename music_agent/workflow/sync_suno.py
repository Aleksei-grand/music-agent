"""
Основной workflow синхронизации с Suno
Скачивание, группировка версий, создание альбомов
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from ..integrations.suno_client import SunoClient, SunoTrack
from ..integrations.poe_client import PoeClient
from ..utils.file_manager import FileManager
from ..utils.id_generator import generate_ulid
from ..models import Database, Song, Generation, Album, Cover, State
from ..config import settings

logger = logging.getLogger(__name__)


class SunoSyncWorkflow:
    """
    Workflow:
    1. Проверить новые треки на Suno
    2. Скачать отсутствующие
    3. Сгруппировать по песням (если несколько версий)
    4. Создать альбомы
    5. Сгенерировать обложки и метаданные
    """
    
    def __init__(self, db: Database, poe_client: Optional[PoeClient] = None):
        self.db = db
        self.file_manager = FileManager(settings.fs_conn)
        self.poe = poe_client
        self.suno = None
        
    def sync(self, cookie: str, dry_run: bool = False) -> Dict:
        """
        Главный метод синхронизации
        
        Returns:
            stats: {"downloaded": N, "grouped": N, "albums_created": N}
        """
        stats = {
            'downloaded': 0,
            'skipped': 0,
            'grouped': 0,
            'albums_created': 0,
            'errors': []
        }
        
        # 1. Подключаемся к Suno
        logger.info("Connecting to Suno...")
        self.suno = SunoClient(cookie, settings.proxy)
        
        # 1.5 Валидируем cookie
        logger.info("Validating cookie...")
        if not self.suno.api_client.validate_cookie():
            stats['errors'].append("Cookie validation failed. Please update SUNO_COOKIE in .env")
            logger.error("Suno cookie invalid or expired")
            return stats
        
        # 2. Получаем треки из библиотеки
        logger.info("Fetching library...")
        try:
            tracks = self.suno.get_all_tracks(use_browser_fallback=True)
        except Exception as e:
            logger.error(f"Failed to fetch library: {e}")
            stats['errors'].append(f"Fetch failed: {e}")
            return stats
        
        logger.info(f"Found {len(tracks)} tracks in Suno library")
        
        # 3. Скачиваем новые треки
        new_tracks = []
        for track in tracks:
            if self.file_manager.track_exists(track.id):
                logger.debug(f"Track already downloaded: {track.title}")
                stats['skipped'] += 1
                continue
            
            if dry_run:
                logger.info(f"[DRY RUN] Would download: {track.title}")
                stats['downloaded'] += 1
                continue
            
            # Скачиваем
            try:
                results = self.suno.download_track(track, self.file_manager.raw_dir)
                if results.get('audio'):
                    logger.info(f"Downloaded: {track.title}")
                    stats['downloaded'] += 1
                    new_tracks.append(track)
                    
                    # Сохраняем в БД
                    self._save_to_db(track)
                else:
                    stats['errors'].append(f"Failed to download audio for {track.id}")
            except Exception as e:
                logger.error(f"Error downloading {track.id}: {e}")
                stats['errors'].append(f"Download error {track.id}: {e}")
        
        # 4. Группируем треки по песням (если несколько версий)
        if new_tracks and not dry_run:
            self._group_tracks_into_songs(new_tracks)
            stats['grouped'] = len(new_tracks)
        
        # 5. Создаём альбомы для групп
        if not dry_run:
            albums_created = self._create_albums_for_groups()
            stats['albums_created'] = albums_created
        
        logger.info(f"Sync complete: {stats}")
        return stats
    
    def _save_to_db(self, track: SunoTrack):
        """Сохранить трек в БД"""
        session = self.db.session()
        try:
            # Создаём Generation
            gen = Generation(
                id=generate_ulid(),
                external_id=track.id,
                audio_url=track.audio_url,
                image_url=track.image_url,
                title=track.title,
                lyrics=track.lyrics,
                style=track.style,
                duration=track.duration,
                processed=False
            )
            session.add(gen)
            session.commit()
            logger.debug(f"Saved to DB: {gen.id}")
        except Exception as e:
            logger.error(f"DB error: {e}")
            session.rollback()
        finally:
            session.close()
    
    def _group_tracks_into_songs(self, tracks: List[SunoTrack]):
        """
        Группировка треков по песням
        Логика: если названия похожи (без дат/версий) - это одна песня
        """
        # Группируем по "нормализованному" названию
        groups = defaultdict(list)
        
        for track in tracks:
            # Нормализуем название (убираем даты, версии и т.д.)
            normalized = self._normalize_title(track.title)
            groups[normalized].append(track)
        
        logger.info(f"Grouped into {len(groups)} songs")
        
        session = self.db.session()
        try:
            for normalized_title, track_group in groups.items():
                if len(track_group) > 1:
                    logger.info(f"Found {len(track_group)} versions of '{normalized_title}'")
                
                # Создаём Song для каждого трека
                for i, track in enumerate(track_group):
                    # Находим Generation
                    gen = session.query(Generation).filter_by(external_id=track.id).first()
                    if not gen:
                        continue
                    
                    # Определяем тип версии
                    version_type = self._detect_version_type(track.title, i, len(track_group))
                    
                    song = Song(
                        id=generate_ulid(),
                        generation_id=gen.id,
                        title=track.title,
                        original_lyrics=track.lyrics,
                        type=self._detect_genre(track.style),
                        style=track.style,
                        state=State.PENDING,
                        # Определяем язык по тексту
                        translated_to="russian" if version_type == "original" else "english"
                    )
                    session.add(song)
                    
                    logger.debug(f"Created song: {song.title} ({version_type})")
            
            session.commit()
        except Exception as e:
            logger.error(f"Error grouping tracks: {e}")
            session.rollback()
        finally:
            session.close()
    
    def _create_albums_for_groups(self) -> int:
        """
        Создать альбомы для сгруппированных песен
        Одна песня с несколькими версиями = один альбом (сингл)
        """
        session = self.db.session()
        albums_created = 0
        
        try:
            # Получаем песни без альбома
            songs = session.query(Song).filter_by(album_id="").all()
            
            # Группируем по "базовому" названию
            groups = defaultdict(list)
            for song in songs:
                base_title = self._normalize_title(song.title)
                groups[base_title].append(song)
            
            for base_title, song_group in groups.items():
                # Создаём альбом
                album_id = generate_ulid()
                
                # Определяем основную песню (самая свежая или первая)
                main_song = song_group[0]
                
                album = Album(
                    id=album_id,
                    title=base_title,
                    type=main_song.type,
                    primary_genre=self._map_to_distributor_genre(main_song.type),
                    artist=settings.suno_account if hasattr(settings, 'suno_account') else "Artist"
                )
                session.add(album)
                
                # Привязываем песни к альбому
                for i, song in enumerate(song_group):
                    song.album_id = album_id
                    song.order = i + 1
                
                albums_created += 1
                logger.info(f"Created album: {album.title} ({len(song_group)} tracks)")
                
                # Генерируем обложку если есть Poe API
                if self.poe:
                    self._generate_album_cover(album, main_song, session)
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Error creating albums: {e}")
            session.rollback()
        finally:
            session.close()
        
        return albums_created
    
    def _generate_album_cover(self, album: Album, main_song: Song, session):
        """Сгенерировать обложку для альбома"""
        try:
            # Анализируем песню
            analysis = self.poe.analyze_song_for_cover(
                lyrics=main_song.original_lyrics,
                title=album.title,
                style=main_song.style
            )
            
            # Создаём промпт
            prompt = self.poe.generate_cover_prompt(
                album_title=album.title,
                song_lyrics=main_song.original_lyrics[:500],
                style=analysis.get('mood', ''),
                mood=analysis.get('colors', '')
            )
            
            # Генерируем изображение
            cover_id = generate_ulid()
            cover_path = self.file_manager.covers_dir / cover_id
            cover_path.mkdir(exist_ok=True)
            
            # Сохраняем промпт
            with open(cover_path / "prompt.txt", 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            # Создаём запись в БД
            cover = Cover(
                id=cover_id,
                album_id=album.id,
                prompt=prompt,
                state=State.PENDING  # Потом вручную сгенерируем через Poe
            )
            session.add(cover)
            album.cover_id = cover_id
            
            logger.info(f"Created cover draft for album: {album.title}")
            
        except Exception as e:
            logger.error(f"Error generating cover: {e}")
    
    @staticmethod
    def _normalize_title(title: str) -> str:
        """Нормализовать название для группировки"""
        import re
        # Убираем даты в скобках, версии и т.д.
        title = re.sub(r'\s*\(\d{4}\)\s*', '', title)  # (2024)
        title = re.sub(r'\s*-\s*version\s*\w*', '', title, flags=re.I)  # - version
        title = re.sub(r'\s*\([^)]*version[^)]*\)', '', title, flags=re.I)  # (version)
        title = re.sub(r'\s+', ' ', title).strip().lower()
        return title
    
    @staticmethod
    def _detect_version_type(title: str, index: int, total: int) -> str:
        """Определить тип версии по названию"""
        title_lower = title.lower()
        if 'english' in title_lower or 'translation' in title_lower:
            return "english"
        if 'russian' in title_lower or 'original' in title_lower:
            return "original"
        # Если первая версия - считаем оригиналом, остальные - переводами
        return "original" if index == 0 else "english"
    
    @staticmethod
    def _detect_genre(style: str) -> str:
        """Определить жанр из стиля Suno"""
        style_lower = style.lower()
        genre_map = {
            'pop': 'pop',
            'rock': 'rock',
            'electronic': 'electronic',
            'hip hop': 'hip-hop',
            'rap': 'hip-hop',
            'jazz': 'jazz',
            'classical': 'classical',
            'folk': 'folk',
            'r&b': 'rnb',
            'soul': 'rnb'
        }
        for key, genre in genre_map.items():
            if key in style_lower:
                return genre
        return "pop"  # default
    
    @staticmethod
    def _map_to_distributor_genre(internal_genre: str) -> str:
        """Преобразовать в жанр для дистрибьютора"""
        # RouteNote genres
        genre_map = {
            'pop': 'Pop',
            'rock': 'Rock',
            'electronic': 'Electronic',
            'hip-hop': 'Hip Hop/Rap',
            'jazz': 'Jazz',
            'classical': 'Classical',
            'folk': 'Folk',
            'rnb': 'R&B/Soul'
        }
        return genre_map.get(internal_genre, 'Pop')

"""
RouteNote дистрибьютор
Автоматизация через Playwright (нет официального API)
"""
import logging
import time
from pathlib import Path
from typing import Optional, Dict
import json

from playwright.sync_api import sync_playwright, Page, expect

from .base import BaseDistributor, AlbumInfo, UploadResult, TrackInfo

logger = logging.getLogger(__name__)


class RouteNoteDistributor(BaseDistributor):
    """
    RouteNote - бесплатный дистрибьютор
    Автоматизация загрузки через браузер
    """
    
    NAME = "routenote"
    DISPLAY_NAME = "RouteNote"
    
    BASE_URL = "https://routenote.com"
    UPLOAD_URL = "https://routenote.com/upload"
    
    # RouteNote жанры (частичный список, основные)
    GENRES = {
        "Alternative": "Alternative",
        "Blues": "Blues",
        "Classical": "Classical",
        "Country": "Country",
        "Dance": "Dance",
        "Electronic": "Electronic",
        "Folk": "Folk",
        "Hip Hop/Rap": "Hip Hop/Rap",
        "Jazz": "Jazz",
        "Latin": "Latin",
        "Metal": "Metal",
        "Pop": "Pop",
        "R&B/Soul": "R&B/Soul",
        "Reggae": "Reggae",
        "Rock": "Rock",
        "Soundtrack": "Soundtrack",
        "World": "World",
    }
    
    def __init__(self, cookie: str, proxy: Optional[str] = None, headless: bool = True):
        super().__init__(cookie, proxy)
        self.headless = headless
        self.page: Optional[Page] = None
        self.playwright = None
        self.browser = None
        
    def authenticate(self) -> bool:
        """Проверить что куки рабочие"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                
                # Устанавливаем куки
                context.add_cookies([{
                    'name': 'session',
                    'value': self.cookie,
                    'domain': '.routenote.com',
                    'path': '/'
                }])
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}/dashboard", timeout=30000)
                
                # Проверяем что авторизованы (ищем элементы дашборда)
                try:
                    page.wait_for_selector("[data-testid='dashboard']", timeout=5000)
                    logger.info("RouteNote authentication successful")
                    return True
                except:
                    logger.error("RouteNote authentication failed")
                    return False
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"Authentication check error: {e}")
            return False
    
    def upload_album(self, album: AlbumInfo, auto_submit: bool = False) -> UploadResult:
        """
        Загрузить альбом в RouteNote
        
        Args:
            album: Информация об альбоме
            auto_submit: Автоматически отправить на модерацию
        """
        # Проверяем валидацию
        errors = self.validate_album(album)
        if errors:
            return UploadResult(
                success=False,
                message="Validation failed",
                errors=errors
            )
        
        try:
            self.playwright = sync_playwright().start()
            
            # Запускаем браузер
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                proxy={"server": self.proxy} if self.proxy else None
            )
            
            context = self.browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            
            # Куки
            context.add_cookies([{
                'name': 'routenote_session',
                'value': self.cookie,
                'domain': '.routenote.com',
                'path': '/'
            }])
            
            self.page = context.new_page()
            
            # Шаг 1: Открываем страницу загрузки
            logger.info("Opening RouteNote upload page...")
            self.page.goto(self.UPLOAD_URL, timeout=60000)
            
            # Ждём загрузки формы
            self.page.wait_for_selector("form#upload-form", timeout=30000)
            
            # Шаг 2: Заполняем информацию об альбоме
            logger.info(f"Filling album info: {album.title}")
            self._fill_album_info(album)
            
            # Шаг 3: Загружаем обложку
            logger.info("Uploading cover...")
            self._upload_cover(album.cover_path)
            
            # Шаг 4: Добавляем треки
            logger.info(f"Adding {len(album.tracks)} tracks...")
            for i, track in enumerate(album.tracks, 1):
                self._add_track(track, i)
            
            # Шаг 5: Выбираем сторы (все по умолчанию)
            self._select_stores()
            
            # Шаг 6: Сохраняем черновик или отправляем
            if auto_submit:
                result = self._submit_release()
            else:
                result = self._save_draft()
            
            return result
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            # Скриншот для отладки
            if self.page:
                self.page.screenshot(path="routenote_error.png")
            return UploadResult(
                success=False,
                message=f"Upload failed: {str(e)}",
                errors=[str(e)]
            )
        finally:
            self._cleanup()
    
    def _fill_album_info(self, album: AlbumInfo):
        """Заполнить информацию об альбоме"""
        page = self.page
        
        # Название альбома
        page.fill("input[name='album_title']", album.title)
        
        # Имя артиста
        page.fill("input[name='artist_name']", album.artist)
        
        # Лейбл (если есть)
        if album.record_label:
            page.fill("input[name='record_label']", album.record_label)
        
        # Жанр (primary)
        genre_value = self._map_genre(album.primary_genre)
        page.select_option("select[name='primary_genre']", genre_value)
        
        # Жанр (secondary, если есть)
        if album.secondary_genre:
            secondary_value = self._map_genre(album.secondary_genre)
            page.select_option("select[name='secondary_genre']", secondary_value)
        
        # UPC (если есть)
        if album.upc:
            page.fill("input[name='upc']", album.upc)
        
        # Имя и фамилия для роялти
        if album.first_name:
            page.fill("input[name='first_name']", album.first_name)
        if album.last_name:
            page.fill("input[name='last_name']", album.last_name)
        
        time.sleep(0.5)
    
    def _upload_cover(self, cover_path: Path):
        """Загрузить обложку"""
        page = self.page
        
        # Находим input для файла
        file_input = page.locator("input[type='file'][accept*='image']")
        file_input.set_input_files(str(cover_path))
        
        # Ждём превью
        page.wait_for_selector(".cover-preview", timeout=30000)
        time.sleep(1)
    
    def _add_track(self, track: TrackInfo, index: int):
        """Добавить трек в альбом"""
        page = self.page
        
        # Кнопка добавления трека
        if index > 1:
            page.click("button#add-track")
            time.sleep(0.5)
        
        # Номер трека
        track_selector = f".track-item:nth-child({index})"
        
        # Название трека
        page.fill(f"{track_selector} input[name='track_title']", track.title)
        
        # Загрузка файла
        file_input = page.locator(f"{track_selector} input[type='file'][accept*='audio']")
        file_input.set_input_files(str(track.file_path))
        
        # Ждём загрузки
        page.wait_for_selector(f"{track_selector} .upload-complete", timeout=120000)
        
        # ISRC (если есть)
        if track.isrc:
            page.fill(f"{track_selector} input[name='isrc']", track.isrc)
        
        # Instrumental
        if track.instrumental:
            page.check(f"{track_selector} input[name='instrumental']")
        
        # Текст песни (если не инструментал)
        if track.lyrics and not track.instrumental:
            page.fill(f"{track_selector} textarea[name='lyrics']", track.lyrics)
        
        time.sleep(0.5)
    
    def _select_stores(self):
        """Выбрать музыкальные площадки"""
        page = self.page
        
        # По умолчанию выбираем все
        # Или можно выбрать конкретные
        try:
            # Кнопка "Select All"
            page.click("button#select-all-stores")
        except:
            logger.warning("Could not click select-all, using defaults")
    
    def _save_draft(self) -> UploadResult:
        """Сохранить как черновик"""
        page = self.page
        
        page.click("button#save-draft")
        
        # Ждём подтверждения
        page.wait_for_selector(".alert-success", timeout=10000)
        
        # Ищем ID релиза в URL или на странице
        url = page.url
        release_id = None
        if "/upload/" in url:
            parts = url.split("/upload/")
            if len(parts) > 1:
                release_id = parts[1].split("/")[0]
        
        logger.info(f"Draft saved, ID: {release_id}")
        
        return UploadResult(
            success=True,
            distributor_id=release_id,
            message="Draft saved successfully",
            url=url
        )
    
    def _submit_release(self) -> UploadResult:
        """Отправить на модерацию"""
        page = self.page
        
        # Ставим галочку соглашения
        page.check("input[name='terms_accepted']")
        
        # Кнопка отправки
        page.click("button#submit-release")
        
        # Ждём подтверждения
        page.wait_for_selector(".alert-success", timeout=30000)
        
        url = page.url
        
        return UploadResult(
            success=True,
            message="Release submitted for review",
            url=url
        )
    
    def _map_genre(self, genre: str) -> str:
        """Преобразовать жанр в формат RouteNote"""
        genre_lower = genre.lower()
        
        mapping = {
            "pop": "Pop",
            "rock": "Rock",
            "electronic": "Electronic",
            "hip-hop": "Hip Hop/Rap",
            "hip hop": "Hip Hop/Rap",
            "rap": "Hip Hop/Rap",
            "jazz": "Jazz",
            "classical": "Classical",
            "rnb": "R&B/Soul",
            "r&b": "R&B/Soul",
            "soul": "R&B/Soul",
            "country": "Country",
            "folk": "Folk",
            "metal": "Metal",
            "dance": "Dance",
            "alternative": "Alternative",
            "latin": "Latin",
            "reggae": "Reggae",
            "blues": "Blues",
            "world": "World",
            "soundtrack": "Soundtrack",
        }
        
        return mapping.get(genre_lower, "Pop")
    
    def check_status(self, distributor_id: str) -> Dict:
        """Проверить статус релиза"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                
                context.add_cookies([{
                    'name': 'routenote_session',
                    'value': self.cookie,
                    'domain': '.routenote.com',
                    'path': '/'
                }])
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}/releases/{distributor_id}", timeout=30000)
                
                # Ищем статус
                try:
                    status_elem = page.locator(".release-status")
                    status = status_elem.inner_text()
                    
                    return {
                        'status': status,
                        'live': 'live' in status.lower() or 'approved' in status.lower(),
                        'in_review': 'review' in status.lower() or 'pending' in status.lower(),
                        'rejected': 'rejected' in status.lower()
                    }
                except:
                    return {'status': 'unknown'}
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _cleanup(self):
        """Закрыть браузер"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

"""
Sferoom (sferoom.space) дистрибьютор
Российский дистрибьютор
"""
import logging
import time
from pathlib import Path
from typing import Optional, Dict

from playwright.sync_api import sync_playwright, Page

from .base import BaseDistributor, AlbumInfo, UploadResult, TrackInfo

logger = logging.getLogger(__name__)


class SferoomDistributor(BaseDistributor):
    """
    Sferoom - российский дистрибьютор
    Автоматизация через браузер
    """
    
    NAME = "sferoom"
    DISPLAY_NAME = "Sferoom"
    
    BASE_URL = "https://sferoom.space"
    UPLOAD_URL = "https://sferoom.space/dashboard/releases/new"
    
    def __init__(self, cookie: str, proxy: Optional[str] = None, headless: bool = True):
        super().__init__(cookie, proxy)
        self.headless = headless
        self.page: Optional[Page] = None
        
    def authenticate(self) -> bool:
        """Проверить аутентификацию"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                
                # Sferoom использует JWT токены обычно
                context.add_cookies([{
                    'name': 'token',
                    'value': self.cookie,
                    'domain': '.sferoom.space',
                    'path': '/'
                }])
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}/dashboard", timeout=30000)
                
                try:
                    page.wait_for_selector("[data-testid='dashboard']", timeout=5000)
                    return True
                except:
                    return False
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False
    
    def upload_album(self, album: AlbumInfo, auto_submit: bool = False) -> UploadResult:
        """Загрузить альбом в Sferoom"""
        errors = self.validate_album(album)
        if errors:
            return UploadResult(success=False, message="Validation failed", errors=errors)
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1920, "height": 1080})
                
                context.add_cookies([{
                    'name': 'token',
                    'value': self.cookie,
                    'domain': '.sferoom.space',
                    'path': '/'
                }])
                
                page = context.new_page()
                self.page = page
                
                # Открываем страницу создания релиза
                logger.info("Opening Sferoom upload page...")
                page.goto(self.UPLOAD_URL, timeout=60000)
                
                # Ждём загрузки
                page.wait_for_selector("form.release-form", timeout=30000)
                
                # Заполняем форму
                self._fill_album_info(album)
                self._upload_cover(album.cover_path)
                
                # Добавляем треки
                for i, track in enumerate(album.tracks, 1):
                    self._add_track(track, i)
                
                # Сохраняем или отправляем
                if auto_submit:
                    result = self._submit_release()
                else:
                    result = self._save_draft()
                
                browser.close()
                return result
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            if self.page:
                self.page.screenshot(path="sferoom_error.png")
            return UploadResult(success=False, message=str(e), errors=[str(e)])
    
    def _fill_album_info(self, album: AlbumInfo):
        """Заполнить информацию об альбоме"""
        page = self.page
        
        # Название
        page.fill("input[name='title']", album.title)
        
        # Артист
        page.fill("input[name='artist']", album.artist)
        
        # Жанр
        genre = self._map_genre(album.primary_genre)
        page.select_option("select[name='genre']", genre)
        
        # Лейбл (если есть)
        if album.record_label:
            page.fill("input[name='label']", album.record_label)
        
        # UPC
        if album.upc:
            page.fill("input[name='upc']", album.upc)
        
        time.sleep(0.5)
    
    def _upload_cover(self, cover_path: Path):
        """Загрузить обложку"""
        page = self.page
        
        file_input = page.locator("input[type='file'][name='cover']")
        file_input.set_input_files(str(cover_path))
        
        # Ждём загрузки
        page.wait_for_selector(".cover-preview", timeout=30000)
        time.sleep(1)
    
    def _add_track(self, track: TrackInfo, index: int):
        """Добавить трек"""
        page = self.page
        
        # Кнопка добавления трека
        if index > 1:
            page.click("button.add-track")
            time.sleep(0.5)
        
        # Селектор для трека
        track_row = f".track-row:nth-child({index})"
        
        # Название
        page.fill(f"{track_row} input[name='track_title']", track.title)
        
        # Загрузка файла
        file_input = page.locator(f"{track_row} input[type='file'][name='audio']")
        file_input.set_input_files(str(track.file_path))
        
        # Ждём загрузки
        page.wait_for_selector(f"{track_row} .upload-success", timeout=120000)
        
        # ISRC
        if track.isrc:
            page.fill(f"{track_row} input[name='isrc']", track.isrc)
        
        # Текст песни
        if track.lyrics:
            page.fill(f"{track_row} textarea[name='lyrics']", track.lyrics)
        
        time.sleep(0.5)
    
    def _save_draft(self) -> UploadResult:
        """Сохранить черновик"""
        page = self.page
        
        page.click("button.save-draft")
        page.wait_for_selector(".success-message", timeout=10000)
        
        url = page.url
        release_id = url.split("/")[-1] if "/releases/" in url else None
        
        return UploadResult(
            success=True,
            distributor_id=release_id,
            message="Draft saved",
            url=url
        )
    
    def _submit_release(self) -> UploadResult:
        """Отправить на модерацию"""
        page = self.page
        
        # Согласие с правилами
        page.check("input[name='agreement']")
        
        # Отправка
        page.click("button.submit-release")
        page.wait_for_selector(".success-message", timeout=30000)
        
        return UploadResult(
            success=True,
            message="Release submitted",
            url=page.url
        )
    
    def _map_genre(self, genre: str) -> str:
        """Маппинг жанров для Sferoom"""
        mapping = {
            "pop": "Поп",
            "rock": "Рок",
            "electronic": "Электроника",
            "hip-hop": "Хип-хоп",
            "hip hop": "Хип-хоп",
            "rap": "Хип-хоп",
            "jazz": "Джаз",
            "classical": "Классика",
            "folk": "Фолк",
            "metal": "Метал",
            "alternative": "Альтернатива",
        }
        return mapping.get(genre.lower(), "Поп")
    
    def check_status(self, distributor_id: str) -> Dict:
        """Проверить статус"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context()
                
                context.add_cookies([{
                    'name': 'token',
                    'value': self.cookie,
                    'domain': '.sferoom.space',
                    'path': '/'
                }])
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}/dashboard/releases/{distributor_id}", timeout=30000)
                
                try:
                    status = page.locator(".status-badge").inner_text()
                    return {
                        'status': status,
                        'live': 'опубликован' in status.lower() or 'published' in status.lower(),
                        'in_review': 'модерация' in status.lower() or 'review' in status.lower()
                    }
                except:
                    return {'status': 'unknown'}
                finally:
                    browser.close()
                    
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

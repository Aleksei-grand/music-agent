"""
Клиент для Suno (Reverse Engineering + Playwright fallback)
API endpoints изучены через DevTools
"""
import requests
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Generator
from datetime import datetime
import time
import re
import os

from ..utils.retry import retry_with_backoff
from ..utils.rate_limiter import SUNO_RATE_LIMITER
from ..config import settings

logger = logging.getLogger(__name__)


class SunoTrack:
    """Модель трека от Suno"""
    def __init__(self, data: dict):
        self.id = data.get('id')
        self.title = data.get('title', 'Untitled')
        self.audio_url = data.get('audio_url')
        self.image_url = data.get('image_url')
        self.video_url = data.get('video_url')
        self.lyrics = data.get('metadata', {}).get('prompt', '')  # Текст песни
        self.style = data.get('metadata', {}).get('tags', '')
        self.duration = data.get('metadata', {}, {}).get('duration', 0)
        self.created_at = data.get('created_at')
        self.is_public = data.get('is_public', False)
        self.play_count = data.get('play_count', 0)
        
    def __repr__(self):
        return f"SunoTrack(id={self.id}, title='{self.title}')"


class SunoAPIClient:
    """
    Reverse Engineering клиент для Suno API
    Использует внутренние endpoints сайта
    """
    
    BASE_URL = "https://studio-api.suno.ai"
    
    def __init__(self, cookie: str, proxy: Optional[str] = None):
        self.cookie = cookie
        self.proxy = proxy
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cookie': cookie,
            'Origin': 'https://suno.com',
            'Referer': 'https://suno.com/',
        })
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
    
    def validate_cookie(self) -> bool:
        """
        Проверить валидность cookie перед использованием
        
        Returns:
            True если cookie рабочий, False если нет
        """
        logger.debug("Validating Suno cookie...")
        max_attempts = 3
        transient_errors = 0
        
        for attempt in range(1, max_attempts + 1):
            try:
                SUNO_RATE_LIMITER.acquire()
                
                response = self.session.get(
                    f"{self.BASE_URL}/api/feed/",
                    params={'limit': 1},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info("Suno cookie is valid")
                    return True
                if response.status_code in (401, 403):
                    logger.error(f"Suno cookie expired or invalid ({response.status_code})")
                    return False
                if response.status_code == 429:
                    logger.warning("Suno rate limited (429)")
                    return True  # Cookie валиден, но rate limited
                if 500 <= response.status_code < 600:
                    transient_errors += 1
                    logger.warning(
                        f"Suno cookie validation transient server error {response.status_code} "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    if attempt < max_attempts:
                        time.sleep(1.5 * attempt)
                    continue
                
                logger.warning(
                    f"Suno cookie validation returned unexpected status {response.status_code}"
                )
                return False
                    
            except requests.RequestException as e:
                transient_errors += 1
                logger.warning(
                    f"Cookie validation request error (attempt {attempt}/{max_attempts}): {e}"
                )
                if attempt < max_attempts:
                    time.sleep(1.5 * attempt)
        
        if transient_errors:
            logger.warning(
                "Suno cookie validation could not be completed due to transient errors; "
                "continuing sync and relying on main fetch step."
            )
            return True
        
        return False
    
    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        exceptions=(requests.RequestException,),
        on_retry=lambda attempt, e: logger.warning(f"Suno API retry {attempt}: {e}")
    )
    def _fetch_page(self, params: dict) -> dict:
        """Внутренний метод с retry для получения страницы"""
        SUNO_RATE_LIMITER.acquire()
        response = self.session.get(
            f"{self.BASE_URL}/api/feed/",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_library(self, limit: int = 1000) -> List[SunoTrack]:
        """
        Получить все треки из библиотеки пользователя
        Endpoint: /api/feed/
        """
        tracks = []
        cursor = None
        
        while True:
            params = {'limit': min(limit, 100)}  # Макс 100 за раз
            if cursor:
                params['cursor'] = cursor
            
            try:
                data = self._fetch_page(params)
                
                clips = data.get('clips', [])
                if not clips:
                    break
                
                for clip_data in clips:
                    track = SunoTrack(clip_data)
                    tracks.append(track)
                    logger.debug(f"Found track: {track.title} ({track.created_at})")
                
                # Пагинация
                cursor = data.get('cursor')
                if not cursor or len(tracks) >= limit:
                    break
                    
                time.sleep(0.5)  # Не DDOS'им сервер
                
            except requests.RequestException as e:
                logger.error(f"Error fetching library: {e}")
                raise
        
        logger.info(f"Loaded {len(tracks)} tracks from Suno library")
        return tracks
    
    def get_track(self, track_id: str) -> Optional[SunoTrack]:
        """
        Получить конкретный трек по ID
        Endpoint: /api/feed/?ids={id}
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/feed/",
                params={'ids': track_id},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            clips = data.get('clips', [])
            if clips:
                return SunoTrack(clips[0])
            return None
            
        except requests.RequestException as e:
            logger.error(f"Error fetching track {track_id}: {e}")
            return None
    
    def download_audio(self, track: SunoTrack, output_path: Path) -> bool:
        """Скачать аудио файл"""
        if not track.audio_url:
            logger.error(f"No audio URL for track {track.id}")
            return False
        
        try:
            response = self.session.get(track.audio_url, timeout=60, stream=True)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded audio: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return False
    
    def download_image(self, track: SunoTrack, output_path: Path) -> bool:
        """Скачать обложку"""
        if not track.image_url:
            logger.error(f"No image URL for track {track.id}")
            return False
        
        try:
            response = self.session.get(track.image_url, timeout=30)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return False


class SunoBrowserClient:
    """
    Fallback клиент через Playwright (браузерная автоматизация)
    Используется если API блокирует
    """
    
    def __init__(self, cookie: str, headless: bool = True, browser_path: Optional[str] = None):
        self.cookie = cookie
        self.headless = headless
        self.browser_path = browser_path
        
    def get_library(self) -> List[SunoTrack]:
        """Получить треки через браузер"""
        from playwright.sync_api import sync_playwright
        
        tracks = []
        
        with sync_playwright() as p:
            launch_kwargs = {"headless": self.headless}
            normalized_path = (self.browser_path or "").strip().strip('"').strip("'")
            if normalized_path and Path(normalized_path).exists():
                launch_kwargs["executable_path"] = normalized_path
                # Пробуем использовать user-data-dir (профиль браузера)
                # Для Яндекс браузера профиль обычно в %LOCALAPPDATA%\Yandex\YandexBrowser\User Data
                yandex_profile = Path(os.environ.get('LOCALAPPDATA', '')) / "Yandex" / "YandexBrowser" / "User Data"
                chrome_profile = Path(os.environ.get('LOCALAPPDATA', '')) / "Google" / "Chrome" / "User Data"
                
                if yandex_profile.exists():
                    logger.info(f"Using Yandex browser profile: {yandex_profile}")
                    launch_kwargs["args"] = [f"--user-data-dir={yandex_profile}"]
                elif chrome_profile.exists():
                    logger.info(f"Using Chrome profile: {chrome_profile}")
                    launch_kwargs["args"] = [f"--user-data-dir={chrome_profile}"]
            
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context()
            
            # Устанавливаем куки
            context.add_cookies([{
                'name': '__session',
                'value': self._extract_session_cookie(),
                'domain': '.suno.com',
                'path': '/'
            }])
            
            page = context.new_page()
            
            try:
                # Сначала пробуем получить данные напрямую через API в браузере
                logger.info("Trying to fetch data via browser API...")
                tracks = self._fetch_via_browser_api(page)
                
                if tracks:
                    logger.info(f"Successfully fetched {len(tracks)} tracks via browser API")
                    return tracks
                
                # Fallback: парсим HTML страницы
                logger.info("Falling back to HTML parsing...")
                tracks = self._fetch_via_html_parsing(page)
                
                return tracks
                
            except Exception as e:
                logger.error(f"Browser error: {e}")
                # Делаем скриншот для отладки
                try:
                    page.screenshot(path="suno_debug.png")
                    logger.info("Screenshot saved to suno_debug.png")
                except:
                    pass
                return tracks
            finally:
                browser.close()
    
    def _fetch_via_browser_api(self, page) -> List[SunoTrack]:
        """Получить треки через API запрос в браузере"""
        tracks = []
        
        try:
            # Пробуем несколько endpoints
            endpoints = [
                'https://studio-api.suno.ai/api/feed/?limit=100',
                'https://studio-api.suno.ai/api/feed/v2?limit=100',
                'https://suno.com/api/feed?limit=100',
            ]
            
            for endpoint in endpoints:
                js_code = f"""
                async () => {{
                    try {{
                        const response = await fetch('{endpoint}', {{
                            method: 'GET',
                            headers: {{
                                'Accept': 'application/json',
                                'Content-Type': 'application/json'
                            }},
                            credentials: 'include'
                        }});
                        if (!response.ok) {{
                            return {{ error: `HTTP ${{response.status}}: ${{response.statusText}}` }};
                        }}
                        const data = await response.json();
                        return {{ success: true, data: data }};
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
                """
                
                result = page.evaluate(js_code)
                
                if result and isinstance(result, dict):
                    if result.get('success') and result.get('data'):
                        logger.info(f"Successfully fetched from {endpoint}")
                        return self._parse_feed_data(result['data'])
                    elif 'error' in result:
                        logger.debug(f"Endpoint {endpoint} error: {result['error']}")
                        continue
            
            # Если все endpoints не сработали, пробуем найти данные в window.__INITIAL_STATE__ или аналогичном
            logger.info("Trying to extract data from page state...")
            state_js = """
            () => {
                // Ищем данные в глобальных переменных
                const sources = [
                    window.__INITIAL_STATE__,
                    window.__DATA__,
                    window.__PRELOADED_STATE__,
                    window.SUNO_DATA,
                    window.APP_STATE
                ];
                for (let src of sources) {
                    if (src && (src.clips || src.feed || src.tracks || src.songs)) {
                        return src;
                    }
                }
                // Ищем в script тегах
                const scripts = document.querySelectorAll('script');
                for (let script of scripts) {
                    const text = script.textContent || '';
                    if (text.includes('clips') || text.includes('feed')) {
                        const match = text.match(/\{[\s\S]*"clips"[\s\S]*\}/);
                        if (match) {
                            try {
                                return JSON.parse(match[0]);
                            } catch (e) {}
                        }
                    }
                }
                return null;
            }
            """
            state_result = page.evaluate(state_js)
            if state_result:
                logger.info("Found data in page state")
                return self._parse_feed_data(state_result)
            
            return tracks
            
        except Exception as e:
            logger.warning(f"Browser API fetch failed: {e}")
            return tracks
    
    def _parse_feed_data(self, data) -> List[SunoTrack]:
        """Парсит данные из feed API"""
        tracks = []
        
        if not isinstance(data, dict):
            return tracks
        
        clips = data.get('clips', [])
        if not clips:
            # Пробуем другие ключи
            for key in ['data', 'tracks', 'items', 'results', 'feed']:
                if key in data:
                    clips = data[key]
                    break
        
        if not isinstance(clips, list):
            logger.warning(f"Clips is not a list: {type(clips)}")
            return tracks
        
        for clip in clips:
            if not isinstance(clip, dict):
                continue
                
            track = SunoTrack(
                id=clip.get('id') or clip.get('track_id') or clip.get('clip_id', ''),
                title=clip.get('title') or clip.get('name', 'Untitled'),
                audio_url=clip.get('audio_url') or clip.get('url', ''),
                image_url=clip.get('image_url') or clip.get('cover_image_url', ''),
                created_at=clip.get('created_at') or clip.get('created', ''),
                tags=clip.get('metadata', {}).get('tags', '') if isinstance(clip.get('metadata'), dict) else '',
                is_favorite=clip.get('is_favorite', False)
            )
            
            if track.id:
                tracks.append(track)
        
        logger.info(f"Parsed {len(tracks)} tracks from feed data")
        return tracks
    
    def _fetch_via_html_parsing(self, page) -> List[SunoTrack]:
        """Получить треки через парсинг HTML"""
        tracks = []
        
        # Открываем home (library теперь редиректит сюда)
        logger.info("Opening Suno home page...")
        page.goto("https://suno.com/home", timeout=60000)
        
        # Ждём загрузки страницы
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        time.sleep(5)  # Даём время для рендеринга React
        
        # Проверяем, не редиректнуло ли на login
        current_url = page.url
        if 'login' in current_url or 'auth' in current_url:
            logger.error(f"Redirected to login page: {current_url}")
            return tracks
        
        logger.info(f"Current URL: {current_url}")
        
        # Проверяем авторизацию (наличие кнопки Sign In)
        try:
            sign_in_btn = page.query_selector("text='Sign In'")
            if sign_in_btn:
                is_visible = sign_in_btn.is_visible()
                if is_visible:
                    logger.error("❌ NOT LOGGED IN to Suno!")
                    logger.error("Please update SUNO_COOKIE in .env file")
                    logger.error("Cookie has expired or is invalid.")
                    page.screenshot(path="suno_not_logged_in.png")
                    return tracks
        except Exception as e:
            logger.debug(f"Sign In check error: {e}")
        
        # На home странице может быть несколько секций - ищем Library/My Library
        library_links = [
            "a:has-text('Library')",
            "a:has-text('My Library')",
            "a:has-text('My Songs')",
            "[data-testid='library-link']",
            "a[href*='/library']",
            "button:has-text('Library')",
        ]
        
        for link_selector in library_links:
            try:
                link = page.query_selector(link_selector)
                if link:
                    logger.info(f"Found library link: {link_selector}")
                    link.click()
                    time.sleep(3)  # Ждём загрузки библиотеки
                    logger.info(f"Clicked library link, new URL: {page.url}")
                    break
            except Exception as e:
                logger.debug(f"Library link {link_selector} not found or clickable: {e}")
                continue
        
        # Пробуем разные селекторы (Suno часто меняет дизайн)
        # Сначала ищем ССЫЛКИ на песни (это надежнее чем div'ы с классом 'track')
        selectors = [
            "a[href*='/song/']",  # Прямые ссылки на песни
            "a[href*='/clip/']",
            "a[href*='suno.com/song/']",
            "[data-testid='track-item']",
            "[data-track-id]",
            ".track-item",
            ".library-item",
            "article[data-track-id]",
            "[class*='LibraryItem']",
            "[class*='library'] > div > div",  # вложенные в library
            "div[class*='group'] a[href*='/song/']",  # группы с песнями
        ]
        
        track_elements = []
        used_selector = None
        
        for selector in selectors:
            try:
                logger.debug(f"Trying selector: {selector}")
                page.wait_for_selector(selector, timeout=10000)
                track_elements = page.query_selector_all(selector)
                if track_elements:
                    used_selector = selector
                    logger.info(f"Found {len(track_elements)} tracks using selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        if not track_elements:
            logger.error("No tracks found with any selector")
            # Делаем скриншот для отладки
            page.screenshot(path="suno_debug.png")
            logger.info("Screenshot saved to suno_debug.png")
            
            # Пробуем получить HTML для анализа
            html = page.content()
            if len(html) < 1000:
                logger.error(f"Page content too short ({len(html)} chars), possible auth issue")
            return tracks
        
        # Прокручиваем для подгрузки всех треков
        self._scroll_to_load_all(page)
        
        # Перезагружаем элементы после скролла
        if used_selector:
            track_elements = page.query_selector_all(used_selector)
        
        logger.info(f"Parsing {len(track_elements)} track elements...")
        
        # Сохраняем HTML для отладки
        try:
            html_preview = page.content()[:5000]
            with open("suno_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            logger.info("Saved page HTML to suno_page.html")
        except Exception as e:
            logger.warning(f"Could not save HTML: {e}")
        
        # Логируем первый элемент для анализа
        if track_elements:
            try:
                first_html = track_elements[0].inner_html()[:500]
                logger.info(f"First element HTML preview: {first_html}")
            except Exception as e:
                logger.warning(f"Could not get element HTML: {e}")
        
        for elem in track_elements:
            try:
                # Если элемент сам является ссылкой (a[href*='/song/'])
                tag_name = elem.evaluate("el => el.tagName.toLowerCase()")
                track_id = None
                
                if tag_name == 'a':
                    # Это ссылка - извлекаем ID прямо из href
                    href = elem.get_attribute('href')
                    logger.debug(f"Link element href: {href}")
                    if href:
                        # Ищем UUID в ссылке
                        match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', href)
                        if match:
                            track_id = match.group(0)
                            logger.debug(f"Found track_id via UUID in link href: {track_id}")
                        else:
                            # Пробуем старый формат /song/ID или /clip/ID
                            match = re.search(r'/(song|clip)/([a-f0-9-]+)', href)
                            if match:
                                track_id = match.group(2)
                                logger.debug(f"Found track_id via /song/ path: {track_id}")
                else:
                    # Это контейнер - ищем атрибуты
                    for attr in ['data-track-id', 'data-id', 'id']:
                        track_id = elem.get_attribute(attr)
                        if track_id:
                            logger.debug(f"Found track_id via attribute {attr}: {track_id}")
                            break
                    
                    # Если нет атрибута, ищем вложенные ссылки
                    if not track_id:
                        link = elem.query_selector("a[href*='/song/']") or elem.query_selector("a[href*='/clip/']")
                        if link:
                            href = link.get_attribute('href')
                            match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', href)
                            if match:
                                track_id = match.group(0)
                                logger.debug(f"Found track_id via nested link: {track_id}")
                
                if not track_id:
                    try:
                        elem_html = elem.inner_html()[:300] if elem else "N/A"
                        logger.debug(f"Skipping element without track_id. HTML: {elem_html}")
                    except:
                        logger.debug("Skipping element without track_id (could not get HTML)")
                    continue
                
                # Ищем название трека
                title = "Untitled"
                
                if tag_name == 'a':
                    # Для ссылок: текст ссылки часто является названием
                    link_text = elem.inner_text().strip()
                    if link_text and len(link_text) > 1 and 'Make a' not in link_text:
                        title = link_text
                        logger.debug(f"Found title in link text: {title}")
                    else:
                        # Или ищем img alt или aria-label
                        img = elem.query_selector("img")
                        if img:
                            alt = img.get_attribute('alt')
                            if alt:
                                title = alt
                                logger.debug(f"Found title in img alt: {title}")
                        if title == "Untitled":
                            aria = elem.get_attribute('aria-label')
                            if aria:
                                title = aria
                                logger.debug(f"Found title in aria-label: {title}")
                else:
                    # Для контейнеров пробуем разные селекторы
                    title_selectors = [
                        ".track-title",
                        "[class*='title']",
                        "h3",
                        "h4",
                        ".text-primary",
                        "span[class*='text']",
                        "a"  # сама ссылка может содержать название
                    ]
                    
                    for title_sel in title_selectors:
                        title_elem = elem.query_selector(title_sel)
                        if title_elem:
                            title_text = title_elem.inner_text().strip()
                            if title_text and len(title_text) > 1 and 'Make a' not in title_text:
                                title = title_text
                                break
                
                # Дата создания
                date_selectors = [
                    ".track-date",
                    "time",
                    "[datetime]",
                    ".date",
                ]
                
                created_at = None
                for date_sel in date_selectors:
                    date_elem = elem.query_selector(date_sel)
                    if date_elem:
                        created_at = date_elem.get_attribute('datetime') or date_elem.inner_text()
                        if created_at:
                            break
                
                # Создаём объект с минимальными данными
                track_data = {
                    'id': track_id,
                    'title': title,
                    'created_at': created_at,
                    'metadata': {}
                }
                track = SunoTrack(track_data)
                tracks.append(track)
                logger.info(f"✓ Parsed track: {title} ({track_id[:8]}...)")
                
            except Exception as e:
                logger.warning(f"Error parsing track element: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"Successfully parsed {len(tracks)} tracks from {len(track_elements)} elements")
        
        return tracks
    
    def _extract_session_cookie(self) -> str:
        """Извлечь session из cookie строки"""
        match = re.search(r'__session=([^;]+)', self.cookie)
        if match:
            return match.group(1)
        match = re.search(r'session=([^;]+)', self.cookie)
        return match.group(1) if match else self.cookie
    
    def _scroll_to_load_all(self, page):
        """Прокрутка страницы для подгрузки всех треков"""
        logger.info("Scrolling to load all tracks...")
        last_height = 0
        retries = 0
        
        while retries < 5:
            # Прокручиваем вниз
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Проверяем высоту
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                retries += 1
            else:
                retries = 0
                last_height = new_height
                logger.debug(f"Loaded more tracks, height: {new_height}")


class SunoClient:
    """
    Унифицированный клиент Suno
    Сначала пробует API (быстрее), потом браузер (надёжнее)
    """
    
    def __init__(self, cookie: str, proxy: Optional[str] = None):
        self.cookie = cookie
        self.proxy = proxy
        self.api_client = SunoAPIClient(cookie, proxy)
        self.browser_client = None  # Создаём только при необходимости
    
    def get_all_tracks(self, use_browser_fallback: bool = True) -> List[SunoTrack]:
        """
        Получить все треки
        Сначала пробует API, при неудаче - браузер
        """
        try:
            logger.info("Trying API method...")
            return self.api_client.get_library()
        except Exception as e:
            logger.warning(f"API method failed: {e}")
            
            if use_browser_fallback:
                logger.info("Falling back to browser method...")
                self.browser_client = SunoBrowserClient(
                    self.cookie,
                    headless=settings.playwright_headless,
                    browser_path=settings.playwright_browser_path or None
                )
                return self.browser_client.get_library()
            else:
                raise
    
    def download_track(self, track: SunoTrack, raw_dir: Path) -> Dict[Path, bool]:
        """
        Скачать трек полностью (audio + image + metadata)
        Returns: {file: success}
        """
        results = {}
        track_dir = raw_dir / track.id
        track_dir.mkdir(parents=True, exist_ok=True)
        
        # Скачиваем аудио
        audio_path = track_dir / "audio.mp3"
        if not audio_path.exists():
            results['audio'] = self.api_client.download_audio(track, audio_path)
        else:
            logger.info(f"Audio already exists: {audio_path}")
            results['audio'] = True
        
        # Скачиваем обложку
        image_path = track_dir / "cover.jpg"
        if not image_path.exists():
            results['image'] = self.api_client.download_image(track, image_path)
        else:
            logger.info(f"Image already exists: {image_path}")
            results['image'] = True
        
        # Сохраняем метаданные
        metadata_path = track_dir / "metadata.json"
        if not metadata_path.exists():
            metadata = {
                'id': track.id,
                'title': track.title,
                'style': track.style,
                'lyrics': track.lyrics,
                'duration': track.duration,
                'created_at': track.created_at,
                'audio_url': track.audio_url,
                'image_url': track.image_url,
                'downloaded_at': datetime.utcnow().isoformat()
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            results['metadata'] = True
            logger.info(f"Saved metadata: {metadata_path}")
        else:
            results['metadata'] = True
        
        return results

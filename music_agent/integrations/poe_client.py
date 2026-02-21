"""
Клиент для Poe API (poe.com)
Используется для:
- Перевода текстов песен (модель Claude-Opus-4.6)
- Генерации обложек (модель Nano-Banana-Pro)
"""
import fastapi_poe as fp
from typing import List, Optional, Generator
import logging
import re
import base64
import time
from pathlib import Path

from ..utils.retry import retry_with_backoff
from ..utils.rate_limiter import POE_RATE_LIMITER

logger = logging.getLogger(__name__)


class PoeClient:
    """Клиент для работы с Poe API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    @retry_with_backoff(
        max_retries=3,
        initial_delay=2.0,
        exceptions=(Exception,),
        on_retry=lambda attempt, e: logger.warning(f"Poe API retry {attempt}: {e}")
    )
    def translate_lyrics(
        self, 
        text: str, 
        target_language: str = "english",
        model: str = "Claude-Opus-4.6",
        context: str = ""
    ) -> str:
        """
        Перевод текста песни
        
        Args:
            text: Исходный текст на русском
            target_language: Целевой язык
            model: Модель для перевода
            context: Дополнительный контекст (жанр, настроение)
        """
        system_prompt = f"""You are a professional translator specializing in song lyrics.
Translate the following lyrics from Russian to {target_language}.
Preserve the rhyme, rhythm, and emotional impact of the original.
Maintain the poetic structure and metaphors where possible.
{context}

Provide only the translated lyrics without explanations."""

        messages = [
            fp.ProtocolMessage(role="system", content=system_prompt),
            fp.ProtocolMessage(role="user", content=text)
        ]
        
        # Rate limiting
        POE_RATE_LIMITER.acquire()
        
        response = ""
        try:
            for partial in fp.get_bot_response_sync(
                messages=messages,
                bot_name=model,
                api_key=self.api_key
            ):
                response += partial
                
            logger.info(f"Translated text using {model}")
            POE_RATE_LIMITER.on_success()
            return response.strip()
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            POE_RATE_LIMITER.on_error()
            raise
    
    def generate_cover_prompt(
        self,
        album_title: str,
        song_lyrics: str = "",
        style: str = "",
        mood: str = ""
    ) -> str:
        """
        Создание промпта для генерации обложки на основе песни
        
        Args:
            album_title: Название альбома
            song_lyrics: Текст песни (для понимания тематики)
            style: Музыкальный стиль
            mood: Настроение
        """
        system_prompt = """You are an expert in album cover design and visual art.
Create a detailed prompt for generating an album cover.
The prompt should be vivid, artistic, and suitable for AI image generation.
Include details about: style, colors, composition, mood, and visual elements.

The prompt should be in English and optimized for image generation AI."""

        user_prompt = f"""Create a prompt for an album cover with the following details:
Title: {album_title}
Style: {style or "Not specified"}
Mood: {mood or "Not specified"}
Lyrics excerpt: {song_lyrics[:500] if song_lyrics else "Not provided"}

Create a detailed, artistic prompt for image generation.
The cover should be square (1:1 aspect ratio) suitable for music platforms.
Include details about colors, lighting, style, and atmosphere."""

        messages = [
            fp.ProtocolMessage(role="system", content=system_prompt),
            fp.ProtocolMessage(role="user", content=user_prompt)
        ]
        
        response = ""
        try:
            for partial in fp.get_bot_response_sync(
                messages=messages,
                bot_name="Claude-Opus-4.6",  # Для создания промпта используем Claude
                api_key=self.api_key
            ):
                response += partial
                
            return response.strip()
            
        except Exception as e:
            logger.error(f"Cover prompt generation error: {e}")
            raise
    
    @retry_with_backoff(
        max_retries=3,
        initial_delay=2.0,
        exceptions=(Exception,),
        on_retry=lambda attempt, e: logger.warning(f"Poe API retry {attempt}: {e}")
    )
    def generate_cover_image(
        self,
        prompt: str,
        model: str = "Nano-Banana-Pro",
        output_path: Optional[Path] = None
    ) -> str:
        """
        Генерация обложки альбома
        
        Args:
            prompt: Описание обложки (от generate_cover_prompt)
            model: Модель для генерации (Nano-Banana-Pro)
            output_path: Куда сохранить изображение (опционально)
            
        Returns:
            Путь к сохранённому файлу или base64 строка
        """
        system_prompt = """You are an expert album cover designer. 
Create a stunning, professional album cover artwork.
The image should be 3000x3000 pixels, high quality, suitable for music distribution.
No text or letters on the image (the title will be added later if needed)."""

        messages = [
            fp.ProtocolMessage(role="system", content=system_prompt),
            fp.ProtocolMessage(role="user", content=prompt)
        ]
        
        # Rate limiting
        POE_RATE_LIMITER.acquire()
        
        try:
            logger.info(f"Generating cover with {model}...")
            
            # Собираем полный ответ
            full_response = ""
            for partial in fp.get_bot_response_sync(
                messages=messages,
                bot_name=model,
                api_key=self.api_key
            ):
                full_response += partial
            
            # Проверяем, вернул ли Poe URL или base64
            # Обычно Poe возвращает markdown с изображением: ![description](url)
            # или base64: data:image/png;base64,...
            
            image_url = None
            base64_data = None
            
            # Ищем URL в markdown
            url_match = re.search(r'!\[.*?\]\((.*?)\)', full_response)
            if url_match:
                image_url = url_match.group(1)
                logger.info(f"Found image URL in response")
            
            # Ищем base64
            base64_match = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', full_response)
            if base64_match:
                base64_data = base64_match.group(2)
                logger.info(f"Found base64 image data")
            
            # Если нашли URL - скачиваем
            if image_url:
                import requests
                response = requests.get(image_url, timeout=60)
                response.raise_for_status()
                image_bytes = response.content
                
                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)
                    logger.info(f"Saved cover to: {output_path}")
                    POE_RATE_LIMITER.on_success()
                    return str(output_path)
                else:
                    # Возвращаем base64
                    POE_RATE_LIMITER.on_success()
                    return base64.b64encode(image_bytes).decode()
            
            # Если base64
            elif base64_data:
                image_bytes = base64.b64decode(base64_data)
                
                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)
                    logger.info(f"Saved cover to: {output_path}")
                    POE_RATE_LIMITER.on_success()
                    return str(output_path)
                else:
                    POE_RATE_LIMITER.on_success()
                    return base64_data
            
            else:
                # Poe может вернуть описание вместо изображения
                # В таком случае нужно попросить сгенерировать изображение ещё раз
                logger.warning("No image found in response, got text instead")
                logger.debug(f"Response: {full_response[:500]}")
                POE_RATE_LIMITER.on_error()
                raise ValueError("Model returned text instead of image. Try again or check model name.")
                
        except Exception as e:
            logger.error(f"Cover generation error: {e}")
            POE_RATE_LIMITER.on_error()
            raise
    
    def analyze_song_for_cover(
        self,
        lyrics: str,
        title: str,
        style: str = ""
    ) -> dict:
        """
        Анализ песни для создания концепции обложки
        
        Returns:
            dict с ключами: mood, colors, themes, visual_elements
        """
        system_prompt = """Analyze the song and extract key visual elements for an album cover.
Return your analysis in this exact format:
MOOD: [primary mood]
COLORS: [suggested color palette]
THEMES: [main themes]
VISUAL_ELEMENTS: [key visual elements]
COMPOSITION: [suggested composition]
STYLE: [art style - e.g., abstract, photorealistic, minimalist, etc.]"""

        user_prompt = f"""Title: {title}
Style: {style or "Not specified"}
Lyrics:
{lyrics[:1000]}

Analyze this song for album cover design."""

        messages = [
            fp.ProtocolMessage(role="system", content=system_prompt),
            fp.ProtocolMessage(role="user", content=user_prompt)
        ]
        
        response = ""
        for partial in fp.get_bot_response_sync(
            messages=messages,
            bot_name="Claude-Opus-4.6",
            api_key=self.api_key
        ):
            response += partial
        
        # Парсинг ответа
        result = {}
        for line in response.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.lower().strip()] = value.strip()
        
        return result

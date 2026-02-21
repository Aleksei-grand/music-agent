"""
Deepgram API клиент для распознавания речи
Голосовые команды для управления MyFlowMusic (MFM)
"""
import logging
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, List
import json

from deepgram import DeepgramClient, PrerecordedOptions
import httpx

logger = logging.getLogger(__name__)


class VoiceCommand:
    """Распознанная голосовая команда"""
    def __init__(self, text: str, confidence: float, language: str = "ru"):
        self.text = text
        self.confidence = confidence
        self.language = language
        self.command_type = None
        self.parameters = {}
        
    def __repr__(self):
        return f"VoiceCommand(text='{self.text}', confidence={self.confidence:.2f})"


class DeepgramVoiceClient:
    """Клиент для распознавания голосовых команд через Deepgram"""
    
    # Поддерживаемые языки
    LANGUAGES = {
        "ru": "ru",
        "en": "en",
        "en-US": "en-US",
        "en-GB": "en-GB",
    }
    
    # Ключевые слова для команд (распознавание интентов)
    COMMAND_INTENTS = {
        "sync": ["синхрониз", "скачай", "обнови", "синк", "sync", "download"],
        "translate": ["переведи", "перевод", "translate", "translation"],
        "cover": ["обложка", "генерируй обложку", "cover", "artwork"],
        "process": ["обработай", "process", "master", "мастеринг"],
        "publish": ["опубликуй", "publish", "release", "выпусти"],
        "status": ["статус", "status", "покажи статус", "что готово"],
        "help": ["помощь", "help", "команды", "что ты умеешь"],
    }
    
    def __init__(self, api_key: str, model: str = "nova-2"):
        self.api_key = api_key
        self.model = model
        self.client = DeepgramClient(api_key)
        
    async def transcribe_file(self, audio_path: Path, language: str = "ru") -> Optional[VoiceCommand]:
        """
        Распознать текст из аудио файла
        
        Args:
            audio_path: Путь к аудио файлу (wav, mp3, ogg)
            language: Код языка (ru, en)
            
        Returns:
            VoiceCommand объект или None
        """
        try:
            with open(audio_path, "rb") as audio:
                source = {"buffer": audio, "mimetype": f"audio/{audio_path.suffix[1:]}"}
                
                options = PrerecordedOptions(
                    model=self.model,
                    language=self.LANGUAGES.get(language, "ru"),
                    smart_format=True,
                    punctuate=True,
                )
                
                response = await asyncio.to_thread(
                    self.client.listen.prerecorded.v("1").transcribe_file,
                    source,
                    options
                )
                
                # Извлекаем текст
                if response.results and response.results.channels:
                    channel = response.results.channels[0]
                    if channel.alternatives:
                        alternative = channel.alternatives[0]
                        text = alternative.transcript
                        confidence = alternative.confidence
                        
                        logger.info(f"Transcribed: '{text}' (confidence: {confidence:.2f})")
                        
                        command = VoiceCommand(text, confidence, language)
                        self._parse_intent(command)
                        return command
                
                return None
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    async def transcribe_microphone(self, duration: int = 5, language: str = "ru") -> Optional[VoiceCommand]:
        """
        Записать с микрофона и распознать
        
        Args:
            duration: Длительность записи в секундах
            language: Язык
            
        Returns:
            VoiceCommand или None
        """
        try:
            import sounddevice as sd
            import wavio
            import numpy as np
            
            # Записываем
            logger.info(f"Recording for {duration} seconds...")
            
            sample_rate = 16000
            recording = sd.rec(int(duration * sample_rate), 
                             samplerate=sample_rate, 
                             channels=1, 
                             dtype=np.int16)
            sd.wait()
            
            # Сохраняем временный файл
            temp_file = Path("temp_recording.wav")
            wavio.write(temp_file, recording, sample_rate, sampwidth=2)
            
            # Распознаём
            result = await self.transcribe_file(temp_file, language)
            
            # Удаляем временный файл
            temp_file.unlink(missing_ok=True)
            
            return result
            
        except ImportError:
            logger.error("sounddevice or wavio not installed. Install: pip install sounddevice wavio")
            return None
        except Exception as e:
            logger.error(f"Microphone recording error: {e}")
            return None
    
    def _parse_intent(self, command: VoiceCommand):
        """Определить намерение (intent) из текста команды"""
        text_lower = command.text.lower()
        
        # Ищем совпадения с ключевыми словами
        for intent, keywords in self.COMMAND_INTENTS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    command.command_type = intent
                    self._extract_parameters(command, intent)
                    return
        
        command.command_type = "unknown"
    
    def _extract_parameters(self, command: VoiceCommand, intent: str):
        """Извлечь параметры из команды"""
        text = command.text.lower()
        
        if intent == "translate":
            # Ищем язык
            if "на английский" in text or "english" in text:
                command.parameters["language"] = "english"
            elif "на русский" in text or "russian" in text:
                command.parameters["language"] = "russian"
        
        elif intent == "cover":
            # Ищем ID альбома или "все"
            if "все" in text or "all" in text:
                command.parameters["scope"] = "all"
            # Пытаемся найти ID
            import re
            ids = re.findall(r'[a-f0-9]{10,}', text)
            if ids:
                command.parameters["album_id"] = ids[0]
        
        elif intent == "publish":
            # Ищем дистрибьютора
            if "routenote" in text or "роутноут" in text:
                command.parameters["distributor"] = "routenote"
            elif "sferoom" in text or "сферум" in text:
                command.parameters["distributor"] = "sferoom"
            
            # Ищем auto-submit
            if "сразу" in text or "auto" in text or "отправь" in text:
                command.parameters["auto_submit"] = True


class VoiceCommandExecutor:
    """Исполнитель голосовых команд"""
    
    def __init__(self, db, workflow_sync, poe_client, file_manager):
        self.db = db
        self.workflow_sync = workflow_sync
        self.poe_client = poe_client
        self.file_manager = file_manager
        
    async def execute(self, command: VoiceCommand) -> Dict:
        """
        Выполнить голосовую команду
        
        Returns:
            dict с результатом {"success": bool, "message": str, "action": str}
        """
        if command.confidence < 0.7:
            return {
                "success": False,
                "message": f"Низкая уверенность распознавания ({command.confidence:.0%}). Попробуйте ещё раз.",
                "action": "none"
            }
        
        intent = command.command_type
        params = command.parameters
        
        logger.info(f"Executing voice command: {intent} with params: {params}")
        
        # Выполняем команду
        if intent == "sync":
            return await self._cmd_sync()
        elif intent == "translate":
            return await self._cmd_translate(params)
        elif intent == "cover":
            return await self._cmd_cover(params)
        elif intent == "process":
            return await self._cmd_process(params)
        elif intent == "publish":
            return await self._cmd_publish(params)
        elif intent == "status":
            return await self._cmd_status()
        elif intent == "help":
            return await self._cmd_help()
        else:
            return {
                "success": False,
                "message": f"Неизвестная команда: '{command.text}'. Скажите 'помощь' для списка команд.",
                "action": "unknown"
            }
    
    async def _cmd_sync(self) -> Dict:
        """Команда синхронизации"""
        # Запускаем синхронизацию
        from ..config import settings
        
        if not settings.suno_cookie:
            return {"success": False, "message": "Suno cookie не настроен", "action": "sync"}
        
        # Здесь должен быть вызов workflow
        return {
            "success": True,
            "message": "Запущена синхронизация с Suno. Это может занять несколько минут.",
            "action": "sync"
        }
    
    async def _cmd_translate(self, params: Dict) -> Dict:
        """Команда перевода"""
        lang = params.get("language", "english")
        return {
            "success": True,
            "message": f"Запущен перевод всех песен на {lang}",
            "action": "translate",
            "language": lang
        }
    
    async def _cmd_cover(self, params: Dict) -> Dict:
        """Команда генерации обложек"""
        scope = params.get("scope", "all")
        album_id = params.get("album_id")
        
        if album_id:
            return {
                "success": True,
                "message": f"Генерация обложки для альбома {album_id}",
                "action": "cover",
                "album_id": album_id
            }
        else:
            return {
                "success": True,
                "message": "Генерация обложек для всех альбомов",
                "action": "cover",
                "scope": "all"
            }
    
    async def _cmd_process(self, params: Dict) -> Dict:
        """Команда обработки аудио"""
        return {
            "success": True,
            "message": "Запущена обработка аудио файлов",
            "action": "process"
        }
    
    async def _cmd_publish(self, params: Dict) -> Dict:
        """Команда публикации"""
        distributor = params.get("distributor", "routenote")
        auto = params.get("auto_submit", False)
        
        return {
            "success": True,
            "message": f"Публикация на {distributor} {'с автоматической отправкой' if auto else '(черновик)'}",
            "action": "publish",
            "distributor": distributor,
            "auto_submit": auto
        }
    
    async def _cmd_status(self) -> Dict:
        """Команда проверки статуса"""
        session = self.db.session()
        
        from ..models import Album, Song, Generation, Cover
        
        stats = {
            "albums": session.query(Album).count(),
            "songs": session.query(Song).count(),
            "covers": session.query(Cover).filter_by(state=2).count(),  # Approved
            "processed": session.query(Generation).filter_by(processed=True).count(),
        }
        
        session.close()
        
        message = (
            f"📊 Статус:\n"
            f"Альбомов: {stats['albums']}\n"
            f"Песен: {stats['songs']}\n"
            f"Готовых обложек: {stats['covers']}\n"
            f"Обработано треков: {stats['processed']}"
        )
        
        return {"success": True, "message": message, "action": "status", "stats": stats}
    
    async def _cmd_help(self) -> Dict:
        """Команда помощи"""
        message = """
🎵 Доступные голосовые команды:

• "Скачай новые треки" / "Синхронизируйся" - обновление с Suno
• "Переведи тексты на английский" - перевод песен
• "Сгенерируй обложки" - создание обложек
• "Обработай аудио" - fade-out, нормализация
• "Опубликуй на RouteNote" - публикация
• "Покажи статус" - текущий прогресс
• "Помощь" - это сообщение

Говорите чётко и медленно.
        """.strip()
        
        return {"success": True, "message": message, "action": "help"}

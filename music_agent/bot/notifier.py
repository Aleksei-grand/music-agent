"""
Telegram Notifier - уведомления о завершении задач
"""
import logging
from typing import Optional, List
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TaskNotifier:
    """
    Отправка уведомлений в Telegram о завершении задач
    """
    
    def __init__(self, bot_token: str, chat_ids: Optional[List[str]] = None):
        """
        Args:
            bot_token: Токен Telegram бота
            chat_ids: Список chat_id для уведомлений (если None - используем все активные чаты)
        """
        self.bot = Bot(token=bot_token) if bot_token else None
        self.chat_ids = set(chat_ids or [])
        self.subscribers: set = set()  # Автоматически подписанные пользователи
    
    def add_subscriber(self, chat_id: str):
        """Добавить подписчика"""
        self.subscribers.add(str(chat_id))
        logger.info(f"Added notification subscriber: {chat_id}")
    
    def remove_subscriber(self, chat_id: str):
        """Удалить подписчика"""
        self.subscribers.discard(str(chat_id))
    
    def _get_target_chats(self) -> List[str]:
        """Получить список чатов для отправки"""
        if self.chat_ids:
            return list(self.chat_ids)
        return list(self.subscribers)
    
    async def notify_task_completed(
        self,
        task_type: str,
        task_name: str,
        success: bool,
        details: Optional[dict] = None,
        error: Optional[str] = None
    ):
        """
        Отправить уведомление о завершении задачи
        
        Args:
            task_type: Тип задачи (sync, translate, cover, process, publish)
            task_name: Название задачи
            success: Успешно ли выполнена
            details: Дополнительные детали
            error: Текст ошибки если неуспешно
        """
        if not self.bot:
            return
        
        # Emoji по типу задачи
        task_emojis = {
            "sync": "🔄",
            "translate": "🌐",
            "cover": "🎨",
            "process": "🎵",
            "publish": "📤",
            "default": "✅"
        }
        
        emoji = task_emojis.get(task_type, task_emojis["default"])
        status_emoji = "✅" if success else "❌"
        
        # Формируем сообщение
        message = f"{status_emoji} <b>{task_name}</b>\n\n"
        
        if success:
            message += f"{emoji} Задача выполнена успешно!\n"
            
            if details:
                message += "\n📊 Результаты:\n"
                for key, value in details.items():
                    # Форматируем ключ
                    key_display = {
                        "downloaded": "Скачано",
                        "translated": "Переведено",
                        "processed": "Обработано",
                        "albums_created": "Альбомов создано",
                        "cover_id": "ID обложки",
                        "distributor_id": "ID дистрибьютора"
                    }.get(key, key)
                    message += f"  • {key_display}: {value}\n"
        else:
            message += f"❌ <b>Ошибка:</b>\n{error or 'Неизвестная ошибка'}\n"
        
        message += f"\n🕐 {datetime.now().strftime('%H:%M:%S')}"
        
        # Отправляем
        for chat_id in self._get_target_chats():
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify {chat_id}: {e}")
    
    async def notify_sync_completed(self, stats: dict, success: bool = True, error: str = None):
        """Уведомление о завершении синхронизации"""
        await self.notify_task_completed(
            task_type="sync",
            task_name="Синхронизация с Suno",
            success=success,
            details=stats if success else None,
            error=error
        )
    
    async def notify_translation_completed(
        self,
        album_title: str,
        translated: int,
        total: int,
        success: bool = True,
        error: str = None
    ):
        """Уведомление о завершении перевода"""
        await self.notify_task_completed(
            task_type="translate",
            task_name=f"Перевод: {album_title}",
            success=success,
            details={"translated": f"{translated}/{total}"},
            error=error
        )
    
    async def notify_cover_completed(
        self,
        album_title: str,
        cover_id: Optional[str] = None,
        success: bool = True,
        error: str = None
    ):
        """Уведомление о генерации обложки"""
        details = {"cover_id": cover_id} if cover_id else {}
        await self.notify_task_completed(
            task_type="cover",
            task_name=f"Обложка: {album_title}",
            success=success,
            details=details,
            error=error
        )
    
    async def notify_processing_completed(
        self,
        album_title: str,
        processed: int,
        total: int,
        success: bool = True,
        error: str = None
    ):
        """Уведомление об обработке аудио"""
        await self.notify_task_completed(
            task_type="process",
            task_name=f"Обработка: {album_title}",
            success=success,
            details={"processed": f"{processed}/{total}"},
            error=error
        )
    
    async def notify_publish_completed(
        self,
        album_title: str,
        distributor: str,
        distributor_id: Optional[str] = None,
        success: bool = True,
        error: str = None
    ):
        """Уведомление о публикации"""
        details = {"distributor": distributor}
        if distributor_id:
            details["distributor_id"] = distributor_id
        
        await self.notify_task_completed(
            task_type="publish",
            task_name=f"Публикация: {album_title}",
            success=success,
            details=details,
            error=error
        )


# Глобальный экземпляр (инициализируется при старте)
notifier: Optional[TaskNotifier] = None


def init_notifier(bot_token: str, chat_ids: Optional[List[str]] = None):
    """Инициализировать глобальный notifier"""
    global notifier
    notifier = TaskNotifier(bot_token, chat_ids)
    return notifier

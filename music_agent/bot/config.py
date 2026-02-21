"""
Конфигурация Telegram бота
"""
from pydantic_settings import BaseSettings
from typing import List


class BotConfig(BaseSettings):
    """Настройки бота"""
    
    # Telegram Bot Token от @BotFather
    telegram_bot_token: str = ""
    
    # ID администраторов (список чисел)
    telegram_admin_ids: List[int] = []
    
    # Режим работы: polling или webhook
    bot_mode: str = "polling"  # polling | webhook
    
    # Webhook URL (если режим webhook)
    webhook_url: str = ""
    webhook_port: int = 8443
    
    # Путь для хранения временных файлов
    bot_temp_dir: str = "./temp/bot"
    
    # Максимальный размер файла (MB)
    max_file_size_mb: int = 50
    
    class Config:
        env_prefix = "MUSIC_AGENT_"
        env_file = ".env"


bot_config = BotConfig()


# Тексты сообщений
class BotMessages:
    """Сообщения бота"""
    
    START = """
🌊 <b>MyFlowMusic Bot</b>

Привет! Я помогу тебе управлять музыкой:
• Скачивать треки с Suno
• Переводить тексты
• Генерировать обложки
• Публиковать на дистрибьюторах

Используй /help для списка команд
    """
    
    HELP = """
📋 <b>Команды:</b>

<b>🎵 Основные:</b>
/sync - Скачать новые треки с Suno
/translate - Перевести тексты
/cover - Сгенерировать обложки
/process - Обработать аудио
/publish - Опубликовать альбом
/status - Показать статус

<b>⚙️ Управление:</b>
/cancel - Отменить текущую операцию
/settings - Настройки
/vault - История работы

<b>❓ Помощь:</b>
/help - Это сообщение
/about - О боте

💡 <i>Совет: Можно использовать кнопки внизу</i>
    """
    
    NOT_AUTHORIZED = "❌ У вас нет доступа к этому боту."
    
    SYNC_STARTED = """
🔄 <b>Синхронизация запущена</b>

Скачиваю треки с Suno...
Это может занять несколько минут.
    """
    
    SYNC_COMPLETE = """
✅ <b>Синхронизация завершена</b>

📥 Скачано: {downloaded}
⏭️ Пропущено: {skipped}
💿 Альбомов создано: {albums}
    """
    
    CHOICE_ALBUM = "📀 Выберите альбом:"
    CHOICE_DISTRIBUTOR = "🌐 Выберите дистрибьютора:"
    
    PROCESSING = "⏳ Обрабатываю..."
    COMPLETED = "✅ Готово!"
    ERROR = "❌ Ошибка: {error}"

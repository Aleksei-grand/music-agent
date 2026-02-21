#!/usr/bin/env python3
"""
Запуск Telegram бота
"""
import asyncio
import logging
from pathlib import Path
import sys

# Добавляем путь к myflowmusic
sys.path.insert(0, str(Path(__file__).parent))

from music_agent.config import settings
from music_agent.models import Database
from music_agent.integrations.poe_client import PoeClient
from music_agent.workflow.sync_suno import SunoSyncWorkflow
from music_agent.utils.file_manager import FileManager
from music_agent.bot.bot import MusicAgentBot


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )


async def main():
    """Главная функция"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting MyFlowMusic Bot...")
    
    # Проверяем конфигурацию
    if not settings.telegram_bot_token:
        logger.error("Telegram bot token not configured!")
        print("❌ Ошибка: MUSIC_AGENT_TELEGRAM_BOT_TOKEN не настроен")
        print("Добавьте токен в .env файл")
        return
    
    # Инициализируем компоненты
    logger.info("Initializing components...")
    
    db = Database(settings.db_type, settings.db_conn).connect()
    
    poe_client = None
    if settings.poe_api_key:
        poe_client = PoeClient(settings.poe_api_key)
        logger.info("Poe client initialized")
    
    file_manager = FileManager(settings.fs_conn)
    workflow_sync = SunoSyncWorkflow(db, poe_client)
    
    # Создаём и запускаем бота
    bot = MusicAgentBot(db, workflow_sync, poe_client, file_manager)
    
    try:
        logger.info("Bot starting...")
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")

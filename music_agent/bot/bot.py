"""
Telegram Bot - точка входа
Smart Architecture: Router + Handlers + Middleware
"""
import logging
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from .config import bot_config, BotMessages
from ..vault.manager import VaultManager
from ..utils.process_manager import process_manager, ProcessTask

logger = logging.getLogger(__name__)

# Хранение связи user_id -> task_id для возможности отмены
user_active_tasks: Dict[int, str] = {}


class ProgressTracker:
    """Отслеживание прогресса операции с обновлением сообщения"""
    
    def __init__(self, query, operation_name: str, steps: list):
        self.query = query
        self.operation_name = operation_name
        self.steps = steps
        self.current_step = 0
        self.message = None
        self.cancelled = False
        
    async def start(self):
        """Начать отслеживание"""
        self.start_time = asyncio.get_event_loop().time()
        await self._update()
        
    async def next_step(self, detail: str = ""):
        """Перейти к следующему шагу"""
        if self.cancelled:
            return False
        self.current_step += 1
        await self._update(detail)
        return True
        
    async def _update(self, detail: str = ""):
        """Обновить сообщение"""
        if self.cancelled:
            return
            
        progress = int((self.current_step / len(self.steps)) * 100)
        elapsed = int(asyncio.get_event_loop().time() - self.start_time)
        
        bars_filled = int(progress / 10)
        progress_bar = "█" * bars_filled + "░" * (10 - bars_filled)
        
        text = f"<b>{self.operation_name}</b>\n\n"
        text += f"{progress_bar} {progress}%\n"
        text += f"⏱ {elapsed}с\n\n"
        
        for i, step in enumerate(self.steps):
            if i < self.current_step:
                text += f"✅ {step}\n"
            elif i == self.current_step:
                text += f"⏳ <b>{step}</b>\n"
            else:
                text += f"⬜ {step}\n"
        
        if detail:
            text += f"\n<i>{detail}</i>"
        
        try:
            await self.query.edit_message_text(text, parse_mode='HTML')
        except Exception:
            pass  # Игнорируем ошибки редактирования (сообщение не изменилось)
            
    async def success(self, result_text: str):
        """Успешное завершение"""
        if self.cancelled:
            return
        elapsed = int(asyncio.get_event_loop().time() - self.start_time)
        text = f"✅ <b>{self.operation_name} — Готово!</b>\n\n"
        text += f"⏱ Время: {elapsed}с\n\n"
        text += result_text
        
        try:
            await self.query.edit_message_text(text, parse_mode='HTML')
        except Exception:
            pass
            
    async def error(self, error_msg: str):
        """Ошибка"""
        if self.cancelled:
            return
        elapsed = int(asyncio.get_event_loop().time() - self.start_time)
        text = f"❌ <b>{self.operation_name} — Ошибка</b>\n\n"
        text += f"⏱ Время: {elapsed}с\n"
        text += f"\n<code>{error_msg[:500]}</code>"
        
        try:
            await self.query.edit_message_text(text, parse_mode='HTML')
        except Exception:
            pass
            
    def cancel(self):
        """Отменить операцию"""
        self.cancelled = True


class MusicAgentBot:
    """
    Главный класс бота
    Использует паттерн Router + Handlers
    """
    
    def __init__(self, db, workflow_sync, poe_client, file_manager):
        self.db = db
        self.workflow_sync = workflow_sync
        self.poe_client = poe_client
        self.file_manager = file_manager
        self.vault = VaultManager()
        
        self.application: Optional[Application] = None
        
        # Состояния для ConversationHandler
        self.STATES = {
            'MENU': 0,
            'SELECT_ALBUM': 1,
            'SELECT_DISTRIBUTOR': 2,
            'CONFIRM': 3,
        }
    
    async def initialize(self):
        """Инициализация бота"""
        if not bot_config.telegram_bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Создаём приложение
        self.application = (
            Application.builder()
            .token(bot_config.telegram_bot_token)
            .build()
        )
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("Bot initialized")
    
    async def run(self):
        """
        Запуск бота с graceful shutdown
        """
        if not self.application:
            await self.initialize()
        
        import signal
        import sys
        
        # Флаг для graceful shutdown
        self._shutdown_event = False
        
        def signal_handler(sig, frame):
            """Обработчик сигналов SIGINT, SIGTERM"""
            logger.info(f"Received signal {sig}, initiating graceful shutdown...")
            self._shutdown_event = True
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Инициализация
        await self.application.initialize()
        await self.application.start()
        
        # Запускаем polling в отдельной задаче
        poll_task = asyncio.create_task(
            self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        )
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        # Ждём сигнала shutdown
        try:
            while not self._shutdown_event:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main task cancelled")
        
        # Graceful shutdown
        logger.info("Stopping bot...")
        
        # Отменяем задачу polling
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        
        # Останавливаем приложение
        await self.application.stop()
        await self.application.shutdown()
        
        logger.info("Bot stopped gracefully")
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        app = self.application
        
        # Базовые команды
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("cancel", self._cmd_cancel))
        app.add_handler(CommandHandler("about", self._cmd_about))
        
        # Основные команды
        app.add_handler(CommandHandler("sync", self._cmd_sync))
        app.add_handler(CommandHandler("status", self._cmd_status))
        
        # Conversation handlers для сложных сценариев
        # Translate
        translate_conv = ConversationHandler(
            entry_points=[CommandHandler("translate", self._cmd_translate_start)],
            states={
                self.STATES['SELECT_ALBUM']: [
                    CallbackQueryHandler(self._callback_select_album, pattern="^album:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self._cmd_cancel)],
        )
        app.add_handler(translate_conv)
        
        # Cover
        cover_conv = ConversationHandler(
            entry_points=[CommandHandler("cover", self._cmd_cover_start)],
            states={
                self.STATES['SELECT_ALBUM']: [
                    CallbackQueryHandler(self._callback_select_album_cover, pattern="^cover_album:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self._cmd_cancel)],
        )
        app.add_handler(cover_conv)
        
        # Process (с превью и подтверждением)
        process_conv = ConversationHandler(
            entry_points=[CommandHandler("process", self._cmd_process_start)],
            states={
                self.STATES['SELECT_ALBUM']: [
                    CallbackQueryHandler(self._callback_select_album_process, pattern="^process_album:")
                ],
                self.STATES['CONFIRM']: [
                    CallbackQueryHandler(self._callback_confirm_process, pattern="^process_confirm:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self._cmd_cancel)],
        )
        app.add_handler(process_conv)
        
        # Publish
        publish_conv = ConversationHandler(
            entry_points=[CommandHandler("publish", self._cmd_publish_start)],
            states={
                self.STATES['SELECT_ALBUM']: [
                    CallbackQueryHandler(self._callback_select_album_publish, pattern="^publish_album:")
                ],
                self.STATES['SELECT_DISTRIBUTOR']: [
                    CallbackQueryHandler(self._callback_select_distributor, pattern="^distributor:")
                ],
                self.STATES['CONFIRM']: [
                    CallbackQueryHandler(self._callback_confirm_publish, pattern="^confirm:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self._cmd_cancel)],
        )
        app.add_handler(publish_conv)
        
        # Vault
        app.add_handler(CommandHandler("vault", self._cmd_vault))
        
        # Обработка ошибок
        app.add_error_handler(self._error_handler)
    
    # ============ Базовые команды ============
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        if not self._check_auth(update.effective_user.id):
            await update.message.reply_text(BotMessages.NOT_AUTHORIZED)
            return
        
        await update.message.reply_text(
            BotMessages.START,
            parse_mode='HTML',
            reply_markup=self._get_main_keyboard()
        )
        
        # Логируем
        self.vault.log_conversation(
            user_msg="/start",
            assistant_response="Bot started",
            source="telegram"
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            BotMessages.HELP,
            parse_mode='HTML'
        )
    
    async def _cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /cancel - отмена активной задачи"""
        user_id = update.effective_user.id
        
        # Проверяем, есть ли активная задача
        if user_id in user_active_tasks:
            task_id = user_active_tasks[user_id]
            
            # Отменяем задачу
            cancelled = await process_manager.cancel_task(task_id)
            
            if cancelled:
                await update.message.reply_text(
                    "✅ Операция отменена. Задача будет остановлена...",
                    reply_markup=self._get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "⚠️ Не удалось отменить задачу (возможно, уже завершена)",
                    reply_markup=self._get_main_keyboard()
                )
            
            # Убираем из активных
            del user_active_tasks[user_id]
            
        else:
            await update.message.reply_text(
                "ℹ️ Нет активных операций для отмены.",
                reply_markup=self._get_main_keyboard()
            )
        
        return ConversationHandler.END
    
    async def _cmd_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /about"""
        about_text = """
🌊 <b>MyFlowMusic Bot v0.2.0-alpha</b>
<i>by GrandEmotions / VOLNAI</i>

Автоматизация музыкального workflow:
• Suno integration
• Poe API (переводы, обложки)
• Audio processing
• Distributors (RouteNote, Sferoom)

Создан для @grandemotions
        """
        await update.message.reply_text(about_text, parse_mode='HTML')
    
    # ============ Основные команды ============
    
    async def _cmd_sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Синхронизация с Suno"""
        user_id = update.effective_user.id
        
        # Отправляем сообщение о начале
        message = await update.message.reply_text(
            BotMessages.SYNC_STARTED,
            parse_mode='HTML'
        )
        
        # Запускаем синхронизацию в фоне
        from ..config import settings
        from ..workflow.sync_suno import SunoSyncWorkflow
        
        workflow = SunoSyncWorkflow(self.db, self.poe_client)
        
        try:
            stats = await asyncio.to_thread(
                workflow.sync,
                settings.suno_cookie,
                dry_run=False
            )
            
            # Обновляем сообщение
            result_text = BotMessages.SYNC_COMPLETE.format(
                downloaded=stats['downloaded'],
                skipped=stats['skipped'],
                albums=stats['albums_created']
            )
            
            await message.edit_text(result_text, parse_mode='HTML')
            
            # Логируем
            self.vault.log_workflow(
                "sync",
                {},
                {"success": True, "stats": stats},
                0,
                "telegram"
            )
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            await message.edit_text(f"❌ Ошибка: {str(e)}")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статус"""
        from ..models import Album, Song, Generation, Cover
        
        session = self.db.session()
        
        stats = {
            "albums": session.query(Album).count(),
            "songs": session.query(Song).count(),
            "processed": session.query(Generation).filter_by(processed=True).count(),
            "covers": session.query(Cover).filter_by(state=2).count(),
        }
        
        session.close()
        
        status_text = f"""
📊 <b>Текущий статус:</b>

💿 Альбомов: {stats['albums']}
🎵 Песен: {stats['songs']}
✅ Обработано: {stats['processed']}
🎨 Обложек: {stats['covers']}

Используйте /sync для обновления
        """
        
        await update.message.reply_text(status_text, parse_mode='HTML')
    
    # ============ Conversation: Translate ============
    
    async def _cmd_translate_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать перевод"""
        albums = self._get_albums_list()
        
        if not albums:
            await update.message.reply_text("❌ Нет альбомов для перевода")
            return ConversationHandler.END
        
        keyboard = []
        for album_id, title in albums:
            keyboard.append([InlineKeyboardButton(title, callback_data=f"album:{album_id}")])
        
        keyboard.append([InlineKeyboardButton("Все альбомы", callback_data="album:all")])
        
        await update.message.reply_text(
            BotMessages.CHOICE_ALBUM,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.STATES['SELECT_ALBUM']
    
    async def _callback_select_album(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбран альбом для перевода с отменой"""
        query = update.callback_query
        await query.answer()
        
        album_id = query.data.split(":")[1]
        user_id = update.effective_user.id
        
        # Проверяем, нет ли активной задачи
        if user_id in user_active_tasks:
            await query.edit_message_text(
                "❌ У вас уже есть активная операция. Дождитесь завершения или используйте /cancel"
            )
            return ConversationHandler.END
        
        # Создаем трекер прогресса
        tracker = ProgressTracker(
            query,
            "🌐 Перевод текстов",
            ["Подключение к API", "Анализ песен", "Перевод", "Сохранение"]
        )
        await tracker.start()
        
        # Callback для обновления прогресса
        async def on_progress(task: ProcessTask):
            if tracker.cancelled:
                return
            
            # Обновляем прогресс
            if task.progress > 0:
                step = int((task.progress / 100) * len(tracker.steps))
                tracker.current_step = min(step, len(tracker.steps) - 1)
            
            tracker.message = task.message
            await tracker._update(task.message)
        
        try:
            await tracker.next_step("Запуск задачи...")
            
            # Получаем информацию об альбоме
            session = self.db.session()
            from ..models import Album, Song
            album = session.query(Album).get(album_id)
            songs_count = session.query(Song).filter_by(album_id=album_id).count()
            session.close()
            
            # Запускаем через ProcessManager с возможностью отмены
            task = await process_manager.start_task(
                command=[sys.executable, "-m", "music_agent.commands.translate", "--album-id", album_id],
                operation="translate",
                target_id=album_id,
                cwd=str(Path(__file__).parent.parent.parent),
                on_progress=on_progress
            )
            
            # Сохраняем связь user -> task
            user_active_tasks[user_id] = task.id
            
            await tracker.next_step(f"Найдено песен: {songs_count}")
            
            # Ждем завершения с проверкой отмены
            while task.status == "running":
                await asyncio.sleep(1)
                
                # Проверяем, не была ли отменена
                if tracker.cancelled:
                    await process_manager.cancel_task(task.id)
                    await query.edit_message_text("❌ Операция отменена")
                    del user_active_tasks[user_id]
                    return ConversationHandler.END
            
            # Убираем из активных
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            
            if task.status == "completed":
                # Парсим результат
                output = task.result or ""
                translated_count = songs_count
                for line in output.split('\n'):
                    if 'Переведено' in line or 'translated' in line.lower():
                        import re
                        nums = re.findall(r'\d+', line)
                        if nums:
                            translated_count = int(nums[0])
                
                result_text = f"📀 Альбом: <b>{album.title if album else album_id}</b>\n"
                result_text += f"📝 Переведено песен: <b>{translated_count}/{songs_count}</b>\n"
                result_text += f"🌐 Язык: <b>English</b>"
                
                await tracker.success(result_text)
                
            elif task.status == "cancelled":
                await query.edit_message_text("❌ Операция отменена")
                
            else:
                error_msg = task.error or "Unknown error"
                await tracker.error(error_msg)
                
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await tracker.error(str(e))
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
        
        return ConversationHandler.END
    
    # ============ Conversation: Cover ============
    
    async def _cmd_cover_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать генерацию обложек"""
        albums = self._get_albums_without_covers()
        
        if not albums:
            await update.message.reply_text("✅ Все альбомы уже имеют обложки")
            return ConversationHandler.END
        
        keyboard = []
        for album_id, title in albums:
            keyboard.append([InlineKeyboardButton(title, callback_data=f"cover_album:{album_id}")])
        
        keyboard.append([InlineKeyboardButton("Все без обложек", callback_data="cover_album:all")])
        
        await update.message.reply_text(
            "🎨 Выберите альбом для генерации обложки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.STATES['SELECT_ALBUM']
    
    async def _callback_select_album_cover(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбран альбом для обложки с отменой"""
        query = update.callback_query
        await query.answer()
        
        album_id = query.data.split(":")[1]
        user_id = update.effective_user.id
        
        if user_id in user_active_tasks:
            await query.edit_message_text("❌ У вас уже есть активная операция.")
            return ConversationHandler.END
        
        tracker = ProgressTracker(
            query,
            "🎨 Генерация обложки",
            ["Анализ песни", "Создание промпта", "Генерация", "Обработка", "Сохранение"]
        )
        await tracker.start()
        
        async def on_progress(task: ProcessTask):
            if tracker.cancelled:
                return
            tracker.current_step = min(int((task.progress / 100) * len(tracker.steps)), len(tracker.steps) - 1)
            tracker.message = task.message
            await tracker._update(task.message)
        
        try:
            session = self.db.session()
            from ..models import Album, Song
            album = session.query(Album).get(album_id)
            main_song = session.query(Song).filter_by(album_id=album_id).first()
            session.close()
            
            task = await process_manager.start_task(
                command=[sys.executable, "-m", "music_agent.commands.cover", "--album-id", album_id],
                operation="cover",
                target_id=album_id,
                cwd=str(Path(__file__).parent.parent.parent),
                on_progress=on_progress
            )
            
            user_active_tasks[user_id] = task.id
            
            while task.status == "running":
                await asyncio.sleep(1)
                if tracker.cancelled:
                    await process_manager.cancel_task(task.id)
                    await query.edit_message_text("❌ Операция отменена")
                    del user_active_tasks[user_id]
                    return ConversationHandler.END
            
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            
            if task.status == "completed":
                result_text = f"📀 Альбом: <b>{album.title if album else album_id}</b>\n"
                result_text += f"🎨 Размер: <b>3000x3000</b>\n"
                result_text += f"🤖 Модель: <b>Nano-Banana-Pro</b>\n"
                if main_song:
                    result_text += f"🎵 Основана на: <i>{main_song.title}</i>"
                await tracker.success(result_text)
            elif task.status == "cancelled":
                await query.edit_message_text("❌ Операция отменена")
            else:
                await tracker.error(task.error or "Unknown error")
                
        except Exception as e:
            logger.error(f"Cover generation error: {e}")
            await tracker.error(str(e))
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
        
        return ConversationHandler.END
    
    # ============ Conversation: Process ============
    
    async def _cmd_process_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать обработку аудио"""
        albums = self._get_albums_list()
        
        keyboard = []
        for album_id, title in albums:
            keyboard.append([InlineKeyboardButton(title, callback_data=f"process_album:{album_id}")])
        
        keyboard.append([InlineKeyboardButton("Все альбомы", callback_data="process_album:all")])
        
        await update.message.reply_text(
            "🎵 Выберите альбом для обработки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.STATES['SELECT_ALBUM']
    
    async def _callback_select_album_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбран альбом для обработки - показываем превью"""
        query = update.callback_query
        await query.answer()
        
        album_id = query.data.split(":")[1]
        user_id = update.effective_user.id
        
        if user_id in user_active_tasks:
            await query.edit_message_text("❌ У вас уже есть активная операция.")
            return ConversationHandler.END
        
        # Генерируем превью
        try:
            from ..utils.preview_helper import preview_helper
            from ..utils.file_manager import FileManager
            
            session = self.db.session()
            file_manager = FileManager(self.file_manager.fs_conn if self.file_manager else ".")
            
            preview = preview_helper.generate_process_preview(
                album_id=album_id,
                session=session,
                file_manager=file_manager
            )
            session.close()
            
            if not preview:
                await query.edit_message_text("❌ Нет треков для обработки")
                return ConversationHandler.END
            
            # Сохраняем preview в context для подтверждения
            context.user_data['process_preview'] = preview.to_dict()
            context.user_data['process_album_id'] = album_id
            
            # Показываем превью
            text = preview_helper.format_preview_for_telegram(preview)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Обработать", callback_data="process_confirm:yes"),
                    InlineKeyboardButton("✏️ Изменить", callback_data="process_confirm:edit")
                ],
                [InlineKeyboardButton("❌ Отмена", callback_data="process_confirm:no")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            return self.STATES['CONFIRM']
            
        except Exception as e:
            logger.error(f"Preview generation error: {e}")
            await query.edit_message_text(f"❌ Ошибка создания превью: {str(e)}")
            return ConversationHandler.END
    
    async def _callback_confirm_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение обработки после превью"""
        query = update.callback_query
        await query.answer()
        
        choice = query.data.split(":")[1]
        
        if choice == "no":
            await query.edit_message_text("❌ Обработка отменена")
            return ConversationHandler.END
        
        if choice == "edit":
            # Перенаправляем на редактирование
            album_id = context.user_data.get('process_album_id')
            await query.edit_message_text(
                f"✏️ Откройте Web UI для редактирования:\n"
                f"<a href='http://localhost:8000/albums/{album_id}/edit'>Редактировать альбом</a>",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Запускаем обработку
        album_id = context.user_data.get('process_album_id')
        user_id = update.effective_user.id
        
        tracker = ProgressTracker(
            query,
            "🎚️ Обработка аудио",
            ["Анализ треков", "Нормализация (-14 LUFS)", "Fade-out", "Обрезка тишины", "ID3 теги"]
        )
        await tracker.start()
        
        async def on_progress(task: ProcessTask):
            if tracker.cancelled:
                return
            tracker.current_step = min(int((task.progress / 100) * len(tracker.steps)), len(tracker.steps) - 1)
            tracker.message = task.message
            await tracker._update(task.message)
        
        try:
            session = self.db.session()
            from ..models import Album
            album = session.query(Album).get(album_id)
            session.close()
            
            task = await process_manager.start_task(
                command=[sys.executable, "-m", "music_agent.commands.process", "--album-id", album_id],
                operation="process",
                target_id=album_id,
                cwd=str(Path(__file__).parent.parent.parent),
                on_progress=on_progress
            )
            
            user_active_tasks[user_id] = task.id
            
            while task.status == "running":
                await asyncio.sleep(1)
                if tracker.cancelled:
                    await process_manager.cancel_task(task.id)
                    await query.edit_message_text("❌ Операция отменена")
                    del user_active_tasks[user_id]
                    return ConversationHandler.END
            
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            
            if task.status == "completed":
                result_text = f"📀 Альбом: <b>{album.title if album else album_id}</b>\n"
                result_text += f"🎵 Обработано треков\n"
                result_text += f"🔊 Нормализация: <b>-14 LUFS</b>\n"
                result_text += f"📉 Fade-out: <b>3 сек</b>\n"
                result_text += f"🏷 ID3 теги: <b>✓</b>"
                await tracker.success(result_text)
            elif task.status == "cancelled":
                await query.edit_message_text("❌ Операция отменена")
            else:
                await tracker.error(task.error or "Unknown error")
                
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            await tracker.error(str(e))
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
        
        return ConversationHandler.END
    
    # ============ Conversation: Publish ============
    
    async def _cmd_publish_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать публикацию"""
        albums = self._get_ready_albums()
        
        if not albums:
            await update.message.reply_text("❌ Нет готовых альбомов для публикации")
            return ConversationHandler.END
        
        keyboard = []
        for album_id, title in albums:
            keyboard.append([InlineKeyboardButton(title, callback_data=f"publish_album:{album_id}")])
        
        await update.message.reply_text(
            BotMessages.CHOICE_ALBUM,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.STATES['SELECT_ALBUM']
    
    async def _callback_select_album_publish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбран альбом для публикации"""
        query = update.callback_query
        await query.answer()
        
        album_id = query.data.split(":")[1]
        context.user_data['publish_album_id'] = album_id
        
        # Выбор дистрибьютора
        keyboard = [
            [InlineKeyboardButton("RouteNote", callback_data="distributor:routenote")],
            [InlineKeyboardButton("Sferoom", callback_data="distributor:sferoom")],
        ]
        
        await query.edit_message_text(
            BotMessages.CHOICE_DISTRIBUTOR,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return self.STATES['SELECT_DISTRIBUTOR']
    
    async def _callback_select_distributor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбран дистрибьютор - показываем предпросмотр"""
        query = update.callback_query
        await query.answer()
        
        distributor = query.data.split(":")[1]
        context.user_data['publish_distributor'] = distributor
        
        album_id = context.user_data.get('publish_album_id')
        
        # Получаем детали альбома для предпросмотра
        session = self.db.session()
        from ..models import Album, Song, Cover
        album = session.query(Album).get(album_id)
        songs = session.query(Song).filter_by(album_id=album_id).order_by(Song.order).all()
        
        preview_text = f"📋 <b>Предпросмотр публикации</b>\n\n"
        preview_text += f"📀 <b>{album.title if album else 'Unknown'}</b>\n"
        preview_text += f"👤 Исполнитель: {album.artist if album and album.artist else 'Unknown Artist'}\n"
        preview_text += f"📤 Дистрибьютор: <b>{distributor.capitalize()}</b>\n\n"
        
        preview_text += f"🎵 Треки ({len(songs)}):\n"
        for i, song in enumerate(songs[:5], 1):
            preview_text += f"  {i}. {song.title}\n"
        if len(songs) > 5:
            preview_text += f"  ... и ещё {len(songs) - 5}\n"
        
        preview_text += f"\n🎨 Обложка: {'✅' if album and album.cover else '❌'}\n"
        preview_text += f"🔒 Cookie: {'✅ Настроен' if (distributor == 'routenote' and self._check_cookie('routenote')) or (distributor == 'sferoom' and self._check_cookie('sferoom')) else '❌ Не настроен'}"
        
        session.close()
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Публиковать", callback_data="confirm:yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="confirm:no")
            ]
        ]
        
        await query.edit_message_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        return self.STATES['CONFIRM']
    
    def _check_cookie(self, distributor: str) -> bool:
        """Проверить наличие cookie для дистрибьютора"""
        from ..config import settings
        if distributor == 'routenote':
            return bool(settings.routenote_cookie)
        elif distributor == 'sferoom':
            return bool(settings.sferoom_cookie)
        return False
    
    async def _callback_confirm_publish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение публикации с прогрессом и отменой"""
        query = update.callback_query
        await query.answer()
        
        choice = query.data.split(":")[1]
        
        if choice == "no":
            await query.edit_message_text("❌ Публикация отменена")
            return ConversationHandler.END
        
        album_id = context.user_data.get('publish_album_id')
        distributor = context.user_data.get('publish_distributor')
        user_id = update.effective_user.id
        
        if user_id in user_active_tasks:
            await query.edit_message_text("❌ У вас уже есть активная операция.")
            return ConversationHandler.END
        
        tracker = ProgressTracker(
            query,
            f"📤 Публикация на {distributor.capitalize()}",
            ["Подключение к аккаунту", "Загрузка метаданных", "Загрузка треков", "Загрузка обложки", "Отправка"]
        )
        await tracker.start()
        
        async def on_progress(task: ProcessTask):
            if tracker.cancelled:
                return
            tracker.current_step = min(int((task.progress / 100) * len(tracker.steps)), len(tracker.steps) - 1)
            tracker.message = task.message
            await tracker._update(task.message)
        
        try:
            session = self.db.session()
            from ..models import Album, Song
            album = session.query(Album).get(album_id)
            session.close()
            
            task = await process_manager.start_task(
                command=[
                    sys.executable, "-m", "music_agent.commands.publish",
                    "--distributor", distributor,
                    "--album-id", album_id
                ],
                operation="publish",
                target_id=album_id,
                cwd=str(Path(__file__).parent.parent.parent),
                on_progress=on_progress
            )
            
            user_active_tasks[user_id] = task.id
            
            while task.status == "running":
                await asyncio.sleep(1)
                if tracker.cancelled:
                    await process_manager.cancel_task(task.id)
                    await query.edit_message_text("❌ Операция отменена")
                    del user_active_tasks[user_id]
                    return ConversationHandler.END
            
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            
            if task.status == "completed":
                output = task.result or ""
                dist_id = None
                for line in output.split('\n'):
                    if 'ID:' in line or 'id:' in line:
                        import re
                        ids = re.findall(r'[A-Za-z0-9_-]{10,}', line)
                        if ids:
                            dist_id = ids[0]
                
                result_text = f"📀 Альбом: <b>{album.title if album else album_id}</b>\n"
                result_text += f"📤 Дистрибьютор: <b>{distributor.capitalize()}</b>\n"
                if dist_id:
                    result_text += f"🆔 ID: <code>{dist_id}</code>\n"
                result_text += f"\n⏳ Статус: <i>На модерации</i>"
                await tracker.success(result_text)
                
            elif task.status == "cancelled":
                await query.edit_message_text("❌ Операция отменена")
            else:
                error_msg = task.error or "Unknown error"
                if "captcha" in error_msg.lower():
                    error_msg = "Требуется капча. Попробуйте CLI"
                elif "login" in error_msg.lower() or "auth" in error_msg.lower():
                    error_msg = "Ошибка авторизации. Проверьте cookie"
                elif "timeout" in error_msg.lower():
                    error_msg = "Таймаут. Попробуйте позже"
                await tracker.error(error_msg)
                
        except Exception as e:
            logger.error(f"Publish error: {e}")
            await tracker.error(str(e))
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
        
        return ConversationHandler.END
    
    # ============ Vault ============
    
    async def _cmd_vault(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику vault"""
        prefs = self.vault.get_user_preferences(days=7)
        
        text = f"""
📚 <b>Статистика за неделю:</b>

📈 Активность: {prefs['activity_level']} действий
📉 Ошибок: {prefs['error_rate']:.0%}

🔝 Топ команды:
{chr(10).join(f"  • {c['name']}: {c['count']}" for c in prefs['favorite_commands'][:3])}

Используйте CLI для полной статистики:
<code>agent vault stats --days 7</code>
        """
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    # ============ Helpers ============
    
    def _check_auth(self, user_id: int) -> bool:
        """Проверка авторизации"""
        if not bot_config.telegram_admin_ids:
            return True  # Если не настроены админы - разрешаем всем
        return user_id in bot_config.telegram_admin_ids
    
    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Главная клавиатура"""
        keyboard = [
            ["🔄 Синхронизация", "📊 Статус"],
            ["🌐 Перевод", "🎨 Обложки"],
            ["🎵 Обработка", "📤 Публикация"],
            ["❓ Помощь"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def _get_albums_list(self):
        """Получить список альбомов"""
        from ..models import Album
        session = self.db.session()
        albums = [(a.id, a.title) for a in session.query(Album).all()]
        session.close()
        return albums
    
    def _get_albums_without_covers(self):
        """Альбомы без обложек"""
        from ..models import Album
        session = self.db.session()
        albums = [(a.id, a.title) for a in session.query(Album).filter(
            (Album.cover_id == None) | (Album.cover_id == '')
        ).all()]
        session.close()
        return albums
    
    def _get_ready_albums(self):
        """Готовые к публикации альбомы"""
        from ..models import Album
        session = self.db.session()
        albums = []
        for album in session.query(Album).all():
            if album.cover_id and hasattr(album, 'songs') and album.songs:
                if not album.routenote_id and not album.sferoom_id:
                    albums.append((album.id, album.title))
        session.close()
        return albums
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ошибок"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже."
            )
    
    # ============ Run ============
    
    async def run(self):
        """Запуск бота"""
        await self.initialize()
        
        if bot_config.bot_mode == "webhook":
            # Webhook mode
            await self.application.start()
            await self.application.updater.start_webhook(
                listen="0.0.0.0",
                port=bot_config.webhook_port,
                url_path=bot_config.telegram_bot_token,
                webhook_url=f"{bot_config.webhook_url}/{bot_config.telegram_bot_token}"
            )
        else:
            # Polling mode (default)
            logger.info("Starting bot in polling mode...")
            await self.application.run_polling()

"""
Команда: agent voice
Голосовое управление через Deepgram
"""
import click
import logging
import asyncio
from pathlib import Path

from ..config import settings
from ..voice.deepgram_client import DeepgramVoiceClient, VoiceCommandExecutor
from ..models import Database
from ..integrations.poe_client import PoeClient
from ..workflow.sync_suno import SunoSyncWorkflow
from ..utils.file_manager import FileManager

logger = logging.getLogger(__name__)


@click.group(name="voice")
def voice():
    """🎤 Голосовое управление"""
    pass


@click.command(name="listen")
@click.option('--duration', '-d', default=5, help='Длительность записи (секунды)')
@click.option('--language', '-l', default='ru', help='Язык (ru, en)')
def listen(duration: int, language: str):
    """Записать и распознать голосовую команду"""
    
    if not settings.voice_api_key:
        click.echo("❌ Ошибка: Deepgram API key не настроен", err=True)
        click.echo("Установите MUSIC_AGENT_VOICE_API_KEY в .env")
        return
    
    click.echo(f"🎤 Нажмите Enter и говорите ({duration} секунд)...")
    input()
    
    client = DeepgramVoiceClient(settings.voice_api_key, settings.voice_model)
    
    try:
        click.echo("🔴 Запись...", nl=False)
        command = asyncio.run(client.transcribe_microphone(duration, language))
        click.echo(" ✅")
        
        if command:
            click.echo(f"\n📝 Распознано: '{command.text}'")
            click.echo(f"📊 Уверенность: {command.confidence:.0%}")
            click.echo(f"🎯 Команда: {command.command_type}")
            
            if command.parameters:
                click.echo(f"⚙️  Параметры: {command.parameters}")
            
            # Выполняем
            if click.confirm("\nВыполнить эту команду?"):
                _execute_voice_command(command)
        else:
            click.echo("❌ Не удалось распознать")
            
    except Exception as e:
        click.echo(f" ❌ Ошибка: {e}", err=True)


@click.command(name="file")
@click.argument('audio_path', type=click.Path(exists=True))
@click.option('--language', '-l', default='ru', help='Язык')
def transcribe_file(audio_path: str, language: str):
    """Распознать аудио файл"""
    
    if not settings.voice_api_key:
        click.echo("❌ Deepgram API key не настроен", err=True)
        return
    
    path = Path(audio_path)
    client = DeepgramVoiceClient(settings.voice_api_key)
    
    click.echo(f"🔍 Распознавание: {path}")
    
    try:
        command = asyncio.run(client.transcribe_file(path, language))
        
        if command:
            click.echo(f"\n📝 Текст: {command.text}")
            click.echo(f"📊 Уверенность: {command.confidence:.2f}")
            click.echo(f"🎯 Тип: {command.command_type}")
        else:
            click.echo("❌ Не удалось распознать")
            
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}", err=True)


@click.command(name="commands")
def list_commands():
    """Показать список голосовых команд"""
    
    click.echo("""
🎵 Голосовые команды:

📥 Скачивание:
   "Скачай новые треки с Suno"
   "Синхронизируй библиотеку"
   "Обнови треки"

🌐 Обработка:
   "Переведи тексты на английский"
   "Сгенерируй обложки для всех альбомов"
   "Обработай аудио файлы"

📤 Публикация:
   "Опубликуй на RouteNote"
   "Выпусти на Sferoom"
   "Отправь на модерацию"

📊 Информация:
   "Покажи статус"
   "Что готово?"
   "Сколько треков обработано?"

💡 Советы:
   • Говорите чётко и не слишком быстро
   • Уверенность > 70% для выполнения
   • Можно сказать "помощь" для подсказки
""")


def _execute_voice_command(command):
    """Выполнить распознанную команду"""
    
    db = Database(settings.db_type, settings.db_conn).connect()
    poe = PoeClient(settings.poe_api_key) if settings.poe_api_key else None
    file_manager = FileManager(settings.fs_conn)
    
    executor = VoiceCommandExecutor(db, None, poe, file_manager)
    
    try:
        result = asyncio.run(executor.execute(command))
        
        click.echo(f"\n{'✅' if result['success'] else '❌'} {result['message']}")
        
        # Сохраняем в vault
        from ..vault.manager import VaultManager
        vault = VaultManager()
        vault.log_conversation(
            user_message=command.text,
            assistant_response=result['message'],
            source="voice"
        )
        
    except Exception as e:
        click.echo(f"❌ Ошибка выполнения: {e}", err=True)


# Регистрируем команды
voice.add_command(listen)
voice.add_command(transcribe_file)
voice.add_command(list_commands)


if __name__ == '__main__':
    voice()

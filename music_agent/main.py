"""
MyFlowMusic (MFM) CLI
Главная точка входа
"""
import click
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from commands.sync import sync
from commands.translate import translate
from commands.cover import cover, cover_status, cover_validate
from commands.process import process, process_status, audio_info
from commands.publish import publish, publish_status, check_status
from commands.voice_cmd import voice
from commands.vault_cmd import vault
from commands.web import web
from commands.export_import import export_group, import_group, backup, restore
from commands.import_local import import_files, scan_raw


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """
    🌊 MyFlowMusic (MFM) - AI-ассистент для музыкантов от GrandEmotions / VOLNAI
    
    v0.2.0 - Теперь с голосовым управлением, историей и веб-интерфейсом!
    
    Основные команды:
    
    \b
    📥 Скачивание:
       agent sync              Скачать треки с Suno
    
    \b
    🌐 Обработка:
       agent translate         Перевести тексты
       agent cover             Сгенерировать обложки
       agent process           Обработать аудио
    
    \b
    📤 Публикация:
       agent publish           Опубликовать
       agent publish-status    Статус публикаций
    
    \b
    🎤 Голосовое управление:
       agent voice listen      Записать команду
       agent voice commands    Список команд
    
    \b
    📚 История (Vault):
       agent vault summary     Ежедневный отчёт
       agent vault stats       Статистика
       agent vault search      Поиск по истории
    
    \b
    🌐 Web UI:
       agent web               Запустить веб-интерфейс
       agent web --port 8080
    
    \b
    📊 Информация:
       agent cover-status      Статус обложек
       agent process-status    Статус обработки
       agent audio-info        Инфо об аудио
    
    \b
    💾 Бэкап:
       agent export json       Экспорт в JSON
       agent export archive    Экспорт в ZIP
       agent import json       Импорт из JSON
       agent backup            Быстрый бэкап
    
    \b
    📁 Локальные файлы:
       agent import-files      Импорт MP3 (без Suno)
       agent scan-raw          Сканировать raw/
    
    Примеры:
        agent sync
        agent voice listen
        agent vault summary
        agent web
        agent import-files ~/Music/*.mp3 --create-album --album-title "My Songs"
    """
    pass


# Основные команды
cli.add_command(sync)
cli.add_command(translate)
cli.add_command(cover)
cli.add_command(process)
cli.add_command(publish)

# Voice, Vault, Web
cli.add_command(voice)
cli.add_command(vault)
cli.add_command(web)

# Export/Import
cli.add_command(export_group)
cli.add_command(import_group)

# Local import
cli.add_command(import_files, name='import-files')
cli.add_command(scan_raw, name='scan-raw')
cli.add_command(backup)
cli.add_command(restore)

# Статус и инфо
cli.add_command(cover_status)
cli.add_command(cover_validate)
cli.add_command(process_status)
cli.add_command(audio_info)
cli.add_command(publish_status)
cli.add_command(check_status)

# Псевдонимы
cli.add_command(sync, name='s')
cli.add_command(translate, name='t')
cli.add_command(cover, name='c')
cli.add_command(process, name='p')
cli.add_command(publish, name='pub')
cli.add_command(voice, name='v')
cli.add_command(web, name='w')


if __name__ == '__main__':
    cli()

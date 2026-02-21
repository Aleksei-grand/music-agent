"""
Команда: agent sync
Синхронизация треков с Suno
"""
import click
import logging
from pathlib import Path

from ..config import settings
from ..models import Database
from ..integrations.poe_client import PoeClient
from ..workflow.sync_suno import SunoSyncWorkflow

logger = logging.getLogger(__name__)


@click.command()
@click.option('--cookie', '-c', help='Suno cookie (или из .env)')
@click.option('--dry-run', is_flag=True, help='Показать что будет скачано без скачивания')
@click.option('--verbose', '-v', is_flag=True, help='Подробный вывод')
def sync(cookie: str, dry_run: bool, verbose: bool):
    """Скачать новые треки с Suno и создать альбомы"""
    
    # Настройка логирования
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Cookie
    suno_cookie = cookie or settings.suno_cookie
    if not suno_cookie:
        click.echo("❌ Ошибка: Не указан Suno cookie", err=True)
        click.echo("Используйте --cookie или установите MUSIC_AGENT_SUNO_COOKIE в .env")
        return
    
    # Подключаемся к БД
    click.echo("📂 Подключение к базе данных...")
    db = Database(settings.db_type, settings.db_conn, debug=verbose)
    db.connect().migrate()
    
    # Poe клиент (опционально)
    poe_client = None
    if settings.poe_api_key:
        click.echo("🤖 Подключение к Poe API...")
        poe_client = PoeClient(settings.poe_api_key)
    else:
        click.echo("⚠️  Poe API не настроен - обложки не будут генерироваться")
    
    # Запускаем синхронизацию
    click.echo("🎵 Запуск синхронизации с Suno...")
    click.echo("-" * 50)
    
    workflow = SunoSyncWorkflow(db, poe_client)
    stats = workflow.sync(suno_cookie, dry_run=dry_run)
    
    # Результаты
    click.echo("-" * 50)
    click.echo("✅ Синхронизация завершена!")
    click.echo(f"📥 Скачано: {stats['downloaded']}")
    click.echo(f"⏭️  Пропущено (уже есть): {stats['skipped']}")
    click.echo(f"🎶 Сгруппировано в песни: {stats['grouped']}")
    click.echo(f"💿 Создано альбомов: {stats['albums_created']}")
    
    if stats['errors']:
        click.echo(f"\n⚠️  Ошибки ({len(stats['errors'])}):")
        for error in stats['errors'][:5]:  # Показываем первые 5
            click.echo(f"   - {error}")


if __name__ == '__main__':
    sync()

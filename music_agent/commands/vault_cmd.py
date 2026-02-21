"""
Команда: agent vault
Управление историей и персонализацией
"""
import click
import logging
from datetime import date, timedelta

from ..vault.manager import VaultManager

logger = logging.getLogger(__name__)


@click.group(name="vault")
def vault():
    """📚 История и персонализация"""
    pass


@click.command(name="summary")
@click.option('--date', '-d', help='Дата (YYYY-MM-DD), по умолчанию сегодня')
def generate_summary(date_str: str):
    """Сгенерировать ежедневный отчёт"""
    
    target_date = date.today()
    if date_str:
        try:
            from datetime import datetime
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            click.echo("❌ Неверный формат даты. Используйте YYYY-MM-DD", err=True)
            return
    
    manager = VaultManager()
    
    click.echo(f"📊 Генерация отчёта за {target_date}...")
    
    result = manager.generate_daily_summary(target_date)
    
    if result:
        click.echo(f"✅ Сохранено: {result}")
    else:
        click.echo("ℹ️  Нет данных за эту дату")


@click.command(name="stats")
@click.option('--days', '-d', default=30, help='Период в днях')
def show_stats(days: int):
    """Показать статистику использования"""
    
    manager = VaultManager()
    prefs = manager.get_user_preferences(days)
    
    click.echo(f"\n📊 Статистика за последние {days} дней:")
    click.echo("-" * 40)
    
    click.echo(f"\n📈 Активность: {prefs['activity_level']} действий")
    click.echo(f"📉 Уровень ошибок: {prefs['error_rate']:.1%}")
    
    click.echo(f"\n🔝 Любимые команды:")
    for cmd in prefs['favorite_commands']:
        click.echo(f"   • {cmd['name']}: {cmd['count']} раз")
    
    click.echo(f"\n🔄 Частые workflow:")
    for wf in prefs['favorite_workflows']:
        click.echo(f"   • {wf['name']}: {wf['count']} раз")
    
    click.echo(f"\n📱 Источники:")
    for source in prefs['preferred_sources']:
        click.echo(f"   • {source}")


@click.command(name="search")
@click.argument('query')
@click.option('--type', 'entry_type', help='Тип записи (conversation, workflow, error)')
@click.option('--limit', '-l', default=10, help='Лимит результатов')
def search_vault(query: str, entry_type: str, limit: int):
    """Поиск по истории"""
    
    manager = VaultManager()
    results = manager.search(query, entry_type, limit)
    
    if not results:
        click.echo("Ничего не найдено")
        return
    
    click.echo(f"\n🔍 Найдено {len(results)} результатов:\n")
    
    for i, entry in enumerate(results, 1):
        click.echo(f"{i}. [{entry['type'].upper()}] {entry['timestamp']}")
        
        if entry['type'] == 'conversation':
            content = entry['content']
            click.echo(f"   User: {content['user'][:100]}...")
            click.echo(f"   Assistant: {content['assistant'][:100]}...")
        elif entry['type'] == 'workflow':
            click.echo(f"   Workflow: {entry['content']['workflow']}")
        elif entry['type'] == 'error':
            click.echo(f"   Error: {entry['content']['error_type']}")
        
        click.echo()


@click.command(name="last")
@click.option('--n', default=5, help='Количество записей')
def show_last(n: int):
    """Показать последние записи"""
    
    manager = VaultManager()
    
    # Ищем последние записи
    entries = []
    for json_file in sorted(manager.vault_path.rglob("*.json"), 
                           key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
        try:
            import json
            with open(json_file, 'r', encoding='utf-8') as f:
                entries.append(json.load(f))
        except:
            pass
    
    if not entries:
        click.echo("Нет записей")
        return
    
    click.echo(f"\n🕐 Последние {len(entries)} записей:\n")
    
    for entry in entries:
        click.echo(f"[{entry['type'].upper()}] {entry['timestamp']} | {entry['source']}")
        
        if entry['type'] == 'conversation':
            click.echo(f"  👤 {entry['content']['user'][:80]}...")
        elif entry['type'] == 'command':
            click.echo(f"  ⚡ {entry['content']['command']}")


@click.command(name="preferences")
def show_preferences():
    """Показать персонализированные рекомендации"""
    
    manager = VaultManager()
    prefs = manager.get_user_preferences(days=30)
    
    click.echo("\n🎯 Персонализация:")
    click.echo("-" * 40)
    
    # Рекомендации на основе истории
    if prefs['activity_level'] > 50:
        click.echo("\n💡 Вы активный пользователь!")
        click.echo("   Рекомендация: Используйте --all для пакетной обработки")
    
    if prefs['error_rate'] > 0.2:
        click.echo("\n⚠️  Высокий уровень ошибок")
        click.echo("   Рекомендация: Используйте --dry-run перед реальными операциями")
    
    # Частые команды
    if prefs['favorite_commands']:
        top_cmd = prefs['favorite_commands'][0]['name']
        click.echo(f"\n⚡ Частая команда: {top_cmd}")
        click.echo(f"   Псевдоним: agent {top_cmd[:1]}")
    
    click.echo("\n📊 Ваша статистика сохраняется в vault/")
    click.echo("   Для просмотра: agent vault stats")


# Регистрируем команды
vault.add_command(generate_summary)
vault.add_command(show_stats)
vault.add_command(search_vault)
vault.add_command(show_last)
vault.add_command(show_preferences)


if __name__ == '__main__':
    vault()

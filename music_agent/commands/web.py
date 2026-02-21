"""
Команда: agent web
Запуск Web UI
"""
import click
import logging
import uvicorn

from ..config import settings

logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', '-h', default='0.0.0.0', help='Хост для запуска')
@click.option('--port', '-p', default=8080, help='Порт')
@click.option('--reload', is_flag=True, help='Автоперезагрузка (для разработки)')
def web(host: str, port: int, reload: bool):
    """🌐 Запустить Web UI"""
    
    click.echo(f"🌐 Запуск Web UI на http://{host}:{port}")
    click.echo("Нажмите Ctrl+C для остановки")
    
    try:
        uvicorn.run(
            "myflowmusic.web.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        click.echo("\n👋 Web UI остановлен")


if __name__ == '__main__':
    web()

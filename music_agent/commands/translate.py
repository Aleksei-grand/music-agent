"""
Команда: agent translate
Перевод текстов песен через Poe API
"""
import click
import logging
from sqlalchemy import text

from ..config import settings
from ..models import Database, Song
from ..integrations.poe_client import PoeClient

logger = logging.getLogger(__name__)


@click.command()
@click.option('--song-id', '-s', help='ID конкретной песни (или все без перевода)')
@click.option('--album-id', '-a', help='ID альбома (перевести все песни альбома)')
@click.option('--language', '-l', default='english', help='Язык перевода')
@click.option('--model', '-m', default=None, help='Модель Poe (по умолчанию из config)')
@click.option('--dry-run', is_flag=True, help='Показать что будет переведено')
def translate(song_id: str, album_id: str, language: str, model: str, dry_run: bool):
    """Перевести тексты песен на другой язык"""
    
    logging.basicConfig(level=logging.INFO)
    
    if not settings.poe_api_key:
        click.echo("❌ Ошибка: Poe API ключ не настроен", err=True)
        return
    
    # Подключаемся
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    poe = PoeClient(settings.poe_api_key)
    translation_model = model or settings.poe_translation_model
    
    # Получаем песни для перевода
    if song_id:
        songs = session.query(Song).filter_by(id=song_id).all()
    elif album_id:
        songs = session.query(Song).filter_by(album_id=album_id).all()
    else:
        # Все песни без перевода
        songs = session.query(Song).filter(
            (Song.translated_lyrics == '') | (Song.translated_lyrics == None)
        ).all()
    
    if not songs:
        click.echo("ℹ️  Нет песен для перевода")
        return
    
    click.echo(f"📝 Найдено песен для перевода: {len(songs)}")
    click.echo(f"🌐 Язык: {language}")
    click.echo(f"🤖 Модель: {translation_model}")
    click.echo("-" * 50)
    
    translated_count = 0
    
    for song in songs:
        if not song.original_lyrics:
            click.echo(f"⏭️  {song.title}: нет текста")
            continue
        
        click.echo(f"🔄 Перевод: {song.title}...", nl=False)
        
        if dry_run:
            click.echo(" [DRY RUN]")
            continue
        
        try:
            # Переводим
            translated = poe.translate_lyrics(
                text=song.original_lyrics,
                target_language=language,
                model=translation_model,
                context=f"Style: {song.style}, Genre: {song.type}"
            )
            
            # Сохраняем
            song.translated_lyrics = translated
            song.translated_to = language
            session.commit()
            
            click.echo(" ✅")
            translated_count += 1
            
        except Exception as e:
            click.echo(f" ❌ Ошибка: {e}")
            logger.error(f"Translation error for {song.id}: {e}")
    
    click.echo("-" * 50)
    click.echo(f"✅ Переведено: {translated_count}/{len(songs)}")
    
    session.close()


if __name__ == '__main__':
    translate()

"""
Команда: agent cover
Генерация обложек альбомов через Poe API
"""
import click
import logging
from pathlib import Path

from ..config import settings
from ..models import Database, Album, Cover, State
from ..integrations.poe_client import PoeClient
from ..utils.image_processor import ImageProcessor
from ..utils.file_manager import FileManager
from ..utils.id_generator import generate_ulid

logger = logging.getLogger(__name__)


@click.command()
@click.option('--album-id', '-a', help='ID конкретного альбома')
@click.option('--all', 'generate_all', is_flag=True, help='Сгенерировать для всех альбомов без обложек')
@click.option('--regenerate', is_flag=True, help='Перегенерировать существующие')
@click.option('--size', default=3000, help='Размер обложки (пиксели)')
@click.option('--dry-run', is_flag=True, help='Показать что будет сгенерировано')
def cover(album_id: str, generate_all: bool, regenerate: bool, size: int, dry_run: bool):
    """Сгенерировать обложки для альбомов"""
    
    logging.basicConfig(level=logging.INFO)
    
    # Проверяем Poe API
    if not settings.poe_api_key:
        click.echo("❌ Ошибка: Poe API ключ не настроен", err=True)
        click.echo("Установите MUSIC_AGENT_POE_API_KEY в .env")
        return
    
    # Подключаемся к БД
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    # Инициализируем клиенты
    poe = PoeClient(settings.poe_api_key)
    processor = ImageProcessor()
    file_manager = FileManager(settings.fs_conn)
    
    # Определяем какие альбомы обрабатывать
    if album_id:
        albums = [session.query(Album).get(album_id)]
        if not albums[0]:
            click.echo(f"❌ Альбом {album_id} не найден", err=True)
            return
    elif generate_all or regenerate:
        query = session.query(Album)
        if not regenerate:
            # Только без обложек
            query = query.filter(
                (Album.cover_id == None) | (Album.cover_id == '')
            )
        albums = query.all()
    else:
        click.echo("❌ Укажите --album-id или --all", err=True)
        return
    
    if not albums:
        click.echo("ℹ️  Нет альбомов для обработки")
        return
    
    click.echo(f"🎨 Найдено альбомов: {len(albums)}")
    click.echo(f"🤖 Модель: {settings.poe_cover_model}")
    click.echo(f"📐 Размер: {size}x{size}")
    click.echo("-" * 50)
    
    generated = 0
    failed = 0
    
    for album in albums:
        click.echo(f"\n📝 Альбом: {album.title}")
        
        if dry_run:
            click.echo("   [DRY RUN] Будет сгенерирована обложка")
            generated += 1
            continue
        
        try:
            # Получаем основную песню альбома для анализа
            main_song = None
            if hasattr(album, 'songs') and album.songs:
                main_song = album.songs[0]
            
            # Шаг 1: Анализируем песню
            click.echo("   🔍 Анализ песни...", nl=False)
            if main_song and main_song.original_lyrics:
                analysis = poe.analyze_song_for_cover(
                    lyrics=main_song.original_lyrics,
                    title=album.title,
                    style=main_song.style
                )
                click.echo(" ✅")
                logger.debug(f"Analysis: {analysis}")
            else:
                analysis = {}
                click.echo(" ⚠️ (нет текста)")
            
            # Шаг 2: Создаём промпт
            click.echo("   ✍️  Создание промпта...", nl=False)
            prompt = poe.generate_cover_prompt(
                album_title=album.title,
                song_lyrics=main_song.original_lyrics if main_song else "",
                style=analysis.get('style', album.type),
                mood=analysis.get('mood', '')
            )
            click.echo(" ✅")
            
            # Сохраняем промпт
            cover_id = generate_ulid()
            cover_dir = file_manager.covers_dir / cover_id
            cover_dir.mkdir(parents=True, exist_ok=True)
            
            with open(cover_dir / "prompt.txt", 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            # Шаг 3: Генерируем изображение
            click.echo(f"   🎨 Генерация ({settings.poe_cover_model})...", nl=False)
            
            source_path = cover_dir / "source.jpg"
            result_path = poe.generate_cover_image(
                prompt=prompt,
                model=settings.poe_cover_model,
                output_path=source_path
            )
            click.echo(" ✅")
            
            # Шаг 4: Обрабатываем для дистрибьютора
            click.echo(f"   📐 Обработка ({size}x{size})...", nl=False)
            
            processed_path = cover_dir / f"cover_{size}.jpg"
            process_result = processor.process_for_distribution(
                input_path=Path(result_path),
                output_path=processed_path,
                target_size=size
            )
            click.echo(" ✅")
            
            # Проверяем результат
            if process_result['errors']:
                click.echo(f"   ⚠️  Ошибки: {process_result['errors']}")
            
            # Шаг 5: Сохраняем в БД
            cover_obj = Cover(
                id=cover_id,
                album_id=album.id,
                prompt=prompt,
                local_path=str(processed_path),
                state=State.APPROVED
            )
            session.add(cover_obj)
            album.cover_id = cover_id
            session.commit()
            
            click.echo(f"   💾 Сохранено: {processed_path}")
            generated += 1
            
        except Exception as e:
            click.echo(f" ❌ Ошибка: {e}")
            logger.error(f"Cover generation error for album {album.id}: {e}")
            failed += 1
            session.rollback()
    
    click.echo("\n" + "-" * 50)
    click.echo(f"✅ Сгенерировано: {generated}")
    if failed:
        click.echo(f"❌ Ошибок: {failed}")
    
    session.close()


@click.command(name='cover-status')
def cover_status():
    """Показать статус обложек"""
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    total_albums = session.query(Album).count()
    with_covers = session.query(Album).filter(
        (Album.cover_id != None) & (Album.cover_id != '')
    ).count()
    
    pending_covers = session.query(Cover).filter_by(state=State.PENDING).count()
    approved_covers = session.query(Cover).filter_by(state=State.APPROVED).count()
    
    click.echo("📊 Статус обложек:")
    click.echo(f"   Всего альбомов: {total_albums}")
    click.echo(f"   С обложками: {with_covers}")
    click.echo(f"   Без обложек: {total_albums - with_covers}")
    click.echo(f"   Обложек в ожидании: {pending_covers}")
    click.echo(f"   Обложек одобрено: {approved_covers}")
    
    if total_albums - with_covers > 0:
        click.echo(f"\n💡 Запустите: agent cover --all")
    
    session.close()


@click.command(name='cover-validate')
@click.argument('path', type=click.Path(exists=True))
def cover_validate(path: str):
    """Проверить обложку на соответствие требованиям"""
    from ..utils.image_processor import check_cover_requirements
    
    image_path = Path(path)
    click.echo(f"🔍 Проверка: {image_path}")
    
    processor = ImageProcessor()
    result = processor.validate_cover(image_path)
    
    click.echo(f"\nРазмер: {result.get('original_size', 'N/A')}")
    
    if result['valid']:
        click.echo("✅ Обложка соответствует требованиям!")
    else:
        click.echo("❌ Обложка НЕ соответствует:")
        for error in result['errors']:
            click.echo(f"   - {error}")
    
    if result['warnings']:
        click.echo("\n⚠️  Предупреждения:")
        for warning in result['warnings']:
            click.echo(f"   - {warning}")


if __name__ == '__main__':
    cover()

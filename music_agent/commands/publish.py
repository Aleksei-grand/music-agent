"""
Команда: agent publish
Публикация на дистрибьюторах
"""
import click
import logging
from datetime import datetime

from ..config import settings
from ..models import Database, Album, Song, Generation
from ..distributors.factory import DistributorFactory
from ..distributors.base import AlbumInfo, TrackInfo
from ..utils.file_manager import FileManager

logger = logging.getLogger(__name__)


@click.command()
@click.option('--distributor', '-d', required=True,
              type=click.Choice(['routenote', 'sferoom']),
              help='Дистрибьютор для публикации')
@click.option('--album-id', '-a', help='ID альбома для публикации')
@click.option('--all', 'publish_all', is_flag=True,
              help='Опубликовать все готовые альбомы')
@click.option('--cookie', '-c', help='Cookie для аутентификации (или из .env)')
@click.option('--auto-submit', is_flag=True,
              help='Автоматически отправить на модерацию (иначе сохранить черновик)')
@click.option('--headless', is_flag=True, default=True,
              help='Запускать браузер в фоновом режиме')
@click.option('--dry-run', is_flag=True,
              help='Показать что будет опубликовано без реальной загрузки')
def publish(
    distributor: str,
    album_id: str,
    publish_all: bool,
    cookie: str,
    auto_submit: bool,
    headless: bool,
    dry_run: bool
):
    """Опубликовать альбом на дистрибьюторе"""
    
    logging.basicConfig(level=logging.INFO)
    
    # Получаем cookie
    cookie_value = cookie
    if not cookie_value:
        if distributor == 'routenote':
            cookie_value = settings.routenote_cookie
        elif distributor == 'sferoom':
            cookie_value = settings.sferoom_cookie
    
    if not cookie_value:
        click.echo(f"❌ Ошибка: Cookie для {distributor} не указан", err=True)
        click.echo(f"Установите MUSIC_AGENT_{distributor.upper()}_COOKIE в .env или используйте --cookie")
        return
    
    # Подключаемся к БД
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    file_manager = FileManager(settings.fs_conn)
    
    # Находим альбомы для публикации
    albums_to_publish = []
    
    if album_id:
        album = session.query(Album).get(album_id)
        if album:
            albums_to_publish.append(album)
        else:
            click.echo(f"❌ Альбом {album_id} не найден", err=True)
            return
    
    elif publish_all:
        # Альбомы с обложкой и треками, но без публикации
        albums = session.query(Album).all()
        for album in albums:
            if album.cover_id and hasattr(album, 'songs') and album.songs:
                if not album.routenote_id and not album.sferoom_id:
                    albums_to_publish.append(album)
    
    else:
        click.echo("❌ Укажите --album-id или --all", err=True)
        return
    
    if not albums_to_publish:
        click.echo("ℹ️  Нет альбомов для публикации")
        return
    
    click.echo(f"📀 Альбомов для публикации: {len(albums_to_publish)}")
    click.echo(f"🌐 Дистрибьютор: {distributor}")
    click.echo(f"🚀 Авто-отправка: {'ON' if auto_submit else 'OFF (черновик)'}")
    click.echo("-" * 50)
    
    # Создаём дистрибьютор
    try:
        dist = DistributorFactory.create(
            distributor,
            cookie=cookie_value,
            proxy=settings.proxy,
            headless=headless
        )
    except Exception as e:
        click.echo(f"❌ Ошибка создания дистрибьютора: {e}", err=True)
        return
    
    # Публикуем
    published = 0
    failed = 0
    
    for album in albums_to_publish:
        click.echo(f"\n💿 {album.title}")
        
        # Проверяем наличие всех файлов
        if not album.cover:
            click.echo("   ❌ Нет обложки")
            failed += 1
            continue
        
        cover_path = Path(album.cover.local_path)
        if not cover_path.exists():
            click.echo(f"   ❌ Файл обложки не найден: {cover_path}")
            failed += 1
            continue
        
        # Собираем треки
        tracks = []
        album_dir = file_manager.get_album_dir(album.id)
        
        for song in sorted(album.songs, key=lambda s: s.order):
            if not song.generation:
                continue
            
            # Ищем обработанный файл
            track_file = None
            for ext in ['mp3', 'wav', 'flac']:
                candidate = album_dir / f"{song.order:02d}-{song.title}.{ext}"
                if candidate.exists():
                    track_file = candidate
                    break
            
            if not track_file:
                click.echo(f"   ⚠️  Не найден файл для: {song.title}")
                continue
            
            tracks.append(TrackInfo(
                title=song.title,
                file_path=track_file,
                order=song.order,
                isrc=song.isrc,
                lyrics=song.translated_lyrics or song.original_lyrics
            ))
        
        if not tracks:
            click.echo("   ❌ Нет треков для загрузки")
            failed += 1
            continue
        
        # Создаём объект альбома
        album_info = AlbumInfo(
            title=album.title,
            artist=album.artist or "Unknown Artist",
            tracks=tracks,
            cover_path=cover_path,
            primary_genre=album.primary_genre or "Pop",
            secondary_genre=album.secondary_genre,
            upc=album.upc,
            record_label=album.record_label,
            first_name=album.first_name,
            last_name=album.last_name
        )
        
        # Валидация
        errors = dist.validate_album(album_info)
        if errors:
            click.echo("   ❌ Ошибки валидации:")
            for error in errors:
                click.echo(f"      - {error}")
            failed += 1
            continue
        
        if dry_run:
            click.echo(f"   [DRY RUN] Будет опубликовано: {len(tracks)} треков")
            published += 1
            continue
        
        # Публикация
        try:
            click.echo("   🔄 Загрузка...", nl=False)
            
            result = dist.upload_album(album_info, auto_submit=auto_submit)
            
            if result.success:
                click.echo(" ✅")
                click.echo(f"   📋 ID: {result.distributor_id}")
                click.echo(f"   🔗 URL: {result.url}")
                
                # Сохраняем в БД
                if distributor == 'routenote':
                    album.routenote_id = result.distributor_id
                elif distributor == 'sferoom':
                    album.sferoom_id = result.distributor_id
                
                album.published = True
                album.published_at = datetime.utcnow()
                session.commit()
                
                published += 1
            else:
                click.echo(" ❌")
                click.echo(f"   Ошибка: {result.message}")
                for error in result.errors:
                    click.echo(f"      - {error}")
                failed += 1
                
        except Exception as e:
            click.echo(f" ❌ Ошибка: {e}")
            logger.error(f"Publish error for {album.id}: {e}")
            failed += 1
    
    click.echo("\n" + "-" * 50)
    click.echo(f"✅ Опубликовано: {published}")
    if failed:
        click.echo(f"❌ Ошибок: {failed}")
    
    session.close()


@click.command(name='publish-status')
@click.option('--distributor', '-d', help='Фильтр по дистрибьютору')
def publish_status(distributor: str):
    """Показать статус публикаций"""
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    query = session.query(Album)
    
    if distributor == 'routenote':
        albums = query.filter(Album.routenote_id != None).all()
    elif distributor == 'sferoom':
        albums = query.filter(Album.sferoom_id != None).all()
    else:
        albums = query.filter(
            (Album.routenote_id != None) | (Album.sferoom_id != None)
        ).all()
    
    if not albums:
        click.echo("ℹ️  Нет опубликованных альбомов")
        return
    
    click.echo(f"📀 Опубликованных альбомов: {len(albums)}")
    click.echo("-" * 50)
    
    for album in albums:
        click.echo(f"\n💿 {album.title}")
        if album.routenote_id:
            click.echo(f"   RouteNote: {album.routenote_id}")
        if album.sferoom_id:
            click.echo(f"   Sferoom: {album.sferoom_id}")
        click.echo(f"   Дата: {album.published_at}")
    
    session.close()


@click.command(name='check-status')
@click.option('--distributor', '-d', required=True,
              type=click.Choice(['routenote', 'sferoom']))
@click.option('--album-id', '-a', required=True,
              help='ID альбома в системе')
@click.option('--cookie', '-c', help='Cookie для аутентификации')
@click.option('--headless', is_flag=True, default=True)
def check_status(distributor: str, album_id: str, cookie: str, headless: bool):
    """Проверить статус релиза на дистрибьюторе"""
    
    cookie_value = cookie
    if not cookie_value:
        if distributor == 'routenote':
            cookie_value = settings.routenote_cookie
        elif distributor == 'sferoom':
            cookie_value = settings.sferoom_cookie
    
    if not cookie_value:
        click.echo("❌ Cookie не указан", err=True)
        return
    
    try:
        dist = DistributorFactory.create(
            distributor,
            cookie=cookie_value,
            headless=headless
        )
        
        click.echo(f"🔍 Проверка статуса {album_id} на {distributor}...")
        
        status = dist.check_status(album_id)
        
        click.echo(f"\nСтатус: {status.get('status', 'unknown')}")
        
        if status.get('live'):
            click.echo("✅ Релиз опубликован!")
        elif status.get('in_review'):
            click.echo("⏳ На модерации")
        elif status.get('rejected'):
            click.echo("❌ Отклонён")
            
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}", err=True)


if __name__ == '__main__':
    publish()

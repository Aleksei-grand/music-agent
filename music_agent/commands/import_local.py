"""
Команда: agent import
Импорт локальных аудио файлов (без Suno)
"""
import click
import logging
from pathlib import Path
from datetime import datetime

from ..config import settings
from ..models import Database, Song, Generation, Album
from ..utils.file_manager import FileManager
from ..utils.id_generator import generate_ulid
from ..utils.transliterator import auto_transliterate

logger = logging.getLogger(__name__)


@click.command()
@click.argument('files', nargs=-1, required=True)
@click.option('--title', '-t', help='Название песни (если не указано - из имени файла)')
@click.option('--artist', '-a', default='', help='Исполнитель')
@click.option('--album', help='ID альбома (или создать новый)')
@click.option('--create-album', is_flag=True, help='Создать новый альбом')
@click.option('--album-title', help='Название нового альбома (с --create-album)')
@click.option('--type', 'song_type', default='Pop', help='Жанр/тип песни')
@click.option('--lyrics', '-l', help='Текст песни')
@click.option('--dry-run', is_flag=True, help='Показать что будет сделано')
def import_files(files, title, artist, album, create_album, album_title, song_type, lyrics, dry_run):
    """
    Импортировать локальные аудио файлы в систему
    
    Examples:
        agent import /path/to/song.mp3
        agent import /path/to/*.mp3 --artist "My Name" --create-album --album-title "My Album"
        agent import song.mp3 --title "My Song" --lyrics "file://lyrics.txt"
    """
    logging.basicConfig(level=logging.INFO)
    
    if not files:
        click.echo("❌ Укажите файлы для импорта", err=True)
        return
    
    # Подключаемся
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    file_manager = FileManager(settings.fs_conn)
    
    # Загружаем lyrics из файла если указано
    if lyrics and lyrics.startswith('file://'):
        lyrics_file = Path(lyrics[7:])
        if lyrics_file.exists():
            lyrics = lyrics_file.read_text(encoding='utf-8')
        else:
            click.echo(f"❌ Файл lyrics не найден: {lyrics_file}")
            return
    
    # Определяем альбом
    album_id = None
    if create_album:
        # Создаём новый альбом
        album_id = generate_ulid()
        album_obj = Album(
            id=album_id,
            title=album_title or f"Imported {datetime.now().strftime('%Y-%m-%d')}",
            artist=artist or "Unknown Artist",
            type="Album",
            created_at=datetime.utcnow()
        )
        if not dry_run:
            session.add(album_obj)
            session.commit()
        click.echo(f"📀 {'[DRY RUN] ' if dry_run else ''}Создан альбом: {album_obj.title} ({album_id})")
    elif album:
        # Используем существующий
        album_obj = session.query(Album).get(album)
        if not album_obj:
            click.echo(f"❌ Альбом {album} не найден", err=True)
            session.close()
            return
        album_id = album
        click.echo(f"📀 Добавляем в альбом: {album_obj.title}")
    
    imported = 0
    
    for i, file_path in enumerate(files, 1):
        path = Path(file_path)
        if not path.exists():
            click.echo(f"❌ Файл не найден: {path}")
            continue
        
        # Определяем название
        song_title = title or path.stem
        click.echo(f"\n🎵 {song_title}")
        
        # Генерируем ID
        gen_id = generate_ulid()
        song_id = generate_ulid()
        
        # Копируем в raw/
        raw_dir = file_manager.get_raw_track_dir(gen_id)
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / "audio.mp3"
        
        if dry_run:
            click.echo(f"   [DRY RUN] Скопировать {path} → {raw_path}")
        else:
            import shutil
            shutil.copy2(path, raw_path)
            click.echo(f"   ✅ Скопировано в {raw_path}")
        
        # Авто-транслитерация
        intl_title = auto_transliterate(song_title)
        click.echo(f"   🌐 Международное название: {intl_title}")
        
        if not dry_run:
            # Создаём Generation
            gen = Generation(
                id=gen_id,
                external_id=f"local_{gen_id}",  # Префикс для локальных файлов
                title=song_title,
                lyrics=lyrics or "",
                processed=False,
                created_at=datetime.utcnow()
            )
            session.add(gen)
            
            # Создаём Song
            song = Song(
                id=song_id,
                title=song_title,
                intl_title=intl_title,
                type=song_type,
                album_id=album_id or "",
                order=i,
                generation_id=gen_id,
                original_lyrics=lyrics or "",
                provider="local",
                created_at=datetime.utcnow()
            )
            session.add(song)
            session.commit()
            
            click.echo(f"   ✅ Сохранено в БД: {song_id}")
        else:
            click.echo(f"   [DRY RUN] Создать Generation: {gen_id}")
            click.echo(f"   [DRY RUN] Создать Song: {song_id}")
        
        imported += 1
    
    session.close()
    
    click.echo(f"\n{'='*50}")
    click.echo(f"✅ Импортировано: {imported} файлов")
    
    if album_id and not dry_run:
        click.echo(f"\nСледующие шаги:")
        click.echo(f"  1. agent cover --album-id {album_id}")
        click.echo(f"  2. agent process --album-id {album_id}")
        click.echo(f"  3. agent publish --album-id {album_id}")


@click.command()
@click.option('--album-id', '-a', required=True, help='ID альбома для сканирования')
def scan_raw(album_id: str):
    """
    Сканировать папку raw/ и добавить существующие файлы в альбом
    
    Полезно если вы скопировали файлы вручную
    """
    logging.basicConfig(level=logging.INFO)
    
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    file_manager = FileManager(settings.fs_conn)
    
    # Проверяем альбом
    album = session.query(Album).get(album_id)
    if not album:
        click.echo(f"❌ Альбом {album_id} не найден", err=True)
        session.close()
        return
    
    click.echo(f"📀 Сканирование raw/ для альбома: {album.title}")
    
    # Ищем папки в raw/
    found = 0
    added = 0
    
    for raw_subdir in file_manager.raw_dir.iterdir():
        if not raw_subdir.is_dir():
            continue
        
        audio_file = raw_subdir / "audio.mp3"
        if not audio_file.exists():
            continue
        
        found += 1
        track_id = raw_subdir.name
        
        # Проверяем, есть ли уже в БД
        existing = session.query(Generation).filter_by(external_id=track_id).first()
        if existing:
            click.echo(f"   ℹ️  Уже в БД: {track_id}")
            continue
        
        # Создаём запись
        gen_id = generate_ulid()
        song_id = generate_ulid()
        
        # Используем имя папки как название (можно улучшить)
        song_title = track_id.replace('_', ' ').replace('-', ' ')
        intl_title = auto_transliterate(song_title)
        
        gen = Generation(
            id=gen_id,
            external_id=track_id,
            title=song_title,
            processed=False,
            created_at=datetime.utcnow()
        )
        session.add(gen)
        
        song = Song(
            id=song_id,
            title=song_title,
            intl_title=intl_title,
            album_id=album_id,
            order=found,
            generation_id=gen_id,
            provider="local",
            created_at=datetime.utcnow()
        )
        session.add(song)
        
        click.echo(f"   ✅ Добавлен: {song_title}")
        added += 1
    
    session.commit()
    session.close()
    
    click.echo(f"\n{'='*50}")
    click.echo(f"Найдено папок: {found}")
    click.echo(f"Добавлено новых: {added}")


if __name__ == '__main__':
    import_files()

"""
Команды: agent export / agent import
Экспорт и импорт данных
"""
import click
import json
import logging
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

from ..config import settings
from ..models import Database, Album, Song, Generation, Cover

logger = logging.getLogger(__name__)


@click.group(name="export")
def export_group():
    """📤 Экспорт данных"""
    pass


@click.group(name="import")
def import_group():
    """📥 Импорт данных"""
    pass


@click.command(name="json")
@click.option('--output', '-o', default='myflowmusic_export.json', help='Файл для экспорта')
@click.option('--albums', is_flag=True, help='Только альбомы')
@click.option('--songs', is_flag=True, help='Только песни')
@click.option('--full', is_flag=True, help='Полный экспорт со всеми связями')
def export_json(output: str, albums: bool, songs: bool, full: bool):
    """Экспорт в JSON"""
    
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "version": "1.0"
    }
    
    # Если не указано что конкретно - экспортируем всё
    export_all = not (albums or songs) or full
    
    if export_all or albums:
        click.echo("📀 Экспорт альбомов...")
        albums_data = []
        for album in session.query(Album).all():
            albums_data.append({
                "id": album.id,
                "title": album.title,
                "subtitle": album.subtitle,
                "artist": album.artist,
                "primary_genre": album.primary_genre,
                "secondary_genre": album.secondary_genre,
                "upc": album.upc,
                "published": album.published,
                "published_at": album.published_at.isoformat() if album.published_at else None,
                "routenote_id": album.routenote_id,
                "sferoom_id": album.sferoom_id,
                "created_at": album.created_at.isoformat() if album.created_at else None
            })
        data["albums"] = albums_data
        click.echo(f"   ✅ {len(albums_data)} альбомов")
    
    if export_all or songs:
        click.echo("🎵 Экспорт песен...")
        songs_data = []
        for song in session.query(Song).all():
            songs_data.append({
                "id": song.id,
                "title": song.title,
                "album_id": song.album_id,
                "order": song.order,
                "style": song.style,
                "type": song.type,
                "original_lyrics": song.original_lyrics,
                "translated_lyrics": song.translated_lyrics,
                "translated_to": song.translated_to,
                "isrc": song.isrc,
                "state": song.state,
                "created_at": song.created_at.isoformat() if song.created_at else None
            })
        data["songs"] = songs_data
        click.echo(f"   ✅ {len(songs_data)} песен")
    
    if full:
        click.echo("🎨 Экспорт обложек...")
        covers_data = []
        for cover in session.query(Cover).all():
            covers_data.append({
                "id": cover.id,
                "album_id": cover.album_id,
                "prompt": cover.prompt,
                "local_path": cover.local_path,
                "state": cover.state,
                "created_at": cover.created_at.isoformat() if cover.created_at else None
            })
        data["covers"] = covers_data
        click.echo(f"   ✅ {len(covers_data)} обложек")
        
        click.echo("⚡ Экспорт генераций...")
        gens_data = []
        for gen in session.query(Generation).all():
            gens_data.append({
                "id": gen.id,
                "external_id": gen.external_id,
                "title": gen.title,
                "lyrics": gen.lyrics,
                "style": gen.style,
                "duration": gen.duration,
                "processed": gen.processed,
                "processed_at": gen.processed_at.isoformat() if gen.processed_at else None,
                "created_at": gen.created_at.isoformat() if gen.created_at else None
            })
        data["generations"] = gens_data
        click.echo(f"   ✅ {len(gens_data)} генераций")
    
    session.close()
    
    # Сохраняем
    output_path = Path(output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    click.echo(f"\n💾 Экспортировано в: {output_path}")
    click.echo(f"📊 Размер: {output_path.stat().st_size / 1024:.1f} KB")


@click.command(name="archive")
@click.option('--output', '-o', default=None, help='Имя архива')
@click.option('--include-audio', is_flag=True, help='Включить аудио файлы')
def export_archive(output: str, include_audio: bool):
    """Экспорт в ZIP архив (JSON + файлы)"""
    
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"myflowmusic_backup_{timestamp}.zip"
    
    output_path = Path(output)
    
    with click.progressbar(length=100, label='Создание архива') as bar:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Экспортируем JSON
            bar.update(10)
            db = Database(settings.db_type, settings.db_conn).connect()
            session = db.session()
            
            data = {
                "exported_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "albums": [],
                "songs": [],
                "covers": [],
                "generations": []
            }
            
            for album in session.query(Album).all():
                data["albums"].append({
                    "id": album.id,
                    "title": album.title,
                    "artist": album.artist,
                    "primary_genre": album.primary_genre,
                    "published": album.published
                })
            
            for song in session.query(Song).all():
                data["songs"].append({
                    "id": song.id,
                    "title": song.title,
                    "album_id": song.album_id,
                    "original_lyrics": song.original_lyrics,
                    "translated_lyrics": song.translated_lyrics
                })
            
            session.close()
            bar.update(30)
            
            # Добавляем JSON в архив
            zf.writestr('data.json', json.dumps(data, ensure_ascii=False, indent=2))
            
            # 2. Добавляем файлы обложек
            covers_dir = Path(settings.fs_conn) / "covers"
            if covers_dir.exists():
                for cover_file in covers_dir.rglob("*.jpg"):
                    arcname = f"covers/{cover_file.parent.name}/{cover_file.name}"
                    zf.write(cover_file, arcname)
            
            bar.update(30)
            
            # 3. Добавляем аудио если нужно
            if include_audio:
                albums_dir = Path(settings.fs_conn) / "albums"
                if albums_dir.exists():
                    for audio_file in albums_dir.rglob("*.mp3"):
                        arcname = f"audio/{audio_file.parent.name}/{audio_file.name}"
                        zf.write(audio_file, arcname)
            
            bar.update(30)
    
    click.echo(f"\n💾 Архив создан: {output_path}")
    click.echo(f"📊 Размер: {output_path.stat().st_size / 1024 / 1024:.1f} MB")


@click.command(name="json")
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='Проверить без импорта')
def import_json(input_file: str, dry_run: bool):
    """Импорт из JSON"""
    
    input_path = Path(input_file)
    
    click.echo(f"📂 Чтение файла: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    stats = {"albums": 0, "songs": 0, "skipped": 0}
    
    # Импорт альбомов
    if "albums" in data:
        click.echo(f"\n📀 Импорт альбомов...")
        for album_data in data["albums"]:
            # Проверяем существование
            existing = session.query(Album).get(album_data["id"])
            if existing:
                click.echo(f"   ⏭️  Пропущен (уже есть): {album_data.get('title')}")
                stats["skipped"] += 1
                continue
            
            if not dry_run:
                album = Album(
                    id=album_data["id"],
                    title=album_data.get("title", ""),
                    subtitle=album_data.get("subtitle", ""),
                    artist=album_data.get("artist", ""),
                    primary_genre=album_data.get("primary_genre", ""),
                    secondary_genre=album_data.get("secondary_genre", ""),
                    upc=album_data.get("upc", ""),
                    published=album_data.get("published", False),
                    routenote_id=album_data.get("routenote_id", ""),
                    sferoom_id=album_data.get("sferoom_id", "")
                )
                session.add(album)
                stats["albums"] += 1
            
            click.echo(f"   ✅ {album_data.get('title')}")
    
    # Импорт песен
    if "songs" in data:
        click.echo(f"\n🎵 Импорт песен...")
        for song_data in data["songs"]:
            existing = session.query(Song).get(song_data["id"])
            if existing:
                stats["skipped"] += 1
                continue
            
            if not dry_run:
                song = Song(
                    id=song_data["id"],
                    title=song_data.get("title", ""),
                    album_id=song_data.get("album_id", ""),
                    order=song_data.get("order", 0),
                    style=song_data.get("style", ""),
                    type=song_data.get("type", ""),
                    original_lyrics=song_data.get("original_lyrics", ""),
                    translated_lyrics=song_data.get("translated_lyrics", ""),
                    translated_to=song_data.get("translated_to", ""),
                    isrc=song_data.get("isrc", ""),
                    state=song_data.get("state", 0)
                )
                session.add(song)
                stats["songs"] += 1
            
            click.echo(f"   ✅ {song_data.get('title')}")
    
    if not dry_run:
        session.commit()
    
    session.close()
    
    click.echo(f"\n{'[DRY RUN] ' if dry_run else ''}📊 Импорт завершён:")
    click.echo(f"   Альбомов: {stats['albums']}")
    click.echo(f"   Песен: {stats['songs']}")
    click.echo(f"   Пропущено: {stats['skipped']}")


@click.command(name="check")
@click.argument('input_file', type=click.Path(exists=True))
def check_import(input_file: str):
    """Проверить файл импорта"""
    
    input_path = Path(input_file)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    click.echo("📋 Содержимое файла:")
    click.echo(f"   Версия: {data.get('version', 'unknown')}")
    click.echo(f"   Дата экспорта: {data.get('exported_at', 'unknown')}")
    
    click.echo("\n📦 Объекты:")
    if "albums" in data:
        click.echo(f"   Альбомов: {len(data['albums'])}")
    if "songs" in data:
        click.echo(f"   Песен: {len(data['songs'])}")
    if "covers" in data:
        click.echo(f"   Обложек: {len(data['covers'])}")
    if "generations" in data:
        click.echo(f"   Генераций: {len(data['generations'])}")
    
    # Проверяем конфликты
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    conflicts = 0
    if "albums" in data:
        for album_data in data["albums"]:
            if session.query(Album).get(album_data["id"]):
                conflicts += 1
    
    session.close()
    
    if conflicts:
        click.echo(f"\n⚠️  Конфликтов ID: {conflicts} (будут пропущены)")
    else:
        click.echo("\n✅ Конфликтов не найдено")


# Регистрируем команды
export_group.add_command(export_json)
export_group.add_command(export_archive)

import_group.add_command(import_json)
import_group.add_command(check_import)


# Aliases
@click.command(name="backup")
@click.option('--output', '-o', default=None, help='Имя файла')
def backup(output: str):
    """Быстрый бэкап (alias для export archive)"""
    ctx = click.get_current_context()
    ctx.invoke(export_archive, output=output, include_audio=False)


@click.command(name="restore")
@click.argument('backup_file', type=click.Path(exists=True))
def restore(backup_file: str):
    """Восстановление из бэкапа"""
    # Разархивируем и импортируем
    import tempfile
    
    backup_path = Path(backup_file)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        click.echo("📂 Распаковка архива...")
        with zipfile.ZipFile(backup_path, 'r') as zf:
            zf.extractall(tmpdir)
        
        # Импортируем JSON
        json_file = Path(tmpdir) / "data.json"
        if json_file.exists():
            ctx = click.get_current_context()
            ctx.invoke(import_json, input_file=str(json_file), dry_run=False)
        
        # Копируем обложки
        covers_dir = Path(tmpdir) / "covers"
        if covers_dir.exists():
            target_covers = Path(settings.fs_conn) / "covers"
            click.echo("🎨 Восстановление обложек...")
            for cover_dir in covers_dir.iterdir():
                if cover_dir.is_dir():
                    target = target_covers / cover_dir.name
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(cover_dir, target)


if __name__ == '__main__':
    export_group()

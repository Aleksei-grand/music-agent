"""
Команда: agent process
Обработка аудио файлов
- Конвертация
- Fade-out
- Нормализация
- Запись тегов
"""
import click
import logging
from pathlib import Path
from datetime import datetime

from ..config import settings
from ..models import Database, Song, Generation, Album
from ..audio.processor import AudioProcessor
from ..audio.analyzer import AudioAnalyzer, QualityChecker
from ..utils.file_manager import FileManager
from ..utils.id_generator import generate_ulid

logger = logging.getLogger(__name__)


@click.command()
@click.option('--song-id', '-s', help='ID конкретной песни')
@click.option('--album-id', '-a', help='ID альбома (обработать все песни)')
@click.option('--all', 'process_all', is_flag=True, help='Обработать все необработанные')
@click.option('--format', '-f', 'output_format', default='mp3', 
              type=click.Choice(['mp3', 'wav', 'flac', 'm4a']), 
              help='Выходной формат')
@click.option('--fade-out', default=3.0, help='Длительность fade-out (секунды)')
@click.option('--no-normalize', is_flag=True, help='Отключить нормализацию громкости')
@click.option('--check-only', is_flag=True, help='Только проверить качество, не обрабатывать')
@click.option('--dry-run', is_flag=True, help='Показать что будет сделано')
def process(
    song_id: str,
    album_id: str,
    process_all: bool,
    output_format: str,
    fade_out: float,
    no_normalize: bool,
    check_only: bool,
    dry_run: bool
):
    """Обработать аудио файлы для дистрибуции"""
    
    logging.basicConfig(level=logging.INFO)
    
    # Подключаемся к БД
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    # Инициализируем процессор
    processor = AudioProcessor(settings.ffmpeg_path)
    analyzer = AudioAnalyzer(settings.ffmpeg_path)
    file_manager = FileManager(settings.fs_conn)
    
    # Определяем что обрабатывать
    songs_to_process = []
    
    if song_id:
        song = session.query(Song).get(song_id)
        if song:
            songs_to_process.append(song)
        else:
            click.echo(f"❌ Песня {song_id} не найдена", err=True)
            return
    
    elif album_id:
        album = session.query(Album).get(album_id)
        if album and hasattr(album, 'songs'):
            songs_to_process = album.songs
        else:
            click.echo(f"❌ Альбом {album_id} не найден", err=True)
            return
    
    elif process_all:
        # Все песни с необработанными generation
        songs_to_process = session.query(Song).join(Generation).filter(
            Generation.processed == False
        ).all()
    
    else:
        click.echo("❌ Укажите --song-id, --album-id или --all", err=True)
        return
    
    if not songs_to_process:
        click.echo("ℹ️  Нет песен для обработки")
        return
    
    click.echo(f"🎵 Песен для обработки: {len(songs_to_process)}")
    click.echo(f"📐 Формат: {output_format}")
    click.echo(f"🔉 Fade-out: {fade_out}s")
    click.echo(f"📢 Нормализация: {'OFF' if no_normalize else 'ON (-14 LUFS)'}")
    click.echo("-" * 50)
    
    processed = 0
    failed = 0
    
    for song in songs_to_process:
        click.echo(f"\n🎵 {song.title}")
        
        # Получаем generation (исходный файл)
        if not song.generation:
            click.echo("   ❌ Нет исходного файла (generation)")
            continue
        
        gen = song.generation
        input_path = file_manager.raw_dir / gen.external_id / "audio.mp3"
        
        if not input_path.exists():
            click.echo(f"   ❌ Файл не найден: {input_path}")
            continue
        
        # Если только проверка
        if check_only:
            click.echo("   🔍 Проверка качества...", nl=False)
            check = QualityChecker.check_all(input_path, analyzer)
            
            if check['passed']:
                click.echo(" ✅ OK")
            else:
                click.echo(" ❌ Есть проблемы:")
                for issue in check['issues']:
                    click.echo(f"      - {issue}")
            
            if check['warnings']:
                click.echo("   ⚠️  Предупреждения:")
                for warning in check['warnings']:
                    click.echo(f"      - {warning}")
            
            # Показываем анализ
            analysis = check['analysis']
            if analysis.get('bpm'):
                click.echo(f"   📊 BPM: {analysis['bpm']}")
            if analysis.get('duration'):
                click.echo(f"   ⏱️  Длительность: {analysis['duration']:.1f}s")
            
            continue
        
        # Формируем выходной путь с использованием международного названия
        from ..utils.transliterator import auto_transliterate, generate_filename
        
        # Получаем международное название
        if song.intl_title:
            intl_title = song.intl_title
        else:
            intl_title = auto_transliterate(song.title)
        
        version_type = song.translated_to.lower() if song.translated_to else 'original'
        safe_name = generate_filename(intl_title, version_type)
        output_filename = f"{song.order:02d}-{safe_name}.{output_format}"
        
        album_dir = file_manager.get_album_dir(song.album_id or 'unreleased')
        output_path = album_dir / output_filename
        
        if dry_run:
            click.echo(f"   [DRY RUN] Будет создан: {output_path}")
            processed += 1
            continue
        
        # Обрабатываем
        try:
            click.echo("   🔄 Обработка...", nl=False)
            
            # Подготавливаем метаданные
            metadata = {
                'title': song.title,
                'artist': song.album.artist if song.album else 'Unknown Artist',
                'album': song.album.title if song.album else 'Unknown Album',
                'genre': song.type or 'Pop',
                'track': str(song.order)
            }
            
            # Обработка
            result = processor.process_track(
                input_path=input_path,
                output_path=output_path,
                format=output_format,
                fade_out=fade_out,
                normalize_lufs=not no_normalize,
                trim_silence=True,
                metadata=metadata
            )
            
            if result['success']:
                click.echo(" ✅")
                
                # Показываем что сделали
                for op in result.get('operations', []):
                    click.echo(f"      ✓ {op}")
                
                # Добавляем обложку если есть
                if song.album and song.album.cover:
                    cover_path = Path(song.album.cover.local_path)
                    if cover_path.exists():
                        processor.add_metadata(output_path, {}, cover_path)
                        click.echo("      ✓ Добавлена обложка")
                
                # Обновляем в БД
                gen.processed = True
                gen.processed_at = datetime.utcnow()
                session.commit()
                
                processed += 1
            else:
                click.echo(" ❌")
                for error in result.get('errors', []):
                    click.echo(f"      - {error}")
                failed += 1
                
        except Exception as e:
            click.echo(f" ❌ Ошибка: {e}")
            logger.error(f"Processing error for {song.id}: {e}")
            failed += 1
    
    click.echo("\n" + "-" * 50)
    click.echo(f"✅ Обработано: {processed}")
    if failed:
        click.echo(f"❌ Ошибок: {failed}")
    
    session.close()


@click.command(name='process-status')
def process_status():
    """Показать статус обработки аудио"""
    from datetime import datetime
    
    db = Database(settings.db_type, settings.db_conn).connect()
    session = db.session()
    
    total_gen = session.query(Generation).count()
    processed = session.query(Generation).filter_by(processed=True).count()
    pending = total_gen - processed
    
    click.echo("📊 Статус обработки аудио:")
    click.echo(f"   Всего генераций: {total_gen}")
    click.echo(f"   Обработано: {processed}")
    click.echo(f"   Ожидает: {pending}")
    
    if pending > 0:
        click.echo(f"\n💡 Запустите: agent process --all")
    
    session.close()


@click.command(name='audio-info')
@click.argument('path', type=click.Path(exists=True))
def audio_info(path: str):
    """Показать информацию об аудио файле"""
    file_path = Path(path)
    
    processor = AudioProcessor()
    analyzer = AudioAnalyzer()
    
    click.echo(f"🔍 Анализ: {file_path}")
    click.echo("-" * 50)
    
    # Базовая информация
    info = processor.get_info(file_path)
    if 'error' not in info:
        click.echo(f"📐 Формат: {info.get('format', 'Unknown')}")
        click.echo(f"⏱️  Длительность: {info.get('duration', 0):.2f} сек")
        click.echo(f"🎚️  Sample rate: {info.get('sample_rate', 0)} Hz")
        click.echo(f"🔊 Каналов: {info.get('channels', 0)}")
        click.echo(f"📦 Битрейт: {info.get('bitrate', 'Unknown')} kbps")
        click.echo(f"🔧 Кодек: {info.get('codec', 'Unknown')}")
    else:
        click.echo(f"❌ Ошибка: {info['error']}")
        return
    
    click.echo("\n📊 Расширенный анализ...")
    
    # BPM
    bpm = analyzer.detect_bpm(file_path)
    if bpm:
        click.echo(f"🥁 BPM: {bpm:.1f}")
    
    # Громкость
    loudness = analyzer.analyze_loudness(file_path)
    if loudness:
        click.echo(f"🔉 Громкость: {loudness['integrated']:.1f} LUFS")
        click.echo(f"📈 True Peak: {loudness['true_peak']:.1f} dB")
    
    # Тишина
    silences = analyzer.detect_silence(file_path)
    if silences:
        click.echo(f"🔇 Участков тишины: {len(silences)}")
        for s in silences[:3]:  # Первые 3
            click.echo(f"      {s['start']:.1f}s - {s['end']:.1f}s ({s['duration']:.1f}s)")
    
    # Клиппинг
    has_clipping = analyzer.detect_clipping(file_path)
    if has_clipping:
        click.echo("⚠️  Обнаружен клиппинг!")
    
    # Валидация
    validation = processor.validate_for_distribution(file_path)
    click.echo("\n✅ Проверка для дистрибуции:")
    if validation['valid']:
        click.echo("   Файл готов к публикации!")
    else:
        click.echo("   ❌ Проблемы:")
        for error in validation['errors']:
            click.echo(f"      - {error}")
    
    if validation['warnings']:
        click.echo("   ⚠️  Предупреждения:")
        for warning in validation['warnings']:
            click.echo(f"      - {warning}")


if __name__ == '__main__':
    process()

"""
Аудио процессор для подготовки треков к дистрибуции
- Конвертация форматов
- Fade-out
- Нормализация громкости
- Запись ID3 тегов
"""
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple
import json
import re

from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range

logger = logging.getLogger(__name__)


class AudioRequirements:
    """Требования дистрибьюторов к аудио"""
    
    # Форматы
    FORMATS = {
        'wav': {'codec': 'pcm_s16le', 'ext': 'wav'},
        'mp3': {'codec': 'libmp3lame', 'ext': 'mp3', 'bitrate': '320k'},
        'flac': {'codec': 'flac', 'ext': 'flac'},
        'm4a': {'codec': 'aac', 'ext': 'm4a', 'bitrate': '256k'}
    }
    
    # Качество
    SAMPLE_RATE = 44100  # Hz
    MIN_SAMPLE_RATE = 44100
    BIT_DEPTH = 16  # bits
    CHANNELS = 2  # Stereo
    
    # Громкость (LUFS - Loudness Units Full Scale)
    TARGET_LUFS = -14  # Стандарт для стриминговых платформ
    TARGET_TRUE_PEAK = -1.0  # dB
    LOUDNESS_RANGE = 11  # LU


class AudioProcessor:
    """Процессор аудио файлов"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        self.requirements = AudioRequirements()
    
    def process_track(
        self,
        input_path: Path,
        output_path: Path,
        format: str = "mp3",
        fade_out: Optional[float] = None,
        normalize_lufs: bool = True,
        trim_silence: bool = True,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Полная обработка трека
        
        Args:
            input_path: Входной файл
            output_path: Куда сохранить
            format: Выходной формат (mp3, wav, flac)
            fade_out: Длительность fade-out в секундах
            normalize_lufs: Нормализовать громкость до -14 LUFS
            trim_silence: Обрезать тишину в конце
            metadata: ID3 теги {title, artist, album, ...}
            
        Returns:
            dict с результатами обработки
        """
        logger.info(f"Processing: {input_path} -> {output_path}")
        
        result = {
            'input': str(input_path),
            'output': str(output_path),
            'success': False,
            'operations': [],
            'errors': []
        }
        
        try:
            # Загружаем аудио
            audio = AudioSegment.from_file(str(input_path))
            original_duration = len(audio) / 1000  # секунды
            
            logger.info(f"Loaded: {len(audio)/1000:.2f}s, {audio.channels}ch, {audio.frame_rate}Hz")
            
            # 1. Обрезка тишины в конце
            if trim_silence:
                logger.info("Trimming end silence...")
                audio = self._trim_end_silence(audio, silence_threshold=-50, min_silence_len=1000)
                if len(audio) < original_duration * 1000:
                    result['operations'].append(f"trimmed_silence ({original_duration - len(audio)/1000:.1f}s)")
            
            # 2. Fade-out
            if fade_out and fade_out > 0:
                logger.info(f"Applying fade-out: {fade_out}s")
                fade_ms = int(fade_out * 1000)
                if len(audio) > fade_ms:
                    # Fade-out последние N секунд
                    audio = audio.fade_out(fade_ms)
                    result['operations'].append(f"fade_out ({fade_out}s)")
            
            # 3. Нормализация громкости (LUFS)
            if normalize_lufs:
                logger.info(f"Normalizing to {self.requirements.TARGET_LUFS} LUFS...")
                audio = self._normalize_lufs(audio, target_lufs=self.requirements.TARGET_LUFS)
                result['operations'].append(f"normalized_lufs ({self.requirements.TARGET_LUFS} LUFS)")
            
            # 4. Конвертация формата и сохранение
            logger.info(f"Converting to {format}...")
            
            # Убеждаемся что частота дискретизации корректная
            if audio.frame_rate != self.requirements.SAMPLE_RATE:
                audio = audio.set_frame_rate(self.requirements.SAMPLE_RATE)
            
            # Экспортируем
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            export_params = {
                'format': format,
                'tags': metadata or {}
            }
            
            if format == 'mp3':
                export_params['bitrate'] = self.requirements.FORMATS['mp3']['bitrate']
                export_params['id3v2_version'] = '3'
            elif format == 'm4a':
                export_params['bitrate'] = self.requirements.FORMATS['m4a']['bitrate']
            
            audio.export(str(output_path), **export_params)
            
            result['success'] = True
            result['duration'] = len(audio) / 1000
            result['format'] = format
            
            logger.info(f"Saved: {output_path} ({result['duration']:.2f}s)")
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def _trim_end_silence(self, audio: AudioSegment, 
                          silence_threshold: int = -50, 
                          min_silence_len: int = 1000) -> AudioSegment:
        """Обрезать тишину в конце трека"""
        # Находим последний не-тишиный участок
        from pydub.silence import detect_nonsilent
        
        ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_threshold
        )
        
        if ranges:
            # Берём от начала до конца последнего звукового участка
            last_end = ranges[-1][1]
            # Добавляем немного тишины (200ms) для естественности
            end_pos = min(last_end + 200, len(audio))
            return audio[:end_pos]
        
        return audio
    
    def _normalize_lufs(self, audio: AudioSegment, target_lufs: float = -14) -> AudioSegment:
        """
        Нормализация громкости до стандарта LUFS
        Использует ffmpeg loudnorm фильтр
        """
        # Временный файл
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_in:
            tmp_in_path = tmp_in.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_out:
            tmp_out_path = tmp_out.name
        
        try:
            # Сохраняем вход
            audio.export(tmp_in_path, format='wav')
            
            # Запускаем ffmpeg с loudnorm
            # Сначала анализируем
            cmd_analysis = [
                self.ffmpeg, '-i', tmp_in_path,
                '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd_analysis, capture_output=True, text=True)
            
            # Парсим параметры из stderr (ffmpeg выводит туда)
            stderr = result.stderr
            json_match = re.search(r'\{[^}]*\}', stderr, re.DOTALL)
            
            if json_match:
                stats = json.loads(json_match.group())
                
                # Применяем коррекцию
                filter_str = (
                    f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:"
                    f"measured_I={stats['input_i']}:"
                    f"measured_TP={stats['input_tp']}:"
                    f"measured_LRA={stats['input_lra']}:"
                    f"measured_thresh={stats['input_thresh']}:"
                    f"offset={stats['target_offset']}"
                )
                
                cmd_apply = [
                    self.ffmpeg, '-y', '-i', tmp_in_path,
                    '-af', filter_str,
                    '-ar', str(self.requirements.SAMPLE_RATE),
                    tmp_out_path
                ]
                
                subprocess.run(cmd_apply, check=True, capture_output=True)
                
                # Загружаем результат
                return AudioSegment.from_wav(tmp_out_path)
            else:
                # Fallback: простая нормализация pydub
                logger.warning("LUFS analysis failed, using simple normalization")
                return normalize(audio)
                
        except Exception as e:
            logger.error(f"LUFS normalization error: {e}, using fallback")
            return normalize(audio)
        finally:
            # Cleanup
            Path(tmp_in_path).unlink(missing_ok=True)
            Path(tmp_out_path).unlink(missing_ok=True)
    
    def convert_format(
        self,
        input_path: Path,
        output_path: Path,
        target_format: str = "mp3",
        preserve_metadata: bool = True
    ) -> bool:
        """Простая конвертация формата"""
        try:
            audio = AudioSegment.from_file(str(input_path))
            
            # Настройки формата
            kwargs = {'format': target_format}
            if target_format == 'mp3':
                kwargs['bitrate'] = '320k'
                kwargs['id3v2_version'] = '3'
            
            audio.export(str(output_path), **kwargs)
            logger.info(f"Converted: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return False
    
    def add_metadata(
        self,
        file_path: Path,
        metadata: Dict[str, str],
        cover_image: Optional[Path] = None
    ) -> bool:
        """
        Добавить/обновить ID3 теги
        
        Args:
            metadata: {title, artist, album, year, genre, ...}
            cover_image: Путь к изображению обложки
        """
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, TIT2, TPE1, TALB, TYER, TCON, APIC
            
            audio = MP3(str(file_path))
            
            # Создаём ID3 если нет
            if audio.tags is None:
                audio.add_tags()
            
            tags = audio.tags
            
            # Записываем теги
            if 'title' in metadata:
                tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
            if 'artist' in metadata:
                tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
            if 'album' in metadata:
                tags['TALB'] = TALB(encoding=3, text=metadata['album'])
            if 'year' in metadata:
                tags['TYER'] = TYER(encoding=3, text=str(metadata['year']))
            if 'genre' in metadata:
                tags['TCON'] = TCON(encoding=3, text=metadata['genre'])
            
            # Обложка
            if cover_image and cover_image.exists():
                with open(cover_image, 'rb') as img:
                    tags['APIC'] = APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=img.read()
                    )
            
            audio.save()
            logger.info(f"Updated metadata: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Metadata error: {e}")
            return False
    
    def get_info(self, file_path: Path) -> Dict:
        """Получить информацию об аудио файле"""
        try:
            audio = AudioSegment.from_file(str(file_path))
            
            info = {
                'path': str(file_path),
                'duration': len(audio) / 1000,  # секунды
                'channels': audio.channels,
                'sample_rate': audio.frame_rate,
                'sample_width': audio.sample_width,
                'bitrate': None,
                'format': file_path.suffix.lower().replace('.', '')
            }
            
            # Пробуем получить битрейт через ffprobe
            try:
                cmd = [
                    self.ffprobe, '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', str(file_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                data = json.loads(result.stdout)
                
                if 'format' in data and 'bit_rate' in data['format']:
                    info['bitrate'] = int(data['format']['bit_rate']) // 1000  # kbps
                    
            except Exception as e:
                logger.debug(f"ffprobe error: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"Cannot get info for {file_path}: {e}")
            return {'error': str(e)}
    
    def validate_for_distribution(self, file_path: Path) -> Dict:
        """Проверить соответствие требованиям дистрибьюторов"""
        errors = []
        warnings = []
        
        info = self.get_info(file_path)
        
        if 'error' in info:
            return {'valid': False, 'errors': [info['error']], 'info': info}
        
        # Проверка формата
        if info['format'] not in ['mp3', 'wav', 'flac']:
            warnings.append(f"Format {info['format']} may not be accepted by all distributors")
        
        # Проверка частоты дискретизации
        if info['sample_rate'] < self.requirements.MIN_SAMPLE_RATE:
            errors.append(f"Sample rate {info['sample_rate']}Hz is below minimum {self.requirements.MIN_SAMPLE_RATE}Hz")
        
        # Проверка битрейта для MP3
        if info['format'] == 'mp3' and info['bitrate']:
            if info['bitrate'] < 192:
                warnings.append(f"Low bitrate: {info['bitrate']}kbps, recommended 320kbps")
        
        # Проверка каналов
        if info['channels'] != self.requirements.CHANNELS:
            warnings.append(f"{info['channels']} channels, expected {self.requirements.CHANNELS} (stereo)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'info': info
        }

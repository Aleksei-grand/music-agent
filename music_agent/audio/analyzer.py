"""
Анализатор аудио файлов
- BPM (темп)
- Обнаружение тишины
- Проверка на клиппинг
- Анализ частот
"""
import logging
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """Анализатор аудио файлов"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
    
    def analyze_full(self, file_path: Path) -> Dict:
        """Полный анализ аудио файла"""
        logger.info(f"Analyzing: {file_path}")
        
        analysis = {
            'file': str(file_path),
            'bpm': None,
            'duration': None,
            'silences': [],
            'clipping': False,
            'loudness': None,
            'quality_issues': []
        }
        
        try:
            # Получаем базовую информацию
            info = self._get_audio_info(file_path)
            analysis['duration'] = info.get('duration')
            analysis['sample_rate'] = info.get('sample_rate')
            
            # Анализируем BPM
            bpm = self.detect_bpm(file_path)
            if bpm:
                analysis['bpm'] = round(bpm, 1)
            
            # Ищем тишину
            silences = self.detect_silence(file_path)
            analysis['silences'] = silences
            
            # Проверяем клиппинг
            analysis['clipping'] = self.detect_clipping(file_path)
            
            # Анализ громкости
            loudness = self.analyze_loudness(file_path)
            analysis['loudness'] = loudness
            
            # Проверка качества
            issues = self._check_quality(file_path, info)
            analysis['quality_issues'] = issues
            
            logger.info(f"Analysis complete: BPM={analysis['bpm']}, "
                       f"Silences={len(silences)}, Clipping={analysis['clipping']}")
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def detect_bpm(self, file_path: Path) -> Optional[float]:
        """
        Определить BPM (beats per minute)
        Использует aubio или librosa
        """
        try:
            # Пробуем через aubio
            import aubio
            
            # Конвертируем во временный WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            
            cmd = [
                self.ffmpeg, '-y', '-i', str(file_path),
                '-ar', '44100', '-ac', '1',  # Mono, 44.1kHz
                tmp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Анализируем BPM
            samplerate = 44100
            win_s = 512
            hop_s = 256
            
            s = aubio.source(tmp_path, samplerate, hop_s)
            o = aubio.tempo("default", win_s, hop_s, samplerate)
            
            beats = []
            total_frames = 0
            
            while True:
                samples, read = s()
                is_beat = o(samples)
                if is_beat:
                    this_beat = o.get_last_s()
                    beats.append(this_beat)
                total_frames += read
                if read < hop_s:
                    break
            
            # Удаляем временный файл
            Path(tmp_path).unlink(missing_ok=True)
            
            if len(beats) > 1:
                # Считаем средний BPM
                bpms = []
                for i in range(1, len(beats)):
                    bpms.append(60.0 / (beats[i] - beats[i-1]))
                return np.median(bpms)
            
        except ImportError:
            logger.warning("aubio not installed, trying librosa")
        except Exception as e:
            logger.debug(f"aubio BPM detection failed: {e}")
        
        # Fallback: используем librosa
        try:
            import librosa
            
            y, sr = librosa.load(str(file_path), sr=None)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            
            if isinstance(tempo, np.ndarray):
                tempo = tempo[0]
            
            return float(tempo)
            
        except ImportError:
            logger.warning("librosa not installed")
        except Exception as e:
            logger.error(f"BPM detection failed: {e}")
        
        return None
    
    def detect_silence(
        self,
        file_path: Path,
        silence_threshold: int = -50,  # dB
        min_silence_duration: float = 2.0  # seconds
    ) -> List[Dict]:
        """
        Обнаружить участки тишины
        
        Returns:
            Список словарей с {'start', 'end', 'duration'}
        """
        silences = []
        
        try:
            # Используем ffmpeg silencedetect
            cmd = [
                self.ffmpeg, '-i', str(file_path),
                '-af', f'silencedetect=noise={silence_threshold}dB:d={min_silence_duration}',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            stderr = result.stderr
            
            # Парсим вывод
            silence_starts = []
            silence_ends = []
            
            for line in stderr.split('\n'):
                if 'silence_start:' in line:
                    match = self._extract_float(line, 'silence_start:')
                    if match:
                        silence_starts.append(match)
                elif 'silence_end:' in line:
                    match = self._extract_float(line, 'silence_end:')
                    if match:
                        silence_ends.append(match)
            
            # Формируем результат
            for i, start in enumerate(silence_starts):
                if i < len(silence_ends):
                    end = silence_ends[i]
                    silences.append({
                        'start': round(start, 2),
                        'end': round(end, 2),
                        'duration': round(end - start, 2)
                    })
            
            logger.debug(f"Found {len(silences)} silence segments")
            
        except Exception as e:
            logger.error(f"Silence detection error: {e}")
        
        return silences
    
    def detect_clipping(self, file_path: Path, threshold: float = 0.99) -> bool:
        """
        Проверить наличие клиппинга (перегрузки)
        
        Args:
            threshold: Уровень считается клиппингом (0.99 = -0.1 dB)
        """
        try:
            cmd = [
                self.ffmpeg, '-i', str(file_path),
                '-af', 'volumedetect',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            stderr = result.stderr
            
            # Ищем максимальный уровень
            max_volume = None
            for line in stderr.split('\n'):
                if 'max_volume:' in line:
                    match = self._extract_float(line, 'max_volume:')
                    if match is not None:
                        max_volume = match
            
            if max_volume is not None:
                # Конвертируем dB в линейную шкалу
                # max_volume должен быть около 0 dB для клиппинга
                if max_volume >= -0.5:  # Очень близко к 0 dB
                    logger.warning(f"Possible clipping detected: {max_volume} dB")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Clipping detection error: {e}")
            return False
    
    def analyze_loudness(self, file_path: Path) -> Optional[Dict]:
        """
        Анализ громкости (LUFS)
        
        Returns:
            {'integrated': ..., 'true_peak': ..., 'lra': ...}
        """
        try:
            cmd = [
                self.ffmpeg, '-i', str(file_path),
                '-af', 'loudnorm=print_format=json',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            stderr = result.stderr
            
            # Ищем JSON в выводе
            import re
            json_match = re.search(r'\{[^}]*\}', stderr, re.DOTALL)
            
            if json_match:
                stats = json.loads(json_match.group())
                return {
                    'integrated': float(stats.get('input_i', 0)),
                    'true_peak': float(stats.get('input_tp', 0)),
                    'lra': float(stats.get('input_lra', 0)),
                    'threshold': float(stats.get('input_thresh', 0))
                }
            
        except Exception as e:
            logger.error(f"Loudness analysis error: {e}")
        
        return None
    
    def generate_waveform(
        self,
        file_path: Path,
        output_path: Path,
        width: int = 1200,
        height: int = 400,
        color: str = '#1DB954'  # Spotify green
    ) -> bool:
        """Генерация waveform изображения"""
        try:
            import matplotlib.pyplot as plt
            import librosa.display
            import librosa
            
            # Загружаем аудио
            y, sr = librosa.load(str(file_path), sr=None)
            
            # Создаём фигуру
            fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
            
            # Рисуем waveform
            librosa.display.waveshow(y, sr=sr, color=color, ax=ax)
            
            # Убираем оси
            ax.axis('off')
            plt.tight_layout(pad=0)
            
            # Сохраняем
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, bbox_inches='tight', pad_inches=0, 
                       facecolor='none', edgecolor='none')
            plt.close()
            
            logger.info(f"Generated waveform: {output_path}")
            return True
            
        except ImportError:
            logger.error("matplotlib or librosa not installed")
            return False
        except Exception as e:
            logger.error(f"Waveform generation error: {e}")
            return False
    
    def _get_audio_info(self, file_path: Path) -> Dict:
        """Получить базовую информацию через ffprobe"""
        try:
            cmd = [
                self.ffprobe, '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            info = {}
            
            if 'format' in data:
                fmt = data['format']
                info['duration'] = float(fmt.get('duration', 0))
                info['bitrate'] = int(fmt.get('bit_rate', 0)) // 1000
                info['format'] = fmt.get('format_name', '')
            
            if 'streams' in data and len(data['streams']) > 0:
                stream = data['streams'][0]
                info['sample_rate'] = int(stream.get('sample_rate', 0))
                info['channels'] = int(stream.get('channels', 0))
                info['codec'] = stream.get('codec_name', '')
            
            return info
            
        except Exception as e:
            logger.error(f"ffprobe error: {e}")
            return {}
    
    def _check_quality(self, file_path: Path, info: Dict) -> List[str]:
        """Проверка проблем с качеством"""
        issues = []
        
        # Проверка длительности
        if info.get('duration', 0) < 30:
            issues.append("Track is very short (< 30 seconds)")
        if info.get('duration', 0) > 600:  # 10 минут
            issues.append("Track is very long (> 10 minutes)")
        
        # Проверка частоты дискретизации
        if info.get('sample_rate', 0) < 44100:
            issues.append(f"Low sample rate: {info['sample_rate']}Hz")
        
        # Проверка моно/стерео
        if info.get('channels', 0) == 1:
            issues.append("Mono audio (stereo recommended)")
        
        return issues
    
    @staticmethod
    def _extract_float(text: str, prefix: str) -> Optional[float]:
        """Извлечь число из строки после префикса"""
        try:
            idx = text.find(prefix)
            if idx >= 0:
                num_str = text[idx + len(prefix):].strip()
                # Берём только первое число
                num_str = num_str.split()[0].rstrip(':')
                return float(num_str)
        except:
            pass
        return None


class QualityChecker:
    """Проверка качества трека перед публикацией"""
    
    @staticmethod
    def check_all(file_path: Path, analyzer: AudioAnalyzer) -> Dict:
        """Полная проверка качества"""
        issues = []
        warnings = []
        
        # Анализ
        analysis = analyzer.analyze_full(file_path)
        
        # Проверка BPM (если вдруг скачет)
        if analysis.get('bpm'):
            if analysis['bpm'] < 60 or analysis['bpm'] > 200:
                warnings.append(f"Unusual BPM: {analysis['bpm']}")
        
        # Проверка тишины в конце
        silences = analysis.get('silences', [])
        if silences:
            last_silence = silences[-1]
            if last_silence['end'] >= analysis.get('duration', 0) - 1:
                # Тишина в конце - это нормально, но если длинная...
                if last_silence['duration'] > 5:
                    warnings.append(f"Long silence at end: {last_silence['duration']:.1f}s")
        
        # Проверка клиппинга
        if analysis.get('clipping'):
            issues.append("Audio clipping detected - distortion present")
        
        # Проверка громкости
        loudness = analysis.get('loudness')
        if loudness:
            if loudness['integrated'] > -10:
                warnings.append(f"Very loud: {loudness['integrated']:.1f} LUFS (recommended -14)")
            elif loudness['integrated'] < -20:
                warnings.append(f"Very quiet: {loudness['integrated']:.1f} LUFS (recommended -14)")
        
        # Другие проблемы
        issues.extend(analysis.get('quality_issues', []))
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'analysis': analysis
        }

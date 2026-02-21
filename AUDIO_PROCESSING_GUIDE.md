# 🎵 Аудио Обработка - Руководство

## Быстрый старт

```bash
# Проверить статус
python agent.py process-status

# Обработать все необработанные треки
python agent.py process --all

# Обработать конкретный альбом
python agent.py process --album-id 01HQ...

# С проверкой качества
python agent.py process --all --check-only
```

## Что делает обработка

```
┌─────────────────────────────────────────────────────────────┐
│                    АУДИО ОБРАБОТКА                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🎵 Входной файл (от Suno)                                  │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────┐                                        │
│  │ 1. Trim Silence │ Обрезка тишины в конце                 │
│  │    (если > 1s)  │                                        │
│  └────────┬────────┘                                        │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ 2. Fade-out     │ Плавное затухание (по умолч. 3 сек)    │
│  │    (3-6 сек)    │                                        │
│  └────────┬────────┘                                        │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ 3. Normalize    │ Нормализация до -14 LUFS               │
│  │    (-14 LUFS)   │ (стандарт Spotify/Apple Music)         │
│  └────────┬────────┘                                        │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ 4. Convert      │ Конвертация в MP3 320kbps              │
│  │    (MP3/WAV/FLAC│ или другой формат                       │
│  └────────┬────────┘                                        │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ 5. Add Tags     │ Запись ID3 тегов и обложки             │
│  │    (Metadata)   │                                        │
│  └────────┬────────┘                                        │
│           ▼                                                 │
│  💿 Готовый файл в storage/albums/{album_id}/               │
│       01-Song Title (english version).mp3                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Требования к аудио

### Форматы для дистрибьюторов

| Формат | Битрейт | Частота | Каналы | Использование |
|--------|---------|---------|--------|---------------|
| MP3    | 320 kbps| 44.1 kHz| Stereo | Универсальный |
| WAV    | 16-bit  | 44.1 kHz| Stereo | Высокое качество|
| FLAC   | Lossless| 44.1 kHz| Stereo | Для аудиофилов|
| M4A    | 256 kbps| 44.1 kHz| Stereo | Apple экосистема|

### Громкость (LUFS)

**Целевые значения:**
- **-14 LUFS** - Стандарт для Spotify, Apple Music, YouTube
- **-12 LUFS** - Для более громкого звучания
- **-16 LUFS** - Для акустической музыки

**True Peak:** -1.0 dB (защита от клиппинга)

## Команды

### Обработка

```bash
# Все необработанные треки
python agent.py process --all

# Конкретная песня
python agent.py process --song-id 01HQ...

# Весь альбом
python agent.py process --album-id 01HQ...

# Только проверить (не обрабатывать)
python agent.py process --all --check-only

# Другой формат
python agent.py process --all --format wav

# Без нормализации
python agent.py process --all --no-normalize

# Другой fade-out
python agent.py process --all --fade-out 5
```

### Проверка качества

```bash
# Информация о файле
python agent.py audio-info ./my-song.mp3

# Вывод:
# 📐 Формат: mp3
# ⏱️  Длительность: 185.40 сек
# 🎚️  Sample rate: 44100 Hz
# 🔊 Каналов: 2
# 📦 Битрейт: 320 kbps
# 🥁 BPM: 128.5
# 🔉 Громкость: -12.3 LUFS
```

### Статус

```bash
python agent.py process-status

# 📊 Статус обработки аудио:
#    Всего генераций: 25
#    Обработано: 20
#    Ожидает: 5
```

## Примеры workflow

### Полный цикл

```bash
# 1. Скачать с Suno
python agent.py sync

# 2. Перевести тексты
python agent.py translate --all

# 3. Сгенерировать обложки
python agent.py cover --all

# 4. Обработать аудио
python agent.py process --all --format mp3

# 5. Проверить результат
python agent.py audio-info storage/albums/xxx/01-Song.mp3
```

### Подготовка к публикации

```bash
# Проверить все файлы перед публикацией
for file in storage/albums/*/0*.mp3; do
    echo "Checking: $file"
    python agent.py audio-info "$file" | grep -E "(LUFS|BPM|готово)"
done
```

## Структура после обработки

```
storage/albums/{album_id}/
├── 01-Song Title (original version).mp3
├── 02-Song Title (english version).mp3
├── cover.jpg                    # Обложка альбома
└── metadata.json                # Информация о релизе
```

## Технические детали

### Fade-out

```python
# Стандартный fade-out: 3 секунды
# Для длинных треков: 5-6 секунд
# Для коротких: 1-2 секунды

agent process --fade-out 3   # По умолчанию
agent process --fade-out 5   # Более плавный
```

### Нормализация LUFS

```python
# Используется ffmpeg loudnorm фильтр
# Target: -14 LUFS
# True Peak: -1.0 dB
# Loudness Range: 11 LU

# Результат: все треки одинаковой громкости
# как на Spotify/Apple Music
```

### ID3 Теги

Записываемые поля:
- **Title** - Название песни
- **Artist** - Исполнитель
- **Album** - Название альбома
- **Genre** - Жанр
- **Track** - Номер трека
- **APIC** - Обложка (embedded)

## Возможные проблемы

### "File not found"
```bash
# Проверьте что sync выполнен
python agent.py sync

# Проверьте пути
ls storage/raw/{track_id}/audio.mp3
```

### "Low bitrate"
```bash
# Используйте WAV или FLAC
python agent.py process --format wav

# Или MP3 320kbps (по умолчанию)
python agent.py process --format mp3
```

### "Audio clipping"
```bash
# Уменьшите громкость источника
# Или используйте более мягкую нормализацию
python agent.py process --no-normalize
```

### "Mono audio"
```bash
# Стерео обязательно для дистрибьюторов
# Проверьте настройки в Suno
```

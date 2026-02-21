# 📁 Руководство: Импорт локальных файлов (без Suno)

## Быстрый ответ: ДА, можно!

Вы можете самостоятельно скопировать файлы в папку `raw/` и затем импортировать их в систему.

---

## Способ 1: Через CLI (рекомендуется)

### Импорт файлов с автоматическим созданием альбома:
```bash
# Импорт одного файла
agent import-files /path/to/song.mp3

# Импорт нескольких файлов
agent import-files ~/Music/*.mp3

# Импорт с созданием альбома
agent import-files ~/Music/*.mp3 \
  --create-album \
  --album-title "My New Album" \
  --artist "My Name"

# Импорт в существующий альбом
agent import-files ~/Music/song.mp3 --album-id xxxxxx

# С указанием текста песни
agent import-files song.mp3 --lyrics "file://lyrics.txt"
```

### Что происходит:
1. Файл копируется в `storage/raw/{generated_id}/audio.mp3`
2. Создаётся запись в БД (Generation + Song)
3. Автоматически создаётся `intl_title` (транслитерация)

---

## Способ 2: Ручное копирование + Сканирование

Если вы уже скопировали файлы вручную:

### Шаг 1: Создайте структуру папок
```bash
storage/
└── raw/
    ├── my_song_1/
    │   └── audio.mp3
    ├── my_song_2/
    │   └── audio.mp3
    └── another_track/
        └── audio.mp3
```

### Шаг 2: Создайте альбом (через Web UI или CLI)
```bash
# Или создайте через Web UI: http://localhost:8000/albums/bulk
```

### Шаг 3: Отсканируйте папку raw/
```bash
# Альбом должен существовать
agent scan-raw --album-id {album_id}
```

### Что происходит:
- Система находит все папки в `raw/`
- Для каждой папки создаёт Generation + Song
- Добавляет песни в указанный альбом

---

## Способ 3: Через Web UI (drag-and-drop)

1. Откройте `http://localhost:8000/upload`
2. Перетащите файлы в зону загрузки
3. Файлы автоматически попадут в `raw/`
4. Затем используйте `agent scan-raw` или создайте альбом вручную

---

## После импорта

```bash
# 1. Проверьте что файлы импортировались
agent process-status

# 2. Сгенерируйте обложку
agent cover --album-id {album_id}

# 3. Обработайте аудио
agent process --album-id {album_id}

# 4. Опубликуйте
agent publish --album-id {album_id}
```

---

## Пример полного workflow

```bash
# 1. У вас есть файлы в ~/Downloads/my_songs/
# 2. Импортируем их
agent import-files ~/Downloads/my_songs/*.mp3 \
  --create-album \
  --album-title "Summer Hits" \
  --artist "DJ Me"

# Получаем album_id из вывода команды (например: abc123)

# 3. Генерируем обложку
agent cover --album-id abc123

# 4. Обрабатываем (с превью в Telegram/Web)
agent process --album-id abc123

# 5. Публикуем
agent publish --album-id abc123 --distributor routenote
```

---

## Структура после импорта

```
storage/
├── raw/
│   ├── gen_xxx/          # ← Сгенерированный ID
│   │   └── audio.mp3     # ← Ваш файл здесь
│   └── gen_yyy/
│       └── audio.mp3
├── albums/
│   └── album_zzz/        # ← После process
│       ├── 01-Song (original version).mp3
│       └── 02-Another (english version).mp3
└── covers/
    └── cover_www/
        └── cover_3000.jpg
```

---

## ⚠️ Важно

1. **Имена файлов**: Система использует название папки или ID для имени трека. Лучше использовать `agent import-files` с `--title`.

2. **Транслитерация**: Автоматически создаётся `intl_title` (латиница). Проверьте через Web UI (`/albums/{id}/edit`).

3. **Metadata**: Локальные файлы не содержат текста песни. Добавьте через `--lyrics` или Web UI.

4. **Формат**: Поддерживаются MP3, WAV, FLAC. Рекомендуется MP3 320kbps.

---

## 💡 Совет

Используйте **`agent import-files`** — это самый удобный способ:
- ✅ Автоматическое создание альбома
- ✅ Правильные названия
- ✅ Транслитерация
- ✅ Метаданные (artist, genre)

---

**Готово к импорту!** 🎵

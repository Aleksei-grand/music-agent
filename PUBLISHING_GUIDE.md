# 📤 Публикация - Руководство

## Быстрый старт

```bash
# Проверить статус публикаций
python agent.py publish-status

# Опубликовать все готовые альбомы на RouteNote
python agent.py publish --distributor routenote --all

# Опубликовать конкретный альбом
python agent.py publish --distributor sferoom --album-id 01HQ...

# Сохранить как черновик (без отправки на модерацию)
python agent.py publish --distributor routenote --all

# Автоматически отправить на модерацию
python agent.py publish --distributor routenote --all --auto-submit
```

## Поддерживаемые дистрибьюторы

### RouteNote (Бесплатный)
- 🌐 Сайт: https://routenote.com
- 💰 Цена: Бесплатно (15% комиссии) или $25/год (0% комиссии)
- 📍 Покрытие: Глобальное (Spotify, Apple Music, etc.)
- 🔧 Метод: Браузерная автоматизация (Playwright)

### Sferoom (Российский)
- 🌐 Сайт: https://sferoom.space
- 💰 Цена: Бесплатно
- 📍 Покрытие: VK Music, Yandex Music, Звук и др.
- 🔧 Метод: Браузерная автоматизация (Playwright)

## Получение Cookie

### RouteNote

1. Откройте https://routenote.com в Chrome
2. Войдите в аккаунт
3. F12 → Application → Cookies
4. Найдите `routenote_session` или `session`
5. Скопируйте значение в `.env`:
```env
MUSIC_AGENT_ROUTENOTE_COOKIE=abc123...
```

### Sferoom

1. Откройте https://sferoom.space
2. Войдите в аккаунт
3. F12 → Application → Cookies
4. Найдите `token`
5. Скопируйте значение:
```env
MUSIC_AGENT_SFEROOM_COOKIE=eyJhbG...
```

## Workflow публикации

```
┌─────────────────────────────────────────────────────────────┐
│                    ПУБЛИКАЦИЯ АЛЬБОМА                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Проверка готовности                                     │
│     └─ Есть ли обложка? (3000x3000)                        │
│     └─ Есть ли треки? (обработанные)                       │
│     └─ Заполнены метаданные?                               │
│                                                             │
│  2. Валидация                                               │
│     └─ Проверка форматов (MP3/WAV)                         │
│     └─ Проверка битрейта (мин. 192kbps)                    │
│     └─ Проверка обложки (квадрат, 3000px)                  │
│                                                             │
│  3. Запуск браузера                                         │
│     └─ Playwright Chromium                                  │
│     └─ Установка cookies                                    │
│     └─ Открытие страницы загрузки                          │
│                                                             │
│  4. Заполнение форм                                         │
│     └─ Название альбома                                     │
│     └─ Имя артиста                                          │
│     └─ Жанр                                                 │
│     └─ UPC (если есть)                                      │
│                                                             │
│  5. Загрузка файлов                                         │
│     └─ Обложка                                              │
│     └─ Аудио файлы (по одному)                             │
│     └─ ISRC для каждого трека (если есть)                  │
│                                                             │
│  6. Завершение                                              │
│     └─ Сохранить черновик ← По умолчанию                   │
│     └─ Отправить на модерацию ← С --auto-submit            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Команды

### Основные

```bash
# Опубликовать все готовые альбомы
python agent.py publish --distributor routenote --all
python agent.py publish --distributor sferoom --all

# Конкретный альбом
python agent.py publish --distributor routenote --album-id 01HQ...

# С указанием cookie напрямую
python agent.py publish --distributor routenote --cookie "session=..." --all

# Видимый браузер (для отладки)
python agent.py publish --distributor routenote --all --no-headless

# Только проверка (dry-run)
python agent.py publish --distributor routenote --all --dry-run
```

### Статус

```bash
# Все публикации
python agent.py publish-status

# По конкретному дистрибьютору
python agent.py publish-status --distributor routenote
```

### Проверка статуса релиза

```bash
# Проверить модерацию
python agent.py check-status \
    --distributor routenote \
    --album-id RN-12345
```

## Требования дистрибьюторов

### RouteNote

| Параметр | Требование |
|----------|------------|
| Формат | MP3 320kbps, WAV 16-bit, FLAC |
| Частота | 44.1 kHz |
| Каналы | Stereo (2) |
| Обложка | 3000x3000 px, JPEG/PNG, квадрат |
| Макс. размер файла | 500 MB |
| Мин. длительность | 60 секунд |

### Sferoom

| Параметр | Требование |
|----------|------------|
| Формат | MP3, WAV, FLAC |
| Частота | 44.1 kHz |
| Обложка | 3000x3000 px |
| Текст песен | Обязателен для всех треков |

## Примеры workflow

### Полный цикл

```bash
# 1. Скачать с Suno
python agent.py sync

# 2. Перевести
python agent.py translate --all

# 3. Обложки
python agent.py cover --all

# 4. Обработка аудио
python agent.py process --all

# 5. Публикация на RouteNote (черновик)
python agent.py publish --distributor routenote --all

# 6. Публикация на Sferoom
python agent.py publish --distributor sferoom --all
```

### Публикация на оба дистрибьютора

```bash
#!/bin/bash
ALBUM_ID="01HQ..."

# RouteNote
python agent.py publish \
    --distributor routenote \
    --album-id $ALBUM_ID \
    --auto-submit

# Sferoom
python agent.py publish \
    --distributor sferoom \
    --album-id $ALBUM_ID \
    --auto-submit
```

## Решение проблем

### "Cookie expired"
```bash
# Обновите cookie в .env
# Перелогиньтесь на сайте и скопируйте новый cookie
```

### "Cover too small"
```bash
# Перегенерируйте обложку с нужным размером
python agent.py cover --album-id xxx --size 3000
```

### "Audio validation failed"
```bash
# Переобработайте аудио
python agent.py process --album-id xxx
```

### Браузер не запускается
```bash
# Установите playwright browsers
playwright install chromium
```

### Таймаут загрузки
```bash
# Медленный интернет - увеличьте таймаут в коде
# Или используйте более быстрое соединение
```

## Безопасность

⚠️ **Важно:**
- Cookie дают полный доступ к аккаунту
- Храните `.env` в безопасности
- Не коммитьте `.env` в git
- Используйте отдельный аккаунт для автоматизации
- Регулярно обновляйте cookie

## Ограничения

1. **CAPTCHA** - Если появится, автоматизация сломается
2. **Изменения UI** - Если сайт обновится, селекторы могут сломаться
3. **Скорость** - Браузер работает медленнее API
4. **Стабильность** - Зависит от стабильности сайта дистрибьютора

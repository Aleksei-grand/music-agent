# 🌊 MyFlowMusic (MFM)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Beta%20Ready-brightgreen)](https://github.com/Aleksei-grand/MyFlowMusic/releases)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](Dockerfile)

**Персональный AI-ассистент для музыкантов** — автоматизирует создание, обработку и публикацию музыки от Suno AI до стриминговых платформ.

> 🎵 **Создавай в Suno → MyFlowMusic делает всё остальное → Трек на Spotify/Apple Music**

---

## 🎯 О проекте

MyFlowMusic (MFM) — это open-source инструмент, который берёт на себя всю рутину после создания музыки:

**Полный pipeline:**
1. 📥 **Скачивание** — Автоматическая синхронизация треков с Suno
2. 🌐 **Транслитерация** — Русские названия → латиница для международных релизов
3. 📝 **Перевод** — AI-перевод текстов (опционально)
4. 🎨 **Обложка** — Генерация 3000x3000 через AI
5. 🎵 **Мастеринг** — Нормализация -14 LUFS, fade-out, ID3 теги
6. 📤 **Публикация** — Автозагрузка на RouteNote/Sferoom

**Статус:** Beta Ready v0.2.0

---

## ✨ Ключевые фичи

### 🌐 Транслитерация названий (NEW!)
```
"Моя Песня" → "Moya Pesnya" → "01-Moya Pesnya (original version).mp3"
"Любовь"    → "Lyubov"      → "02-Lyubov (english version).mp3"
```
- Автоматическая транслитерация русских названий
- Ручное редактирование через Web UI
- Генерация имён файлов международного образца

### 📋 Превью перед операциями (NEW!)
```
/process → 📋 Показывает какие файлы будут созданы
         → [✅ Обработать] [✏️ Изменить] [❌ Отмена]
```
- Предпросмотр перед обработкой аудио
- Предпросмотр перед публикацией
- В Telegram Bot и Web UI

### ⛔ True Cancellation (NEW!)
```
Запущена обработка → /cancel → Мгновенная остановка
```
- Отмена задач в Telegram Bot
- Управление процессами через ProcessManager

### 📁 Массовые операции (NEW!)
```
/albums/bulk → Выбор нескольких альбомов → Массовая обработка
```
- Bulk actions: translate, cover, process, publish
- Фильтрация альбомов по статусу

---

## 🚀 Быстрый старт

### Docker (Рекомендуется)

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/Aleksei-grand/MyFlowMusic.git
cd MyFlowMusic

# 2. Настройте окружение
cp .env.example .env
# Отредактируйте .env - добавьте API ключи

# 3. Запустите
docker-compose up -d

# 4. Откройте Web UI
open http://localhost:8000
```

### Локальная установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/Aleksei-grand/MyFlowMusic.git
cd MyFlowMusic

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте окружение
cp .env.example .env
# Отредактируйте .env

# 5. Запустите
python agent.py sync
```

---

## 📖 Использование

### CLI (Основной интерфейс)

```bash
# Синхронизация с Suno
agent sync

# Перевод текстов
agent translate --album-id xxx

# Генерация обложки
agent cover --album-id xxx

# Обработка аудио (с превью)
agent process --album-id xxx

# Публикация
agent publish --album-id xxx --distributor routenote
```

### Telegram Bot

```
/start    - Главное меню
/sync     - Синхронизация с Suno
/translate - Перевод текстов
/cover    - Генерация обложки
/process  - Обработка аудио (с превью!)
/publish  - Публикация (с превью!)
/cancel   - Отмена текущей операции
```

**@grandemotions1_bot** — попробуйте бота

### Web UI

```
http://localhost:8000

Доступные страницы:
- /           - Dashboard со статистикой
- /albums     - Список альбомов
- /albums/bulk - Массовые операции
- /upload     - Drag-and-drop загрузка
- /tasks      - Мониторинг задач
```

---

## 🏗️ Архитектура

```
music_agent/
├── commands/           # CLI команды
│   ├── sync.py        # Синхронизация с Suno
│   ├── translate.py   # Перевод текстов
│   ├── cover.py       # Генерация обложек
│   ├── process.py     # Обработка аудио
│   ├── publish.py     # Публикация
│   └── import_local.py # Импорт локальных файлов
├── utils/
│   ├── transliterator.py    # Рус→Lat транслитерация
│   ├── preview_helper.py    # Превью операций
│   ├── process_manager.py   # Управление процессами
│   └── file_manager.py      # Работа с файлами
├── web/               # Web UI (FastAPI)
├── bot/               # Telegram Bot
└── models.py          # SQLAlchemy модели
```

**Технологии:**
- Python 3.10+
- FastAPI (Web UI)
- python-telegram-bot
- SQLAlchemy (SQLite/PostgreSQL)
- FFmpeg (аудио обработка)
- Playwright (автоматизация дистрибьюторов)

---

## ⚙️ Конфигурация

Создайте `.env` файл:

```env
# Обязательные
SUNO_COOKIE=your_suno_cookie_here
POE_API_KEY=your_poe_api_key_here

# Дистрибьюторы (опционально)
ROUTENOTE_COOKIE=your_routenote_cookie
SFEROOM_COOKIE=your_sferoom_cookie

# Telegram Bot (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_IDS=your_telegram_id

# База данных (опционально, по умолчанию SQLite)
DB_TYPE=sqlite
DB_CONN=./storage/music_agent.db
```

---

## 📊 Статус готовности

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **CLI** | ✅ 95% | Полностью работает |
| **Web UI** | ✅ 100% | Drag-and-drop, превью, bulk, inline edit |
| **Telegram Bot** | ✅ 100% | True cancellation, прогресс, превью |
| **Транслитерация** | ✅ 100% | Авто + ручное редактирование |
| **Дистрибьюторы** | ⚠️ 70% | Работает, но CSS-зависимы |

---

## 🛣️ Roadmap

### v0.2.0 (Текущая) ✅
- [x] Транслитерация названий
- [x] Превью перед операциями
- [x] True cancellation
- [x] Bulk операции
- [x] Inline редактирование

### v0.3.0 (Планируется)
- [ ] Голосовая обратная связь
- [ ] Smart recovery для дистрибьюторов
- [ ] Analytics dashboard
- [ ] Batch upload папок

---

## 🤝 Contributing

Мы приветствуем вклад в проект! См. [CONTRIBUTING.md](CONTRIBUTING.md)

```bash
# Форкните репозиторий
git clone https://github.com/YOUR_USERNAME/MyFlowMusic.git

# Создайте ветку
git checkout -b feature/amazing-feature

# Коммит
git commit -m 'Add amazing feature'

# Пуш
git push origin feature/amazing-feature

# Откройте Pull Request
```

---

## 📝 Документация

- [AUDIO_PROCESSING_GUIDE.md](AUDIO_PROCESSING_GUIDE.md) — Гайд по обработке аудио
- [COVER_GENERATION_GUIDE.md](COVER_GENERATION_GUIDE.md) — Генерация обложек
- [PUBLISHING_GUIDE.md](PUBLISHING_GUIDE.md) — Публикация
- [IMPORT_LOCAL_GUIDE.md](IMPORT_LOCAL_GUIDE.md) — Импорт локальных файлов
- [TELEGRAM_BOT_GUIDE.md](TELEGRAM_BOT_GUIDE.md) — Telegram Bot
- [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) — Web UI
- [CHANGELOG.md](CHANGELOG.md) — История изменений

---

## 📄 Лицензия

Распространяется под лицензией MIT. См. [LICENSE](LICENSE)

---

## 👤 Автор

**GrandEmotions / VOLNAI**
- Telegram: [@grandemotions1](https://t.me/grandemotions1)
- GitHub: [@Aleksei-grand](https://github.com/Aleksei-grand)

---

## 🙏 Благодарности

- [Suno AI](https://suno.ai) — за возможность создавать музыку
- [Poe](https://poe.com) — за API для AI-моделей
- Сообщество open-source — за инструменты и библиотеки

---

<p align="center">
  <b>🌊 MyFlowMusic — от Suno до стримингов без рутины</b>
</p>

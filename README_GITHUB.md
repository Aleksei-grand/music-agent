# 🌊 MyFlowMusic (MFM)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](Dockerfile)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)](tests/)

> **Персональный ассистент для музыкантов** — автоматизирует создание, обработку и публикацию музыки.

![MyFlowMusic Dashboard](docs/images/dashboard.png)

## ✨ Возможности

- 📥 **Suno Integration** — Скачивание и синхронизация треков
- 🌐 **AI Перевод** — Автоматический перевод текстов через Claude
- 🎨 **AI Обложки** — Генерация обложек альбомов
- 🎵 **Аудио Обработка** — Нормализация, fade-out, теги
- 📤 **Авто-публикация** — RouteNote, Sferoom (и больше)
- 🎤 **Голосовое Управление** — Управляйте голосом
- 🤖 **Telegram Bot** — Управление из телефона
- 🌐 **Web UI** — Красивый дашборд
- 📚 **История** — Vault система с отчётами

## 🚀 Быстрый старт

### Docker (Рекомендуется)

```bash
# Clone репозиторий
git clone https://github.com/username/music-agent.git
cd music-agent

# Настройте окружение
cp .env.example .env
# Отредактируйте .env

# Запустите
docker-compose up -d

# Откройте http://localhost:8080
```

### Local Installation

```bash
# Установите Python 3.10+
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Настройте окружение
cp .env.example .env
# Отредактируйте .env

# Запустите
python agent.py web
```

## 📖 Документация

- [🚀 Getting Started Guide](docs/GETTING_STARTED.md)
- [🎵 Audio Processing](AUDIO_PROCESSING_GUIDE.md)
- [🎨 Cover Generation](COVER_GENERATION_GUIDE.md)
- [📤 Publishing](PUBLISHING_GUIDE.md)
- [🤖 Telegram Bot](TELEGRAM_BOT_GUIDE.md)
- [🌐 Web UI](WEB_UI_GUIDE.md)
- [🔒 Security](FINAL_SECURITY_REPORT.md)

## 🖥️ Интерфейсы

### 1. CLI (Command Line)
```bash
# Синхронизация с Suno
python agent.py sync

# Перевод песен
python agent.py translate --all

# Генерация обложек
python agent.py cover --all

# Обработка аудио
python agent.py process --all

# Публикация
python agent.py publish --all
```

### 2. Telegram Bot
```
@YourMusicAgentBot

Команды:
/sync      - Синхронизировать
/translate - Перевести тексты
/cover     - Сгенерировать обложки
/process   - Обработать аудио
/publish   - Опубликовать
/status    - Статус
```

### 3. Voice Control
```bash
python agent.py voice listen
# Скажите: "Скачай новые треки"
```

### 4. Web UI
```bash
python agent.py web --port 8080
# Откройте http://localhost:8080
```

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     INTERFACES                              │
├──────────────┬──────────────┬──────────────┬────────────────┤
│     CLI      │   Telegram   │    Voice     │    Web UI      │
└──────────────┴──────────────┴──────────────┴────────────────┘
       │              │               │              │
       └──────────────┴───────────────┴──────────────┘
                          │
              ┌───────────▼────────────┐
              │    Core Modules        │
              │  • SunoSyncWorkflow    │
              │  • AudioProcessor      │
              │  • PoeClient           │
              │  • VaultManager        │
              └───────────┬────────────┘
                          │
              ┌───────────▼────────────┐
              │  Integrations          │
              │  • Suno API            │
              │  • Poe API             │
              │  • Deepgram            │
              │  • RouteNote           │
              │  • Sferoom             │
              └────────────────────────┘
```

## 🔧 Настройка

### Обязательные переменные (.env)

```bash
# API Keys
POE_API_KEY=your_poe_key          # poe.com/api_key
DEEPGRAM_API_KEY=your_key         # console.deepgram.com
TELEGRAM_BOT_TOKEN=your_token     # @BotFather

# Suno
SUNO_COOKIE=__session=xxx         # Из браузера

# Database (опционально)
DB_TYPE=sqlite                    # или postgres
DB_CONN=music_agent.db
```

### Опциональные

```bash
# Audio
AUDIO_TARGET_LUFS=-14
AUDIO_FADE_OUT=3

# Web UI
WEB_HOST=127.0.0.1
WEB_PORT=8080

# Storage
STORAGE_BASE_PATH=./storage
```

## 🧪 Тестирование

```bash
# Установите dev зависимости
pip install -r requirements-dev.txt

# Запустите тесты
pytest --cov=music_agent

# Проверка стиля
flake8 music_agent/
black music_agent/

# Проверка типов
mypy music_agent/
```

## 📦 Деплой

### Docker Compose (Рекомендуется)

```yaml
version: '3.8'
services:
  music-agent:
    image: ghcr.io/username/music-agent:latest
    ports:
      - "8080:8080"
    volumes:
      - ./storage:/app/storage
      - ./.env:/app/.env:ro
    restart: unless-stopped
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

## 🤝 Contributing

Смотрите [CONTRIBUTING.md](CONTRIBUTING.md)

```bash
# Fork репозитория
git clone https://github.com/YOUR_USERNAME/music-agent.git

# Создайте branch
git checkout -b feature/amazing-feature

# Сделайте commit
git commit -m 'Add amazing feature'

# Push
git push origin feature/amazing-feature

# Создайте Pull Request
```

## 📊 Статистика

- 🎵 **70+** файлов
- 📝 **12,000+** строк кода
- 🔌 **5** интеграций
- 🖥️ **4** интерфейса
- 🧪 **6** тестовых модулей

## 🗺️ Roadmap

### v0.3.0 (Q2 2024)
- [ ] Новые дистрибьюторы (DistroKid, TuneCore)
- [ ] Поддержка S3 для файлов
- [ ] Redis task queue
- [ ] Webhooks

### v0.4.0 (Q3 2024)
- [ ] YouTube upload
- [ ] Spotify analytics
- [ ] Multi-user support
- [ ] API keys management

### v1.0.0 (Q4 2024)
- [ ] Kubernetes ready
- [ ] Enterprise features
- [ ] White-label solution

## 🔒 Безопасность

- ✅ Security audited
- ✅ Secrets masked in logs
- ✅ Rate limiting (60 req/min)
- ✅ Path validation
- ✅ SQL Injection protected
- ✅ XSS protected

Смотрите [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md)

## 📜 License

MIT License - смотрите [LICENSE](LICENSE)

## 🙏 Благодарности

- [Poe API](https://poe.com) - AI переводы и обложки
- [Suno](https://suno.com) - Генерация музыки
- [Deepgram](https://deepgram.com) - Распознавание речи
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)

---

<p align="center">
  <b>⭐ Star us on GitHub — it motivates us a lot!</b>
</p>

<p align="center">
  <a href="https://github.com/username/music-agent">GitHub</a> •
  <a href="https://t.me/music_agent">Telegram</a> •
  <a href="https://twitter.com/music_agent">Twitter</a>
</p>

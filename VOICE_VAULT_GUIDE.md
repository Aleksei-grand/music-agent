# 🎤 Voice Commands & 📚 Vault - Руководство

## 🎤 Голосовое управление (Deepgram)

### Настройка

```bash
# Добавьте в .env
MUSIC_AGENT_VOICE_API_KEY=your_deepgram_key
MUSIC_AGENT_VOICE_MODEL=nova-2
```

Получить ключ: https://console.deepgram.com

### Использование

```bash
# Слушать команду с микрофона
python agent.py voice listen
# 🔴 Запись... (5 секунд)
# 📝 Распознано: "Скачай новые треки"

# С другой длительностью
python agent.py voice listen --duration 10

# На английском
python agent.py voice listen --language en

# Распознать файл
python agent.py voice file ./command.wav
```

### Доступные голосовые команды

| Команда | Примеры фраз |
|---------|--------------|
| **sync** | "Скачай новые треки", "Синхронизируйся", "Обнови библиотеку" |
| **translate** | "Переведи тексты на английский", "Сделай перевод" |
| **cover** | "Сгенерируй обложки", "Создай артворк" |
| **process** | "Обработай аудио", "Сделай мастеринг" |
| **publish** | "Опубликуй на RouteNote", "Выпусти на Sferoom" |
| **status** | "Покажи статус", "Что готово?" |
| **help** | "Помощь", "Какие команды?" |

### Как работает

```
🎤 Голос → 🧠 Deepgram (STT) → 🎯 Intent Recognition → ⚡ Execution

1. Записываем аудио с микрофона
2. Отправляем в Deepgram API
3. Получаем текст с confidence score
4. Определяем intent (команду)
5. Извлекаем параметры
6. Выполняем!
```

## 📚 Vault - Система истории

### Структура

```
vault/
├── conversations/          # Диалоги
│   └── 2026/02/21/
│       └── 143022_conversation_abc123.json
│
├── workflows/              # Выполненные workflow
│   └── 2026/02/21/
│       └── 143500_workflow_def456.json
│
├── daily/                  # Ежедневные отчёты
│   └── 2026/02/
│       ├── 21_summary.json
│       └── 21_summary.md
│
└── summaries/              # Сводки
```

### Команды Vault

```bash
# Сгенерировать отчёт за сегодня
python agent.py vault summary

# За конкретную дату
python agent.py vault summary --date 2026-02-20

# Статистика использования
python agent.py vault stats --days 30

# Поиск по истории
python agent.py vault search "перевод"
python agent.py vault search "error" --type error

# Последние записи
python agent.py vault last --n 10

# Персонализированные рекомендации
python agent.py vault preferences
```

### Формат записей

**JSON (структурированные данные):**
```json
{
  "id": "abc123",
  "timestamp": "2026-02-21T14:30:22",
  "date": "2026-02-21",
  "type": "conversation",
  "source": "voice",
  "tags": ["dialog", "voice"],
  "content": {
    "user": "Скачай новые треки",
    "assistant": "Запущена синхронизация...",
    "metadata": {}
  }
}
```

**Markdown (читаемый отчёт):**
```markdown
# 📊 Отчёт за 2026-02-21

## 📈 Статистика
- Всего записей: 15
- Диалогов: 5
- Workflow'ов: 8

## 🔄 Workflow'ы
### sync
- Всего: 3
- Успешно: 3 ✅
```

## 🎯 Персонализация

Vault анализирует вашу историю:

```python
# Автоматически извлекаются предпочтения
{
  "favorite_commands": [
    {"name": "sync", "count": 25},
    {"name": "translate", "count": 18}
  ],
  "favorite_workflows": [
    {"name": "suno_sync", "count": 20}
  ],
  "preferred_sources": ["cli", "voice", "telegram"],
  "activity_level": 45,
  "error_rate": 0.05
}
```

### Рекомендации

На основе истории:
- **Частые команды** → предлагаются псевдонимы
- **Ошибки** → рекомендуется --dry-run
- **Активность** → советы по оптимизации

## 🔗 Интеграция

Все команды автоматически логируются:

```python
# При выполнении любой команды:
vault.log_command(
    command="sync",
    args={"dry_run": False},
    result={"success": True, "downloaded": 5},
    source="cli"  # или "voice", "telegram", "web"
)
```

## 💡 Сценарии использования

### Ежедневный мониторинг
```bash
# Вечером проверяем что сделано
python agent.py vault summary
# Смотрим отчёт: vault/daily/2026/02/21_summary.md
```

### Поиск по истории
```bash
# Найти когда переводили конкретный трек
python agent.py vault search "Spring Melody"

# Найти все ошибки
python agent.py vault search "failed" --type error
```

### Анализ продуктивности
```bash
# Статистика за месяц
python agent.py vault stats --days 30

# Сколько треков обработано
python agent.py vault search "process" | wc -l
```

## 🔐 Приватность

- Все данные хранятся **локально** в `vault/`
- Ничего не отправляется в облако
- Можно удалить: `rm -rf vault/`
- Или экспортировать для анализа

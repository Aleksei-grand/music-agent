# Contributing to MyFlowMusic (MFM)

Спасибо за интерес к проекту! Вот как вы можете помочь:

## 🚀 Быстрый старт

1. Fork репозитория
2. Clone вашего fork
3. Создайте virtual environment
4. Установите зависимости

```bash
git clone https://github.com/YOUR_USERNAME/music-agent.git
cd music-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 📋 Требования к коду

### Code Style
- Python 3.10+
- PEP 8
- Type hints (где возможно)
- Docstrings для функций

### Запуск проверок
```bash
# Линтер
flake8 music_agent/

# Форматирование
black music_agent/

# Типизация
mypy music_agent/

# Тесты
pytest
```

## 🌿 Workflow

1. Создайте branch: `git checkout -b feature/my-feature`
2. Сделайте изменения
3. Добавьте тесты
4. Запустите проверки
5. Commit: `git commit -m "Add feature"`
6. Push: `git push origin feature/my-feature`
7. Создайте Pull Request

## 📝 Commit Messages

```
feat: добавить новую фичу
fix: исправить баг
docs: обновить документацию
style: форматирование (без кода)
refactor: рефакторинг
test: добавить тесты
chore: обновить зависимости
```

## 🐛 Bug Reports

Создайте Issue с:
- Описанием проблемы
- Шагами воспроизведения
- Ожидаемое поведение
- Логи ошибок
- Версия ПО

## 💡 Feature Requests

Создайте Issue с тегом `enhancement`:
- Описание фичи
- Почему это нужно
- Возможная реализация

## 📚 Документация

- Обновляйте README при изменении API
- Добавляйте docstrings
- Обновляйте CHANGELOG.md

## ⚠️ Security

Не создавайте PR с:
- API ключами
- Паролями
- Cookie сессий

Security issues: security@music-agent.local

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

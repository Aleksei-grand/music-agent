# 🚀 Команды для публикации на GitHub

## Пошаговая инструкция

### 1. Проверьте статус репозитория

```bash
# Перейдите в папку проекта
cd "C:\Users\asnov\OneDrive\Рабочий стол\Для работы\Леша\py4e\РАЗНОЕ\Музыкальный агент"

# Проверьте статус
git status
```

Должно показать много изменённых файлов.

---

### 2. Добавьте все файлы

```bash
# Добавьте все изменения
git add .

# Проверьте что всё добавлено
git status
```

---

### 3. Создайте коммит

```bash
# Коммит с описанием всех изменений
git commit -m "v0.2.0-beta: Full UI support, transliteration, preview, cancellation

Major features added:
- Transliteration: Russian titles → Latin (auto + manual edit)
- Preview before operations: Shows output filenames before processing
- True cancellation: Stop tasks via /cancel in Telegram Bot
- Bulk operations: Process multiple albums at once
- Inline editing: Edit metadata in Web UI
- Import local files: agent import-files command

Interfaces:
- CLI: 95% functional
- Web UI: 100% (drag-drop, preview, bulk, inline edit)
- Telegram Bot: 100% (cancellation, progress, preview)

New modules:
- utils/transliterator.py
- utils/preview_helper.py
- utils/process_manager.py
- commands/import_local.py

Updated:
- README.md with new features
- All templates with preview modals
- API endpoints for preview
"
```

---

### 4. Создайте тег версии

```bash
# Создайте аннотированный тег
git tag -a v0.2.0-beta -m "Beta release v0.2.0

Full feature release with:
- Complete Web UI (100%)
- Complete Telegram Bot (100%)
- Russian-to-Latin transliteration
- Preview before all operations
- True task cancellation
- Bulk album operations
- Local file import

Docker: ghcr.io/aleksei-grand/myflowmusic:v0.2.0-beta
"
```

---

### 5. Отправьте на GitHub

```bash
# Отправьте main ветку
git push origin main

# Отправьте тег
git push origin v0.2.0-beta
```

---

### 6. Создайте Release на GitHub (вручную)

1. Откройте: https://github.com/Aleksei-grand/MyFlowMusic/releases
2. Нажмите **"Draft a new release"**
3. В поле "Choose a tag" выберите `v0.2.0-beta`
4. Заголовок: `v0.2.0-beta - Full UI Support`
5. Описание (скопируйте ниже):

```markdown
## 🎉 Beta Release v0.2.0

### ✨ Новые возможности

#### 🌐 Транслитерация названий
- Автоматическая конвертация русских названий в латиницу
- Ручное редактирование через Web UI
- Генерация имён файлов международного образца

**Примеры:**
- "Моя Песня" → "Moya Pesnya" → `01-Moya Pesnya (original version).mp3`
- "Любовь" → "Lyubov" → `02-Lyubov (english version).mp3`

#### 📋 Превью перед операциями
- Показывает какие файлы будут созданы перед обработкой
- Подтверждение в Telegram Bot и Web UI
- Возможность отмены или редактирования

#### ⛔ True Cancellation
- Команда `/cancel` в Telegram Bot
- Мгновенная остановка процессов
- Управление через ProcessManager

#### 📁 Массовые операции
- Страница `/albums/bulk` для выбора нескольких альбомов
- Bulk actions: translate, cover, process, publish
- Модальное окно прогресса

#### 📥 Импорт локальных файлов
```bash
agent import-files ~/Music/*.mp3 --create-album --album-title "My Album"
```

### 📊 Статус готовности

| Компонент | Статус |
|-----------|--------|
| CLI | ✅ 95% |
| Web UI | ✅ 100% |
| Telegram Bot | ✅ 100% |
| Транслитерация | ✅ 100% |
| Дистрибьюторы | ⚠️ 70% (CSS-зависимы) |

### 🐳 Docker

```bash
docker pull ghcr.io/aleksei-grand/myflowmusic:v0.2.0-beta
```

### 📖 Документация

- [Импорт локальных файлов](IMPORT_LOCAL_GUIDE.md)
- [Telegram Bot](TELEGRAM_BOT_GUIDE.md)
- [Web UI](WEB_UI_GUIDE.md)

### 🙏 Автор

**GrandEmotions / VOLNAI**
- Telegram: [@grandemotions1](https://t.me/grandemotions1)
- Bot: [@grandemotions1_bot](https://t.me/grandemotions1_bot)
```

6. Прикрепите бинарники (если нужно) или оставьте как есть
7. Нажмите **"Publish release"**

---

## ✅ Проверка после публикации

### Проверьте на GitHub:

1. **Репозиторий**: https://github.com/Aleksei-grand/MyFlowMusic
   - Должен показывать свежий коммит
   - README должен отображаться

2. **Releases**: https://github.com/Aleksei-grand/MyFlowMusic/releases
   - Должен быть тег `v0.2.0-beta`
   - Должен быть Release с описанием

3. **Packages**: https://github.com/Aleksei-grand?tab=packages
   - Должен быть Docker образ `myflowmusic:v0.2.0-beta`
   (собирается автоматически через CI/CD)

4. **Actions**: https://github.com/Aleksei-grand/MyFlowMusic/actions
   - Должны быть зелёные галочки у workflows

---

## 🔧 Если нужно исправить

```bash
# Если забыли что-то добавить в последний коммит
git add .
git commit --amend -m "v0.2.0-beta: Full UI support..."
git push origin main --force

# Если нужно удалить тег и создать заново
git tag -d v0.2.0-beta
git push origin --delete v0.2.0-beta
git tag -a v0.2.0-beta -m "..."
git push origin v0.2.0-beta
```

---

## 🎉 Готово!

После выполнения всех шагов проект будет опубликован на GitHub с:
- ✅ Новым релизом v0.2.0-beta
- ✅ Обновлённым README
- ✅ Docker образом
- ✅ CI/CD пайплайнами

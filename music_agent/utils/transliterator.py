"""
Транслитерация русского текста в латиницу
"""
import re

# Словарь транслитерации (ISO 9 / ГОСТ 7.79)
TRANSLIT_DICT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Заглавные
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
}

# Альтернативные варианты для более читаемых названий
READABLE_DICT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Заглавные
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
}


def transliterate(text: str, readable: bool = True) -> str:
    """
    Транслитерация русского текста в латиницу
    
    Args:
        text: Исходный текст
        readable: Использовать более читаемый вариант (True) или ISO 9 (False)
    
    Returns:
        Транслитерированный текст
    """
    if not text:
        return ""
    
    # Если текст уже латиницей - возвращаем как есть
    if not contains_cyrillic(text):
        return text
    
    dictionary = READABLE_DICT if readable else TRANSLIT_DICT
    
    result = []
    for char in text:
        if char in dictionary:
            result.append(dictionary[char])
        else:
            result.append(char)
    
    return ''.join(result)


def contains_cyrillic(text: str) -> bool:
    """Проверить, содержит ли текст кириллицу"""
    return bool(re.search('[\u0400-\u04FF]', text))


def contains_latin(text: str) -> bool:
    """Проверить, содержит ли текст латиницу"""
    return bool(re.search('[a-zA-Z]', text))


def auto_transliterate(title: str, max_length: int = 50) -> str:
    """
    Автоматическая транслитерация названия для международного релиза
    
    Rules:
    1. Если уже латиница - оставить как есть
    2. Если кириллица - транслитерировать
    3. Ограничить длину
    4. Убрать лишние пробелы
    
    Args:
        title: Название песни
        max_length: Максимальная длина результата
    
    Returns:
        Готовое международное название
    """
    if not title:
        return "Untitled"
    
    # Если уже латиница (и нет кириллицы) - оставляем
    if contains_latin(title) and not contains_cyrillic(title):
        result = title
    else:
        # Транслитерируем
        result = transliterate(title)
    
    # Очищаем
    result = result.strip()
    result = re.sub(r'\s+', ' ', result)  # Множественные пробелы → один
    
    # Ограничиваем длину
    if len(result) > max_length:
        result = result[:max_length].rsplit(' ', 1)[0]  # Обрезаем по слову
    
    return result or "Untitled"


def generate_filename(title: str, version_type: str = "original", max_length: int = 40) -> str:
    """
    Сгенерировать имя файла для трека
    
    Args:
        title: Название (intl_title)
        version_type: Тип версии (original, english)
        max_length: Максимальная длина
    
    Returns:
        Безопасное имя файла без расширения
    """
    # Формируем полное название
    full_name = f"{title} ({version_type} version)"
    
    # Очищаем от недопустимых символов
    safe_name = re.sub(r'[<>:"/\\|?*]', '', full_name)
    safe_name = safe_name.strip()
    
    # Ограничиваем длину
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length].rsplit(' ', 1)[0]
    
    return safe_name


# Примеры использования
if __name__ == "__main__":
    examples = [
        "Моя Песня",
        "Любовь и Мир",
        "Summer Vibes",  # Уже латиница
        "Ёжик в тумане",
        "Привет, мир!",
    ]
    
    print("Примеры транслитерации:")
    print("-" * 50)
    for ex in examples:
        intl = auto_transliterate(ex)
        filename = generate_filename(intl, "original")
        print(f"'{ex}' → '{intl}' → '{filename}.mp3'")

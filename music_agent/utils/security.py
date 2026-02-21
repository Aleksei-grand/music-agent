"""
Security utilities
- Secret masking in logs
- Path validation
- Input sanitization
"""
import logging
import re
from pathlib import Path
from typing import Optional


class SecretMaskFilter(logging.Filter):
    """
    Фильтр для маскирования секретов в логах
    
    Маскирует:
    - API ключи
    - Токены
    - Cookie
    - Пароли
    """
    
    # Паттерны для поиска секретов
    PATTERNS = [
        (re.compile(r'(api[_-]?key[=:])["\']?[\w-]+["\']?', re.I), r'\1***'),
        (re.compile(r'(token[=:])["\']?[\w-]+["\']?', re.I), r'\1***'),
        (re.compile(r'(cookie[=:])["\']?[^\s&\"\']+["\']?', re.I), r'\1***'),
        (re.compile(r'(password[=:])["\']?[^\s&\"\']+["\']?', re.I), r'\1***'),
        (re.compile(r'(secret[=:])["\']?[^\s&\"\']+["\']?', re.I), r'\1***'),
        (re.compile(r'(session[=:])["\']?[^\s&\"\']+["\']?', re.I), r'\1***'),
        (re.compile(r'(__session=)[^;\s&]+', re.I), r'\1***'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Маскировать секреты в сообщении"""
        if isinstance(record.msg, str):
            record.msg = self._mask_secrets(record.msg)
        
        # Маскируем в args тоже
        if record.args:
            record.args = tuple(
                self._mask_secrets(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _mask_secrets(self, text: str) -> str:
        """Применить все паттерны маскирования"""
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_security_logging():
    """Настроить безопасное логирование"""
    # Добавляем фильтр к root logger
    root_logger = logging.getLogger()
    mask_filter = SecretMaskFilter()
    root_logger.addFilter(mask_filter)


def validate_path_within_base(path: Path, base_path: Path) -> bool:
    """
    Проверить, что path находится внутри base_path
    
    Args:
        path: Путь для проверки
        base_path: Базовый разрешённый путь
        
    Returns:
        True если path внутри base_path, False если нет
    """
    try:
        path = path.resolve()
        base_path = base_path.resolve()
        path.relative_to(base_path)
        return True
    except (ValueError, RuntimeError):
        return False


def sanitize_filename(filename: str) -> str:
    """
    Очистить имя файла от опасных символов
    
    Args:
        filename: Исходное имя файла
        
    Returns:
        Безопасное имя файла
    """
    if not filename:
        return "untitled"
    
    # Убираем path traversal
    filename = re.sub(r'[\\/]', '_', filename)
    
    # Убираем спецсимволы
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    
    # Убираем control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Убираем множественные пробелы/underscores
    filename = re.sub(r'\s+', ' ', filename).strip()
    filename = re.sub(r'_{2,}', '_', filename)
    
    # Ограничиваем длину
    if len(filename) > 200:
        filename = filename[:200]
    
    # Если пустое - возвращаем default
    if not filename or filename == '.':
        return "untitled"
    
    return filename


def validate_album_id(album_id: str) -> bool:
    """
    Валидировать ID альбома
    
    Ожидается ULID формат: 26 символов, base32
    """
    if not album_id:
        return False
    
    # ULID: 26 символов [0-9A-Z]
    if len(album_id) != 26:
        return False
    
    if not re.match(r'^[0-9A-Z]+$', album_id, re.I):
        return False
    
    return True


def validate_cover_id(cover_id: str) -> bool:
    """Валидировать ID обложки (также ULID)"""
    return validate_album_id(cover_id)


class SecurityError(Exception):
    """Базовое исключение для ошибок безопасности"""
    pass


class PathTraversalError(SecurityError):
    """Попытка path traversal"""
    pass


class ValidationError(SecurityError):
    """Ошибка валидации входных данных"""
    pass

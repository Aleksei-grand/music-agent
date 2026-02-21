"""
Retry декоратор для API запросов
"""
import logging
import time
from functools import wraps
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Декоратор для retry с экспоненциальной задержкой
    
    Args:
        max_retries: Максимальное количество попыток
        initial_delay: Начальная задержка в секундах
        max_delay: Максимальная задержка
        exponential_base: База для экспоненциального роста
        exceptions: Исключения для перехвата
        on_retry: Callback при retry (функция с аргументами attempt, exception)
    
    Пример:
        @retry_with_backoff(max_retries=3, exceptions=(RequestException,))
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    
                    if on_retry:
                        on_retry(attempt, e)
                    
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            return None  # Should never reach here
        
        return wrapper
    return decorator


async def async_retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """Async версия retry декоратора"""
    import asyncio
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    
                    if on_retry:
                        await on_retry(attempt, e)
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            return None
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit Breaker паттерн для защиты от каскадных ошибок
    
    Состояния:
    - CLOSED: Всё работает, запросы проходят
    - OPEN: Слишком много ошибок, запросы блокируются
    - HALF_OPEN: Пробуем восстановиться
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Вызвать функцию с защитой circuit breaker"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker: attempting reset")
            else:
                raise CircuitBreakerOpen("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Проверить, пора ли пробовать восстановиться"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """Обработка успешного вызова"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Обработка ошибки"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit breaker: OPEN after {self.failure_count} failures")


class CircuitBreakerOpen(Exception):
    """Исключение: Circuit breaker открыт"""
    pass

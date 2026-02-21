"""
Rate Limiter для API запросов
Защита от превышения лимитов
"""
import time
import logging
from threading import Lock
from typing import Optional, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token Bucket алгоритм для rate limiting
    
    Позволяет:
    - Быстрые всплески запросов (если есть токены)
    - Плавное ограничение в долгосрочной перспективе
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Скорость пополнения (токенов/секунду)
            capacity: Максимальное количество токенов
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Попытаться потратить токены
        
        Returns:
            True если токены есть, False если нет
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Пополняем токены
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Время ожидания до доступности токенов"""
        with self.lock:
            if self.tokens >= tokens:
                return 0.0
            
            needed = tokens - self.tokens
            return needed / self.rate


class RateLimiter:
    """
    Rate Limiter с разными стратегиями
    """
    
    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        """
        Args:
            requests_per_minute: Максимум запросов в минуту
            burst_size: Максимальный burst
        """
        rate = requests_per_minute / 60.0  # токенов в секунду
        self.bucket = TokenBucket(rate=rate, capacity=burst_size)
        self.min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0
        self.last_request_time = 0
        self.lock = Lock()
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        Получить разрешение на запрос
        
        Args:
            blocking: Ждать если лимит превышен
            
        Returns:
            True если разрешено, False если нет
        """
        while True:
            with self.lock:
                now = time.time()
                time_since_last = now - self.last_request_time
                
                # Проверяем минимальный интервал
                if time_since_last < self.min_interval:
                    if not blocking:
                        return False
                    wait_time = self.min_interval - time_since_last
                else:
                    wait_time = 0
                
                # Проверяем bucket
                if not self.bucket.consume(1):
                    if not blocking:
                        return False
                    wait_time = max(wait_time, self.bucket.wait_time(1))
                else:
                    self.last_request_time = now
                    return True
            
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                time.sleep(wait_time)


def rate_limited(limiter: RateLimiter):
    """
    Декоратор для rate limiting
    
    Пример:
        limiter = RateLimiter(requests_per_minute=30)
        
        @rate_limited(limiter)
        def api_call():
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.acquire()
            return func(*args, **kwargs)
        return wrapper
    return decorator


class AdaptiveRateLimiter:
    """
    Адаптивный rate limiter с backoff при ошибках
    
    При ошибках 429 (Too Many Requests) автоматически снижает rate
    """
    
    def __init__(
        self,
        initial_rate: int = 60,
        min_rate: int = 5,
        max_rate: int = 120,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1
    ):
        self.rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        
        self.limiter = RateLimiter(requests_per_minute=self.rate)
        self.consecutive_successes = 0
        self.consecutive_errors = 0
    
    def acquire(self, blocking: bool = True) -> bool:
        return self.limiter.acquire(blocking)
    
    def on_success(self):
        """Вызывать при успешном запросе"""
        self.consecutive_successes += 1
        self.consecutive_errors = 0
        
        # Увеличиваем rate после серии успехов
        if self.consecutive_successes >= 10:
            new_rate = min(self.max_rate, int(self.rate * self.recovery_factor))
            if new_rate != self.rate:
                logger.info(f"Adaptive rate limiter: increasing rate to {new_rate}/min")
                self.rate = new_rate
                self.limiter = RateLimiter(requests_per_minute=self.rate)
            self.consecutive_successes = 0
    
    def on_error(self, status_code: Optional[int] = None):
        """Вызывать при ошибке запроса"""
        self.consecutive_errors += 1
        self.consecutive_successes = 0
        
        # Снижаем rate при ошибках
        if status_code == 429 or self.consecutive_errors >= 3:
            new_rate = max(self.min_rate, int(self.rate * self.backoff_factor))
            if new_rate != self.rate:
                logger.warning(f"Adaptive rate limiter: decreasing rate to {new_rate}/min")
                self.rate = new_rate
                self.limiter = RateLimiter(requests_per_minute=self.rate)


# Глобальные limiters для разных API
POE_RATE_LIMITER = AdaptiveRateLimiter(
    initial_rate=30,   # 30 запросов в минуту
    min_rate=5,
    max_rate=60
)

SUNO_RATE_LIMITER = RateLimiter(
    requests_per_minute=20,  # Suno не любит частые запросы
    burst_size=5
)

DEEPGRAM_RATE_LIMITER = RateLimiter(
    requests_per_minute=120,  # Deepgram более щедрый
    burst_size=20
)

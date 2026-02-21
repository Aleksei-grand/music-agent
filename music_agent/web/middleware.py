"""
Security middleware для Web UI
- Rate limiting
- Security headers
- Request validation
"""
import time
import logging
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware
    
    Ограничивает количество запросов с одного IP
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.requests: dict = {}  # ip -> [(timestamp, count), ...]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Обработка запроса с rate limiting"""
        client_ip = request.client.host if request.client else "unknown"
        
        # Проверяем rate limit
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": 60}
            )
        
        # Продолжаем обработку
        response = await call_next(request)
        
        # Добавляем заголовки rate limiting
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        
        return response
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Проверить, не превышен ли лимит"""
        now = time.time()
        window = 60  # 1 минута
        
        # Очищаем старые записи
        if client_ip in self.requests:
            self.requests[client_ip] = [
                (ts, cnt) for ts, cnt in self.requests[client_ip]
                if now - ts < window
            ]
        else:
            self.requests[client_ip] = []
        
        # Считаем запросы
        total_requests = sum(cnt for ts, cnt in self.requests[client_ip])
        
        # Проверяем лимит
        if total_requests >= self.requests_per_minute:
            return False
        
        # Добавляем текущий запрос
        if self.requests[client_ip]:
            last_ts, last_cnt = self.requests[client_ip][-1]
            if now - last_ts < 1:  # В ту же секунду
                self.requests[client_ip][-1] = (last_ts, last_cnt + 1)
            else:
                self.requests[client_ip].append((now, 1))
        else:
            self.requests[client_ip].append((now, 1))
        
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Добавление security headers
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Добавить security headers к ответу"""
        response = await call_next(request)
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.tailwindcss.com cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' ws: wss:;"
        )
        
        # XSS Protection
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS (только в продакшене с HTTPS)
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Валидация входящих запросов
    """
    
    # Максимальный размер тела запроса (10 MB)
    MAX_BODY_SIZE = 10 * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Валидировать запрос"""
        # Проверяем размер тела для POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                if int(content_length) > self.MAX_BODY_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request entity too large"}
                    )
        
        # Проверяем path на потенциально опасные символы
        path = request.url.path
        if ".." in path or "//" in path:
            logger.warning(f"Suspicious path detected: {path}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid path"}
            )
        
        return await call_next(request)


def require_api_key(endpoint_func: Callable) -> Callable:
    """
    Декоратор для защиты API ключом
    
    Использование:
        @app.post("/api/admin/action")
        @require_api_key
        async def admin_action():
            pass
    """
    @wraps(endpoint_func)
    async def wrapper(*args, **kwargs):
        # Получаем request из args (первый аргумент для endpoint функций)
        request = args[0] if args else None
        
        if not request:
            raise HTTPException(status_code=500, detail="Request not found")
        
        # Проверяем API ключ из заголовка
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            raise HTTPException(status_code=401, detail="API key required")
        
        # В реальном приложении сравнивать с хранимым ключом
        # from ..config import settings
        # if api_key != settings.admin_api_key:
        #     raise HTTPException(status_code=403, detail="Invalid API key")
        
        return await endpoint_func(*args, **kwargs)
    
    return wrapper

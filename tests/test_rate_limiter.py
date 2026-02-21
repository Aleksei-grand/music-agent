"""
Rate limiter tests
"""
import pytest
import time

from music_agent.utils.rate_limiter import TokenBucket, RateLimiter


class TestTokenBucket:
    def test_consume_available(self):
        bucket = TokenBucket(rate=1.0, capacity=5)
        
        # Should be able to consume initially (full bucket)
        assert bucket.consume(1) is True
        assert bucket.consume(5) is True
    
    def test_consume_empty(self):
        bucket = TokenBucket(rate=0.1, capacity=1)
        
        # Consume the only token
        assert bucket.consume(1) is True
        
        # Should fail (empty bucket)
        assert bucket.consume(1) is False
    
    def test_refill(self):
        bucket = TokenBucket(rate=10.0, capacity=1)
        
        # Consume token
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False
        
        # Wait for refill
        time.sleep(0.11)  # Wait a bit more than 1/10 second
        
        assert bucket.consume(1) is True


class TestRateLimiter:
    def test_acquire_blocking(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)
        
        # First request should succeed immediately
        assert limiter.acquire(blocking=False) is True
        
        # Second should fail (no blocking)
        assert limiter.acquire(blocking=False) is False
    
    def test_acquire_rate(self):
        # Very high rate limit
        limiter = RateLimiter(requests_per_minute=10000, burst_size=100)
        
        # Should allow many requests
        for _ in range(50):
            assert limiter.acquire(blocking=False) is True

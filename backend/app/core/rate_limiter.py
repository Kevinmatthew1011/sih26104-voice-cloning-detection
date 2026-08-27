import time
import asyncio
from typing import Dict, Tuple, Optional, Callable
from fastapi import Request, HTTPException, status
from app.config import settings


class TokenBucket:
    """
    Process-local token bucket rate limiter with monotonic clock.
    Thread-safe and process-local. Intended for single-process demo / hackathon API protection.
    """
    def __init__(
        self,
        rate_per_minute: int,
        burst_capacity: int,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = float(burst_capacity)
        self.clock = clock or time.monotonic
        self.buckets: Dict[str, Tuple[float, float]] = {}  # ip -> (tokens, last_update)
        self.lock = asyncio.Lock()

    async def consume(self, client_ip: str, tokens_needed: float = 1.0) -> Tuple[bool, int]:
        """
        Attempts to consume tokens for client_ip.
        Returns (is_allowed, retry_after_seconds).
        """
        async with self.lock:
            now = self.clock()
            tokens, last_update = self.buckets.get(client_ip, (self.capacity, now))

            # Refill tokens based on elapsed time
            elapsed = max(0.0, now - last_update)
            tokens = min(self.capacity, tokens + elapsed * self.rate_per_second)

            if tokens >= tokens_needed:
                tokens -= tokens_needed
                self.buckets[client_ip] = (tokens, now)
                return True, 0
            else:
                # Calculate time required to accumulate tokens_needed
                needed = tokens_needed - tokens
                retry_after = max(1, int(needed / self.rate_per_second + 0.999))
                self.buckets[client_ip] = (tokens, now)
                return False, retry_after


# Global process-local limiter instances
detection_limiter = TokenBucket(
    rate_per_minute=settings.DETECTION_RATE_LIMIT_PER_MINUTE,
    burst_capacity=settings.DETECTION_RATE_LIMIT_BURST,
)

report_limiter = TokenBucket(
    rate_per_minute=settings.REPORT_RATE_LIMIT_PER_MINUTE,
    burst_capacity=settings.REPORT_RATE_LIMIT_PER_MINUTE // 2 or 15,
)

history_limiter = TokenBucket(
    rate_per_minute=settings.HISTORY_RATE_LIMIT_PER_MINUTE,
    burst_capacity=settings.HISTORY_RATE_LIMIT_PER_MINUTE // 2 or 30,
)


def get_client_ip(request: Request) -> str:
    """Extract client IP from direct socket connection. Avoid untrusted spoofed proxy headers."""
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


async def rate_limit_detection(request: Request) -> None:
    """Rate limit dependency for POST /api/v1/detections."""
    if not getattr(settings, "RATE_LIMIT_ENABLED", False):
        return

    client_ip = get_client_ip(request)
    allowed, retry_after = await detection_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for voice cloning analysis. Please retry later.",
            headers={"Retry-After": str(retry_after)},
        )


async def rate_limit_report(request: Request) -> None:
    """Rate limit dependency for GET /api/v1/detections/{case_id}/report."""
    if not getattr(settings, "RATE_LIMIT_ENABLED", False):
        return

    client_ip = get_client_ip(request)
    allowed, retry_after = await report_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for forensic evidence reports. Please retry later.",
            headers={"Retry-After": str(retry_after)},
        )

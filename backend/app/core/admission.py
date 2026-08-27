import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import HTTPException, status
from app.config import settings


class InferenceAdmissionBusyError(Exception):
    """Raised when inference capacity is fully saturated and acquisition timeout expires."""
    def __init__(self, retry_after: int = 5, message: str = "AASIST neural inference engine is currently busy. Please retry shortly."):
        super().__init__(message)
        self.retry_after = retry_after
        self.message = message


class InferenceAdmissionController:
    """
    Process-local admission controller for heavy ML inference jobs.
    Serializes or bounds concurrent GPU inference to prevent VRAM spikes, CUDA OOM, and starvation.
    """
    def __init__(self, max_concurrent: int = 1, timeout_seconds: float = 5.0):
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_jobs = 0
        self._lock = asyncio.Lock()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    @asynccontextmanager
    async def acquire_slot(self, timeout: Optional[float] = None):
        """
        Acquires an inference slot within timeout.
        Raises InferenceAdmissionBusyError if capacity is unavailable beyond timeout.
        """
        acquire_timeout = timeout if timeout is not None else self.timeout_seconds
        acquired = False

        try:
            # Attempt to acquire semaphore with timeout
            try:
                await asyncio.wait_for(self.semaphore.acquire(), timeout=acquire_timeout)
                acquired = True
            except asyncio.TimeoutError:
                raise InferenceAdmissionBusyError(
                    retry_after=max(1, int(self.timeout_seconds)),
                    message=f"Neural inference capacity saturated ({self.max_concurrent} active). Queue timeout ({acquire_timeout:.1f}s) exceeded.",
                )

            async with self._lock:
                self._active_jobs += 1

            yield

        finally:
            if acquired:
                async with self._lock:
                    self._active_jobs = max(0, self._active_jobs - 1)
                self.semaphore.release()


# Global process-local inference admission controller
aasist_admission_controller = InferenceAdmissionController(
    max_concurrent=settings.MAX_CONCURRENT_INFERENCE_JOBS,
    timeout_seconds=settings.ADMISSION_TIMEOUT_SECONDS,
)

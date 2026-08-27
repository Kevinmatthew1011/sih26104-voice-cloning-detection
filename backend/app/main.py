import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.v1.router import api_router
from app.core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger("app.security")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and directories are prepared
    await init_db()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown: cleanups if necessary


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    ## SIH 2026: AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks (SIH26104)
    
    Forensic backend API for detecting synthetic speech, neural voice clones, and acoustic replay attacks.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Security headers middleware (nosniff, DENY, referrer-policy)
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on path {request.url.path}: {exc}")
    if getattr(settings, "DEBUG", True):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {str(exc)}"},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred during audio processing. Incident reference logged."},
    )


# Mount API v1 routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "detections_api": f"{settings.API_V1_PREFIX}/detections"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

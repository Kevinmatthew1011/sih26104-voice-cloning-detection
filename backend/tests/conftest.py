import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.config import settings

# Test database in memory or local test db
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True
)

TestingAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_environment():
    orig_upload_dir = settings.UPLOAD_DIR
    orig_engine = settings.DETECTION_ENGINE
    settings.UPLOAD_DIR = settings.UPLOAD_DIR / "test_uploads"
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.DETECTION_ENGINE = "mock"
    yield
    # Cleanup test uploads
    import shutil
    if settings.UPLOAD_DIR.exists():
        shutil.rmtree(settings.UPLOAD_DIR, ignore_errors=True)
    settings.UPLOAD_DIR = orig_upload_dir
    settings.DETECTION_ENGINE = orig_engine


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingAsyncSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

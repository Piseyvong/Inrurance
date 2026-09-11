"""Shared test fixtures for the claims verification demo."""

from io import BytesIO

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile

from app.database import Base
import app.models  # noqa: F401


@pytest.fixture
async def async_db_session(tmp_path):
    """Return an isolated async SQLite database session."""

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


def upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    """Create a Starlette UploadFile for service-level tests."""

    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )

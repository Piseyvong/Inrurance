"""Shared test fixtures for the claims verification demo."""

from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from app.database import Base
import app.models  # noqa: F401


@pytest.fixture()
def db_session():
    """Return an isolated in-memory database session."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    """Create a Starlette UploadFile for service-level tests."""

    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )

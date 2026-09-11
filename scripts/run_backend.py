"""Run the local FastAPI development server from environment settings."""

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        # Without this, the default reload watcher covers the whole project
        # root, so any frontend/src edit restarts the backend (dropped
        # connections, a fresh DB pool) even though nothing backend-side changed.
        reload_dirs=["app"],
    )

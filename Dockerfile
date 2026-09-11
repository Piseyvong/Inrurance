# Backend API image: FastAPI + Tesseract (Khmer/English) OCR + Poppler PDF rendering.
FROM python:3.12-slim

# tesseract-ocr / tesseract-ocr-khm: OCR engine used by app/services/ocr.py.
# poppler-utils: provides pdftoppm, used by app/services/preprocessing.py to
# rasterize PDF pages to PNG before OCR (Tesseract cannot read PDFs directly).
# curl: used by the container healthcheck to call GET /health.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-khm \
        poppler-utils \
        curl \
    && TESSDATA_DIR="$(dpkg -L tesseract-ocr-eng | grep -m1 'tessdata$')" \
    && ln -s "$TESSDATA_DIR" /usr/share/tessdata \
    && rm -rf /var/lib/apt/lists/*

# app/config.py falls back to a Windows Tesseract path when these are unset,
# so the Linux install must be pointed to explicitly.
ENV TESSERACT_CMD=/usr/bin/tesseract \
    TESSERACT_TESSDATA_DIR=/usr/share/tessdata \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
# scripts/ includes seed_demo.py and check_tables.py — run with
# `docker compose ... exec backend python scripts/seed_demo.py`.
COPY scripts ./scripts
RUN cp scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# uploads/processed_uploads/logs are also mounted as volumes in compose so
# files outlive container recreation; the mkdir here just keeps a plain
# `docker run` (without those volumes) from failing on first write.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p uploads processed_uploads logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]

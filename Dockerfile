FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINGENEVAL_DATABASE_URL=sqlite:////data/fingeneval.db \
    FINGENEVAL_REPORT_DIR=/data/reports

RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system app && useradd --system --gid app --uid 10001 app
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --requirement requirements-api.txt
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY data/packs ./data/packs
COPY data/docs ./data/docs
RUN mkdir -p /data/reports && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec uvicorn src.enterprise.api:app --host 0.0.0.0 --port 8000"]

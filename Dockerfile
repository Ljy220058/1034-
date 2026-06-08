FROM python:3.12.4-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==24.2 \
    && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12.4-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8000 \
    RUNNING_CLUB_HOST=0.0.0.0 \
    RUNNING_CLUB_PORT=8000

WORKDIR /app

RUN useradd --create-home --uid 1000 --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv
COPY . /app

RUN chown -R appuser:appuser /app

EXPOSE 8000
USER appuser

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]

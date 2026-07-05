FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt \
    && find /venv -type d -name '__pycache__' -prune -exec rm -rf {} + \
    && rm -rf /venv/lib/python3.12/site-packages/pip* \
              /venv/lib/python3.12/site-packages/setuptools* \
              /venv/lib/python3.12/site-packages/wheel* \
              /venv/bin/pip*

FROM python:3.12-slim-bookworm

RUN useradd --uid 1001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --from=builder /venv /venv
COPY app ./app

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL="sqlite:////tmp/readiness.db" \
    LOG_LEVEL="INFO" \
    PORT=8000

USER 1001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

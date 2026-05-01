FROM python:3.13-slim AS builder

ENV UV_PROJECT_ENVIRONMENT=/workspace/.venv/api \
    UV_COMPILE_BYTECODE=1

WORKDIR /workspace

RUN python -m pip install --no-cache-dir --upgrade pip uv

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN uv sync --locked --project apps/api --no-dev

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/workspace/.venv/api/bin:$PATH

WORKDIR /workspace

COPY --from=builder /workspace/.venv/api /workspace/.venv/api
COPY apps/api apps/api

WORKDIR /workspace/apps/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

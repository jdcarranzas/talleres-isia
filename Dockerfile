# IncidentOps API — imagen reproducible con uv (ADR-004)
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Dependencias de ejecución (capa cacheable, sin dependencias de desarrollo)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Código de la aplicación
COPY src ./src
COPY data ./data

RUN useradd --create-home --uid 10001 incidentops && chown -R incidentops /app
USER incidentops

EXPOSE 8000

CMD ["uvicorn", "--factory", "src.adapters.inbound.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]

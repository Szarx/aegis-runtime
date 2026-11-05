FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements-dev.lock ./
COPY deploy/docker/wheelhouse /wheelhouse
RUN if python -c "from pathlib import Path; raise SystemExit(0 if list(Path('/wheelhouse').glob('*.whl')) else 1)"; then \
        python -m pip install --no-cache-dir --no-index --find-links /wheelhouse -r requirements-dev.lock; \
    else \
        python -m pip install --no-cache-dir -r requirements-dev.lock; \
    fi
COPY collector ./collector
RUN python -m pip install --no-build-isolation --no-deps ./collector \
    && useradd --system --uid 10001 aegis \
    && chown -R aegis:aegis /app
USER aegis
EXPOSE 8000
CMD ["python", "-m", "aegis_collector", "serve", "--migrate", "--host", "0.0.0.0"]

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /srv/studyvault/backend
COPY requirements-prod.txt ./requirements-prod.txt
RUN pip install --no-cache-dir -r requirements-prod.txt \
 && groupadd -g 10001 studyvault \
 && useradd --uid 10001 --gid studyvault --no-create-home studyvault \
 && mkdir -p /srv/data/uploads \
 && chown -R studyvault:studyvault /srv/data
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY tools ./tools
USER studyvault
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

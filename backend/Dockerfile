FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY app ./app
RUN pip install --no-deps . && useradd --create-home --uid 1000 app
COPY alembic.ini ./
COPY migrations ./migrations
COPY sandbox ./sandbox
COPY scripts ./scripts
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

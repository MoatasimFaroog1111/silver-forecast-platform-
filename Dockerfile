FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN python -m silver_forecast.platform_configuration.restore_runtime_artifacts

EXPOSE 8000

CMD ["sh", "-c", "uvicorn silver_forecast.http_api.application:app --host 0.0.0.0 --port ${PORT:-8000}"]

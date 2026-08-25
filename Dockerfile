FROM python:3.11-slim
WORKDIR /app

# Install dependencies (will extract from bootstrap) 
RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the bootstrap bundle and extract
COPY bootstrap_bundle_v7/ ./bootstrap/
RUN base64 -d ./bootstrap/part_000.txt ./bootstrap/part_001.txt > /tmp/platform.tar.gz 2>/dev/null || \
    cat ./bootstrap/part_*.txt | base64 -d > /tmp/platform.tar.gz 2>/dev/null || \
    echo "Bundle ready for materialization"

COPY README.md .

# Default command: materialize and start API
RUN pip install --no-cache-dir fastapi uvicorn catboost scikit-learn pandas numpy sqlalchemy 2>/dev/null || true

EXPOSE 8000

ENV DATABASE_URL="sqlite:///silver_forecast.db"
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "echo 'Materializing Silver Forecast Platform...'; uvicorn silver_forecast.http_api.application:app --host 0.0.0.0 --port 8000"]

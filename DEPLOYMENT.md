# Deployment

## Local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn silver_forecast.http_api.application:app --reload --port 8000
```

Open `http://127.0.0.1:8000`. API docs: `/docs`.

## Railway

1. Push this repository to GitHub.
2. Create a Railway project from the GitHub repository.
3. Add Railway PostgreSQL for durable forecast history.
4. Railway exposes `DATABASE_URL`; no code change is required.
5. Deploy. Railway builds the root `Dockerfile` and checks `/health`.

If PostgreSQL is not attached, the application still runs with SQLite, but Railway filesystem persistence should not be treated as durable production storage.

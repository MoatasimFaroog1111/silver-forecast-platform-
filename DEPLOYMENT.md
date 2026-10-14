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

## Coolify

Deploy the stack from `docker-compose.coolify.yml`.

### 1. Create the resource

1. In Coolify: **New Resource → Docker Compose** and paste `docker-compose.coolify.yml` (or point it at this repository).
2. Do **not** start it yet — set the required environment first.

### 2. Environment

| Variable | Required | Default | Notes |
|---|---|---|---|
| `POSTGRES_PASSWORD` | **Yes** | — | `openssl rand -base64 24`. There is no default on purpose. |
| `DATABASE_URL` | No | `postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/silver` | Override only if you use an external database. |
| `POSTGRES_USER` | No | `postgres` | |
| `POSTGRES_DB` | No | `silver` | |
| `CORS_ALLOWED_ORIGINS` | Recommended | — | Comma-separated origins of your portal domain. |

Set `POSTGRES_PASSWORD` in Coolify's environment editor **before the first start** and keep it stable: it is stored inside the `pgdata` volume, so changing it later requires a manual `ALTER USER` inside the container or a volume reset.

### 3. Domain and HTTPS

1. Open the **app** service → **Domains** and add your domain (the stack exposes no host ports; Coolify's Traefik proxy routes the domain to `app:8000`).
2. Issue a **Let's Encrypt** certificate and enable **Force HTTPS**.
3. Verify `https://<your-domain>/health` returns `{"status": "ok"}`.

The `postgres` service must stay unreachable from the internet: do not attach a domain to it.

### 4. First boot

On first boot the app seeds the PostgreSQL market history from the packaged CSV (restored from the verified runtime bundle) and is immediately usable. `DATABASE_URL` is provided by the compose default; nothing else is required.

### 5. Receiving the daily data push

The `Daily Market Data` GitHub Action can POST each day's new observations to the live API (`POST /api/market/observations`, idempotent upsert). Add these repository secrets (**Settings → Secrets and variables → Actions**) once Coolify is live:

| Secret | Required | Notes |
|---|---|---|
| `PRODUCTION_API_URL` | No | e.g. `https://silver.example.com`. Empty = skip the push step. |
| `MARKET_OBSERVATIONS_TOKEN` | No | Optional bearer token if you front the endpoint with auth. |

### 6. Backups

The `pgdata` volume is the only durable state. Schedule a PostgreSQL backup from the host (Phase 2 adds an automated daily dump):

```bash
docker exec <postgres-container> pg_dump -U postgres silver | gzip > silver-$(date +%F).sql.gz
```

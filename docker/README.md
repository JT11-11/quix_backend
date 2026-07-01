# Backend Docker

Run the FastAPI backend from Docker.

## Setup

From this folder:

```bash
cp ../.env.example ../.env
```

Update `../.env` with your `DATABASE_URL` and `AGENT_BACKEND_SECRET`.

## Run

```bash
docker-compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Stop

```bash
docker-compose down
```

If your Docker install uses Compose v2, `docker compose up --build` and `docker compose down` work too.

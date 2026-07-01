# Quix Proposal Agent Backend

Standalone FastAPI backend for the autonomous proposal agent.

## Setup

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Required environment values:

- `DATABASE_URL`: same Neon Postgres URL used by the frontend.
- `AGENT_BACKEND_SECRET`: shared server-to-server secret also configured in `Proposal_Template`.

The frontend calls this backend through authenticated Next.js proxy routes.

## Docker

```bash
cd Backend/docker
cp ../.env.example ../.env
docker-compose up --build
```

Edit `Backend/.env` before starting the container if you need to set real database or agent secret values.

The backend runs at `http://localhost:8000`.

If your Docker install uses Compose v2, `docker compose up --build` works too.

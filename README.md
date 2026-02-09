# Tick8 Backend

FastAPI backend initialized with PostgreSQL and SQLAlchemy.

## Setup

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file:

```bash
cp .env.example .env
```

4. Update `DATABASE_URL` in `.env` to match your PostgreSQL credentials/database.

5. Run the app:

```bash
uvicorn app.main:app --reload
```

## Database migrations (Alembic)

Create a migration:

```bash
alembic revision --autogenerate -m "create tasks table"
```

Apply migrations:

```bash
alembic upgrade head
```

## Health endpoint

- API health: `GET /api/v1/health`

import os

import psycopg
from fastapi import FastAPI

app = FastAPI(title="Central de Investimentos")

DATABASE_URL = os.environ["DATABASE_URL"]


@app.get("/api/health")
def health():
    """Confirm the API is up and can reach Postgres."""
    with psycopg.connect(DATABASE_URL) as conn:
        db_ok = conn.execute("SELECT 1").fetchone()[0] == 1
    return {"api": "ok", "db": "ok" if db_ok else "erro"}

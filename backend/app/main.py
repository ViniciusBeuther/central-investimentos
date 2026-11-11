import os

import psycopg
from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Central de Investimentos")
app.include_router(router)

DATABASE_URL = os.environ["DATABASE_URL"]


@app.get("/api/health")
def health():
    """Confirm the API is up and can reach Postgres."""
    with psycopg.connect(DATABASE_URL) as conn:
        db_ok = conn.execute("SELECT 1").fetchone()[0] == 1
    return {"api": "ok", "db": "ok" if db_ok else "erro"}

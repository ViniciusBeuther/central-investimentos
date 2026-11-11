"""Alembic environment.

The project has no ORM models, so migrations are written by hand (plain SQL through
`op.execute`) and autogenerate is not used. The database URL comes from DATABASE_URL.
"""
import os

from alembic import context
from sqlalchemy import create_engine, pool


def get_url() -> str:
    url = os.environ["DATABASE_URL"]
    # SQLAlchemy needs the driver name to use psycopg 3.
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=get_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

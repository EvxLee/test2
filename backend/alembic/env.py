from __future__ import annotations
import os, sys, pathlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from dotenv import load_dotenv

# Ensure product/api (and root) are on sys.path so `import database` finds product/api/database
ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCT_API = ROOT / "product" / "api"
for path in (str(PRODUCT_API), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# Load .env from project root
load_dotenv(ROOT / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# database.db creates the engine at import time; ensure DATABASE_URL is set (use project env var if needed)
_db_url = (
    os.getenv("DATABASE_URL")
    or os.getenv("ATLAS_DB_API_CONNECTION_STRING")
    or config.get_main_option("sqlalchemy.url")
)
if _db_url and not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = _db_url

# Import your metadata from the database package
from database.db import Base  # noqa: E402
import database.models        # noqa: F401  (ensure models are registered)
target_metadata = Base.metadata

DB_URL = os.getenv("DATABASE_URL") or os.getenv("ATLAS_DB_API_CONNECTION_STRING") or config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    if not DB_URL:
        raise RuntimeError("No DATABASE_URL set and no sqlalchemy.url in alembic.ini")
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    if not DB_URL:
        raise RuntimeError("No DATABASE_URL set and no sqlalchemy.url in alembic.ini")
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

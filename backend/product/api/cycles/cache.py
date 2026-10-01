import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.db import SessionLocal

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 24 * 60 * 60

_GET_SQL = text("""
    SELECT response, generated_at
    FROM cycles.summary_cache
    WHERE cycle_id = :cycle_id
""")

_UPSERT_SQL = text("""
    INSERT INTO cycles.summary_cache (cycle_id, response, generated_at)
    VALUES (:cycle_id, CAST(:response AS jsonb), now())
    ON CONFLICT (cycle_id) DO UPDATE
        SET response = EXCLUDED.response,
            generated_at = now()
""")

_DELETE_SQL = text("""
    DELETE FROM cycles.summary_cache
    WHERE cycle_id = :cycle_id
""")


def get_cached_summary(cycle_id: str) -> dict | None:
    try:
        with SessionLocal() as session:
            row = session.execute(_GET_SQL, {"cycle_id": cycle_id}).fetchone()
    except SQLAlchemyError:
        logger.warning("[WARN] cache read failed for cycle_id=%s", cycle_id, exc_info=True)
        return None

    if row is None:
        return None

    generated_at = row.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    if age_seconds > CACHE_TTL_SECONDS:
        return None

    return row.response


def write_cached_summary(cycle_id: str, payload: dict) -> None:
    try:
        with SessionLocal() as session:
            session.execute(_UPSERT_SQL, {"cycle_id": cycle_id, "response": json.dumps(payload)})
            session.commit()
    except SQLAlchemyError:
        logger.warning("[WARN] cache write failed for cycle_id=%s", cycle_id, exc_info=True)


def invalidate_cache(cycle_id: str) -> None:
    try:
        with SessionLocal() as session:
            session.execute(_DELETE_SQL, {"cycle_id": cycle_id})
            session.commit()
    except SQLAlchemyError:
        logger.warning("[WARN] cache invalidation failed for cycle_id=%s", cycle_id, exc_info=True)

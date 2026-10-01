from unittest.mock import MagicMock

from files import spaces
from monday_ingest.load import ensure_finals


def test_bucket_defaults_to_example_storage(monkeypatch):
    monkeypatch.delenv("DO_SPACES_BUCKET", raising=False)

    assert spaces._bucket() == "example-atlas-storage"


def test_bucket_uses_env_override(monkeypatch):
    monkeypatch.setenv("DO_SPACES_BUCKET", "custom-bucket")

    assert spaces._bucket() == "custom-bucket"


def test_ensure_finals_does_not_alter_spaces_key_at_runtime():
    cur = MagicMock()

    ensure_finals(cur)

    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert not any(
        "ALTER TABLE monday.files" in statement and "spaces_key" in statement
        for statement in statements
    )


def test_monday_files_spaces_key_migration_contains_upgrade_and_downgrade():
    from alembic.versions import a8f2c1d9e4b6_add_monday_files_spaces_key as migration

    executed = []
    original_execute = migration.op.execute
    migration.op.execute = executed.append
    try:
        migration.upgrade()
        migration.downgrade()
    finally:
        migration.op.execute = original_execute

    assert any("ADD COLUMN IF NOT EXISTS spaces_key TEXT" in sql for sql in executed)
    assert any("DROP COLUMN IF EXISTS spaces_key" in sql for sql in executed)

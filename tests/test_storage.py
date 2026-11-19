import sqlite3
from pathlib import Path

import pytest
from smart_notification_manager.core import migrations
from smart_notification_manager.core.repository import SQLiteRepository


@pytest.mark.asyncio
async def test_sqlite_schema_is_created_in_worker(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    assert await repository.async_schema_version() == 1
    assert (tmp_path / "manager.sqlite3").exists()


@pytest.mark.asyncio
async def test_sqlite_transaction_rolls_back_on_error(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")

    def failing_operation(connection):
        connection.execute("INSERT INTO global_settings(key, value_json) VALUES ('x', '{}')")
        raise RuntimeError("rollback")

    with pytest.raises(RuntimeError, match="rollback"):
        await repository.async_run(failing_operation)

    def count(connection):
        return connection.execute("SELECT COUNT(*) FROM global_settings").fetchone()[0]

    assert await repository.async_run(count) == 0


@pytest.mark.asyncio
async def test_schema_rejects_newer_version(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    await repository.async_schema_version()

    def set_newer(connection):
        connection.execute("PRAGMA user_version = 99")

    await repository.async_run(set_newer)
    with pytest.raises(RuntimeError, match="newer"):
        await repository.async_schema_version()


def test_schema_contains_required_table_names(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")

    def tables(connection):
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    import asyncio

    names = asyncio.run(repository.async_run(tables))
    assert {"rules", "alarm_instances", "recipients", "channels", "delivery_attempts", "audit_log"} <= names


def test_failed_migration_rolls_back_and_can_resume(tmp_path: Path, monkeypatch):
    database = tmp_path / "migration.sqlite3"
    connection = sqlite3.connect(database)
    original_migration = migrations._migration_v1

    def faulty_migration(connection):
        connection.execute("CREATE TABLE partial_schema (value TEXT)")
        raise RuntimeError("deliberate migration failure")

    monkeypatch.setattr(migrations, "_migration_v1", faulty_migration)
    with pytest.raises(RuntimeError, match="deliberate migration failure"):
        migrations.apply_migrations(connection)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'partial_schema'"
    ).fetchone() is None

    monkeypatch.setattr(migrations, "_migration_v1", original_migration)
    connection.close()
    connection = sqlite3.connect(database)
    migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'rules'"
    ).fetchone() is not None
    connection.close()

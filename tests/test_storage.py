import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from smart_notification_manager.core import migrations
from smart_notification_manager.core.models import new_id
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from smart_notification_manager.core.rules import (
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
)


def valid_storage_rule():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return RuleDefinition(
        rule_id=new_id(),
        name="Tür offen",
        description="",
        area_id="flur",
        area_name="Flur",
        category="Sicherheit",
        priority=Priority.WARNING,
        enabled=True,
        triggers=(TriggerDefinition(kind=TriggerKind.STATE, entity_ids=("binary_sensor.door",), to_state="on"),),
        conditions=ConditionNode("all", children=(ConditionNode("entity_state", {"entity_id": "binary_sensor.door", "state": "on"}),)),
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_sqlite_schema_is_created_in_worker(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    assert await repository.async_schema_version() == 2
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
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'rules'"
    ).fetchone() is not None
    connection.close()


@pytest.mark.asyncio
async def test_rule_store_versions_permissions_and_soft_delete(tmp_path: Path):
    store = RuleStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    access = EditorAccess("user-1", frozenset({"edit"}))
    rule = valid_storage_rule()
    saved = await store.async_save(rule, access)
    assert saved.rule_id == rule.rule_id
    assert (await store.async_get(rule.rule_id)).priority is Priority.WARNING

    updated = replace(rule, name="Tür offen – geändert", version=2, updated_at=rule.updated_at)
    assert (await store.async_save(updated, access)).version == 2
    with pytest.raises(ValueError, match="version conflict"):
        await store.async_save(replace(updated, name="veraltete Änderung"), access)
    assert (await store.async_get(rule.rule_id)).name == updated.name

    with pytest.raises(PermissionError):
        await store.async_save(rule, EditorAccess(None, frozenset({"edit"})))

    with pytest.raises(ValueError, match="name"):
        await store.async_save(replace(rule, name=""), access)
    assert (await store.async_get(rule.rule_id)).name == updated.name

    duplicate = await store.async_duplicate(rule, now=rule.updated_at, access=access)
    assert duplicate.rule_id != rule.rule_id
    assert duplicate.enabled is False
    await store.async_delete(rule.rule_id, now=rule.updated_at, access=access)
    assert await store.async_get(rule.rule_id) is None
    assert len(await store.async_list()) == 1

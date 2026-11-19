from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from smart_notification_manager.core.rule_templates import BUILTIN_TEMPLATES, TEMPLATE_FORMAT, RuleTemplateStore
from smart_notification_manager.core.rules import Priority
from smart_notification_manager.core.simulation import simulate_rule

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def rule_payload(rule_id: str | None = None):
    return {
        "rule_id": rule_id or str(uuid4()),
        "name": "Fenster Phase 8",
        "category": "Sicherheit",
        "priority": "warning",
        "enabled": True,
        "version": 1,
        "triggers": [{"kind": "state", "entity_ids": ["binary_sensor.fenster"], "to_state": "on"}],
        "conditions": {"kind": "all", "children": [{"kind": "entity_state", "value": {"entity_id": "binary_sensor.fenster", "state": "on"}}]},
        "routing": {"recipient_ids": ["person-a"], "channel_ids": ["mobile-a"]},
    }


@pytest.mark.asyncio
async def test_builtin_templates_are_complete_and_entity_agnostic(tmp_path: Path):
    assert len(BUILTIN_TEMPLATES) == 14
    assert all("<entity>" in item.definition["entity_placeholders"] for item in BUILTIN_TEMPLATES)
    store = RuleTemplateStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    assert len(await store.async_list()) == 14


@pytest.mark.asyncio
async def test_template_import_preview_conflict_and_secret_rejection(tmp_path: Path):
    store = RuleTemplateStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    value = {"format": TEMPLATE_FORMAT, "template": {"template_id": "custom-one", "name": "Eigene Vorlage", "definition": {"entity_placeholders": ["<entity>"]}}}
    preview = await store.async_import(value, user_id="admin", now=NOW, confirm=False)
    assert preview["confirmed"] is False
    saved = await store.async_import(value, user_id="admin", now=NOW, confirm=True)
    assert saved["confirmed"] is True
    with pytest.raises(ValueError, match="Vorlagenkonflikt"):
        await store.async_import(value, user_id="admin", now=NOW, confirm=True)
    secret = {"format": TEMPLATE_FORMAT, "template": {"name": "Unsicher", "definition": {"entity_placeholders": ["<entity>"], "token": "x"}}}
    with pytest.raises(ValueError, match="Zugangsdaten"):
        await store.async_import(secret, user_id="admin", now=NOW, confirm=False)


@pytest.mark.asyncio
async def test_template_owner_cannot_be_overwritten(tmp_path: Path):
    store = RuleTemplateStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    value = {"template_id": "owned", "name": "Eigentum", "definition": {"entity_placeholders": ["<entity>"]}}
    await store.async_save(value, user_id="user-a", now=NOW)
    with pytest.raises(PermissionError, match="anderen Benutzer"):
        await store.async_save({**value, "name": "Fremde Änderung"}, user_id="user-b", now=NOW)


def test_simulation_is_read_only_and_respects_policy_reason():
    result = simulate_rule(rule_payload(), states={"binary_sensor.fenster": {"before": "off", "after": "on"}}, policy_reasons=[{"action": "suppress", "reason": "quiet_hours", "reason_de": "Ruhezeit ist aktiv."}])
    assert result["would_trigger"] is True
    assert result["would_send"] is False
    assert result["delivery_reason"] == "Ruhezeit ist aktiv."
    assert result["recipients"] == ["person-a"]


@pytest.mark.asyncio
async def test_version_history_and_restore_create_new_version(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = RuleStore(repository)
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    first = rule_from_editor_payload(rule_payload())
    await store.async_save(first, access)
    second = replace(first, name="Fenster geändert", version=2)
    await store.async_save(second, access)
    versions = await store.async_list_versions(first.rule_id)
    assert [item["version"] for item in versions] == [2, 1]
    restored = await store.async_restore(first.rule_id, version=1, access=access, now=NOW, reason="Review")
    assert restored.version == 3
    assert restored.name == first.name
    assert len(await store.async_list_versions(first.rule_id)) == 3


@pytest.mark.asyncio
async def test_critical_restore_requires_explicit_confirmation(tmp_path: Path):
    store = RuleStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    critical = rule_from_editor_payload({**rule_payload(), "priority": Priority.CRITICAL.value})
    await store.async_save(critical, access)
    with pytest.raises(PermissionError, match="Critical"):
        await store.async_restore(critical.rule_id, version=1, access=access, now=NOW, reason="Review")

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from smart_notification_manager.core.policies import PolicyStore, RateLimitPolicy
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


def test_simulation_with_missing_state_is_not_a_delivery_promise():
    result = simulate_rule(rule_payload())
    assert result["data_complete"] is False
    assert result["would_send"] is False
    assert result["delivery_reason"].startswith("Nicht sicher bestimmbar")


@pytest.mark.asyncio
async def test_policy_preview_uses_rate_limit_without_reserving_capacity(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = RuleStore(repository)
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    rule = rule_from_editor_payload(rule_payload())
    await store.async_save(rule, access)
    policies = PolicyStore(repository)
    await policies.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1), user_id="admin", now=NOW)
    await repository.async_run(lambda c: c.execute("INSERT INTO rate_limit_events(event_id,rule_id,occurred_at,kind) VALUES (?,?,?,?)", (str(uuid4()), rule.rule_id, NOW.isoformat(), "notification")))
    first = await repository.async_run(lambda c: policies.preview_in_connection(c, {"rule_id": rule.rule_id, "priority": "normal", "alarm_state": "active"}, now=NOW))
    second = await repository.async_run(lambda c: policies.preview_in_connection(c, {"rule_id": rule.rule_id, "priority": "normal", "alarm_state": "active"}, now=NOW))
    assert first.decision.reason_code == "rate_limit"
    assert second.decision.reason_code == "rate_limit"
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM rate_limit_events").fetchone()[0]) == 1


@pytest.mark.asyncio
async def test_policy_preview_dependency_and_critical_exception(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = RuleStore(repository)
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    rule = rule_from_editor_payload(rule_payload())
    dependency = rule_from_editor_payload(rule_payload())
    await store.async_save(rule, access)
    await store.async_save(dependency, access)
    policies = PolicyStore(repository)
    await policies.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1, critical_exempt=True), user_id="admin", now=NOW)
    await repository.async_run(lambda c: c.execute("INSERT INTO rate_limit_events(event_id,rule_id,occurred_at,kind) VALUES (?,?,?,?)", (str(uuid4()), rule.rule_id, NOW.isoformat(), "notification")))
    await repository.async_run(lambda c: c.execute("INSERT INTO rule_dependencies(rule_id,depends_on_rule_id,expected_state,enabled,updated_by,updated_at) VALUES (?,?,?,?,?,?)", (rule.rule_id, dependency.rule_id, "active", 1, "admin", NOW.isoformat())))
    blocked = await repository.async_run(lambda c: policies.preview_in_connection(c, {"rule_id": rule.rule_id, "priority": "normal", "alarm_state": "active"}, now=NOW))
    await repository.async_run(lambda c: c.execute("INSERT INTO alarm_instances(alarm_id,rule_id,cause_key,alarm_state,acknowledgement_state,delivery_state,escalation_state,started_at) VALUES (?,?,?,?,?,?,?,?)", (str(uuid4()), dependency.rule_id, "dependency", "active", "pending", "pending", "none", NOW.isoformat())))
    critical = await repository.async_run(lambda c: policies.preview_in_connection(c, {"rule_id": rule.rule_id, "priority": "critical", "alarm_state": "active"}, now=NOW))
    assert blocked.decision.reason_code == "dependency_not_met"
    assert critical.decision.reason_code == "allowed"


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
    restored = await store.async_restore(first.rule_id, version=1, access=access, now=NOW, expected_version=2, available_entities={"binary_sensor.fenster"}, reason="Review")
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
        await store.async_restore(critical.rule_id, version=1, access=access, now=NOW, expected_version=1, available_entities={"binary_sensor.fenster"}, reason="Review")


@pytest.mark.asyncio
async def test_restore_rejects_stale_version_and_missing_entity(tmp_path: Path):
    store = RuleStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    first = rule_from_editor_payload(rule_payload())
    await store.async_save(first, access)
    await store.async_save(replace(first, version=2, name="Neu"), access)
    with pytest.raises(ValueError, match="version conflict"):
        await store.async_restore(first.rule_id, version=1, access=access, now=NOW, expected_version=1)
    with pytest.raises(ValueError, match="nicht verfügbare"):
        await store.async_restore(first.rule_id, version=1, access=access, now=NOW, expected_version=2, available_entities=set())
    assert (await store.async_get(first.rule_id)).version == 2


@pytest.mark.asyncio
async def test_restore_rejects_dependency_cycle_and_preserves_alarm_history(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = RuleStore(repository)
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    first = rule_from_editor_payload(rule_payload())
    second = rule_from_editor_payload(rule_payload())
    await store.async_save(first, access)
    await store.async_save(second, access)
    alarm_id = str(uuid4())
    await repository.async_run(lambda c: c.execute("INSERT INTO alarm_instances(alarm_id,rule_id,cause_key,alarm_state,acknowledgement_state,delivery_state,escalation_state,started_at) VALUES (?,?,?,?,?,?,?,?)", (alarm_id, first.rule_id, "cause", "active", "pending", "pending", "none", NOW.isoformat())))
    await repository.async_run(lambda c: c.executemany("INSERT INTO rule_dependencies(rule_id,depends_on_rule_id,expected_state,enabled,updated_by,updated_at) VALUES (?,?,?,?,?,?)", [(first.rule_id, second.rule_id, "inactive", 1, "admin", NOW.isoformat()), (second.rule_id, first.rule_id, "inactive", 1, "admin", NOW.isoformat())]))
    with pytest.raises(ValueError, match="Zirkuläre"):
        await store.async_restore(first.rule_id, version=1, access=access, now=NOW, expected_version=1, available_entities={"binary_sensor.fenster"})
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()[0]) == 1


@pytest.mark.asyncio
async def test_parallel_restores_have_one_version_winner(tmp_path: Path):
    store = RuleStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    access = EditorAccess("admin", frozenset({"edit", "admin"}))
    from smart_notification_manager.core.rule_store import rule_from_editor_payload

    rule = rule_from_editor_payload(rule_payload())
    await store.async_save(rule, access)
    results = await asyncio.gather(
        store.async_restore(rule.rule_id, version=1, access=access, now=NOW, expected_version=1, available_entities={"binary_sensor.fenster"}),
        store.async_restore(rule.rule_id, version=1, access=access, now=NOW, expected_version=1, available_entities={"binary_sensor.fenster"}),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert len(await store.async_list_versions(rule.rule_id)) == 2

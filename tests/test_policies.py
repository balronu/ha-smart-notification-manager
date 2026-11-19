import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from smart_notification_manager.core.models import new_id
from smart_notification_manager.core.policies import (
    Pause,
    PolicyStore,
    QuietHours,
    RateLimitPolicy,
    RuleDependency,
    quiet_hours_active,
)
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from test_storage import valid_storage_rule


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (datetime(2026, 1, 5, 23, tzinfo=UTC), True),
        (datetime(2026, 1, 6, 6, tzinfo=UTC), True),
        (datetime(2026, 1, 6, 12, tzinfo=UTC), False),
    ],
)
def test_quiet_hours_support_overnight_weekdays_and_critical_exception(when, expected):
    quiet = QuietHours("night", "Nacht", True, (0, 1, 2, 3, 4), "22:00", "07:00")
    assert quiet_hours_active(quiet, when, rule_id="rule", priority="normal") is expected
    assert quiet_hours_active(quiet, when, rule_id="rule", priority="critical") is False


@pytest.mark.asyncio
async def test_pause_persists_resume_and_policy_never_creates_delivery_job(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "policy.sqlite3")
    rules = RuleStore(repository)
    rule = await rules.async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = PolicyStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    await store.async_save_pause(Pause("pause", "rule", rule.rule_id, now, now + timedelta(hours=1), "Wartung", "owner"), now=now)
    decision = await store.async_decide({"rule_id": rule.rule_id, "alarm_id": "alarm", "alarm_state": "active", "rule_enabled": True, "priority": "normal"}, now=now + timedelta(minutes=1))
    assert decision.action == "suppress" and decision.reason_code == "paused"
    assert await store.async_list() and (await store.async_list())["pauses"][0]["active"] == 1
    await store.async_resume_pause("pause")
    assert (await store.async_list())["pauses"][0]["active"] == 0


@pytest.mark.asyncio
async def test_rate_limit_is_atomic_under_parallel_events_and_critical_is_exempt(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "policy.sqlite3")
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    store = PolicyStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    await store.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1), user_id="owner", now=now)
    request = {"rule_id": rule.rule_id, "alarm_state": "active", "rule_enabled": True, "priority": "normal"}
    decisions = await asyncio.gather(*(store.async_decide({**request, "alarm_id": str(index)}, now=now) for index in range(4)))
    assert sum(item.action == "allow" for item in decisions) == 1
    assert sum(item.reason_code == "rate_limit" for item in decisions) == 3
    critical = await store.async_decide({**request, "priority": "critical"}, now=now)
    assert critical.action == "allow"


@pytest.mark.asyncio
async def test_dependencies_reject_cycles_unknown_state_and_observation_has_no_delivery(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "policy.sqlite3")
    rules = RuleStore(repository)
    first = await rules.async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    second = await rules.async_save(replace(valid_storage_rule(), rule_id=new_id()), EditorAccess("owner", frozenset({"edit"})))
    store = PolicyStore(repository)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    await store.async_save_dependency(RuleDependency(first.rule_id, second.rule_id, "active"), user_id="owner", now=now)
    with pytest.raises(ValueError, match="Zirkuläre"):
        await store.async_save_dependency(RuleDependency(second.rule_id, first.rule_id, "active"), user_id="owner", now=now)
    blocked = await store.async_decide({"rule_id": first.rule_id, "alarm_state": "active", "rule_enabled": True, "dependency_states": {}}, now=now)
    assert blocked.reason_code == "dependency_not_met"
    spoofed = await store.async_decide({"rule_id": first.rule_id, "alarm_state": "active", "rule_enabled": True, "dependency_states": {second.rule_id: "active"}}, now=now)
    assert spoofed.reason_code == "dependency_not_met"
    await store.async_save_observation(first.rule_id, enabled=True, critical_confirmed=False, user_id="owner", now=now)
    observed = await store.async_decide({"rule_id": first.rule_id, "alarm_state": "active", "rule_enabled": True}, now=now)
    assert observed.action == "observe"
    assert (await store.repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0])) == 0

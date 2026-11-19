from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from smart_notification_manager.const import DOMAIN
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import RuleStore, rule_to_dict
from smart_notification_manager.core.rules import (
    Comparison,
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
)
from smart_notification_manager.websocket import websocket_save


class Connection:
    def __init__(self):
        self.user = SimpleNamespace(id="ha-admin")
        self.results = []
        self.errors = []

    def send_result(self, message_id, payload):
        self.results.append((message_id, payload))

    def send_error(self, message_id, code, message):
        self.errors.append((message_id, code, message))


def base_rule():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return RuleDefinition(
        rule_id="8f7a4f20-8c5e-4e15-a5da-3a7c8e3f0c9b",
        name="Temperatur und Tür",
        description="End-to-end",
        area_id=None,
        area_name=None,
        category="Sicherheit",
        priority=Priority.WARNING,
        enabled=True,
        triggers=(
            TriggerDefinition(TriggerKind.STATE, ("binary_sensor.door",), from_state="off", to_state="on"),
            TriggerDefinition(
                TriggerKind.NUMERIC,
                ("sensor.temperature",),
                comparison=Comparison.BETWEEN,
                threshold=10,
                upper_threshold=20,
                hysteresis=1,
            ),
        ),
        conditions=ConditionNode(
            "all",
            children=(
                ConditionNode("entity_state", {"entity_id": "binary_sensor.door", "state": "on"}),
                ConditionNode(
                    "any",
                    children=(
                        ConditionNode("presence", {"entity_id": "person.michael", "present": True}),
                        ConditionNode("time_window", {"start": "22:00", "end": "07:00"}),
                    ),
                ),
            ),
        ),
        version=1,
        created_at=now,
        updated_at=now,
    )


def implementation(handler):
    """Unwrap HA decorators while retaining the production handler body."""

    return handler.__wrapped__.__wrapped__


@pytest.mark.asyncio
async def test_authenticated_api_round_trip_and_conflict(tmp_path):
    store = RuleStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    hass = SimpleNamespace(data={DOMAIN: {"rule_store": store}})
    connection = Connection()
    payload = rule_to_dict(base_rule())
    handler = implementation(websocket_save)

    await handler(hass, connection, {"id": 1, "rule": payload})
    assert connection.errors == []
    assert connection.results[0][1]["rule"]["version"] == 1
    loaded = await store.async_get(payload["rule_id"])
    assert rule_to_dict(loaded) == payload

    edited = dict(payload, name="Geänderte Regel", version=2)
    await handler(hass, connection, {"id": 2, "rule": edited})
    assert connection.results[-1][1]["rule"]["version"] == 2
    assert (await store.async_get(payload["rule_id"])).name == "Geänderte Regel"

    await handler(hass, connection, {"id": 3, "rule": edited})
    assert connection.errors[-1][0] == 3
    assert "Stack" not in connection.errors[-1][2]
    assert (await store.async_get(payload["rule_id"])).version == 2

    await handler(hass, connection, {"id": 5, "rule": dict(edited, name="")})
    assert connection.errors[-1] == (5, "invalid_format", "Die Regel ist ungültig oder darf nicht geändert werden.")
    assert (await store.async_get(payload["rule_id"])).name == "Geänderte Regel"


@pytest.mark.asyncio
async def test_api_returns_safe_error_when_integration_is_missing():
    connection = Connection()
    await implementation(websocket_save)(SimpleNamespace(data={}), connection, {"id": 4, "rule": rule_to_dict(base_rule())})
    assert connection.errors == [(4, "unknown_error", "Die Regelverwaltung ist derzeit nicht verfügbar.")]

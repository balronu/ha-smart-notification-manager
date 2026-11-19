from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from smart_notification_manager.const import DOMAIN
from smart_notification_manager.core.recipient_store import RecipientStore
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore, rule_to_dict
from smart_notification_manager.core.rules import (
    Comparison,
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
)
from smart_notification_manager.websocket import (
    websocket_channel_group_save,
    websocket_channel_save,
    websocket_recipient_save,
    websocket_rule_routing_save,
    websocket_save,
    websocket_template_save,
)


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


@pytest.mark.asyncio
async def test_recipient_api_persists_devices_without_external_send(tmp_path):
    store = RecipientStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    hass = SimpleNamespace(data={DOMAIN: {"recipient_store": store}})
    connection = Connection()
    handler = implementation(websocket_recipient_save)
    await handler(hass, connection, {"id": 6, "recipient": {"recipient_id": "michael", "display_name": "Michael", "devices": [{"device_id": "phone", "display_name": "Telefon", "channel_id": "mobile", "primary": True, "available": True}]}})
    assert connection.errors == []
    assert (await store.async_list_recipients())[0].devices[0].channel_id == "mobile"


@pytest.mark.asyncio
async def test_channel_group_api_round_trip(tmp_path):
    store = RecipientStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    hass = SimpleNamespace(data={DOMAIN: {"recipient_store": store}})
    connection = Connection()
    await implementation(websocket_channel_group_save)(
        hass,
        connection,
        {"id": 7, "group": {"channel_group_id": "urgent", "display_name": "Dringend", "channel_ids": []}},
    )
    assert connection.errors == []
    assert connection.results[-1][1]["group"]["display_name"] == "Dringend"
    assert (await store.async_list_channel_groups())[0]["channel_group_id"] == "urgent"


@pytest.mark.asyncio
async def test_phase3_channel_template_and_rule_routing_websocket_round_trip(tmp_path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    recipient_store = RecipientStore(repository)
    rule_store = RuleStore(repository)
    hass = SimpleNamespace(data={DOMAIN: {"recipient_store": recipient_store, "rule_store": rule_store}})
    connection = Connection()
    await implementation(websocket_channel_save)(hass, connection, {"id": 8, "channel": {"channel_id": "mobile", "channel_type": "notify", "display_name": "Mobile", "config": {"service": "notify.mobile_app_phone"}}})
    await implementation(websocket_template_save)(hass, connection, {"id": 9, "template": {"template_id": "door", "name": "Tür", "body": "{{ rule_name }}", "version": 1}})
    saved = await rule_store.async_save(base_rule(), EditorAccess("ha-admin", frozenset({"admin"})))
    await implementation(websocket_rule_routing_save)(hass, connection, {"id": 10, "rule_id": saved.rule_id, "routing": {"recipient_ids": ["michael"], "channel_ids": ["mobile"], "all_devices": False}})
    assert connection.errors == []
    assert (await rule_store.async_get(saved.rule_id)).routing["channel_ids"] == ["mobile"]
    assert (await recipient_store.async_list_channels())[0]["channel_id"] == "mobile"

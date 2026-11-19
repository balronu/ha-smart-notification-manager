"""Authenticated Home Assistant WebSocket API for the Phase 2 editor."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Any

import probatio
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .core.adapters import DeliveryRequest
from .core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy, alarm_to_dict
from .core.delivery_store import DeliveryStore
from .core.entity_catalog import list_entity_snapshots
from .core.recipient_store import RecipientStore
from .core.recipients import Recipient, RecipientDevice, RecipientGroup
from .core.rule_store import EditorAccess, RuleStore, rule_from_editor_payload, rule_to_dict

_LOGGER = logging.getLogger(__name__)


def async_register(hass: HomeAssistant) -> None:
    """Register the editor commands once per Home Assistant process."""

    if hass.data.setdefault(DOMAIN, {}).get("websocket_registered"):
        return
    websocket_api.async_register_command(hass, websocket_list)
    websocket_api.async_register_command(hass, websocket_save)
    websocket_api.async_register_command(hass, websocket_delete)
    websocket_api.async_register_command(hass, websocket_duplicate)
    for handler in (websocket_recipient_list, websocket_recipient_save, websocket_recipient_delete, websocket_group_save, websocket_channel_save, websocket_channel_group_save, websocket_channel_group_delete, websocket_template_save, websocket_template_delete, websocket_routing_preview, websocket_rule_routing_save, websocket_delivery_enqueue, websocket_delivery_list, websocket_alarm_list, websocket_alarm_trigger, websocket_alarm_events, websocket_alarm_acknowledge, websocket_alarm_acknowledge_many, websocket_alarm_resolve, websocket_alarm_close):
        websocket_api.async_register_command(hass, handler)
    hass.data[DOMAIN]["websocket_registered"] = True


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/list"})
@websocket_api.async_response
async def websocket_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Return rules and the read-only HA entity catalog to an admin user."""

    try:
        store = _store(hass)
        rules = [rule_to_dict(rule) for rule in await store.async_list()]
        entities = [asdict(snapshot) for snapshot in list_entity_snapshots(hass)]
        connection.send_result(msg["id"], {"rules": rules, "entities": entities})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "smart_notification_manager/save",
        probatio.Required("rule"): dict,
    }
)
@websocket_api.async_response
async def websocket_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Validate and save one rule for the authenticated admin user."""

    try:
        rule = rule_from_editor_payload(msg["rule"])
        saved = await _store(hass).async_save(
            rule,
            EditorAccess(connection.user.id, frozenset({"admin"})),
        )
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regel ist ungültig oder darf nicht geändert werden.")
        return
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)
        return
    connection.send_result(msg["id"], {"rule": rule_to_dict(saved)})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "smart_notification_manager/delete",
        probatio.Required("rule_id"): str,
    }
)
@websocket_api.async_response
async def websocket_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Soft-delete a rule while preserving alarm history."""

    from datetime import UTC, datetime

    try:
        await _store(hass).async_delete(
            msg["rule_id"],
            now=datetime.now(UTC),
            access=EditorAccess(connection.user.id, frozenset({"admin"})),
        )
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)
        return
    connection.send_result(msg["id"], {})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "smart_notification_manager/duplicate",
        probatio.Required("rule"): dict,
    }
)
@websocket_api.async_response
async def websocket_duplicate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Duplicate a rule as disabled, requiring an authenticated admin."""

    from datetime import UTC, datetime

    try:
        rule = rule_from_editor_payload(msg["rule"])
        duplicate = await _store(hass).async_duplicate(
            rule,
            now=datetime.now(UTC),
            access=EditorAccess(connection.user.id, frozenset({"admin"})),
        )
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regel ist ungültig oder darf nicht dupliziert werden.")
        return
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)
        return
    connection.send_result(msg["id"], {"rule": rule_to_dict(duplicate)})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/recipient/list"})
@websocket_api.async_response
async def websocket_recipient_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        store = _recipient_store(hass)
        recipients = [asdict(item) for item in await store.async_list_recipients()]
        groups = [asdict(item) for item in await store.async_list_groups()]
        connection.send_result(msg["id"], {"recipients": recipients, "groups": groups, "channels": await store.async_list_channels(), "channel_groups": await store.async_list_channel_groups(), "templates": await store.async_list_templates()})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/recipient/save", probatio.Required("recipient"): dict})
@websocket_api.async_response
async def websocket_recipient_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["recipient"]
        recipient = Recipient(value["recipient_id"], value["display_name"], bool(value.get("enabled", True)), tuple(RecipientDevice(**device) for device in value.get("devices", [])))
        saved = await _recipient_store(hass).async_save_recipient(recipient)
        connection.send_result(msg["id"], {"recipient": asdict(saved)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Empfänger ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/recipient/delete", probatio.Required("recipient_id"): str})
@websocket_api.async_response
async def websocket_recipient_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _recipient_store(hass).async_delete_recipient(msg["recipient_id"])
        connection.send_result(msg["id"], {})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/group/save", probatio.Required("group"): dict})
@websocket_api.async_response
async def websocket_group_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["group"]
        saved = await _recipient_store(hass).async_save_group(RecipientGroup(value["group_id"], value["display_name"], tuple(value.get("recipient_ids", [])), bool(value.get("enabled", True))))
        connection.send_result(msg["id"], {"group": asdict(saved)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Empfängergruppe ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/channel/save", probatio.Required("channel"): dict})
@websocket_api.async_response
async def websocket_channel_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        saved = await _recipient_store(hass).async_save_channel(msg["channel"])
        connection.send_result(msg["id"], {"channel": saved})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Kanal ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/channel-group/save", probatio.Required("group"): dict})
@websocket_api.async_response
async def websocket_channel_group_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        saved = await _recipient_store(hass).async_save_channel_group(msg["group"])
        connection.send_result(msg["id"], {"group": saved})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Kanalgruppe ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/channel-group/delete", probatio.Required("group_id"): str})
@websocket_api.async_response
async def websocket_channel_group_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _recipient_store(hass).async_delete_channel_group(msg["group_id"])
        connection.send_result(msg["id"], {})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/template/save", probatio.Required("template"): dict})
@websocket_api.async_response
async def websocket_template_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        saved = await _recipient_store(hass).async_save_template(msg["template"])
        connection.send_result(msg["id"], {"template": saved})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Vorlage ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/template/delete", probatio.Required("template_id"): str})
@websocket_api.async_response
async def websocket_template_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _recipient_store(hass).async_delete_template(msg["template_id"])
        connection.send_result(msg["id"], {})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/routing/preview", probatio.Required("payload"): dict})
@websocket_api.async_response
async def websocket_routing_preview(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        preview = await _recipient_store(hass).async_preview(msg["payload"])
        connection.send_result(msg["id"], preview)
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Routing-Vorschau ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/rule/routing/save", probatio.Required("rule_id"): str, probatio.Required("routing"): dict})
@websocket_api.async_response
async def websocket_rule_routing_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        store = _store(hass)
        current = await store.async_get(msg["rule_id"])
        if current is None:
            raise ValueError("Regel nicht gefunden")
        saved = await store.async_save(replace(current, routing=msg["routing"], version=current.version + 1, updated_at=datetime.now(UTC)), EditorAccess(connection.user.id, frozenset({"admin"})))
        connection.send_result(msg["id"], {"rule": rule_to_dict(saved)})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Das Routing der Regel ist ungültig oder darf nicht geändert werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/delivery/enqueue", probatio.Required("request"): dict, probatio.Required("channel_id"): str, probatio.Required("idempotency_key"): str})
@websocket_api.async_response
async def websocket_delivery_enqueue(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Persist a pending job; enqueueing alone never invokes an HA service."""

    try:
        value = msg["request"]
        request = DeliveryRequest(
            attempt_id=value["attempt_id"],
            recipient_id=value["recipient_id"],
            title=str(value.get("title", "")),
            message=value["message"],
            payload=dict(value.get("payload", {})),
        )
        job = await DeliveryStore(_recipient_store(hass).repository).async_enqueue(
            request, idempotency_key=msg["idempotency_key"], channel_id=msg["channel_id"], alarm_id=value.get("alarm_id")
        )
        connection.send_result(msg["id"], {"job": _job_to_dict(job)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Versandauftrag ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/delivery/list"})
@websocket_api.async_response
async def websocket_delivery_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        jobs = await DeliveryStore(_recipient_store(hass).repository).async_list()
        connection.send_result(msg["id"], {"jobs": [_job_to_dict(job) for job in jobs]})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/list"})
@websocket_api.async_response
async def websocket_alarm_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """List persisted alarms and never expose another user's private data."""

    try:
        states = tuple(msg.get("states", ())) or None
        alarms = await _alarm_store(hass).async_list(states=states)
        connection.send_result(msg["id"], {"alarms": [alarm_to_dict(item) for item in alarms]})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarmfilter ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/trigger", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_alarm_trigger(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["request"]
        policy = AlarmPolicy(
            delay_seconds=int(value.get("delay_seconds", 0)),
            repeat_interval_seconds=int(value.get("repeat_interval_seconds", 0)),
            max_repeats=int(value.get("max_repeats", 0)),
            repeat_only_active=bool(value.get("repeat_only_active", True)),
            repeat_only_unacknowledged=bool(value.get("repeat_only_unacknowledged", False)),
            max_duration_seconds=int(value.get("max_duration_seconds", 0)),
            escalation_stages=tuple(value.get("escalation_stages", ())),
        )
        alarm, created = await _alarm_store(hass).async_trigger(
            rule_id=value["rule_id"], entity_id=value["entity_id"], friendly_name=str(value.get("friendly_name", "")),
            area_id=value.get("area_id"), area_name=value.get("area_name"), priority=str(value.get("priority", "normal")),
            previous_state=value.get("previous_state"), current_state=value.get("current_state"), now=datetime.fromisoformat(value["now"]) if value.get("now") else datetime.now(UTC), policy=policy,
        )
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm), "created": created})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarm kann nicht angelegt werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/events", probatio.Required("alarm_id"): str})
@websocket_api.async_response
async def websocket_alarm_events(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], {"events": await _alarm_store(hass).async_events(msg["alarm_id"])})
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/acknowledge", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_alarm_acknowledge(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["request"]
        alarm = await _alarm_store(hass).async_acknowledge(value["alarm_id"], user_id=connection.user.id, now=datetime.now(UTC), scope=str(value.get("scope", "all")), critical_confirmed=bool(value.get("critical_confirmed", False)))
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm)})
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für diesen Alarm fehlt die erforderliche Bestätigung oder Berechtigung.")
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarm kann nicht quittiert werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/acknowledge_many", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_alarm_acknowledge_many(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["request"]
        alarms = await _alarm_store(hass).async_acknowledge_many(value["alarm_ids"], user_id=connection.user.id, now=datetime.now(UTC), scope=str(value.get("scope", "all")), critical_confirmed=bool(value.get("critical_confirmed", False)))
        connection.send_result(msg["id"], {"alarms": [alarm_to_dict(alarm) for alarm in alarms]})
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für mindestens einen Critical-Alarm fehlt die erforderliche Bestätigung.")
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Sammelquittierung ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/resolve", probatio.Required("alarm_id"): str})
@websocket_api.async_response
async def websocket_alarm_resolve(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        current = await _alarm_store(hass).async_get(msg["alarm_id"])
        if current is None:
            raise ValueError("alarm not found")
        state = hass.states.get(current.entity_id) if getattr(hass, "states", None) is not None else None
        actual_state = getattr(state, "state", None)
        alarm = await _alarm_store(hass).async_resolve(msg["alarm_id"], now=datetime.now(UTC), actual_state=actual_state, expected_active_state=current.current_state, available=actual_state not in {None, "unknown", "unavailable"})
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Entwarnung ist für diesen Alarm nicht zulässig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/close", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_alarm_close(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["request"]
        alarm = await _alarm_store(hass).async_close(value["alarm_id"], user_id=connection.user.id, now=datetime.now(UTC), reason=value["reason"], critical_confirmed=bool(value.get("critical_confirmed", False)))
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm)})
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für diesen Critical-Alarm fehlt die erforderliche Bestätigung.")
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarm kann nicht manuell abgeschlossen werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


def _store(hass: HomeAssistant) -> RuleStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("rule_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _recipient_store(hass: HomeAssistant) -> RecipientStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("recipient_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _alarm_store(hass: HomeAssistant) -> AlarmLifecycleStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("alarm_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _job_to_dict(job) -> dict[str, Any]:
    return {
        "attempt_id": job.attempt_id,
        "alarm_id": job.alarm_id,
        "idempotency_key": job.idempotency_key,
        "recipient_id": job.recipient_id,
        "channel_id": job.channel_id,
        "state": job.state,
        "attempt_number": job.attempt_number,
        "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
        "delivery_confirmed": job.delivery_confirmed,
        "payload": job.payload,
    }


def _send_storage_error(connection, msg: dict[str, Any], err: Exception) -> None:
    """Log diagnostics privately and expose only a stable German error."""

    _LOGGER.error("Smart Notification Manager storage operation failed", exc_info=err)
    connection.send_error(
        msg["id"],
        websocket_api.ERR_UNKNOWN_ERROR,
        "Die Regelverwaltung ist derzeit nicht verfügbar.",
    )


def _send_alarm_storage_error(connection, msg: dict[str, Any], err: Exception) -> None:
    _LOGGER.error("Smart Notification Manager alarm operation failed", exc_info=err)
    connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, "Die Alarmverwaltung ist derzeit nicht verfügbar.")

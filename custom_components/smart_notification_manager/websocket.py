"""Authenticated Home Assistant WebSocket API for the Phase 2 editor."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime
from functools import wraps
from typing import Any

import probatio
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .core.adapters import DeliveryRequest
from .core.alarm_center import AlarmCenterStore
from .core.alarm_lifecycle import AlarmLifecycleStore, AlarmPolicy, alarm_to_dict
from .core.automation_migration import AutomationMigrationStore, build_hybrid_plan, discover_automation
from .core.delivery_store import DeliveryStore, PolicySuppressedError
from .core.entity_catalog import list_entity_snapshots
from .core.policies import Pause, PolicyStore, QuietHours, RateLimitPolicy, RuleDependency
from .core.recipient_store import RecipientStore
from .core.recipients import Recipient, RecipientDevice, RecipientGroup
from .core.revalidation import revalidate_alarm
from .core.rule_store import EditorAccess, RuleStore, rule_from_editor_payload, rule_to_dict
from .core.rule_templates import RuleTemplateStore
from .core.simulation import async_policy_preview, simulate_rule

_LOGGER = logging.getLogger(__name__)


def _require_alarm_role(required: str):
    """Authorize legacy alarm commands using the same Phase-6 role model."""

    def decorator(handler):
        @wraps(handler)
        async def wrapped(hass, connection, msg):
            try:
                user_id = _user_id(connection)
                role = await _alarm_center_store(hass).async_role(
                    user_id, is_admin=bool(getattr(connection.user, "is_admin", False))
                )
                allowed = (
                    required == "read" and role in {"admin", "acknowledger", "read_only"}
                ) or (required == "acknowledger" and role in {"admin", "acknowledger"}) or (
                    required == "admin" and role == "admin"
                )
                if not allowed:
                    connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für diese Alarmaktion fehlt die Berechtigung.")
                    return
            except (PermissionError, RuntimeError, sqlite3.Error):
                connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Authentifizierter Alarmzugriff erforderlich.")
                return
            return await handler(hass, connection, msg)

        return wrapped

    return decorator


def async_register(hass: HomeAssistant) -> None:
    """Register the editor commands once per Home Assistant process."""

    if hass.data.setdefault(DOMAIN, {}).get("websocket_registered"):
        return
    websocket_api.async_register_command(hass, websocket_list)
    websocket_api.async_register_command(hass, websocket_save)
    websocket_api.async_register_command(hass, websocket_delete)
    websocket_api.async_register_command(hass, websocket_duplicate)
    for handler in (websocket_recipient_list, websocket_recipient_save, websocket_recipient_delete, websocket_group_save, websocket_channel_save, websocket_channel_group_save, websocket_channel_group_delete, websocket_template_save, websocket_template_delete, websocket_routing_preview, websocket_rule_routing_save, websocket_delivery_enqueue, websocket_delivery_list, websocket_alarm_list, websocket_alarm_trigger, websocket_alarm_events, websocket_alarm_acknowledge, websocket_alarm_acknowledge_many, websocket_alarm_resolve, websocket_alarm_close, websocket_alarm_center_list, websocket_alarm_center_detail, websocket_alarm_category_list, websocket_alarm_category_save, websocket_alarm_category_deactivate, websocket_alarm_filter_list, websocket_alarm_filter_save, websocket_alarm_filter_delete, websocket_alarm_role_save, websocket_policy_list, websocket_policy_quiet_save, websocket_policy_pause_save, websocket_policy_pause_resume, websocket_policy_rate_limit_save, websocket_policy_dependency_save, websocket_policy_observation_save, websocket_policy_evaluate, websocket_phase8_template_list, websocket_phase8_template_save, websocket_phase8_template_delete, websocket_phase8_template_export, websocket_phase8_template_import, websocket_phase8_simulate, websocket_phase10_observe, websocket_phase8_versions, websocket_phase8_restore, websocket_phase9_discover, websocket_phase9_preview, websocket_phase9_prepare, websocket_phase9_activate, websocket_phase9_rollback, websocket_phase9_reference):
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
    _notify_rule_update(hass, saved.rule_id)


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
    _notify_rule_update(hass, msg["rule_id"])


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
        _notify_rule_update(hass, saved.rule_id)
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Das Routing der Regel ist ungültig oder darf nicht geändert werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@_require_alarm_role("admin")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/delivery/enqueue", probatio.Required("request"): dict, probatio.Required("channel_id"): str, probatio.Required("idempotency_key"): str})
@websocket_api.async_response
async def websocket_delivery_enqueue(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Persist a job only after policy evaluation; this never invokes an HA service."""

    try:
        value = msg["request"]
        request = DeliveryRequest(
            attempt_id=value["attempt_id"],
            recipient_id=value["recipient_id"],
            title=str(value.get("title", "")),
            message=value["message"],
            payload=dict(value.get("payload", {})),
        )
        policy_store = _policy_store(hass)
        policy_request = None
        if value.get("administrative_test") is True:
            # Explicit admin-only persist-only test action. It creates no real
            # service call and is intentionally excluded from alarm policy.
            if value.get("test_only") is not True:
                raise PermissionError("Administrativer Testversand muss ausdrücklich als test_only markiert sein")
            policy_store = None
        else:
            policy_request = await _server_policy_request(hass, value.get("alarm_id"))
        job = await _delivery_store(hass).async_enqueue(
            request, idempotency_key=msg["idempotency_key"], channel_id=msg["channel_id"], alarm_id=value.get("alarm_id"), policy_store=policy_store, policy_request=policy_request
        )
        connection.send_result(msg["id"], {"job": _job_to_dict(job)})
    except PolicySuppressedError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, f"Versand unterdrückt: {err.decision.reason_de}")
    except PermissionError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, str(err))
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Versandauftrag ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@_require_alarm_role("read")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/delivery/list"})
@websocket_api.async_response
async def websocket_delivery_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        jobs = await DeliveryStore(_recipient_store(hass).repository).async_list()
        if _alarm_center_store_if_loaded(hass) is not None:
            user_id = _user_id(connection)
            role = await _alarm_center_store(hass).async_role(user_id, is_admin=bool(getattr(connection.user, "is_admin", False)))
            if role != "admin":
                visible = await _alarm_center_store(hass).async_list_alarms(user_id=user_id, role=role, page=1, page_size=100)
                visible_ids = {item["alarm_id"] for item in visible["alarms"]}
                jobs = [job for job in jobs if job.alarm_id in visible_ids]
        connection.send_result(msg["id"], {"jobs": [_job_to_dict(job) for job in jobs]})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@_require_alarm_role("read")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/list"})
@websocket_api.async_response
async def websocket_alarm_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """List persisted alarms and never expose another user's private data."""

    try:
        states = tuple(msg.get("states", ())) or None
        if _alarm_center_store_if_loaded(hass) is None:
            alarms = await _alarm_store(hass).async_list(states=states)
        else:
            user_id = _user_id(connection)
            role = await _alarm_center_store(hass).async_role(user_id, is_admin=bool(getattr(connection.user, "is_admin", False)))
            result = await _alarm_center_store(hass).async_list_alarms(user_id=user_id, role=role, filters={"states": list(states or ())}, page=1, page_size=100)
            connection.send_result(msg["id"], {"alarms": result["alarms"]})
            return
        connection.send_result(msg["id"], {"alarms": [alarm_to_dict(item) for item in alarms]})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarmfilter ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@_require_alarm_role("admin")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/trigger", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_alarm_trigger(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["request"]
        source_rule = await _store(hass).async_get(value["rule_id"], version=value.get("rule_version"))
        policy = AlarmPolicy(
            delay_seconds=int(value.get("delay_seconds", 0)),
            repeat_interval_seconds=int(value.get("repeat_interval_seconds", 0)),
            max_repeats=int(value.get("max_repeats", 0)),
            repeat_only_active=bool(value.get("repeat_only_active", True)),
            repeat_only_unacknowledged=bool(value.get("repeat_only_unacknowledged", False)),
            max_duration_seconds=int(value.get("max_duration_seconds", 0)),
            escalation_stages=tuple(value.get("escalation_stages", ())),
            acknowledgement_mode=str(value.get("acknowledgement_mode", "any")),
            required_recipient_ids=tuple(str(item) for item in value.get("required_recipient_ids", ())),
        )
        alarm, created = await _alarm_store(hass).async_trigger(
            rule_id=value["rule_id"], entity_id=value["entity_id"], friendly_name=str(value.get("friendly_name", "")),
            area_id=value.get("area_id"), area_name=value.get("area_name"), priority=str(value.get("priority", "normal")),
            previous_state=value.get("previous_state"), current_state=value.get("current_state"), now=datetime.fromisoformat(value["now"]) if value.get("now") else datetime.now(UTC), policy=policy, rule_version=value.get("rule_version"),
            category=source_rule.category if source_rule else "Sonstiges",
        )
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm), "created": created})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Alarm kann nicht angelegt werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@_require_alarm_role("read")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/events", probatio.Required("alarm_id"): str})
@websocket_api.async_response
async def websocket_alarm_events(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        if _alarm_center_store_if_loaded(hass) is not None:
            detail = await _alarm_center_store(hass).async_detail(msg["alarm_id"], user_id=_user_id(connection), role=await _alarm_center_store(hass).async_role(_user_id(connection), is_admin=bool(getattr(connection.user, "is_admin", False))))
            connection.send_result(msg["id"], {"events": detail["events"]})
        else:
            connection.send_result(msg["id"], {"events": await _alarm_store(hass).async_events(msg["alarm_id"])})
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@_require_alarm_role("acknowledger")
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


@_require_alarm_role("acknowledger")
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


@_require_alarm_role("admin")
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm/resolve", probatio.Required("alarm_id"): str})
@websocket_api.async_response
async def websocket_alarm_resolve(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        alarm_store = _alarm_store(hass)
        current = await alarm_store.async_get(msg["alarm_id"])
        if current is None:
            raise ValueError("alarm not found")
        rule = await _store(hass).async_get(current.rule_id, version=current.rule_version)
        if rule is None:
            raise ValueError("original rule not found")
        now = datetime.now(UTC)
        result = revalidate_alarm(hass, rule, current, now)
        if not result.safe_to_resolve:
            raise ValueError(result.reason)
        alarm = await alarm_store.async_resolve(msg["alarm_id"], now=now, actual_state=getattr(hass.states.get(current.entity_id), "state", None), expected_active_state=current.current_state, available=True)
        connection.send_result(msg["id"], {"alarm": alarm_to_dict(alarm)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Entwarnung ist für diesen Alarm nicht zulässig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@_require_alarm_role("admin")
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


@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_center/list"})
@websocket_api.async_response
async def websocket_alarm_center_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        user_id = _user_id(connection)
        role = await _alarm_center_store(hass).async_role(user_id, is_admin=bool(getattr(connection.user, "is_admin", False)))
        result = await _alarm_center_store(hass).async_list_alarms(user_id=user_id, role=role, filters=msg.get("filters"), page=msg.get("page", 1), page_size=msg.get("page_size", 25), sort=msg.get("sort", "newest"), group_by=msg.get("group_by"))
        connection.send_result(msg["id"], {**result, "role": role})
    except PermissionError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, str(err))
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Filter der Alarmübersicht sind ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_center/detail", probatio.Required("alarm_id"): str})
@websocket_api.async_response
async def websocket_alarm_center_detail(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        user_id = _user_id(connection)
        role = await _alarm_center_store(hass).async_role(user_id, is_admin=bool(getattr(connection.user, "is_admin", False)))
        connection.send_result(msg["id"], await _alarm_center_store(hass).async_detail(msg["alarm_id"], user_id=user_id, role=role))
    except PermissionError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, str(err))
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Alarmdetails sind ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_alarm_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_category/list"})
@websocket_api.async_response
async def websocket_alarm_category_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"categories": await _alarm_center_store(hass).async_list_categories(include_disabled=bool(msg.get("include_disabled")))})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_category/save", probatio.Required("category"): dict})
@websocket_api.async_response
async def websocket_alarm_category_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        category = await _alarm_center_store(hass).async_save_category(msg["category"], user_id=_user_id(connection), now=datetime.now(UTC))
        connection.send_result(msg["id"], {"category": category})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Kategorie ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_category/deactivate", probatio.Required("category_id"): str})
@websocket_api.async_response
async def websocket_alarm_category_deactivate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    await _alarm_center_store(hass).async_deactivate_category(msg["category_id"], user_id=_user_id(connection), now=datetime.now(UTC))
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_filter/list"})
@websocket_api.async_response
async def websocket_alarm_filter_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"filters": await _alarm_center_store(hass).async_list_filters(_user_id(connection))})


@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_filter/save", probatio.Required("filter"): dict})
@websocket_api.async_response
async def websocket_alarm_filter_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        saved = await _alarm_center_store(hass).async_save_filter(msg["filter"], user_id=_user_id(connection), now=datetime.now(UTC))
        connection.send_result(msg["id"], {"filter": saved})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die persönliche Filteransicht ist ungültig.")


@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_filter/delete", probatio.Required("filter_id"): str})
@websocket_api.async_response
async def websocket_alarm_filter_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    await _alarm_center_store(hass).async_delete_filter(msg["filter_id"], user_id=_user_id(connection))
    connection.send_result(msg["id"], {})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/alarm_role/save", probatio.Required("user_id"): str, probatio.Required("role"): str})
@websocket_api.async_response
async def websocket_alarm_role_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        role = await _alarm_center_store(hass).async_save_role(msg["user_id"], msg["role"], updated_by=_user_id(connection), now=datetime.now(UTC))
        connection.send_result(msg["id"], {"user_id": msg["user_id"], "role": role})
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/list"})
@websocket_api.async_response
async def websocket_policy_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], await _policy_store(hass).async_list())
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/quiet/save", probatio.Required("quiet"): dict})
@websocket_api.async_response
async def websocket_policy_quiet_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["quiet"]
        quiet = QuietHours(value["quiet_id"], value["name"], bool(value.get("enabled", True)), tuple(value.get("weekdays", range(7))), value["start_time"], value["end_time"], value.get("timezone", "UTC"), tuple(value.get("rule_exceptions", ())), tuple(value.get("priority_exceptions", ("critical",))))
        saved = await _policy_store(hass).async_save_quiet_hours(quiet, user_id=connection.user.id, now=datetime.now(UTC))
        connection.send_result(msg["id"], {"quiet": asdict(saved)})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Ruhezeit ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/pause/save", probatio.Required("pause"): dict})
@websocket_api.async_response
async def websocket_policy_pause_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["pause"]
        pause = Pause(value["pause_id"], value["scope_type"], value.get("scope_id"), datetime.fromisoformat(value["starts_at"]), datetime.fromisoformat(value["ends_at"]) if value.get("ends_at") else None, value["reason"], connection.user.id, bool(value.get("critical_confirmed", False)), bool(value.get("active", True)))
        if value.get("priority") == "critical" and not pause.critical_confirmed:
            raise PermissionError("Critical-Pause benötigt Bestätigung")
        saved = await _policy_store(hass).async_save_pause(pause, now=datetime.now(UTC))
        connection.send_result(msg["id"], {"pause": asdict(saved)})
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für diese Critical-Pause fehlt die Bestätigung.")
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Pause ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/pause/resume", probatio.Required("pause_id"): str})
@websocket_api.async_response
async def websocket_policy_pause_resume(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _policy_store(hass).async_resume_pause(msg["pause_id"])
        connection.send_result(msg["id"], {})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/rate-limit/save", probatio.Required("policy"): dict})
@websocket_api.async_response
async def websocket_policy_rate_limit_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["policy"]
        policy = RateLimitPolicy(value["rule_id"], int(value["window_seconds"]), int(value["max_notifications"]), bool(value.get("critical_exempt", True)), bool(value.get("enabled", True)))
        saved = await _policy_store(hass).async_save_rate_limit(policy, user_id=connection.user.id, now=datetime.now(UTC))
        connection.send_result(msg["id"], {"policy": asdict(saved)})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Das Rate-Limit ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/dependency/save", probatio.Required("dependency"): dict})
@websocket_api.async_response
async def websocket_policy_dependency_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        value = msg["dependency"]
        dependency = RuleDependency(value["rule_id"], value["depends_on_rule_id"], value["expected_state"], bool(value.get("enabled", True)))
        saved = await _policy_store(hass).async_save_dependency(dependency, user_id=connection.user.id, now=datetime.now(UTC))
        connection.send_result(msg["id"], {"dependency": asdict(saved)})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regelabhängigkeit ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/observation/save", probatio.Required("rule_id"): str})
@websocket_api.async_response
async def websocket_policy_observation_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _policy_store(hass).async_save_observation(msg["rule_id"], enabled=bool(msg.get("enabled", False)), critical_confirmed=bool(msg.get("critical_confirmed", False)), user_id=connection.user.id, now=datetime.now(UTC))
        connection.send_result(msg["id"], {})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Beobachtungsmodus ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/policy/evaluate", probatio.Required("request"): dict})
@websocket_api.async_response
async def websocket_policy_evaluate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        decision = await _policy_store(hass).async_decide(msg["request"], now=datetime.now(UTC))
        connection.send_result(msg["id"], {"decision": asdict(decision)})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Policy-Entscheidung ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/template/list"})
@websocket_api.async_response
async def websocket_phase8_template_list(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], {"templates": await _template_store(hass).async_list()})
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/template/save", probatio.Required("template"): dict})
@websocket_api.async_response
async def websocket_phase8_template_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        saved = await _template_store(hass).async_save(msg["template"], user_id=_user_id(connection), now=datetime.now(UTC))
        connection.send_result(msg["id"], {"template": saved})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regelvorlage ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/template/delete", probatio.Required("template_id"): str})
@websocket_api.async_response
async def websocket_phase8_template_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        await _template_store(hass).async_delete(msg["template_id"], user_id=_user_id(connection))
        connection.send_result(msg["id"], {})
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regelvorlage kann nicht gelöscht werden.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/template/export", probatio.Required("template_id"): str})
@websocket_api.async_response
async def websocket_phase8_template_export(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], await _template_store(hass).async_export(msg["template_id"]))
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Regelvorlage wurde nicht gefunden.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/template/import", probatio.Required("payload"): dict, probatio.Required("confirm"): bool})
@websocket_api.async_response
async def websocket_phase8_template_import(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        result = await _template_store(hass).async_import(msg["payload"], user_id=_user_id(connection), now=datetime.now(UTC), confirm=msg["confirm"])
        connection.send_result(msg["id"], result)
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Import ist ungültig oder kollidiert mit einer bestehenden Vorlage.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/simulate", probatio.Required("rule"): dict})
@websocket_api.async_response
async def websocket_phase8_simulate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        policy_reasons = []
        if msg.get("rule_id"):
            policy_reasons = await async_policy_preview(
                _recipient_store(hass).repository,
                rule_id=msg["rule_id"],
                priority=str(msg.get("priority", msg["rule"].get("priority", "normal"))),
                now=datetime.now(UTC),
                alarm_state=str(msg.get("alarm_state", "active")),
                category=msg.get("category"),
                entity_id=msg.get("entity_id"),
            )
        result = simulate_rule(
            msg["rule"],
            states=msg.get("states"),
            numeric_states=msg.get("numeric_states"),
            presence=msg.get("presence"),
            now=datetime.now(UTC),
            policy_reasons=policy_reasons,
        )
        connection.send_result(msg["id"], result)
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Simulationseingaben sind ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase10/observe", probatio.Required("rule"): dict})
@websocket_api.async_response
async def websocket_phase10_observe(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Preview a rule for the Phase-10 observation card without any writes."""
    try:
        now = datetime.now(UTC)
        reasons = []
        if msg.get("rule_id"):
            reasons = await async_policy_preview(
                _recipient_store(hass).repository,
                rule_id=msg["rule_id"], priority=str(msg.get("priority", msg["rule"].get("priority", "normal"))),
                now=now, alarm_state=str(msg.get("alarm_state", "active")),
                category=msg.get("category"), entity_id=msg.get("entity_id"),
            )
        result = simulate_rule(msg["rule"], states=msg.get("states"), numeric_states=msg.get("numeric_states"), presence=msg.get("presence"), now=now, policy_reasons=reasons)
        result.update({"observation_mode": True, "mode": "simulation", "action_guarantee": "Keine produktive Aktion", "delivery_started": False, "writes_performed": []})
        connection.send_result(msg["id"], result)
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Beobachtungsdaten sind ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/versions", probatio.Required("rule_id"): str})
@websocket_api.async_response
async def websocket_phase8_versions(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        versions = await _store(hass).async_list_versions(msg["rule_id"], limit=int(msg.get("limit", 20)))
        connection.send_result(msg["id"], {"versions": versions})
    except (KeyError, TypeError, ValueError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Versionshistorie ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase8/restore", probatio.Required("rule_id"): str, probatio.Required("version"): int, probatio.Required("expected_version"): int})
@websocket_api.async_response
async def websocket_phase8_restore(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        restored = await _store(hass).async_restore(
            msg["rule_id"],
            version=msg["version"],
            access=EditorAccess(_user_id(connection), frozenset({"admin"})),
            now=datetime.now(UTC),
            expected_version=msg["expected_version"],
            available_entities=_available_entity_ids(hass),
            reason=str(msg.get("reason", "")),
            critical_confirmed=bool(msg.get("critical_confirmed", False)),
        )
        connection.send_result(msg["id"], {"rule": rule_to_dict(restored)})
        _notify_rule_update(hass, restored.rule_id)
    except (KeyError, TypeError, ValueError, PermissionError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Wiederherstellung ist ungültig oder nicht bestätigt.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/discover", probatio.Required("automations"): list})
@websocket_api.async_response
async def websocket_phase9_discover(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Analyze supplied automation snapshots; no HA automation is written."""

    try:
        connection.send_result(msg["id"], {"automations": [discover_automation(item) for item in msg["automations"]]})
    except (TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Automationsanalyse ist ungültig.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/preview", probatio.Required("automation"): dict})
@websocket_api.async_response
async def websocket_phase9_preview(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        result = build_hybrid_plan(msg["automation"], external_alarm_reference=msg.get("external_alarm_reference"))
        connection.send_result(msg["id"], result)
    except (TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Migrationsvorschau ist ungültig oder nicht sicher.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/prepare", probatio.Required("automation"): dict})
@websocket_api.async_response
async def websocket_phase9_prepare(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        store = _automation_migration_store(hass)
        plan = await store.async_prepare(
            msg["automation"],
            user_id=_user_id(connection),
            available_entities=_available_entity_ids(hass) or set(),
            recipient_ids=[str(item) for item in msg.get("recipient_ids", [])],
            now=datetime.now(UTC),
        )
        connection.send_result(msg["id"], {"plan": plan, "requires_confirmation": True, "original_unchanged": True})
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Für die Migrationsvorbereitung fehlt die Berechtigung.")
    except (TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Migrationsvorbereitung ist ungültig oder nicht sicher.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/activate", probatio.Required("plan_id"): str, probatio.Required("automation"): dict, probatio.Required("confirm"): bool})
@websocket_api.async_response
async def websocket_phase9_activate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        result = await _automation_migration_store(hass).async_activate(msg["plan_id"], msg["automation"], user_id=_user_id(connection), confirm=msg["confirm"], now=datetime.now(UTC))
        connection.send_result(msg["id"], result)
    except PermissionError:
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Die Aktivierung benötigt eine ausdrückliche Bestätigung.")
    except (TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die Aktivierung wurde wegen eines Konflikts abgelehnt.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/rollback", probatio.Required("plan_id"): str})
@websocket_api.async_response
async def websocket_phase9_rollback(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], await _automation_migration_store(hass).async_rollback(msg["plan_id"], user_id=_user_id(connection), now=datetime.now(UTC)))
    except (PermissionError, TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Der Migrationsplan kann nicht zurückgenommen werden.")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "smart_notification_manager/phase9/reference", probatio.Required("automation_id"): str, probatio.Required("execution_ref"): str, probatio.Required("entity_id"): str, probatio.Required("event"): str})
@websocket_api.async_response
async def websocket_phase9_reference(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    try:
        result = await _automation_migration_store(hass).async_reference_event(
            automation_id=msg["automation_id"], execution_ref=msg["execution_ref"], entity_id=msg["entity_id"],
            rule_id=msg.get("rule_id"), event=msg["event"], now=datetime.now(UTC),
        )
        connection.send_result(msg["id"], {"reference": result, "delivery_started": False})
    except (TypeError, ValueError, KeyError):
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Die externe Alarmreferenz ist ungültig.")
    except (RuntimeError, sqlite3.Error) as err:
        _send_storage_error(connection, msg, err)


def _store(hass: HomeAssistant) -> RuleStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("rule_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _automation_migration_store(hass: HomeAssistant) -> AutomationMigrationStore:
    store = hass.data.get(DOMAIN, {}).get("automation_migration_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager ist nicht konfiguriert")
    return store


def _template_store(hass: HomeAssistant) -> RuleTemplateStore:
    store = hass.data.get(DOMAIN, {}).get("rule_template_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _available_entity_ids(hass: HomeAssistant) -> set[str] | None:
    states = getattr(hass, "states", None)
    if states is None:
        return None
    async_all = getattr(states, "async_all", None)
    if callable(async_all):
        return {state.entity_id for state in async_all()}
    return None


def _delivery_store(hass: HomeAssistant) -> DeliveryStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("delivery_store")
    if store is None:
        store = DeliveryStore(_recipient_store(hass).repository)
    return store


async def _server_policy_request(hass: HomeAssistant, alarm_id: str | None) -> dict[str, Any]:
    if not alarm_id:
        raise ValueError("Regulärer Versand benötigt eine bestehende Alarm-ID")
    row = await _delivery_store(hass).repository.async_run(
        lambda connection: connection.execute(
            "SELECT a.alarm_id,a.rule_id,a.alarm_state,a.entity_id,a.priority,r.enabled,r.category FROM alarm_instances AS a LEFT JOIN rules AS r ON r.rule_id=a.rule_id WHERE a.alarm_id=?",
            (alarm_id,),
        ).fetchone()
    )
    if row is None:
        raise ValueError("Alarm für den Versand nicht gefunden")
    return {
        "alarm_id": row["alarm_id"],
        "rule_id": row["rule_id"],
        "alarm_state": row["alarm_state"],
        "entity_id": row["entity_id"],
        "priority": row["priority"],
        "rule_enabled": bool(row["enabled"]) if row["enabled"] is not None else False,
        "category": row["category"],
    }


def _recipient_store(hass: HomeAssistant) -> RecipientStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("recipient_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _policy_store(hass: HomeAssistant) -> PolicyStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("policy_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _alarm_store(hass: HomeAssistant) -> AlarmLifecycleStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("alarm_store")
    if store is None:
        raise RuntimeError("Smart Notification Manager is not configured")
    return store


def _alarm_center_store(hass: HomeAssistant) -> AlarmCenterStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("alarm_center_store")
    if store is None:
        alarm_store = runtime.get("alarm_store")
        if alarm_store is None:
            raise RuntimeError("Smart Notification Manager is not configured")
        store = AlarmCenterStore(alarm_store.repository)
    return store


def _alarm_center_store_if_loaded(hass: HomeAssistant) -> AlarmCenterStore | None:
    return hass.data.get(DOMAIN, {}).get("alarm_center_store")


def _user_id(connection) -> str:
    user = getattr(connection, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise PermissionError("authentifizierter Home-Assistant-Benutzer erforderlich")
    return str(user_id)


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


def _notify_rule_update(hass: HomeAssistant, rule_id: str) -> None:
    """Notify native entities when running inside a real HA event loop.

    The guard keeps the pure WebSocket contract tests independent from HA's
    dispatcher implementation while production Home Assistant always has the
    event-loop verification method.
    """

    if hasattr(hass, "verify_event_loop_thread"):
        async_dispatcher_send(hass, f"{DOMAIN}_rules_updated", rule_id)


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

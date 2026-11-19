"""Authenticated Home Assistant WebSocket API for the Phase 2 editor."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import asdict
from typing import Any

import probatio
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
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
    for handler in (websocket_recipient_list, websocket_recipient_save, websocket_group_save, websocket_channel_save, websocket_template_save, websocket_routing_preview):
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
        connection.send_result(msg["id"], {"recipients": recipients, "groups": groups, "channels": await store.async_list_channels()})
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


def _send_storage_error(connection, msg: dict[str, Any], err: Exception) -> None:
    """Log diagnostics privately and expose only a stable German error."""

    _LOGGER.error("Smart Notification Manager storage operation failed", exc_info=err)
    connection.send_error(
        msg["id"],
        websocket_api.ERR_UNKNOWN_ERROR,
        "Die Regelverwaltung ist derzeit nicht verfügbar.",
    )

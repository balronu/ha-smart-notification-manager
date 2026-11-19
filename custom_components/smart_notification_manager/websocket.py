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


def _store(hass: HomeAssistant) -> RuleStore:
    runtime = hass.data.get(DOMAIN, {})
    store = runtime.get("rule_store")
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

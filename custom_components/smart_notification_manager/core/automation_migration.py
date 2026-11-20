"""Read-only discovery, preview and planning for existing HA automations.

The module deliberately accepts plain Home Assistant YAML-shaped dictionaries.
It never calls a Home Assistant service and never mutates the supplied object.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .models import new_id
from .repository import SQLiteRepository
from .rules import Priority

KNOWN_NOTIFICATION_PREFIXES = ("notify.", "persistent_notification.", "tts.")
KNOWN_NOTIFICATION_SERVICES = {"notify.send_message", "persistent_notification.create"}
SUPPORTED_TRIGGER_PLATFORMS = {"state", "numeric_state", "event", "time", "template", "zone", "sun", "homeassistant"}
_SECRET_KEYS = {"password", "token", "api_key", "access_token", "secret", "authorization"}


@dataclass(frozen=True, slots=True)
class NotificationAction:
    path: tuple[str, ...]
    service: str
    channel: str
    kind: str
    message: str | None
    dynamic: bool = False


def _service_value(action: dict[str, Any]) -> str | None:
    value = action.get("service", action.get("action"))
    return value if isinstance(value, str) else None


def _notification_kind(service: str) -> tuple[str, str] | None:
    if service.startswith("notify."):
        return "Benachrichtigung", service.removeprefix("notify.") or "notify"
    if service == "persistent_notification.create" or service.startswith("persistent_notification."):
        return "Persistente Benachrichtigung", "persistent_notification"
    if service.startswith("tts."):
        return "TTS", service.removeprefix("tts.") or "tts"
    return None


def _iter_actions(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_actions(item, path + (str(index),))
        return
    if not isinstance(value, dict):
        return
    service = _service_value(value)
    if service is not None:
        yield path, value
    if isinstance(value.get("sequence"), list):
        yield from _iter_actions(value["sequence"], path + ("sequence",))
    if isinstance(value.get("then"), list):
        yield from _iter_actions(value["then"], path + ("then",))
    if isinstance(value.get("else"), list):
        yield from _iter_actions(value["else"], path + ("else",))
    if isinstance(value.get("default"), list):
        yield from _iter_actions(value["default"], path + ("default",))
    choices = value.get("choose")
    if isinstance(choices, list):
        for index, choice in enumerate(choices):
            if isinstance(choice, dict):
                yield from _iter_actions(choice.get("sequence", []), path + (f"choose[{index}]", "sequence"))
    repeat = value.get("repeat")
    if isinstance(repeat, dict):
        yield from _iter_actions(repeat.get("sequence", []), path + ("repeat", "sequence"))
    parallel = value.get("parallel")
    if isinstance(parallel, list):
        yield from _iter_actions(parallel, path + ("parallel",))


def _contains_nested_actions(value: Any) -> bool:
    if isinstance(value, dict):
        if any(key in value for key in ("choose", "if", "repeat", "parallel", "sequence")):
            return True
        return any(_contains_nested_actions(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_nested_actions(item) for item in value)
    return False


def _safe_message(action: dict[str, Any]) -> str | None:
    data = action.get("data", action.get("target", {}))
    if not isinstance(data, dict):
        return None
    message = data.get("message")
    return message if isinstance(message, str) else None


def _stable_json(value: Any) -> str:
    return json.dumps(_redact(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[ausgeblendet]" if key.lower() in _SECRET_KEYS else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(token|password|api[_-]?key|secret)=\S+", r"\1=[ausgeblendet]", value)
    return value


def automation_hash(automation: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(automation).encode()).hexdigest()


def discover_automation(automation: dict[str, Any]) -> dict[str, Any]:
    """Analyze one automation without touching HA or the source object."""

    if not isinstance(automation, dict):
        raise TypeError("Automation muss ein Objekt sein")
    source = copy.deepcopy(automation)
    actions = list(_iter_actions(source.get("action", source.get("actions", []))))
    notifications: list[NotificationAction] = []
    unknown: list[dict[str, Any]] = []
    for path, action in actions:
        service = _service_value(action)
        if not service:
            continue
        kind_channel = _notification_kind(service)
        if kind_channel:
            kind, channel = kind_channel
            notifications.append(NotificationAction(path, service, channel, kind, _safe_message(action), "{{" in service or "}}" in service))
        elif "{{" in service or "}}" in service or service.startswith("notify"):
            unknown.append({"path": list(path), "service": "[dynamisch]"})
    triggers = source.get("trigger", source.get("triggers", []))
    triggers = triggers if isinstance(triggers, list) else [triggers]
    unsupported_triggers = [item.get("platform", "unbekannt") for item in triggers if isinstance(item, dict) and item.get("platform") not in SUPPORTED_TRIGGER_PLATFORMS]
    nested = _contains_nested_actions(source.get("action", source.get("actions", [])))
    risks: list[str] = []
    if unknown:
        risks.append("Dynamische oder unbekannte Dienstaktion kann nicht sicher migriert werden.")
    if nested:
        risks.append("Verschachtelte choose/if/repeat/parallel-Aktionen benötigen eine Hybrid- oder manuelle Prüfung.")
    if unsupported_triggers:
        risks.append(f"Nicht unterstützte Trigger-Plattform: {', '.join(map(str, unsupported_triggers))}.")
    if not notifications:
        classification = "nur_manuell" if unknown else "nicht_unterstützt"
        recommendation = "Dynamische Dienstaktion erkannt; manuelle Prüfung erforderlich." if unknown else "Keine Benachrichtigungsaktion erkannt; manuell prüfen."
    elif unknown or unsupported_triggers:
        classification = "nur_manuell"
        recommendation = "Keine automatische Änderung; vollständige manuelle Übertragung erforderlich."
    elif nested or len(actions) != len(notifications):
        classification = "hybrid_migrierbar"
        recommendation = "Originalautomation behalten und nur ausgewählte Benachrichtigungen ersetzen."
    else:
        classification = "vollständig_migrierbar"
        recommendation = "Native Regel als deaktivierter Beobachtungsmodus-Entwurf vorbereiten."
    security_source = " ".join(str(source.get(key, "")) for key in ("id", "alias", "entity_id", "description")).lower()
    if any(marker in security_source for marker in ("sicherheits", "alarm", "heizung", "tür", "door", "strom", "power")):
        risks.append("Sicherheits-, Heizungs-, Tür-, Alarm- oder Stromautomation: ausdrückliche Freigabe erforderlich.")
        if classification == "vollständig_migrierbar":
            classification = "nur_manuell"
            recommendation = "Nur manuell migrierbar; keine automatische Änderung einer sicherheitsrelevanten Automation."
    automation_id = str(source.get("id") or source.get("unique_id") or source.get("alias") or "unbekannte_automation")
    return {
        "automation_id": automation_id,
        "name": source.get("alias") or automation_id,
        "entity_id": source.get("entity_id") or (f"automation.{automation_id}" if automation_id else None),
        "unique_id": source.get("unique_id"),
        "enabled": bool(source.get("enabled", True)),
        "channels": list(dict.fromkeys(item.channel for item in notifications)),
        "notification_actions": [
            {"path": list(item.path), "service": item.service, "channel": item.channel, "kind": item.kind, "message": item.message, "dynamic": item.dynamic}
            for item in notifications
        ],
        "notification_count": len(notifications),
        "action_positions": [".".join(item.path) or "action" for item in notifications],
        "complexity": "hoch" if nested or len(actions) > 3 else ("mittel" if len(actions) > 1 else "niedrig"),
        "classification": classification,
        "migration_capable": classification in {"vollständig_migrierbar", "hybrid_migrierbar"},
        "risks": risks,
        "recommendation": recommendation,
        "source_hash": automation_hash(source),
        "original": _redact(source),
    }


def _entity_id(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _condition_preview(condition: Any) -> dict[str, Any]:
    if isinstance(condition, list):
        return {"kind": "all", "children": [_condition_preview(item) for item in condition]}
    if not isinstance(condition, dict):
        return {"kind": "all", "children": []}
    platform = condition.get("condition", condition.get("platform", "entity_state"))
    if platform in {"and", "or"}:
        return {"kind": "all" if platform == "and" else "any", "children": [_condition_preview(item) for item in condition.get("conditions", [])]}
    value = dict(condition)
    value.pop("condition", None)
    value.pop("platform", None)
    return {"kind": "entity_state" if platform == "state" else str(platform), "value": value, "children": []}


def build_full_migration_draft(automation: dict[str, Any], *, available_entities: set[str] = frozenset(), recipient_ids: list[str] | None = None) -> dict[str, Any]:
    analysis = discover_automation(automation)
    if analysis["classification"] != "vollständig_migrierbar":
        raise ValueError("Automation ist nicht vollständig migrierbar")
    triggers: list[dict[str, Any]] = []
    for item in automation.get("trigger", automation.get("triggers", [])) if isinstance(automation.get("trigger", automation.get("triggers", [])), list) else [automation.get("trigger")]:
        if not isinstance(item, dict) or item.get("platform") not in {"state", "numeric_state"}:
            raise ValueError("Trigger benötigt manuelle Prüfung")
        if item["platform"] == "state":
            triggers.append({"kind": "state", "entity_ids": _entity_id(item.get("entity_id")), "from_state": item.get("from"), "to_state": item.get("to"), "delay_seconds": 0})
        else:
            triggers.append({"kind": "numeric", "entity_ids": _entity_id(item.get("entity_id")), "comparison": "gte" if item.get("above") is not None else "lte", "threshold": item.get("above", item.get("below")), "delay_seconds": 0})
    entities = {entity for trigger in triggers for entity in trigger["entity_ids"]}
    actions = analysis["notification_actions"]
    rule_id = str(uuid5(NAMESPACE_URL, f"smart-notification-manager:{analysis['automation_id']}"))
    return {
        "rule_id": rule_id,
        "name": f"Migration: {analysis['name']}",
        "description": "Entwurf aus einer bestehenden Home-Assistant-Automation; Ursprung bleibt unverändert.",
        "category": "Migration",
        "priority": Priority.NORMAL.value,
        "enabled": False,
        "observation_mode": True,
        "version": 1,
        "triggers": triggers,
        "conditions": _condition_preview(automation.get("condition", [])),
        "routing": {"recipient_ids": list(recipient_ids or []), "channel_ids": [item["channel"] for item in actions]},
        "message_templates": [item["message"] for item in actions if item.get("message")],
        "required_entities": sorted(entities),
        "missing_entities": sorted(entities - set(available_entities)),
        "source_automation_id": analysis["automation_id"],
        "source_hash": analysis["source_hash"],
        "no_automatic_activation": True,
    }


def build_hybrid_plan(automation: dict[str, Any], *, selected_paths: set[tuple[str, ...]] | None = None, external_alarm_reference: str | None = None) -> dict[str, Any]:
    analysis = discover_automation(automation)
    if analysis["classification"] not in {"hybrid_migrierbar", "vollständig_migrierbar"}:
        raise ValueError("Automation ist nicht sicher hybrid migrierbar")
    selected = selected_paths or {tuple(item["path"]) for item in analysis["notification_actions"]}
    reference = external_alarm_reference or f"automation:{analysis['automation_id']}"
    transformed = copy.deepcopy(automation)

    def replace_in(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                if path + (str(index),) in selected and isinstance(item, dict):
                    value[index] = {"service": "smart_notification_manager.send", "data": {"external_alarm_reference": reference, "source_automation": analysis["automation_id"], "original_service": _service_value(item)}}
                else:
                    replace_in(item, path + (str(index),))
        elif isinstance(value, dict):
            for key in ("sequence", "then", "else", "default", "action"):
                if isinstance(value.get(key), (list, dict)):
                    replace_in(value[key], path + (key,))
            for index, choice in enumerate(value.get("choose", []) if isinstance(value.get("choose"), list) else []):
                if isinstance(choice, dict):
                    replace_in(choice.get("sequence", []), path + (f"choose[{index}]", "sequence"))
            if isinstance(value.get("repeat"), dict):
                replace_in(value["repeat"].get("sequence", []), path + ("repeat", "sequence"))
            if isinstance(value.get("parallel"), list):
                replace_in(value["parallel"], path + ("parallel",))

    replace_in(transformed.get("action", transformed.get("actions", [])), ())
    return {"classification": "hybrid_migrierbar", "external_alarm_reference": reference, "original": _redact(automation), "transformed": _redact(transformed), "selected_paths": [list(path) for path in sorted(selected)], "preserved_features": ["Trigger", "Bedingungen", "Variablen", "Wartezeiten", "choose", "if", "repeat", "sonstige Aktionen"], "non_transferable": ["Originaldienst wird durch den Manager-Aufruf ersetzt"], "no_automatic_activation": True}


class AutomationMigrationStore:
    """Persistence for plans and idempotent external alarm references."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_prepare(self, automation: dict[str, Any], *, user_id: str, available_entities: set[str] = frozenset(), recipient_ids: list[str] | None = None, now: datetime | None = None) -> dict[str, Any]:
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        timestamp = now or datetime.now(UTC)
        analysis = discover_automation(automation)
        draft = build_full_migration_draft(automation, available_entities=available_entities, recipient_ids=recipient_ids) if analysis["classification"] == "vollständig_migrierbar" else (build_hybrid_plan(automation) if analysis["classification"] == "hybrid_migrierbar" else None)
        plan = {"plan_id": new_id(), "automation_id": analysis["automation_id"], "source_hash": analysis["source_hash"], "classification": analysis["classification"], "analysis": analysis, "draft": draft, "original": analysis["original"], "status": "prepared", "observation_mode": True}
        def operation(connection):
            connection.execute("INSERT INTO automation_migration_plans(plan_id,automation_id,source_hash,classification,draft_json,original_json,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (plan["plan_id"], plan["automation_id"], plan["source_hash"], plan["classification"], json.dumps(draft, ensure_ascii=False), json.dumps(analysis["original"], ensure_ascii=False), "prepared", user_id, timestamp.isoformat(), timestamp.isoformat()))
            connection.execute("INSERT INTO automation_migration_audit(audit_id,plan_id,automation_id,action,details_json,occurred_at) VALUES (?,?,?,?,?,?)", (new_id(), plan["plan_id"], plan["automation_id"], "prepared", "{}", timestamp.isoformat()))
        await self.repository.async_run(operation)
        return plan

    async def async_reference_event(self, *, automation_id: str, execution_ref: str, entity_id: str, rule_id: str | None, event: str, now: datetime | None = None) -> dict[str, Any]:
        if event not in {"open", "update", "acknowledge", "resolve"}:
            raise ValueError("unbekanntes externes Alarmereignis")
        timestamp = now or datetime.now(UTC)
        def operation(connection):
            row = connection.execute("SELECT * FROM external_alarm_references WHERE automation_id=? AND execution_ref=?", (automation_id, execution_ref)).fetchone()
            if row is None:
                if event != "open":
                    raise ValueError("Für Entwarnung existiert keine externe Alarmreferenz")
                reference_id, alarm_id, status = new_id(), new_id(), "open"
                connection.execute("INSERT INTO external_alarm_references(reference_id,automation_id,execution_ref,entity_id,rule_id,alarm_id,alarm_status,last_event,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (reference_id, automation_id, execution_ref, entity_id, rule_id, alarm_id, status, event, timestamp.isoformat(), timestamp.isoformat()))
            else:
                reference_id, alarm_id, status = row["reference_id"], row["alarm_id"], row["alarm_status"]
                if row["entity_id"] != entity_id:
                    raise ValueError("Externe Alarmreferenz gehört zu einer anderen Entität")
                if event == "open" and status == "resolved":
                    raise ValueError("geschlossene externe Referenz darf nicht erneut geöffnet werden")
                if event == "resolve":
                    status = "resolved"
                elif event == "acknowledge":
                    if status == "resolved":
                        raise ValueError("aufgelöste externe Referenz kann nicht bestätigt werden")
                    status = "acknowledged"
                elif event == "update" and status == "resolved":
                    raise ValueError("aufgelöste externe Referenz kann nicht aktualisiert werden")
                connection.execute("UPDATE external_alarm_references SET last_event=?,alarm_status=?,updated_at=? WHERE reference_id=?", (event, status, timestamp.isoformat(), reference_id))
            return {"reference_id": reference_id, "automation_id": automation_id, "execution_ref": execution_ref, "entity_id": entity_id, "rule_id": rule_id or (row["rule_id"] if row else None), "alarm_id": alarm_id, "alarm_status": status, "last_event": event}
        return await self.repository.async_run(operation)

    async def async_activate(self, plan_id: str, automation: dict[str, Any], *, user_id: str, confirm: bool, now: datetime | None = None) -> dict[str, Any]:
        """Approve a plan only; writing HA automations is intentionally out of scope."""

        if not user_id or not confirm:
            raise PermissionError("Aktivierung benötigt eine ausdrückliche Bestätigung")
        timestamp = now or datetime.now(UTC)
        current_hash = automation_hash(automation)
        def operation(connection):
            row = connection.execute("SELECT * FROM automation_migration_plans WHERE plan_id=?", (plan_id,)).fetchone()
            if row is None:
                raise ValueError("Migrationsplan nicht gefunden")
            if row["source_hash"] != current_hash:
                raise ValueError("Automation wurde seit der Vorschau geändert")
            connection.execute("UPDATE automation_migration_plans SET status='approved',updated_at=? WHERE plan_id=? AND status='prepared'", (timestamp.isoformat(), plan_id))
            return {"plan_id": plan_id, "status": "approved", "automation_changed": False, "ha_write_performed": False, "requires_isolated_fixture": True}
        return await self.repository.async_run(operation)

    async def async_rollback(self, plan_id: str, *, user_id: str, now: datetime | None = None) -> dict[str, Any]:
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        timestamp = now or datetime.now(UTC)
        def operation(connection):
            updated = connection.execute("UPDATE automation_migration_plans SET status='rolled_back',updated_at=? WHERE plan_id=? AND status IN ('prepared','approved')", (timestamp.isoformat(), plan_id))
            if updated.rowcount != 1:
                raise ValueError("Migrationsplan ist nicht rücknehmbar")
            return {"plan_id": plan_id, "status": "rolled_back", "ha_write_performed": False}
        return await self.repository.async_run(operation)

    async def async_get_reference(self, automation_id: str, execution_ref: str) -> dict[str, Any] | None:
        def operation(connection):
            row = connection.execute("SELECT * FROM external_alarm_references WHERE automation_id=? AND execution_ref=?", (automation_id, execution_ref)).fetchone()
            return dict(row) if row else None
        return await self.repository.async_run(operation)

    async def async_export_plan(self, plan_id: str, *, user_id: str) -> dict[str, Any]:
        """Export a redacted local plan, its audit trail and references."""
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")

        def operation(connection):
            row = connection.execute("SELECT * FROM automation_migration_plans WHERE plan_id=?", (plan_id,)).fetchone()
            if row is None:
                raise ValueError("Migrationsplan nicht gefunden")
            plan = dict(row)
            plan["draft"] = _redact(json.loads(plan.pop("draft_json")))
            plan["original"] = _redact(json.loads(plan.pop("original_json")))
            audit = [dict(item) for item in connection.execute("SELECT action,details_json,occurred_at FROM automation_migration_audit WHERE plan_id=? ORDER BY occurred_at", (plan_id,))]
            for item in audit:
                item["details"] = json.loads(item.pop("details_json"))
            references = [dict(item) for item in connection.execute("SELECT * FROM external_alarm_references WHERE automation_id=?", (plan["automation_id"],))]
            return {"format": "smart_notification_manager.phase11", "version": 1, "plan": plan, "audit": audit, "external_references": references}

        return await self.repository.async_run(operation)

    async def async_import_plan(self, payload: dict[str, Any], *, user_id: str, confirm: bool, now: datetime | None = None) -> dict[str, Any]:
        """Import a plan as a new, unapproved local draft; never write HA state."""
        if not user_id or not confirm:
            raise PermissionError("Import benötigt eine ausdrückliche Bestätigung")
        if payload.get("format") != "smart_notification_manager.phase11" or payload.get("version") != 1:
            raise ValueError("Unbekanntes Migrationsformat")
        source = payload.get("plan")
        if not isinstance(source, dict) or not source.get("automation_id") or not source.get("source_hash"):
            raise ValueError("Migrationsplan ist unvollständig")
        timestamp = now or datetime.now(UTC)
        plan_id = new_id()
        plan = {**source, "plan_id": plan_id, "status": "imported", "created_by": user_id, "created_at": timestamp.isoformat(), "updated_at": timestamp.isoformat()}
        plan["draft"] = _redact(plan.get("draft"))
        plan["original"] = _redact(plan.get("original", {}))

        def operation(connection):
            connection.execute("INSERT INTO automation_migration_plans(plan_id,automation_id,source_hash,classification,draft_json,original_json,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (plan_id, plan["automation_id"], plan["source_hash"], plan.get("classification", "nur_manuell"), json.dumps(plan.get("draft"), ensure_ascii=False), json.dumps(plan.get("original", {}), ensure_ascii=False), "imported", user_id, timestamp.isoformat(), timestamp.isoformat()))
            connection.execute("INSERT INTO automation_migration_audit(audit_id,plan_id,automation_id,action,details_json,occurred_at) VALUES (?,?,?,?,?,?)", (new_id(), plan_id, plan["automation_id"], "imported", json.dumps({"source_plan_id": source.get("plan_id")}, ensure_ascii=False), timestamp.isoformat()))
            return {"plan_id": plan_id, "status": "imported", "requires_confirmation": True, "ha_write_performed": False}

        return await self.repository.async_run(operation)

    async def async_create_backup(self, plan_id: str, *, user_id: str, now: datetime | None = None) -> dict[str, Any]:
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        timestamp = now or datetime.now(UTC)
        exported = await self.async_export_plan(plan_id, user_id=user_id)
        backup_id = new_id()
        plan = exported["plan"]
        await self.repository.async_run(lambda connection: connection.execute("INSERT INTO migration_backups(backup_id,plan_id,source_hash,payload_json,created_by,created_at) VALUES (?,?,?,?,?,?)", (backup_id, plan_id, plan["source_hash"], json.dumps(exported, ensure_ascii=False), user_id, timestamp.isoformat())))
        return {"backup_id": backup_id, "plan_id": plan_id, "source_hash": plan["source_hash"], "created_at": timestamp.isoformat(), "ha_write_performed": False}

    async def async_restore_backup(self, backup_id: str, *, user_id: str, expected_source_hash: str, now: datetime | None = None) -> dict[str, Any]:
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        timestamp = now or datetime.now(UTC)

        def operation(connection):
            backup = connection.execute("SELECT * FROM migration_backups WHERE backup_id=?", (backup_id,)).fetchone()
            if backup is None:
                raise ValueError("Sicherung nicht gefunden")
            if backup["source_hash"] != expected_source_hash:
                raise ValueError("Sicherungskonflikt: Quellversion stimmt nicht überein")
            current = connection.execute("SELECT source_hash FROM automation_migration_plans WHERE plan_id=?", (backup["plan_id"],)).fetchone()
            if current is None or current[0] != expected_source_hash:
                raise ValueError("Migrationsplan wurde zwischenzeitlich geändert")
            payload = json.loads(backup["payload_json"])
            plan = payload["plan"]
            connection.execute("UPDATE automation_migration_plans SET classification=?,draft_json=?,original_json=?,status='prepared',updated_at=? WHERE plan_id=?", (plan["classification"], json.dumps(plan.get("draft"), ensure_ascii=False), json.dumps(plan.get("original", {}), ensure_ascii=False), timestamp.isoformat(), backup["plan_id"]))
            connection.execute("INSERT INTO automation_migration_audit(audit_id,plan_id,automation_id,action,details_json,occurred_at) VALUES (?,?,?,?,?,?)", (new_id(), backup["plan_id"], plan["automation_id"], "backup_restored", json.dumps({"backup_id": backup_id}, ensure_ascii=False), timestamp.isoformat()))
            return {"backup_id": backup_id, "plan_id": backup["plan_id"], "status": "prepared", "ha_write_performed": False}

        return await self.repository.async_run(operation)

    async def async_recovery_snapshot(self, *, user_id: str) -> dict[str, Any]:
        """Read all resumable local plans and external mappings after restart."""
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")

        def operation(connection):
            plans = [dict(row) for row in connection.execute("SELECT plan_id,automation_id,source_hash,classification,status,updated_at FROM automation_migration_plans WHERE status IN ('prepared','approved','imported') ORDER BY updated_at")]
            references = [dict(row) for row in connection.execute("SELECT automation_id,execution_ref,entity_id,rule_id,alarm_id,alarm_status,last_event,updated_at FROM external_alarm_references ORDER BY updated_at")]
            return {"plans": plans, "external_references": references, "ha_write_performed": False}

        return await self.repository.async_run(operation)

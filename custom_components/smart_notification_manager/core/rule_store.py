"""Transactional rule persistence and guarded editor operations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any

from .models import ensure_aware, new_id
from .permissions import Permission, can_access
from .policies import _has_dependency_cycle
from .repository import SQLiteRepository
from .rules import (
    Comparison,
    ConditionNode,
    Priority,
    RuleDefinition,
    TriggerDefinition,
    TriggerKind,
    UnknownPolicy,
    validate_rule,
)


@dataclass(frozen=True, slots=True)
class EditorAccess:
    """Authenticated server-side context required for write operations."""

    user_id: str | None
    granted: frozenset[str]


class RuleStore:
    """Persist rules as versioned definitions while retaining alarm history."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_list(self, *, include_disabled: bool = True) -> list[RuleDefinition]:
        def operation(connection):
            query = """
                SELECT rv.definition_json
                FROM rule_versions AS rv
                JOIN rules AS r ON r.rule_id = rv.rule_id
                WHERE rv.version = (SELECT MAX(version) FROM rule_versions WHERE rule_id = rv.rule_id)
                  AND r.deleted_at IS NULL
            """
            parameters: tuple[Any, ...] = ()
            if not include_disabled:
                query += " AND r.enabled = 1"
            query += " ORDER BY r.name COLLATE NOCASE"
            return [_rule_from_dict(json.loads(row[0])) for row in connection.execute(query, parameters)]

        return await self.repository.async_run(operation)

    async def async_get(self, rule_id: str, *, version: int | None = None) -> RuleDefinition | None:
        def operation(connection):
            version_clause = "" if version is None else " AND rv.version = ?"
            parameters: tuple[Any, ...] = (rule_id,) if version is None else (rule_id, version)
            row = connection.execute(
                f"""
                SELECT rv.definition_json
                FROM rule_versions AS rv JOIN rules AS r ON r.rule_id = rv.rule_id
                WHERE rv.rule_id = ? AND r.deleted_at IS NULL
                  {version_clause}
                ORDER BY rv.version DESC LIMIT 1
                """,
                parameters,
            ).fetchone()
            return _rule_from_dict(json.loads(row[0])) if row else None

        return await self.repository.async_run(operation)

    async def async_save(self, rule: RuleDefinition, access: EditorAccess) -> RuleDefinition:
        _require(access, Permission.EDIT)
        validate_rule(rule)
        payload = json.dumps(_rule_to_dict(rule), ensure_ascii=False, sort_keys=True)

        def operation(connection):
            now = rule.updated_at.isoformat()
            current = connection.execute(
                "SELECT MAX(version) FROM rule_versions WHERE rule_id = ?",
                (rule.rule_id,),
            ).fetchone()[0]
            expected_version = 1 if current is None else int(current) + 1
            if rule.version != expected_version:
                raise ValueError(
                    f"rule version conflict: expected {expected_version}, received {rule.version}"
                )
            connection.execute(
                """
                INSERT INTO rules(rule_id, name, category, enabled, created_at, updated_at,
                                  description, area_id, area_name, priority, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(rule_id) DO UPDATE SET name=excluded.name,
                    category=excluded.category, enabled=excluded.enabled,
                    updated_at=excluded.updated_at, description=excluded.description,
                    area_id=excluded.area_id, area_name=excluded.area_name,
                    priority=excluded.priority, deleted_at=NULL
                """,
                (
                    rule.rule_id,
                    rule.name,
                    rule.category,
                    int(rule.enabled),
                    rule.created_at.isoformat(),
                    now,
                    rule.description,
                    rule.area_id,
                    rule.area_name,
                    rule.priority.value,
                ),
            )
            connection.execute(
                "INSERT INTO rule_versions(rule_version_id, rule_id, version, definition_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (new_id(), rule.rule_id, rule.version, payload, now),
            )
            return rule

        return await self.repository.async_run(operation)

    async def async_delete(self, rule_id: str, *, now: datetime, access: EditorAccess) -> bool:
        _require(access, Permission.EDIT)
        ensure_aware(now)

        def operation(connection):
            cursor = connection.execute(
                "UPDATE rules SET enabled = 0, deleted_at = ?, updated_at = ? WHERE rule_id = ? AND deleted_at IS NULL",
                (now.isoformat(), now.isoformat(), rule_id),
            )
            return cursor.rowcount == 1

        deleted = await self.repository.async_run(operation)
        if not deleted:
            raise ValueError("rule not found or already deleted")
        return True

    async def async_duplicate(self, rule: RuleDefinition, *, now: datetime, access: EditorAccess) -> RuleDefinition:
        _require(access, Permission.EDIT)
        duplicate = RuleDefinition(
            rule_id=new_id(),
            name=f"{rule.name} (Kopie)",
            description=rule.description,
            area_id=rule.area_id,
            area_name=rule.area_name,
            category=rule.category,
            priority=rule.priority,
            enabled=False,
            triggers=rule.triggers,
            conditions=rule.conditions,
            version=1,
            created_at=now,
            updated_at=now,
            routing=rule.routing,
        )
        return await self.async_save(duplicate, access)

    async def async_list_versions(self, rule_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return the newest bounded version history without mutating it."""

        bounded = min(100, max(1, int(limit)))
        return await self.repository.async_run(lambda c: [
            {"version": row[0], "definition": json.loads(row[1]), "created_at": row[2]}
            for row in c.execute(
                "SELECT version,definition_json,created_at FROM rule_versions WHERE rule_id=? ORDER BY version DESC LIMIT ?",
                (rule_id, bounded),
            )
        ])

    async def async_restore(self, rule_id: str, version: int, access: EditorAccess, *, now: datetime, expected_version: int | None = None, available_entities: set[str] | None = None, reason: str = "", critical_confirmed: bool = False) -> RuleDefinition:
        """Restore a historical version as a new optimistic version."""

        _require(access, Permission.ADMIN)
        ensure_aware(now)

        def operation(connection):
            current = connection.execute("SELECT MAX(version) FROM rule_versions WHERE rule_id=?", (rule_id,)).fetchone()[0]
            if expected_version is not None and int(current or 0) != expected_version:
                raise ValueError(f"rule version conflict: expected {expected_version}, received {current or 0}")
            source = connection.execute("SELECT definition_json FROM rule_versions WHERE rule_id=? AND version=?", (rule_id, version)).fetchone()
            if source is None:
                raise ValueError("historische Regelversion nicht gefunden")
            restored = _rule_from_dict(json.loads(source[0]))
            if restored.priority is Priority.CRITICAL and not critical_confirmed:
                raise PermissionError("Wiederherstellung einer Critical-Regel benötigt eine Bestätigung")
            if available_entities is not None:
                referenced = {entity_id for trigger in restored.triggers for entity_id in trigger.entity_ids}
                referenced.update(child.value["entity_id"] for child in _condition_nodes(restored.conditions) if isinstance(child.value, dict) and child.value.get("entity_id"))
                missing = referenced - available_entities
                if missing:
                    raise ValueError("Wiederherstellung benötigt nicht verfügbare Entitäten")
            if _has_dependency_cycle(connection, rule_id):
                raise ValueError("Zirkuläre Regelabhängigkeit ist nicht zulässig")
            next_version = int(current or 0) + 1
            restored = replace(restored, version=next_version, updated_at=now)
            validate_rule(restored)
            payload = json.dumps(_rule_to_dict(restored), ensure_ascii=False, sort_keys=True)
            connection.execute("UPDATE rules SET name=?,category=?,enabled=?,updated_at=?,description=?,area_id=?,area_name=?,priority=?,deleted_at=NULL WHERE rule_id=?", (restored.name, restored.category, int(restored.enabled), now.isoformat(), restored.description, restored.area_id, restored.area_name, restored.priority.value, rule_id))
            connection.execute("INSERT INTO rule_versions(rule_version_id,rule_id,version,definition_json,created_at) VALUES (?,?,?,?,?)", (new_id(), rule_id, next_version, payload, now.isoformat()))
            connection.execute("INSERT INTO audit_log(audit_id,user_id,action,object_type,object_id,details_json,occurred_at) VALUES (?,?,?,?,?,?,?)", (new_id(), access.user_id, "rule_restored", "rule", rule_id, json.dumps({"from_version": version, "reason": reason}, ensure_ascii=False), now.isoformat()))
            return restored

        return await self.repository.async_run(operation)


def _require(access: EditorAccess, permission: Permission) -> None:
    if not access.user_id or not can_access(set(access.granted), permission):
        raise PermissionError("authenticated editor permission required")


def _condition_nodes(node):
    yield node
    for child in node.children:
        yield from _condition_nodes(child)


def _rule_to_dict(rule: RuleDefinition) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "area_id": rule.area_id,
        "area_name": rule.area_name,
        "category": rule.category,
        "priority": rule.priority.value,
        "enabled": rule.enabled,
        "triggers": [_trigger_to_dict(trigger) for trigger in rule.triggers],
        "conditions": _condition_to_dict(rule.conditions),
        "version": rule.version,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
        "routing": rule.routing,
    }


def rule_to_dict(rule: RuleDefinition) -> dict[str, Any]:
    """Return the stable JSON contract used by the HA WebSocket API."""

    return _rule_to_dict(rule)


def rule_from_editor_payload(value: dict[str, Any], *, now: datetime | None = None) -> RuleDefinition:
    """Normalize a frontend payload before validation and optimistic save."""

    timestamp = now or datetime.now(UTC)
    rule_id = value.get("rule_id") or new_id()
    created_at = datetime.fromisoformat(value["created_at"]) if value.get("created_at") else timestamp
    return _rule_from_dict(
        {
            **value,
            "rule_id": rule_id,
            "version": int(value.get("version", 1)),
            "created_at": created_at.isoformat(),
            "updated_at": (datetime.fromisoformat(value["updated_at"]) if value.get("updated_at") else timestamp).isoformat(),
            "description": value.get("description", ""),
            "category": value.get("category") or "Sonstiges",
            "priority": value.get("priority", Priority.NORMAL.value),
            "enabled": bool(value.get("enabled", True)),
            "triggers": value.get("triggers", []),
            "conditions": value.get("conditions", {"kind": "all", "children": []}),
        }
    )


def _trigger_to_dict(trigger: TriggerDefinition) -> dict[str, Any]:
    value = asdict(trigger)
    value["kind"] = trigger.kind.value
    value["entity_ids"] = list(trigger.entity_ids)
    value["comparison"] = trigger.comparison.value if trigger.comparison else None
    value["unknown_policy"] = trigger.unknown_policy.value
    value["unavailable_policy"] = trigger.unavailable_policy.value
    return value


def _condition_to_dict(node: ConditionNode) -> dict[str, Any]:
    return {"kind": node.kind, "value": node.value, "children": [_condition_to_dict(child) for child in node.children]}


def _rule_from_dict(value: dict[str, Any]) -> RuleDefinition:
    return RuleDefinition(
        rule_id=value["rule_id"],
        name=value["name"],
        description=value.get("description", ""),
        area_id=value.get("area_id"),
        area_name=value.get("area_name"),
        category=value["category"],
        priority=Priority(value.get("priority", Priority.NORMAL)),
        enabled=bool(value["enabled"]),
        triggers=tuple(
            TriggerDefinition(
                kind=TriggerKind(item["kind"]),
                entity_ids=tuple(item["entity_ids"]),
                from_state=item.get("from_state"),
                to_state=item.get("to_state"),
                comparison=Comparison(item["comparison"]) if item.get("comparison") else None,
                threshold=item.get("threshold"),
                upper_threshold=item.get("upper_threshold"),
                hysteresis=item.get("hysteresis"),
                minimum_duration_seconds=int(item.get("minimum_duration_seconds", 0)),
                delay_seconds=int(item.get("delay_seconds", 0)),
                unknown_policy=UnknownPolicy(item.get("unknown_policy", UnknownPolicy.IGNORE)),
                unavailable_policy=UnknownPolicy(item.get("unavailable_policy", UnknownPolicy.IGNORE)),
            )
            for item in value["triggers"]
        ),
        conditions=_condition_from_dict(value["conditions"]),
        version=int(value["version"]),
        created_at=datetime.fromisoformat(value["created_at"]),
        updated_at=datetime.fromisoformat(value["updated_at"]),
        routing=dict(value.get("routing", {})),
    )


def _condition_from_dict(value: dict[str, Any]) -> ConditionNode:
    return ConditionNode(
        kind=value["kind"],
        value=value.get("value"),
        children=tuple(_condition_from_dict(child) for child in value.get("children", [])),
    )

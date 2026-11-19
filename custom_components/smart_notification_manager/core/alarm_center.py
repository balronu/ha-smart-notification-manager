"""Phase-6 alarm-center queries and user-scoped persistence.

This module is deliberately a query/authorization boundary around the existing
alarm lifecycle tables. It does not create a second alarm store or alter alarm
identifiers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .alarm_lifecycle import _record, alarm_to_dict
from .models import new_id
from .repository import SQLiteRepository

ROLES = {"admin", "acknowledger", "read_only"}
SORTS = {
    "newest": "started_at DESC, alarm_id DESC",
    "oldest": "started_at ASC, alarm_id ASC",
    "priority": "CASE priority WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, started_at DESC",
    "duration": "started_at ASC",
    "area": "COALESCE(area_name, area_id, ''), started_at DESC",
    "category": "category, started_at DESC",
}


@dataclass(frozen=True, slots=True)
class AlarmCategory:
    category_id: str
    name: str
    enabled: bool
    created_by: str
    created_at: str
    updated_by: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SavedAlarmFilter:
    filter_id: str
    user_id: str
    name: str
    definition: dict[str, Any]
    is_default: bool
    created_at: str
    updated_at: str


class AlarmCenterStore:
    """Server-side filters, categories, timelines and roles."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_role(self, user_id: str, *, is_admin: bool = False) -> str:
        if is_admin:
            return "admin"
        return await self.repository.async_run(
            lambda c: (c.execute("SELECT role FROM alarm_user_roles WHERE user_id=?", (user_id,)).fetchone() or ["read_only"])[0]
        )

    async def async_save_role(self, user_id: str, role: str, *, updated_by: str, now: datetime) -> str:
        if not user_id or role not in {"acknowledger", "read_only"}:
            raise ValueError("ungültige Alarmrolle")
        stamp = now.isoformat()
        await self.repository.async_run(lambda c: c.execute(
            "INSERT INTO alarm_user_roles(user_id,role,updated_by,updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
            (user_id, role, updated_by, stamp),
        ))
        return role

    async def async_list_categories(self, *, include_disabled: bool = False) -> list[dict[str, Any]]:
        def operation(c):
            query = "SELECT category_id,name,enabled,created_by,created_at,updated_by,updated_at FROM alarm_categories"
            if not include_disabled:
                query += " WHERE enabled=1"
            query += " ORDER BY name COLLATE NOCASE"
            return [dict(row) for row in c.execute(query)]
        return await self.repository.async_run(operation)

    async def async_save_category(self, value: dict[str, Any], *, user_id: str, now: datetime) -> dict[str, Any]:
        name = str(value.get("name", "")).strip()
        category_id = str(value.get("category_id") or new_id())
        if not name or len(name) > 100:
            raise ValueError("Kategorie benötigt einen gültigen Namen")
        stamp = now.isoformat()
        def operation(c):
            old = c.execute("SELECT created_by,created_at FROM alarm_categories WHERE category_id=?", (category_id,)).fetchone()
            c.execute("INSERT INTO alarm_categories(category_id,name,enabled,created_by,created_at,updated_by,updated_at) VALUES (?,?,?,?,?,?,?) "
                      "ON CONFLICT(category_id) DO UPDATE SET name=excluded.name,enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                      (category_id, name, int(value.get("enabled", True)), old[0] if old else user_id, old[1] if old else stamp, user_id, stamp))
            c.execute("INSERT INTO audit_log(audit_id,user_id,action,object_type,object_id,details_json,occurred_at) VALUES (?,?,?,?,?,?,?)",
                      (new_id(), user_id, "category_saved", "alarm_category", category_id, json.dumps({"name": name}, ensure_ascii=False), stamp))
            return dict(c.execute("SELECT category_id,name,enabled,created_by,created_at,updated_by,updated_at FROM alarm_categories WHERE category_id=?", (category_id,)).fetchone())
        return await self.repository.async_run(operation)

    async def async_deactivate_category(self, category_id: str, *, user_id: str, now: datetime) -> None:
        if not category_id:
            raise ValueError("category_id fehlt")
        await self.repository.async_run(lambda c: c.execute("UPDATE alarm_categories SET enabled=0,updated_by=?,updated_at=? WHERE category_id=?", (user_id, now.isoformat(), category_id)))

    async def async_list_filters(self, user_id: str) -> list[dict[str, Any]]:
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        return await self.repository.async_run(lambda c: [self._filter_dict(row) for row in c.execute("SELECT * FROM saved_alarm_filters WHERE user_id=? ORDER BY is_default DESC,name COLLATE NOCASE", (user_id,))])

    async def async_save_filter(self, value: dict[str, Any], *, user_id: str, now: datetime) -> dict[str, Any]:
        name = str(value.get("name", "")).strip()
        if not name or not isinstance(value.get("definition", {}), dict):
            raise ValueError("Filtername und Filterdefinition sind erforderlich")
        filter_id = str(value.get("filter_id") or new_id()); stamp = now.isoformat()
        def operation(c):
            existing = c.execute("SELECT user_id,created_at FROM saved_alarm_filters WHERE filter_id=?", (filter_id,)).fetchone()
            if existing is not None and existing["user_id"] != user_id:
                raise PermissionError("Die persönliche Filteransicht gehört einem anderen Benutzer.")
            old = existing
            if bool(value.get("is_default")):
                c.execute("UPDATE saved_alarm_filters SET is_default=0 WHERE user_id=?", (user_id,))
            c.execute("INSERT INTO saved_alarm_filters(filter_id,user_id,name,definition_json,is_default,created_at,updated_at) VALUES (?,?,?,?,?,?,?) "
                      "ON CONFLICT(filter_id) DO UPDATE SET name=excluded.name,definition_json=excluded.definition_json,is_default=excluded.is_default,updated_at=excluded.updated_at",
                      (filter_id, user_id, name, json.dumps(value["definition"], ensure_ascii=False), int(bool(value.get("is_default"))), old["created_at"] if old else stamp, stamp))
            return self._filter_dict(c.execute("SELECT * FROM saved_alarm_filters WHERE filter_id=? AND user_id=?", (filter_id, user_id)).fetchone())
        return await self.repository.async_run(operation)

    async def async_delete_filter(self, filter_id: str, *, user_id: str) -> None:
        await self.repository.async_run(lambda c: c.execute("DELETE FROM saved_alarm_filters WHERE filter_id=? AND user_id=?", (filter_id, user_id)))

    async def async_list_alarms(self, *, user_id: str, role: str, filters: dict[str, Any] | None = None, page: int = 1, page_size: int = 25, sort: str = "newest", group_by: str | None = None) -> dict[str, Any]:
        if role not in ROLES or not user_id:
            raise PermissionError("keine Berechtigung für die Alarmübersicht")
        filters = filters or {}; page = max(1, int(page)); page_size = min(100, max(1, int(page_size)))
        def operation(c):
            query = "SELECT * FROM alarm_instances WHERE 1=1"; args: list[Any] = []
            for key, column in (("states", "alarm_state"), ("priorities", "priority")):
                values = filters.get(key) or []
                if values:
                    query += " AND " + column + " IN (" + ",".join("?" for _ in values) + ")"; args.extend(values)
            for key, column in (("category_id", "category_id"), ("area_id", "area_id"), ("rule_id", "rule_id"), ("entity_id", "entity_id"), ("acknowledgement_state", "acknowledgement_state"), ("delivery_state", "delivery_state"), ("escalation_state", "escalation_state")):
                if filters.get(key): query += f" AND {column}=?"; args.append(filters[key])
            if filters.get("category"): query += " AND category=?"; args.append(filters["category"])
            if filters.get("search"):
                term = f"%{str(filters['search']).lower()}%"; query += " AND lower(alarm_id||' '||rule_id||' '||entity_id||' '||friendly_name||' '||coalesce(area_name,'')||' '||category) LIKE ?"; args.append(term)
            if filters.get("open_only"): query += " AND alarm_state IN ('pending','active','overdue')"
            if filters.get("critical_only"): query += " AND priority='critical'"
            if filters.get("date_from"): query += " AND started_at>=?"; args.append(filters["date_from"])
            if filters.get("date_to"): query += " AND started_at<=?"; args.append(filters["date_to"])
            if role != "admin" or filters.get("own_only"):
                query += " AND EXISTS (SELECT 1 FROM json_each(alarm_instances.required_recipient_ids_json) WHERE json_each.value=?)"
                args.append(user_id)
            rows = c.execute(query + " ORDER BY " + SORTS.get(sort, SORTS["newest"]), args).fetchall()
            total = len(rows); start = (page - 1) * page_size; selected = rows[start:start + page_size]
            alarms = [alarm_to_dict(_record(row)) for row in selected]
            for item in alarms:
                item["status_de"] = {"pending":"Ausstehend","active":"Aktiv","overdue":"Überfällig","resolved":"Entwarnt","suppressed":"Unterdrückt","manually_closed":"Manuell erledigt"}.get(item["alarm_state"], "Unbekannt")
                item["acknowledgement_de"] = {"unacknowledged":"Nicht quittiert","partially_acknowledged":"Teilweise quittiert","acknowledged":"Vollständig quittiert"}.get(item["acknowledgement_state"], "Unbekannt")
            groups: dict[str, int] = {}
            if group_by in {"area", "category", "priority", "rule"}:
                key_map = {"area": "area_name", "category": "category", "priority": "priority", "rule": "rule_id"}
                for item in alarms: groups[str(item.get(key_map[group_by]) or "Unbekannt")] = groups.get(str(item.get(key_map[group_by]) or "Unbekannt"), 0) + 1
            return {"alarms": alarms, "total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size, "group_by": group_by, "groups": groups}
        return await self.repository.async_run(operation)

    async def async_detail(self, alarm_id: str, *, user_id: str, role: str) -> dict[str, Any]:
        result = await self.async_list_alarms(user_id=user_id, role=role, filters={"search": alarm_id}, page_size=1)
        if not result["alarms"] or result["alarms"][0]["alarm_id"] != alarm_id:
            raise PermissionError("Alarm nicht gefunden oder nicht zugänglich")
        def operation(c):
            events = [{"event_id": r[0], "event_type": r[1], "payload": json.loads(r[2]), "occurred_at": r[3]} for r in c.execute("SELECT event_id,event_type,payload_json,occurred_at FROM alarm_events WHERE alarm_id=? ORDER BY occurred_at,event_id", (alarm_id,))]
            deliveries = [dict(r) for r in c.execute("SELECT attempt_id,recipient_id,channel_id,state,attempt_number,attempted_at,error_code,error_message FROM delivery_attempts WHERE alarm_id=? ORDER BY attempted_at", (alarm_id,))]
            return {"alarm": result["alarms"][0], "events": events, "deliveries": deliveries}
        return await self.repository.async_run(operation)

    @staticmethod
    def _filter_dict(row) -> dict[str, Any]:
        return {"filter_id": row["filter_id"], "user_id": row["user_id"], "name": row["name"], "definition": json.loads(row["definition_json"]), "is_default": bool(row["is_default"]), "created_at": row["created_at"], "updated_at": row["updated_at"]}

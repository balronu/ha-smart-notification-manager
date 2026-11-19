"""Persistent Phase-4 alarm lifecycle with independent acknowledgement state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from .models import AlarmState, ensure_aware, new_id
from .repository import SQLiteRepository

ACTIVE_STATES = (AlarmState.PENDING.value, AlarmState.ACTIVE.value, AlarmState.OVERDUE.value)
RESOLVABLE_STATES = (AlarmState.ACTIVE.value, AlarmState.OVERDUE.value)


@dataclass(frozen=True, slots=True)
class AlarmPolicy:
    delay_seconds: int = 0
    repeat_interval_seconds: int = 0
    max_repeats: int = 0
    repeat_only_active: bool = True
    repeat_only_unacknowledged: bool = False
    max_duration_seconds: int = 0
    escalation_stages: tuple[dict[str, Any], ...] = ()
    acknowledgement_mode: str = "any"
    required_recipient_ids: tuple[str, ...] = ()
    category: str = "Sonstiges"
    category_id: str | None = None

    def validate(self) -> None:
        for name in ("delay_seconds", "repeat_interval_seconds", "max_repeats", "max_duration_seconds"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if any(not isinstance(stage, dict) for stage in self.escalation_stages):
            raise ValueError("escalation stages must be objects")
        if self.acknowledgement_mode not in {"any", "all_required"}:
            raise ValueError("acknowledgement_mode must be any or all_required")
        if self.acknowledgement_mode == "all_required" and not self.required_recipient_ids:
            raise ValueError("all_required acknowledgement needs recipients")


@dataclass(frozen=True, slots=True)
class AlarmRecord:
    alarm_id: str
    rule_id: str
    cause_key: str
    entity_id: str
    friendly_name: str
    area_id: str | None
    area_name: str | None
    priority: str
    alarm_state: str
    acknowledgement_state: str
    delivery_state: str
    escalation_state: str
    previous_state: str | None
    current_state: str | None
    started_at: datetime
    updated_at: datetime
    pending_until: datetime | None
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    acknowledgement_scope: str
    critical_confirmed: bool
    escalation_level: int
    overdue_at: datetime | None
    closed_at: datetime | None
    closed_by: str | None
    closure_reason: str | None
    repeat_interval_seconds: int
    max_repeats: int
    repeat_count: int
    next_repeat_at: datetime | None
    max_duration_seconds: int
    escalation_stages: tuple[dict[str, Any], ...]
    parent_alarm_id: str | None = None
    rule_version: int | None = None
    acknowledgement_mode: str = "any"
    required_recipient_ids: tuple[str, ...] = ()
    category: str = "Sonstiges"
    category_id: str | None = None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _record(row) -> AlarmRecord:
    return AlarmRecord(
        alarm_id=row["alarm_id"], rule_id=row["rule_id"], cause_key=row["cause_key"], entity_id=row["entity_id"],
        friendly_name=row["friendly_name"], area_id=row["area_id"], area_name=row["area_name"], priority=row["priority"],
        alarm_state=row["alarm_state"], acknowledgement_state=row["acknowledgement_state"], delivery_state=row["delivery_state"],
        escalation_state=row["escalation_state"], previous_state=row["previous_state"], current_state=row["current_state"],
        started_at=_dt(row["started_at"]), updated_at=_dt(row["updated_at"] or row["started_at"]), pending_until=_dt(row["pending_until"]),
        acknowledged_by=row["acknowledged_by"], acknowledged_at=_dt(row["acknowledged_at"]), acknowledgement_scope=row["acknowledgement_scope"],
        critical_confirmed=bool(row["critical_confirmed"]), escalation_level=int(row["escalation_level"]), overdue_at=_dt(row["overdue_at"]),
        closed_at=_dt(row["closed_at"]), closed_by=row["closed_by"], closure_reason=row["closure_reason"],
        repeat_interval_seconds=int(row["repeat_interval_seconds"]), max_repeats=int(row["max_repeats"]), repeat_count=int(row["repeat_count"]),
        next_repeat_at=_dt(row["next_repeat_at"]), max_duration_seconds=int(row["max_duration_seconds"]),
        escalation_stages=tuple(json.loads(row["escalation_json"] or "[]")), parent_alarm_id=row["parent_alarm_id"],
        rule_version=row["rule_version"], acknowledgement_mode=row["acknowledgement_mode"],
        required_recipient_ids=tuple(json.loads(row["required_recipient_ids_json"] or "[]")),
        category=row["category"] if "category" in row.keys() else "Sonstiges",  # noqa: SIM118
        category_id=row["category_id"] if "category_id" in row.keys() else None,  # noqa: SIM118
    )


def _acknowledgement_complete(connection, row, *, pending_user_id: str | None = None) -> bool:
    """Return whether the persisted acknowledgement policy is satisfied."""

    if row["acknowledgement_mode"] != "all_required":
        return pending_user_id is not None or row["acknowledgement_state"] == "acknowledged"
    required = set(json.loads(row["required_recipient_ids_json"] or "[]"))
    if pending_user_id:
        acknowledged = {
            item[0]
            for item in connection.execute(
                "SELECT DISTINCT user_id FROM acknowledgements WHERE alarm_id=?",
                (row["alarm_id"],),
            )
        }
        acknowledged.add(pending_user_id)
    else:
        acknowledged = {
            item[0]
            for item in connection.execute(
                "SELECT DISTINCT user_id FROM acknowledgements WHERE alarm_id=?",
                (row["alarm_id"],),
            )
        }
    return required.issubset(acknowledged)


class AlarmLifecycleStore:
    """Atomic persistence boundary for alarm state, events and acknowledgements."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_trigger(self, *, rule_id: str, entity_id: str, friendly_name: str = "", area_id: str | None = None,
                            area_name: str | None = None, priority: str = "normal", previous_state: str | None = None,
                            current_state: str | None = None, now: datetime, policy: AlarmPolicy | None = None,
                            parent_alarm_id: str | None = None, rule_version: int | None = None,
                            category: str = "Sonstiges", category_id: str | None = None) -> tuple[AlarmRecord, bool]:
        ensure_aware(now); policy = policy or AlarmPolicy(); policy.validate()
        if not entity_id or not rule_id: raise ValueError("rule_id and entity_id are required")
        pending_until = now + timedelta(seconds=policy.delay_seconds) if policy.delay_seconds else None
        state = AlarmState.PENDING.value if pending_until else AlarmState.ACTIVE.value
        next_repeat = now + timedelta(seconds=policy.repeat_interval_seconds) if policy.repeat_interval_seconds and policy.max_repeats > 0 else None

        def operation(connection):
            existing = connection.execute("SELECT * FROM alarm_instances WHERE rule_id=? AND cause_key=? AND alarm_state IN ('pending','active','overdue')", (rule_id, entity_id)).fetchone()
            if existing: return _record(existing), False
            alarm_id = new_id(); stamp = now.isoformat()
            connection.execute("""INSERT INTO alarm_instances(alarm_id,rule_id,rule_version,cause_key,alarm_state,acknowledgement_state,acknowledgement_mode,required_recipient_ids_json,delivery_state,escalation_state,started_at,entity_id,friendly_name,area_id,area_name,priority,previous_state,current_state,pending_until,updated_at,repeat_interval_seconds,max_repeats,next_repeat_at,repeat_only_unacknowledged,max_duration_seconds,escalation_json,parent_alarm_id,category,category_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (alarm_id,rule_id,rule_version,entity_id,state,"unacknowledged",policy.acknowledgement_mode,json.dumps(sorted(set(policy.required_recipient_ids))),"pending","running" if policy.escalation_stages else "idle",stamp,entity_id,friendly_name,area_id,area_name,priority,previous_state,current_state,_iso(pending_until),stamp,policy.repeat_interval_seconds,policy.max_repeats,_iso(next_repeat),int(policy.repeat_only_unacknowledged),policy.max_duration_seconds,json.dumps(policy.escalation_stages, ensure_ascii=False),parent_alarm_id,category.strip() or "Sonstiges",category_id))
            self._event(connection, alarm_id, "triggered", {"entity_id": entity_id, "state": state}, now)
            return _record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()), True
        return await self.repository.async_run(operation)

    async def async_get(self, alarm_id: str) -> AlarmRecord | None:
        def operation(connection):
            row = connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()
            return _record(row) if row else None
        return await self.repository.async_run(operation)

    async def async_list(self, *, states: tuple[str, ...] | None = None) -> list[AlarmRecord]:
        def operation(connection):
            query = "SELECT * FROM alarm_instances"; args: tuple[Any, ...] = ()
            if states:
                query += " WHERE alarm_state IN (" + ",".join("?" for _ in states) + ")"; args = states
            query += " ORDER BY started_at DESC"
            return [_record(row) for row in connection.execute(query, args)]
        return await self.repository.async_run(operation)

    async def async_events(self, alarm_id: str) -> list[dict[str, Any]]:
        return await self.repository.async_run(lambda c: [{"event_id": r[0], "alarm_id": r[1], "event_type": r[2], "payload": json.loads(r[3]), "occurred_at": r[4]} for r in c.execute("SELECT event_id,alarm_id,event_type,payload_json,occurred_at FROM alarm_events WHERE alarm_id=? ORDER BY occurred_at,event_id", (alarm_id,))])

    async def async_activate_pending(self, *, now: datetime, validations: dict[str, bool] | None = None) -> list[AlarmRecord]:
        ensure_aware(now)
        def operation(connection):
            rows = connection.execute("SELECT * FROM alarm_instances WHERE alarm_state='pending' AND pending_until IS NOT NULL AND pending_until<=?", (now.isoformat(),)).fetchall(); result=[]
            for row in rows:
                if validations is not None and not validations.get(row["alarm_id"], False):
                    connection.execute("UPDATE alarm_instances SET alarm_state='suppressed',closure_reason=?,closed_at=?,updated_at=?,next_repeat_at=NULL,escalation_state='complete' WHERE alarm_id=?", ("Auslöser bei erneuter Prüfung nicht mehr gültig.", now.isoformat(), now.isoformat(), row["alarm_id"]))
                    self._event(connection, row["alarm_id"], "suppressed", {"reason": "pending_revalidation_failed"}, now)
                    continue
                connection.execute("UPDATE alarm_instances SET alarm_state='active',pending_until=NULL,updated_at=? WHERE alarm_id=?", (now.isoformat(),row["alarm_id"])); self._event(connection,row["alarm_id"],"activated",{},now); result.append(_record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?",(row["alarm_id"],)).fetchone()))
            return result
        return await self.repository.async_run(operation)

    async def async_suppress(self, alarm_id: str, *, now: datetime, reason: str = "suppressed") -> AlarmRecord:
        ensure_aware(now)
        def operation(connection):
            row = connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()
            if not row: raise ValueError("alarm not found")
            if row["alarm_state"] != AlarmState.PENDING.value: raise ValueError("only pending alarms can be suppressed")
            connection.execute("UPDATE alarm_instances SET alarm_state='suppressed',closure_reason=?,closed_at=?,updated_at=?,next_repeat_at=NULL,escalation_state='complete' WHERE alarm_id=?", (reason, now.isoformat(), now.isoformat(), alarm_id))
            connection.execute("UPDATE delivery_attempts SET state='suppressed',error_code='alarm_closed',error_message='Alarm unterdrückt',next_attempt_at=NULL,lease_until=NULL WHERE alarm_id=? AND state IN ('pending','retry_scheduled')", (alarm_id,))
            self._event(connection, alarm_id, "suppressed", {"reason": reason}, now)
            return _record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone())
        return await self.repository.async_run(operation)

    async def async_due_repeats(self, *, now: datetime) -> list[AlarmRecord]:
        """Advance due alarm repetitions without invoking a delivery adapter."""

        ensure_aware(now)
        def operation(connection):
            rows = connection.execute("SELECT * FROM alarm_instances WHERE next_repeat_at IS NOT NULL AND next_repeat_at<=? AND alarm_state IN ('active','overdue')", (now.isoformat(),)).fetchall(); result = []
            for row in rows:
                if "repeat_only_unacknowledged" in row and row["repeat_only_unacknowledged"] and row["acknowledgement_state"] != "unacknowledged":
                    continue
                if int(row["max_repeats"]) and int(row["repeat_count"]) >= int(row["max_repeats"]):
                    connection.execute("UPDATE alarm_instances SET next_repeat_at=NULL,updated_at=? WHERE alarm_id=?", (now.isoformat(), row["alarm_id"]))
                    continue
                else:
                    count = int(row["repeat_count"]) + 1
                    next_at = now + timedelta(seconds=int(row["repeat_interval_seconds"])) if int(row["repeat_interval_seconds"]) else None
                    connection.execute("UPDATE alarm_instances SET repeat_count=?,next_repeat_at=?,updated_at=? WHERE alarm_id=?", (count, _iso(next_at), now.isoformat(), row["alarm_id"]))
                    self._event(connection, row["alarm_id"], "repeat_due", {"repeat_count": count}, now)
                result.append(_record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (row["alarm_id"],)).fetchone()))
            return result
        return await self.repository.async_run(operation)

    async def async_due_escalations(self, *, now: datetime) -> list[AlarmRecord]:
        """Advance due configured escalation stages; routing remains delivery-neutral."""

        ensure_aware(now)
        def operation(connection):
            rows = connection.execute("SELECT * FROM alarm_instances WHERE alarm_state IN ('active','overdue') AND escalation_state='running'").fetchall(); result = []
            for row in rows:
                stages = tuple(json.loads(row["escalation_json"] or "[]")); level = int(row["escalation_level"])
                if _acknowledgement_complete(connection, row):
                    connection.execute("UPDATE alarm_instances SET escalation_state='complete',updated_at=? WHERE alarm_id=? AND escalation_level=?", (now.isoformat(), row["alarm_id"], level))
                    continue
                if level >= len(stages):
                    connection.execute("UPDATE alarm_instances SET escalation_state='complete',updated_at=? WHERE alarm_id=?", (now.isoformat(), row["alarm_id"]))
                    continue
                stage = stages[level]
                due = datetime.fromisoformat(row["started_at"]) + timedelta(seconds=int(stage.get("after_seconds", 0)))
                if due > now: continue
                next_level = level + 1
                state = "complete" if next_level >= len(stages) else "running"
                updated = connection.execute("UPDATE alarm_instances SET escalation_level=?,escalation_state=?,updated_at=? WHERE alarm_id=? AND escalation_level=? AND alarm_state IN ('active','overdue')", (next_level, state, now.isoformat(), row["alarm_id"], level))
                if updated.rowcount != 1:
                    continue
                self._event(connection, row["alarm_id"], "escalated", {"level": next_level, "stage": stage}, now)
                result.append(_record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (row["alarm_id"],)).fetchone()))
            return result
        return await self.repository.async_run(operation)

    async def async_acknowledge(self, alarm_id: str, *, user_id: str, now: datetime, scope: str = "all", critical_confirmed: bool = False) -> AlarmRecord:
        ensure_aware(now)
        if not user_id: raise PermissionError("authenticated user required")
        def operation(connection):
            row = connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()
            if not row: raise ValueError("alarm not found")
            if row["priority"] == "critical" and not critical_confirmed: raise PermissionError("critical acknowledgement requires confirmation")
            if row["alarm_state"] not in RESOLVABLE_STATES and row["alarm_state"] != "active": raise ValueError("alarm cannot be acknowledged in this state")
            if row["acknowledgement_mode"] == "all_required" and user_id not in set(json.loads(row["required_recipient_ids_json"] or "[]")):
                raise PermissionError("user is not a required recipient")
            connection.execute("INSERT INTO acknowledgements(acknowledgement_id,alarm_id,user_id,acknowledged_at,scope,critical_confirmed) VALUES (?,?,?,?,?,?)", (new_id(),alarm_id,user_id,now.isoformat(),scope,int(critical_confirmed)))
            complete = _acknowledgement_complete(connection, row, pending_user_id=user_id)
            state = "acknowledged" if complete else "partially_acknowledged"
            connection.execute("UPDATE alarm_instances SET acknowledgement_state=?,acknowledged_by=?,acknowledged_at=?,acknowledgement_scope=?,critical_confirmed=?,updated_at=? WHERE alarm_id=?", (state,user_id,now.isoformat(),scope,int(critical_confirmed),now.isoformat(),alarm_id))
            self._event(connection,alarm_id,"acknowledged",{"user_id":user_id,"scope":scope,"complete":complete},now)
            return _record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?",(alarm_id,)).fetchone())
        return await self.repository.async_run(operation)

    async def async_acknowledge_many(self, alarm_ids: list[str], **kwargs) -> list[AlarmRecord]:
        now = kwargs["now"]; user_id = kwargs["user_id"]; scope = kwargs.get("scope", "all"); critical_confirmed = kwargs.get("critical_confirmed", False)
        ensure_aware(now)
        if not user_id or not alarm_ids: raise PermissionError("authenticated user and alarms required")
        def operation(connection):
            unique_ids = tuple(dict.fromkeys(alarm_ids)); placeholders = ",".join("?" for _ in unique_ids)
            rows = connection.execute(f"SELECT * FROM alarm_instances WHERE alarm_id IN ({placeholders})", unique_ids).fetchall()
            if len(rows) != len(unique_ids): raise ValueError("one or more alarms not found")
            if any(row["alarm_state"] not in RESOLVABLE_STATES for row in rows): raise ValueError("one or more alarms cannot be acknowledged")
            if any(row["priority"] == "critical" for row in rows) and not critical_confirmed: raise PermissionError("critical acknowledgement requires confirmation")
            if any(row["acknowledgement_mode"] == "all_required" and user_id not in set(json.loads(row["required_recipient_ids_json"] or "[]")) for row in rows):
                raise PermissionError("user is not a required recipient")
            for row in rows:
                connection.execute("INSERT INTO acknowledgements(acknowledgement_id,alarm_id,user_id,acknowledged_at,scope,critical_confirmed) VALUES (?,?,?,?,?,?)", (new_id(), row["alarm_id"], user_id, now.isoformat(), scope, int(critical_confirmed)))
                complete = _acknowledgement_complete(connection, row, pending_user_id=user_id)
                connection.execute("UPDATE alarm_instances SET acknowledgement_state=?,acknowledged_by=?,acknowledged_at=?,acknowledgement_scope=?,critical_confirmed=?,updated_at=? WHERE alarm_id=?", ("acknowledged" if complete else "partially_acknowledged", user_id, now.isoformat(), scope, int(critical_confirmed), now.isoformat(), row["alarm_id"]))
                self._event(connection, row["alarm_id"], "acknowledged", {"user_id": user_id, "scope": scope, "complete": complete}, now)
            return [_record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?", (alarm_id,)).fetchone()) for alarm_id in unique_ids]
        return await self.repository.async_run(operation)

    async def async_resolve(self, alarm_id: str, *, now: datetime, reason: str = "sensor_normalized", actual_state: str | None = None, expected_active_state: str | None = None, available: bool = True) -> AlarmRecord:
        ensure_aware(now)
        if not available or actual_state in {"unknown", "unavailable", None}:
            raise ValueError("sensor state is not safely available")
        if expected_active_state is not None and actual_state == expected_active_state:
            raise ValueError("alarm cause is still active")
        current = await self.async_get(alarm_id)
        if current is not None and current.alarm_state in (AlarmState.RESOLVED.value, AlarmState.SUPPRESSED.value, AlarmState.MANUALLY_CLOSED.value):
            raise ValueError("alarm is already closed")
        if current is None or current.alarm_state not in RESOLVABLE_STATES:
            raise ValueError("only an active alarm can be resolved")
        return await self._close(alarm_id, now=now, state=AlarmState.RESOLVED.value, reason=reason, user_id=None, event_type="resolved")

    async def async_close(self, alarm_id: str, *, user_id: str, now: datetime, reason: str, critical_confirmed: bool = False) -> AlarmRecord:
        ensure_aware(now)
        if not user_id or not reason.strip(): raise ValueError("user and reason are required")
        return await self._close(alarm_id, now=now, state=AlarmState.MANUALLY_CLOSED.value, reason=reason, user_id=user_id, event_type="manually_closed", critical_confirmed=critical_confirmed)

    async def _close(self, alarm_id: str, *, now: datetime, state: str, reason: str, user_id: str | None, event_type: str, critical_confirmed: bool = False) -> AlarmRecord:
        def operation(connection):
            row=connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?",(alarm_id,)).fetchone()
            if not row: raise ValueError("alarm not found")
            if row["alarm_state"] not in ("pending", "active", "overdue"): raise ValueError("alarm is already closed")
            if state == "manually_closed" and row["priority"] == "critical" and not critical_confirmed: raise PermissionError("critical close requires confirmation")
            connection.execute("UPDATE alarm_instances SET alarm_state=?,closure_reason=?,closed_at=?,closed_by=?,resolved_at=?,updated_at=?,next_repeat_at=NULL,escalation_state='complete' WHERE alarm_id=?",(state,reason,now.isoformat(),user_id,now.isoformat() if state=="resolved" else None,now.isoformat(),alarm_id)); connection.execute("UPDATE delivery_attempts SET state='suppressed',error_code='alarm_closed',error_message='Alarm beendet',next_attempt_at=NULL,lease_until=NULL WHERE alarm_id=? AND state IN ('pending','retry_scheduled')", (alarm_id,)); self._event(connection,alarm_id,event_type,{"reason":reason,"user_id":user_id},now); return _record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?",(alarm_id,)).fetchone())
        return await self.repository.async_run(operation)

    async def async_mark_overdue(self, *, now: datetime) -> list[AlarmRecord]:
        ensure_aware(now)
        def operation(connection):
            rows=connection.execute("SELECT * FROM alarm_instances WHERE alarm_state='active' AND max_duration_seconds>0").fetchall(); result=[]
            for row in rows:
                if datetime.fromisoformat(row["started_at"]) + timedelta(seconds=int(row["max_duration_seconds"])) > now:
                    continue
                connection.execute("UPDATE alarm_instances SET alarm_state='overdue',overdue_at=?,updated_at=? WHERE alarm_id=?",(now.isoformat(),now.isoformat(),row["alarm_id"]))
                self._event(connection,row["alarm_id"],"overdue",{},now)
                result.append(_record(connection.execute("SELECT * FROM alarm_instances WHERE alarm_id=?",(row["alarm_id"],)).fetchone()))
            return result
        return await self.repository.async_run(operation)

    @staticmethod
    def _event(connection, alarm_id: str, event_type: str, payload: dict[str, Any], now: datetime) -> None:
        connection.execute("INSERT INTO alarm_events(event_id,alarm_id,event_type,payload_json,occurred_at) VALUES (?,?,?,?,?)", (new_id(),alarm_id,event_type,json.dumps(payload,ensure_ascii=False),now.isoformat()))


def alarm_to_dict(alarm: AlarmRecord) -> dict[str, Any]:
    value = asdict(alarm)
    for key, item in list(value.items()):
        if isinstance(item, datetime): value[key] = item.isoformat()
        elif isinstance(item, tuple): value[key] = list(item)
    return value

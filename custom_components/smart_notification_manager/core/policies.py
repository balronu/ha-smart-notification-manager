"""Persistent Phase-5 notification policy evaluation.

This module decides whether a notification may be handed to delivery. It never
creates a delivery job and never calls a Home Assistant service.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .models import ensure_aware, new_id
from .repository import SQLiteRepository


@dataclass(frozen=True, slots=True)
class QuietHours:
    quiet_id: str
    name: str
    enabled: bool
    weekdays: tuple[int, ...]
    start_time: str
    end_time: str
    timezone: str = "UTC"
    rule_exceptions: tuple[str, ...] = ()
    priority_exceptions: tuple[str, ...] = ("critical",)

    def validate(self) -> None:
        if not self.name.strip() or not self.quiet_id:
            raise ValueError("Ruhezeit benötigt ID und Namen")
        if any(day not in range(7) for day in self.weekdays):
            raise ValueError("Wochentage müssen zwischen 0 und 6 liegen")
        try:
            time.fromisoformat(self.start_time)
            time.fromisoformat(self.end_time)
            ZoneInfo(self.timezone)
        except (TypeError, ValueError) as err:
            raise ValueError("Ruhezeit enthält ungültige Zeit oder Zeitzone") from err


@dataclass(frozen=True, slots=True)
class Pause:
    pause_id: str
    scope_type: str
    scope_id: str | None
    starts_at: datetime
    ends_at: datetime | None
    reason: str
    user_id: str
    critical_confirmed: bool = False
    active: bool = True

    def validate(self) -> None:
        ensure_aware(self.starts_at)
        if self.ends_at:
            ensure_aware(self.ends_at)
            if self.ends_at <= self.starts_at:
                raise ValueError("Pausenende muss nach dem Beginn liegen")
        if self.scope_type not in {"global", "rule", "category", "entity"}:
            raise ValueError("Ungültiger Pausenbereich")
        if self.scope_type != "global" and not self.scope_id:
            raise ValueError("Pausenbereich benötigt eine ID")
        if not self.reason.strip() or not self.user_id:
            raise ValueError("Pause benötigt Begründung und Benutzer")


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    rule_id: str
    window_seconds: int
    max_notifications: int
    critical_exempt: bool = True
    enabled: bool = True

    def validate(self) -> None:
        if self.window_seconds <= 0 or self.max_notifications <= 0:
            raise ValueError("Rate-Limit benötigt positive Zeit und Anzahl")


@dataclass(frozen=True, slots=True)
class RuleDependency:
    rule_id: str
    depends_on_rule_id: str
    expected_state: str
    enabled: bool = True

    def validate(self) -> None:
        if not self.rule_id or not self.depends_on_rule_id or self.rule_id == self.depends_on_rule_id:
            raise ValueError("Regelabhängigkeit ist ungültig")
        if self.expected_state not in {"active", "inactive"}:
            raise ValueError("Abhängigkeit benötigt active oder inactive")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: str
    reason_code: str
    reason_de: str
    observation: bool = False


@dataclass(frozen=True, slots=True)
class PolicyPreview:
    """Read-only result of the same policy checks used for delivery."""

    decision: PolicyDecision
    remaining_capacity: int | None = None


def quiet_hours_active(quiet: QuietHours, now: datetime, *, rule_id: str, priority: str) -> bool:
    quiet.validate()
    if not quiet.enabled or rule_id in quiet.rule_exceptions or priority in quiet.priority_exceptions:
        return False
    local = now.astimezone(ZoneInfo(quiet.timezone))
    current = local.timetz().replace(tzinfo=None)
    start = time.fromisoformat(quiet.start_time)
    end = time.fromisoformat(quiet.end_time)
    if start <= end:
        return local.weekday() in quiet.weekdays and start <= current <= end
    # Overnight windows belong to the weekday on which they start and continue
    # into the following day.
    previous_weekday = (local.weekday() - 1) % 7
    return (local.weekday() in quiet.weekdays and current >= start) or (previous_weekday in quiet.weekdays and current <= end)


class PolicyStore:
    """Transactional policy storage and one central decision boundary."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_list(self) -> dict[str, list[dict]]:
        def operation(connection):
            quiet = []
            for row in connection.execute("SELECT quiet_id,name,enabled,weekdays_json,start_time,end_time,timezone,rule_exceptions_json,priority_exceptions_json FROM quiet_hours ORDER BY name COLLATE NOCASE"):
                quiet.append({"quiet_id": row[0], "name": row[1], "enabled": bool(row[2]), "weekdays": json.loads(row[3]), "start_time": row[4], "end_time": row[5], "timezone": row[6], "rule_exceptions": json.loads(row[7]), "priority_exceptions": json.loads(row[8])})
            pauses = [dict(row) for row in connection.execute("SELECT pause_id,scope_type,scope_id,starts_at,ends_at,reason,user_id,critical_confirmed,active,created_at FROM notification_pauses ORDER BY starts_at DESC")]
            limits = [dict(row) for row in connection.execute("SELECT rule_id,window_seconds,max_notifications,critical_exempt,enabled FROM rate_limit_policies")]
            dependencies = [dict(row) for row in connection.execute("SELECT rule_id,depends_on_rule_id,expected_state,enabled FROM rule_dependencies")]
            observations = [dict(row) for row in connection.execute("SELECT rule_id,enabled,critical_confirmed,updated_by,updated_at FROM observation_modes")]
            decisions = [dict(row) for row in connection.execute("SELECT rule_id,alarm_id,action,reason_code,reason_de,occurred_at FROM policy_decisions ORDER BY occurred_at DESC LIMIT 50")]
            return {"quiet_hours": quiet, "pauses": pauses, "rate_limits": limits, "dependencies": dependencies, "observation_modes": observations, "decisions": decisions}
        return await self.repository.async_run(operation)

    async def async_save_quiet_hours(self, quiet: QuietHours, *, user_id: str, now: datetime) -> QuietHours:
        quiet.validate()
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        await self.repository.async_run(lambda c: c.execute("INSERT INTO quiet_hours(quiet_id,name,enabled,weekdays_json,start_time,end_time,timezone,rule_exceptions_json,priority_exceptions_json,updated_by,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(quiet_id) DO UPDATE SET name=excluded.name,enabled=excluded.enabled,weekdays_json=excluded.weekdays_json,start_time=excluded.start_time,end_time=excluded.end_time,timezone=excluded.timezone,rule_exceptions_json=excluded.rule_exceptions_json,priority_exceptions_json=excluded.priority_exceptions_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (quiet.quiet_id, quiet.name, int(quiet.enabled), json.dumps(quiet.weekdays), quiet.start_time, quiet.end_time, quiet.timezone, json.dumps(quiet.rule_exceptions), json.dumps(quiet.priority_exceptions), user_id, now.isoformat())))
        return quiet

    async def async_save_pause(self, pause: Pause, *, now: datetime) -> Pause:
        pause.validate()
        await self.repository.async_run(lambda c: c.execute("INSERT INTO notification_pauses(pause_id,scope_type,scope_id,starts_at,ends_at,reason,user_id,critical_confirmed,active,created_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(pause_id) DO UPDATE SET ends_at=excluded.ends_at,reason=excluded.reason,critical_confirmed=excluded.critical_confirmed,active=excluded.active", (pause.pause_id, pause.scope_type, pause.scope_id, pause.starts_at.isoformat(), pause.ends_at.isoformat() if pause.ends_at else None, pause.reason, pause.user_id, int(pause.critical_confirmed), int(pause.active), now.isoformat())))
        return pause

    async def async_resume_pause(self, pause_id: str) -> None:
        await self.repository.async_run(lambda c: c.execute("UPDATE notification_pauses SET active=0 WHERE pause_id=?", (pause_id,)))

    async def async_save_rate_limit(self, policy: RateLimitPolicy, *, user_id: str, now: datetime) -> RateLimitPolicy:
        policy.validate()
        await self.repository.async_run(lambda c: c.execute("INSERT INTO rate_limit_policies(rule_id,window_seconds,max_notifications,critical_exempt,enabled,updated_by,updated_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(rule_id) DO UPDATE SET window_seconds=excluded.window_seconds,max_notifications=excluded.max_notifications,critical_exempt=excluded.critical_exempt,enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (policy.rule_id, policy.window_seconds, policy.max_notifications, int(policy.critical_exempt), int(policy.enabled), user_id, now.isoformat())))
        return policy

    async def async_save_dependency(self, dependency: RuleDependency, *, user_id: str, now: datetime) -> RuleDependency:
        dependency.validate()
        def operation(connection):
            if not connection.execute("SELECT 1 FROM rules WHERE rule_id=? AND deleted_at IS NULL", (dependency.rule_id,)).fetchone():
                raise ValueError("Abhängige Regel ist nicht vorhanden oder gelöscht")
            if not connection.execute("SELECT 1 FROM rules WHERE rule_id=? AND deleted_at IS NULL", (dependency.depends_on_rule_id,)).fetchone():
                raise ValueError("Abhängigkeitsregel ist nicht vorhanden oder deaktiviert")
            connection.execute("INSERT INTO rule_dependencies(rule_id,depends_on_rule_id,expected_state,enabled,updated_by,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(rule_id,depends_on_rule_id) DO UPDATE SET expected_state=excluded.expected_state,enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (dependency.rule_id, dependency.depends_on_rule_id, dependency.expected_state, int(dependency.enabled), user_id, now.isoformat()))
            if _has_dependency_cycle(connection, dependency.rule_id):
                raise ValueError("Zirkuläre Regelabhängigkeit ist nicht zulässig")
        await self.repository.async_run(operation)
        return dependency

    async def async_save_observation(self, rule_id: str, *, enabled: bool, critical_confirmed: bool, user_id: str, now: datetime) -> None:
        if enabled and not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        await self.repository.async_run(lambda c: c.execute("INSERT INTO observation_modes(rule_id,enabled,critical_confirmed,updated_by,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(rule_id) DO UPDATE SET enabled=excluded.enabled,critical_confirmed=excluded.critical_confirmed,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (rule_id, int(enabled), int(critical_confirmed), user_id, now.isoformat())))

    async def async_decide(self, request: dict, *, now: datetime) -> PolicyDecision:
        ensure_aware(now)
        return await self.repository.async_run(lambda connection: self.decide_in_connection(connection, request, now=now))

    def decide_in_connection(self, connection, request: dict, *, now: datetime) -> PolicyDecision:
        """Evaluate and, when allowed, reserve one notification atomically."""
        rule_id = request["rule_id"]; priority = request.get("priority", "normal")
        if request.get("alarm_state") not in {"active", "pending", "overdue"}:
            return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "alarm_not_active", "Alarm ist nicht aktiv.", now)
        if not request.get("rule_enabled", True):
            return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "rule_disabled", "Die Regel ist deaktiviert.", now)
        observation = connection.execute("SELECT enabled,critical_confirmed FROM observation_modes WHERE rule_id=?", (rule_id,)).fetchone()
        if observation and observation[0]:
            if priority == "critical" and not observation[1]:
                return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "critical_confirmation_required", "Critical benötigt eine zusätzliche Beobachtungsmodus-Bestätigung.", now)
            return self._record(connection, rule_id, request.get("alarm_id"), "observe", "observation_mode", "Beobachtungsmodus: hypothetischer Versand, keine Zustellung.", now, True)
        if self._paused(connection, request, now) and priority != "critical":
            return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "paused", "Die Benachrichtigung ist pausiert.", now)
        for row in connection.execute("SELECT weekdays_json,start_time,end_time,timezone,rule_exceptions_json,priority_exceptions_json FROM quiet_hours WHERE enabled=1"):
            quiet = QuietHours("stored", "stored", True, tuple(json.loads(row[0])), row[1], row[2], row[3], tuple(json.loads(row[4])), tuple(json.loads(row[5])))
            if quiet_hours_active(quiet, now, rule_id=rule_id, priority=priority):
                return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "quiet_hours", "Ruhezeit ist aktiv.", now)
        for dependency in connection.execute("SELECT depends_on_rule_id,expected_state FROM rule_dependencies WHERE rule_id=? AND enabled=1", (rule_id,)):
            value = self._current_dependency_state(connection, dependency[0])
            if value != dependency[1]:
                return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "dependency_not_met", "Eine Regelabhängigkeit ist nicht erfüllt oder unklar.", now)
        limit = connection.execute("SELECT window_seconds,max_notifications,critical_exempt FROM rate_limit_policies WHERE rule_id=? AND enabled=1", (rule_id,)).fetchone()
        if limit and not (priority == "critical" and limit[2]):
            cutoff = (now - timedelta(seconds=limit[0])).isoformat()
            count = connection.execute("SELECT COUNT(*) FROM rate_limit_events WHERE rule_id=? AND occurred_at>=? AND kind='notification'", (rule_id, cutoff)).fetchone()[0]
            if count >= limit[1]:
                return self._record(connection, rule_id, request.get("alarm_id"), "suppress", "rate_limit", "Das Rate-Limit ist erreicht.", now)
            connection.execute("INSERT INTO rate_limit_events(event_id,rule_id,alarm_id,occurred_at,kind) VALUES (?,?,?,?,?)", (new_id(), rule_id, request.get("alarm_id"), now.isoformat(), "notification"))
        return self._record(connection, rule_id, request.get("alarm_id"), "allow", "allowed", "Benachrichtigung darf an das Delivery-System übergeben werden.", now)

    def preview_in_connection(self, connection, request: dict, *, now: datetime) -> PolicyPreview:
        """Evaluate policy without recording a decision or reserving capacity."""
        ensure_aware(now)
        rule_id = request["rule_id"]
        priority = request.get("priority", "normal")
        if request.get("alarm_state") not in {"active", "pending", "overdue"}:
            return PolicyPreview(PolicyDecision("suppress", "alarm_not_active", "Alarm ist nicht aktiv."), 0)
        if not request.get("rule_enabled", True):
            return PolicyPreview(PolicyDecision("suppress", "rule_disabled", "Die Regel ist deaktiviert."), 0)
        observation = connection.execute("SELECT enabled,critical_confirmed FROM observation_modes WHERE rule_id=?", (rule_id,)).fetchone()
        if observation and observation[0]:
            if priority == "critical" and not observation[1]:
                return PolicyPreview(PolicyDecision("suppress", "critical_confirmation_required", "Critical benötigt eine zusätzliche Beobachtungsmodus-Bestätigung."), 0)
            return PolicyPreview(PolicyDecision("observe", "observation_mode", "Beobachtungsmodus: hypothetischer Versand, keine Zustellung.", True), None)
        if self._paused(connection, request, now) and priority != "critical":
            return PolicyPreview(PolicyDecision("suppress", "paused", "Die Benachrichtigung ist pausiert."), 0)
        for row in connection.execute("SELECT weekdays_json,start_time,end_time,timezone,rule_exceptions_json,priority_exceptions_json FROM quiet_hours WHERE enabled=1"):
            quiet = QuietHours("preview", "preview", True, tuple(json.loads(row[0])), row[1], row[2], row[3], tuple(json.loads(row[4])), tuple(json.loads(row[5])))
            if quiet_hours_active(quiet, now, rule_id=rule_id, priority=priority):
                return PolicyPreview(PolicyDecision("suppress", "quiet_hours", "Ruhezeit ist aktiv."), 0)
        for dependency in connection.execute("SELECT depends_on_rule_id,expected_state FROM rule_dependencies WHERE rule_id=? AND enabled=1", (rule_id,)):
            if self._current_dependency_state(connection, dependency[0]) != dependency[1]:
                return PolicyPreview(PolicyDecision("suppress", "dependency_not_met", "Eine Regelabhängigkeit ist nicht erfüllt oder unklar."), 0)
        limit = connection.execute("SELECT window_seconds,max_notifications,critical_exempt FROM rate_limit_policies WHERE rule_id=? AND enabled=1", (rule_id,)).fetchone()
        if limit and not (priority == "critical" and limit[2]):
            cutoff = (now - timedelta(seconds=limit[0])).isoformat()
            count = connection.execute("SELECT COUNT(*) FROM rate_limit_events WHERE rule_id=? AND occurred_at>=? AND kind='notification'", (rule_id, cutoff)).fetchone()[0]
            remaining = max(0, limit[1] - count)
            if remaining == 0:
                return PolicyPreview(PolicyDecision("suppress", "rate_limit", "Das Rate-Limit ist erreicht."), 0)
            return PolicyPreview(PolicyDecision("allow", "allowed", "Benachrichtigung darf an das Delivery-System übergeben werden."), remaining)
        return PolicyPreview(PolicyDecision("allow", "allowed", "Benachrichtigung darf an das Delivery-System übergeben werden."), None)

    @staticmethod
    def _current_dependency_state(connection, rule_id: str) -> str:
        row = connection.execute("SELECT 1 FROM alarm_instances WHERE rule_id=? AND alarm_state IN ('pending','active','overdue') LIMIT 1", (rule_id,)).fetchone()
        return "active" if row else "inactive"
    def _paused(self, connection, request: dict, now: datetime) -> bool:
        for row in connection.execute("SELECT scope_type,scope_id,starts_at,ends_at,active FROM notification_pauses WHERE active=1"):
            if datetime.fromisoformat(row[2]) > now or (row[3] and datetime.fromisoformat(row[3]) <= now):
                continue
            if row[0] == "global" or (row[0] == "rule" and row[1] == request.get("rule_id")) or (row[0] == "category" and row[1] == request.get("category")) or (row[0] == "entity" and row[1] == request.get("entity_id")):
                return True
        return False

    @staticmethod
    def _record(connection, rule_id, alarm_id, action, reason_code, reason_de, now, observation=False):
        connection.execute("INSERT INTO policy_decisions(decision_id,rule_id,alarm_id,action,reason_code,reason_de,occurred_at) VALUES (?,?,?,?,?,?,?)", (new_id(), rule_id, alarm_id, action, reason_code, reason_de, now.isoformat()))
        return PolicyDecision(action, reason_code, reason_de, observation)


def _has_dependency_cycle(connection, start: str) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(current: str) -> bool:
        if current in visiting:
            return True
        if current in visited:
            return False
        visiting.add(current)
        for row in connection.execute("SELECT depends_on_rule_id FROM rule_dependencies WHERE rule_id=? AND enabled=1", (current,)):
            if visit(row[0]):
                return True
        visiting.remove(current)
        visited.add(current)
        return False

    return visit(start)

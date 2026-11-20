"""Persistent alarm and delivery statistics for the Phase-12 panel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .repository import SQLiteRepository


class StatisticsStore:
    """Read persisted lifecycle data without maintaining a second event stream."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_summary(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        priority: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """Return filtered totals and daily/monthly aggregates from SQLite."""

        return await self.repository.async_run(
            lambda connection: self._read(connection, date_from=date_from, date_to=date_to, priority=priority, state=state)
        )

    @staticmethod
    def _read(connection, *, date_from: str | None, date_to: str | None, priority: str | None, state: str | None) -> dict[str, Any]:
        clauses = ["1=1"]
        args: list[Any] = []
        if date_from:
            clauses.append("started_at >= ?")
            args.append(date_from)
        if date_to:
            clauses.append("started_at <= ?")
            args.append(date_to)
        if priority:
            clauses.append("priority = ?")
            args.append(priority)
        if state:
            clauses.append("alarm_state = ?")
            args.append(state)
        where = " AND ".join(clauses)
        alarms = connection.execute(f"SELECT * FROM alarm_instances WHERE {where}", args).fetchall()
        alarm_ids = [row["alarm_id"] for row in alarms]
        placeholders = ",".join("?" for _ in alarm_ids) or "NULL"
        deliveries = connection.execute(
            f"SELECT state, channel_id, error_code FROM delivery_attempts WHERE alarm_id IN ({placeholders})",
            alarm_ids,
        ).fetchall()
        events = connection.execute(
            f"SELECT event_type, occurred_at, payload_json FROM alarm_events WHERE alarm_id IN ({placeholders})",
            alarm_ids,
        ).fetchall()

        def count_by(rows, key):
            result: dict[str, int] = {}
            for row in rows:
                value = str(row[key] or "unknown")
                result[value] = result.get(value, 0) + 1
            return dict(sorted(result.items()))

        event_counts = count_by(events, "event_type")
        delivery_counts = count_by(deliveries, "state")
        channel_counts = count_by(deliveries, "channel_id")
        errors = count_by([row for row in deliveries if row["error_code"]], "error_code")
        daily: dict[str, dict[str, int]] = {}
        monthly: dict[str, dict[str, int]] = {}
        for row in alarms:
            stamp = str(row["started_at"])
            day = stamp[:10]
            month = stamp[:7]
            for target, key in ((daily, day), (monthly, month)):
                bucket = target.setdefault(key, {"alarms": 0, "critical": 0, "resolved": 0, "acknowledged": 0})
                bucket["alarms"] += 1
                bucket["critical"] += int(row["priority"] == "critical")
                bucket["resolved"] += int(row["alarm_state"] in {"resolved", "manually_closed"})
                bucket["acknowledged"] += int(row["acknowledgement_state"] == "acknowledged")
        return {
            "filters": {"date_from": date_from, "date_to": date_to, "priority": priority, "state": state},
            "totals": {
                "alarms": len(alarms),
                "critical": sum(row["priority"] == "critical" for row in alarms),
                "acknowledged": sum(row["acknowledgement_state"] == "acknowledged" for row in alarms),
                "escalated": sum(row["escalation_state"] in {"running", "complete"} for row in alarms),
                "repeated": event_counts.get("repeat_planned", 0) + event_counts.get("repeat", 0),
                "delivery_attempts": len(deliveries),
                "delivery_errors": sum(1 for row in deliveries if row["error_code"]),
            },
            "by_priority": count_by(alarms, "priority"),
            "by_state": count_by(alarms, "alarm_state"),
            "by_acknowledgement": count_by(alarms, "acknowledgement_state"),
            "by_escalation": count_by(alarms, "escalation_state"),
            "delivery": {"by_state": delivery_counts, "by_channel": channel_counts, "errors": errors},
            "events": event_counts,
            "daily": dict(sorted(daily.items())),
            "monthly": dict(sorted(monthly.items())),
            "generated_at": datetime.now(UTC).isoformat(),
        }


def validate_statistics_filters(payload: dict[str, Any]) -> dict[str, str | None]:
    """Validate public filter values before they reach the SQL boundary."""

    result: dict[str, str | None] = {}
    for key in ("date_from", "date_to", "priority", "state"):
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Statistikfilter {key} muss Text sein")
        result[key] = value
    return result

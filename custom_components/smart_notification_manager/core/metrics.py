"""Small, event-safe metrics coordinator for Phase 7 entities."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .repository import SQLiteRepository


class MetricsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Expose one bounded aggregate query to all native entities."""

    def __init__(self, hass: HomeAssistant, repository: SQLiteRepository) -> None:
        self.repository = repository
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name="smart_notification_manager_metrics",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.repository.async_run(self._read)
        except Exception as err:  # HA turns this into unavailable entities.
            raise UpdateFailed("Metriken konnten nicht gelesen werden") from err

    @staticmethod
    def _read(connection) -> dict[str, Any]:
        row = connection.execute(
            """SELECT
                SUM(CASE WHEN alarm_state IN ('pending','active','overdue') THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN priority='critical' AND alarm_state IN ('pending','active','overdue') THEN 1 ELSE 0 END) AS critical_count,
                SUM(CASE WHEN acknowledgement_state != 'acknowledged' AND alarm_state IN ('pending','active','overdue') THEN 1 ELSE 0 END) AS unack_count
               FROM alarm_instances"""
        ).fetchone()
        pauses = connection.execute(
            "SELECT COUNT(*) FROM notification_pauses WHERE active=1 AND starts_at <= datetime('now') AND (ends_at IS NULL OR ends_at > datetime('now'))"
        ).fetchone()[0]
        delivery_errors = connection.execute(
            "SELECT COUNT(*) FROM delivery_attempts WHERE state IN ('failed','error')"
        ).fetchone()[0]
        return {
            "open_alarms": int(row[0] or 0),
            "critical_alarms": int(row[1] or 0),
            "unacknowledged_alarms": int(row[2] or 0),
            "active_pauses": int(pauses or 0),
            "delivery_errors": int(delivery_errors or 0),
            "healthy": True,
        }


async def async_get_coordinator(hass: HomeAssistant, repository: SQLiteRepository) -> MetricsCoordinator:
    """Create and initially populate the shared coordinator."""

    coordinator = MetricsCoordinator(hass, repository)
    await coordinator.async_config_entry_first_refresh()
    return coordinator

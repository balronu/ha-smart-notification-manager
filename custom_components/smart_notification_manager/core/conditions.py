"""Pure condition contracts; Home Assistant evaluation is a later adapter phase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A local wall-clock window, including overnight windows."""

    start: time
    end: time

    def contains(self, value: time) -> bool:
        if self.start <= self.end:
            return self.start <= value <= self.end
        return value >= self.start or value <= self.end


def is_in_window(window: TimeWindow, timestamp: datetime) -> bool:
    """Evaluate a timezone-aware timestamp without touching HA state."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return window.contains(timestamp.timetz().replace(tzinfo=None))


"""Permission primitives for later HA-user integration."""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    VIEW = "view"
    EDIT = "edit"
    TEST = "test"
    ADMIN = "admin"


def can_access(granted: set[str], required: Permission) -> bool:
    """Apply the Phase-1 deny-by-default rule."""

    return Permission.ADMIN in granted or required.value in granted


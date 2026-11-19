"""Safe, deliberately small notification-template rendering."""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
ALLOWED_FIELDS = frozenset({"rule_name", "priority", "trigger_entity", "friendly_name", "area", "state", "previous_state", "timestamp", "alarm_id"})


def validate_template(template: str) -> tuple[str, ...]:
    """Return unknown placeholders; reject executable/template-language syntax."""

    if not isinstance(template, str) or len(template) > 10_000:
        raise ValueError("Vorlage ist leer, ungültig oder zu lang")
    if "{%" in template or "{{{" in template or "__" in template:
        raise ValueError("Vorlage enthält nicht erlaubte Ausdrücke")
    return tuple(sorted({match.group(1) for match in PLACEHOLDER_RE.finditer(template) if match.group(1) not in ALLOWED_FIELDS}))


def render_template(template: str, values: dict[str, Any]) -> str:
    unknown = validate_template(template)
    if unknown:
        raise ValueError(f"Unbekannte Platzhalter: {', '.join(unknown)}")
    return PLACEHOLDER_RE.sub(lambda match: str(values.get(match.group(1), "")), template)

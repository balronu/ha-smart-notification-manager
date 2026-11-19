"""Phase-8 rule template library with safe JSON import/export."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import new_id
from .repository import SQLiteRepository

TEMPLATE_FORMAT = "smart-notification-manager.rule-template.v1"
_SECRET_KEYS = {"password", "token", "secret", "access_token", "api_key", "credential"}


@dataclass(frozen=True, slots=True)
class RuleTemplate:
    template_id: str
    name: str
    description: str
    category: str
    priority: str
    definition: dict[str, Any]
    version: int = 1
    built_in: bool = False


def _definition(kind: str, description: str, priority: str, category: str) -> RuleTemplate:
    return RuleTemplate(
        f"builtin-{kind}", kind, description, category, priority,
        {"entity_placeholders": ["<entity>"], "trigger": {"kind": "state", "entity_ids": ["<entity>"]}, "conditions": {"kind": "all", "children": [{"kind": "entity_state", "value": {"entity_id": "<entity>", "state": "on"}}]}, "routing": {}, "delay_seconds": 0, "repeat": {}, "escalation": {}, "required_integrations": []},
        built_in=True,
    )


BUILTIN_TEMPLATES = tuple(
    _definition(name, description, priority, category)
    for name, description, priority, category in (
        ("Tür oder Fenster länger geöffnet", "Öffnung bleibt länger als die konfigurierte Dauer bestehen.", "warning", "Sicherheit"),
        ("Wasseraustritt oder Leckage", "Leckagesensor meldet Wasser.", "critical", "Sicherheit"),
        ("Rauch- oder Gasmelder", "Rauch- oder Gasalarm wird erkannt.", "critical", "Sicherheit"),
        ("Temperatur außerhalb des Bereichs", "Temperatur überschreitet eine obere oder untere Grenze.", "warning", "Klima"),
        ("Luftfeuchtigkeit außerhalb des Zielbereichs", "Luftfeuchtigkeit verlässt den Zielbereich.", "warning", "Klima"),
        ("Batterie schwach", "Batteriestand unterschreitet den Zielwert.", "normal", "Energie"),
        ("Gerät oder Sensor nicht erreichbar", "Ein Gerät meldet unavailable.", "warning", "Netzwerk"),
        ("Stromausfall und Stromwiederkehr", "Netzversorgung wechselt den Zustand.", "critical", "Energie"),
        ("Heizung ausgefallen", "Solltemperatur wird trotz aktivem Bedarf nicht erreicht.", "warning", "Heizung"),
        ("Bewegung oder Anwesenheit", "Bewegung oder Anwesenheit wird erkannt.", "normal", "Anwesenheit"),
        ("Wohnmobil-Landstrom ausgefallen", "Landstrom des Wohnmobils fällt aus.", "critical", "Wohnmobil"),
        ("Wohnmobil-Batterie kritisch", "Batteriespannung des Wohnmobils ist kritisch.", "critical", "Wohnmobil"),
        ("Netzwerkgerät offline", "Ein Netzwerkgerät ist nicht erreichbar.", "warning", "Netzwerk"),
        ("Wiederkehrende Erinnerung bei offenem Alarm", "Aktiver Alarm wird kontrolliert erinnert.", "normal", "Sonstiges"),
    )
)


class RuleTemplateStore:
    """Persist custom templates while exposing immutable built-ins."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_list(self) -> list[dict[str, Any]]:
        custom = await self.repository.async_run(self._list_custom)
        return [self.to_dict(item) for item in BUILTIN_TEMPLATES] + custom

    async def async_save(self, value: dict[str, Any], *, user_id: str, now: datetime) -> dict[str, Any]:
        item = self._parse(value, built_in=False)
        if not user_id:
            raise PermissionError("authentifizierter Benutzer erforderlich")
        if item.template_id.startswith("builtin-"):
            raise PermissionError("Integrierte Vorlagen dürfen nicht überschrieben werden")
        stamp = now.isoformat()

        def operation(connection):
            owner = connection.execute("SELECT created_by FROM rule_templates WHERE template_id=?", (item.template_id,)).fetchone()
            if owner is not None and owner[0] != user_id:
                raise PermissionError("Vorlage gehört einem anderen Benutzer")
            connection.execute(
                """INSERT INTO rule_templates(template_id,name,description,category,priority,definition_json,version,created_by,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(template_id) DO UPDATE SET name=excluded.name,description=excluded.description,
                   category=excluded.category,priority=excluded.priority,definition_json=excluded.definition_json,version=excluded.version,updated_at=excluded.updated_at""",
                (item.template_id, item.name, item.description, item.category, item.priority, json.dumps(item.definition, ensure_ascii=False, sort_keys=True), item.version, user_id, stamp),
            )

        await self.repository.async_run(operation)
        return self.to_dict(item)

    async def async_delete(self, template_id: str, *, user_id: str) -> None:
        if template_id.startswith("builtin-"):
            raise ValueError("Integrierte Vorlagen können nicht gelöscht werden.")
        await self.repository.async_run(lambda c: c.execute("DELETE FROM rule_templates WHERE template_id=? AND created_by=?", (template_id, user_id)))

    async def async_import(self, value: dict[str, Any], *, user_id: str, now: datetime, confirm: bool) -> dict[str, Any]:
        if value.get("format") != TEMPLATE_FORMAT:
            raise ValueError("Unbekanntes Vorlagenformat")
        item = self._parse(value.get("template", {}), built_in=False)
        existing = await self.repository.async_run(lambda c: c.execute("SELECT 1 FROM rule_templates WHERE template_id=?", (item.template_id,)).fetchone() is not None)
        preview = {"template": self.to_dict(item), "conflict": existing, "missing_entities": list(item.definition.get("entity_placeholders", []))}
        if not confirm:
            return {"confirmed": False, **preview}
        if existing:
            raise ValueError("Vorlagenkonflikt: ausdrückliche neue ID erforderlich")
        saved = await self.async_save(self.to_dict(item), user_id=user_id, now=now)
        return {"confirmed": True, "template": saved, "conflict": False, "missing_entities": preview["missing_entities"]}

    async def async_export(self, template_id: str) -> dict[str, Any]:
        items = await self.async_list()
        item = next((entry for entry in items if entry["template_id"] == template_id), None)
        if item is None:
            raise ValueError("Vorlage nicht gefunden")
        return {"format": TEMPLATE_FORMAT, "template": item}

    @staticmethod
    def _list_custom(connection) -> list[dict[str, Any]]:
        return [{"template_id": row[0], "name": row[1], "description": row[2], "category": row[3], "priority": row[4], "definition": json.loads(row[5]), "version": row[6], "built_in": False} for row in connection.execute("SELECT template_id,name,description,category,priority,definition_json,version FROM rule_templates ORDER BY name COLLATE NOCASE")]

    @classmethod
    def _parse(cls, value: dict[str, Any], *, built_in: bool) -> RuleTemplate:
        if not isinstance(value, dict):
            raise TypeError("Vorlage muss ein Objekt sein")
        name = str(value.get("name", "")).strip()
        definition = value.get("definition") or {}
        if not name or len(name) > 120 or not isinstance(definition, dict):
            raise ValueError("Vorlage benötigt Namen und Definition")
        cls._reject_secrets(definition)
        priority = str(value.get("priority", "normal"))
        if priority not in {"info", "normal", "warning", "critical"}:
            raise ValueError("Ungültige Vorlagenpriorität")
        if not definition.get("entity_placeholders"):
            raise ValueError("Vorlage muss benötigte Entitäten als Platzhalter beschreiben")
        return RuleTemplate(str(value.get("template_id") or new_id()), name, str(value.get("description", "")), str(value.get("category", "Sonstiges")), priority, definition, int(value.get("version", 1)), built_in)

    @classmethod
    def _reject_secrets(cls, value: Any) -> None:
        if isinstance(value, dict):
            if any(str(key).lower() in _SECRET_KEYS for key in value):
                raise ValueError("Vorlagen dürfen keine Zugangsdaten enthalten")
            for child in value.values():
                cls._reject_secrets(child)
        elif isinstance(value, list):
            for child in value:
                cls._reject_secrets(child)

    @staticmethod
    def to_dict(item: RuleTemplate | dict[str, Any]) -> dict[str, Any]:
        if isinstance(item, dict):
            return {key: item[key] for key in ("template_id", "name", "description", "category", "priority", "definition", "version", "built_in") if key in item}
        return {"template_id": item.template_id, "name": item.name, "description": item.description, "category": item.category, "priority": item.priority, "definition": item.definition, "version": item.version, "built_in": item.built_in}

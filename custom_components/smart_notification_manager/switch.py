"""Rule switches backed by the existing, versioned RuleStore."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SIGNAL_RULES_UPDATED
from .core.permissions import Permission
from .core.rule_store import EditorAccess, rule_to_dict
from .core.rules import Priority


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    runtime = hass.data[DOMAIN]
    rules = await runtime["rule_store"].async_list()
    entities = {rule.rule_id: RuleSwitch(runtime["rule_store"], runtime["metrics_coordinator"], entry, rule) for rule in rules}
    async_add_entities(list(entities.values()))

    async def refresh_rules(*_args) -> None:
        await async_sync_rule_switches(runtime["rule_store"], runtime["metrics_coordinator"], entry, entities, async_add_entities)

    runtime.setdefault("rule_switch_unsubscribers", {})[entry.entry_id] = async_dispatcher_connect(
        hass, SIGNAL_RULES_UPDATED, lambda *args: hass.async_create_task(refresh_rules(*args))
    )


async def async_sync_rule_switches(store, coordinator, entry, entities, async_add_entities) -> None:
    """Reconcile rule entities after editor saves, deletes or routing changes."""

    latest = {rule.rule_id: rule for rule in await store.async_list()}
    new_entities = []
    for rule_id, entity in entities.items():
        rule = latest.pop(rule_id, None)
        if rule is None:
            entity.mark_deleted()
        else:
            entity.update_rule(rule)
    for rule in latest.values():
        entity = RuleSwitch(store, coordinator, entry, rule)
        entities[rule.rule_id] = entity
        new_entities.append(entity)
    if new_entities:
        async_add_entities(new_entities)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Disconnect the rule refresh listener when the config entry unloads."""

    unsubscribe = hass.data.get(DOMAIN, {}).get("rule_switch_unsubscribers", {}).pop(entry.entry_id, None)
    if unsubscribe:
        unsubscribe()
    return True


class RuleSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, store, coordinator, entry, rule) -> None:
        super().__init__(coordinator)
        self._store = store
        self._rule = rule
        self._attr_available = True
        self._attr_name = f"Regel aktiviert: {rule.name}"
        self._attr_unique_id = f"{entry.entry_id}_rule_{rule.rule_id}"

    @property
    def is_on(self):
        return bool(self._rule.enabled)

    @property
    def available(self):
        return bool(self._attr_available and getattr(self.coordinator, "last_update_success", True))

    def update_rule(self, rule) -> None:
        self._rule = rule
        self._attr_name = f"Regel aktiviert: {rule.name}"
        self._attr_available = True
        self.async_write_ha_state()

    def mark_deleted(self) -> None:
        self._attr_available = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._save(True)

    async def async_turn_off(self, **kwargs) -> None:
        current = await self._store.async_get(self._rule.rule_id)
        if current is None:
            self.mark_deleted()
            return
        self._rule = current
        if current.priority is Priority.CRITICAL:
            raise HomeAssistantError("Critical-Regeln dürfen nur über die geschützte Verwaltung deaktiviert werden.")
        await self._save(False)

    async def _save(self, enabled: bool) -> None:
        current = await self._store.async_get(self._rule.rule_id)
        if current is None:
            self.mark_deleted()
            return
        self._rule = current
        value = rule_to_dict(current)
        value["enabled"] = enabled
        value["version"] = self._rule.version + 1
        value["updated_at"] = datetime.now(UTC).isoformat()
        from .core.rule_store import rule_from_editor_payload
        try:
            self._rule = await self._store.async_save(
                rule_from_editor_payload(value), EditorAccess("ha-entity", frozenset({Permission.EDIT.value}))
            )
        except ValueError as err:
            raise HomeAssistantError("Die Regel wurde inzwischen geändert. Bitte den Switch erneut versuchen.") from err
        self.async_write_ha_state()

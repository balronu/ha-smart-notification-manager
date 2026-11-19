import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_notification_manager import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_notification_manager.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_and_unload_do_not_register_delivery_services(hass):
    assert await async_setup(hass, {})
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await async_setup_entry(hass, entry)
    assert hass.data[DOMAIN]["recording_enabled"] is False
    assert await async_unload_entry(hass, entry)
    assert entry.entry_id not in hass.data[DOMAIN]["entries"]
    assert not hass.services.has_service(DOMAIN, "send")


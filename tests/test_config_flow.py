import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_notification_manager.const import DOMAIN


@pytest.mark.asyncio
async def test_user_config_flow_creates_one_entry(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"language": "de", "db_path": "smart_notification_manager.sqlite3"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Smart Notification Manager"


@pytest.mark.asyncio
async def test_options_flow_has_no_delivery_fields(hass, enable_custom_integrations):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"language": "de", "db_path": "db.sqlite3"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    schema_keys = {str(key.schema if hasattr(key, "schema") else key) for key in result["data_schema"].schema}
    assert schema_keys == {"language", "db_path"}

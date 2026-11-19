import pytest
from smart_notification_manager.config_flow import (
    SmartNotificationManagerConfigFlow,
    SmartNotificationManagerOptionsFlow,
)


class ProbeConfigFlow(SmartNotificationManagerConfigFlow):
    def _async_current_entries(self):
        return []

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


class ProbeOptionsFlow(SmartNotificationManagerOptionsFlow):
    @property
    def config_entry(self):
        return self._fake_entry

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


class FakeEntry:
    def __init__(self):
        self.options = {"language": "de", "db_path": "db.sqlite3"}


@pytest.mark.asyncio
async def test_user_config_flow_creates_one_entry():
    flow = ProbeConfigFlow()
    result = await flow.async_step_user()
    assert result["type"] == "form"
    result = await flow.async_step_user({"language": "de", "db_path": "smart_notification_manager.sqlite3"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Smart Notification Manager"


@pytest.mark.asyncio
async def test_options_flow_has_no_delivery_fields():
    flow = ProbeOptionsFlow()
    flow._fake_entry = FakeEntry()
    result = await flow.async_step_init()
    assert result["type"] == "form"
    schema_keys = {str(key.schema if hasattr(key, "schema") else key) for key in result["data_schema"].schema}
    assert schema_keys == {"language", "db_path"}

from pathlib import Path

import pytest
from smart_notification_manager.core.recipient_store import RecipientStore
from smart_notification_manager.core.recipients import Recipient, RecipientDevice, RecipientGroup
from smart_notification_manager.core.repository import SQLiteRepository


@pytest.mark.asyncio
async def test_recipient_group_channel_and_preview_round_trip(tmp_path: Path):
    store = RecipientStore(SQLiteRepository(tmp_path / "manager.sqlite3"))
    await store.async_save_recipient(Recipient("michael", "Michael", devices=(RecipientDevice("phone", "Telefon", "mobile", primary=True),)))
    await store.async_save_group(RecipientGroup("family", "Familie", ("michael",)))
    await store.async_save_channel({"channel_id": "mobile", "channel_type": "mobile", "display_name": "Mobile App", "config": {"service": "notify.mobile_app_phone"}})
    await store.async_save_channel_group({"channel_group_id": "urgent", "display_name": "Dringend", "channel_ids": ["mobile"]})
    assert (await store.async_list_groups())[0].recipient_ids == ("michael",)
    assert (await store.async_list_channels())[0]["channel_type"] == "mobile"
    assert (await store.async_list_channel_groups())[0]["channel_ids"] == ("mobile",)
    preview = await store.async_preview({
        "recipients": [{"recipient_id": "michael", "display_name": "Michael", "devices": [{"device_id": "phone", "display_name": "Telefon", "channel_id": "mobile", "primary": True}]}],
        "groups": [{"group_id": "family", "display_name": "Familie", "recipient_ids": ["michael"]}],
        "group_ids": ["family"],
        "channels": [{"channel_id": "mobile", "channel_type": "mobile", "supports_media": False}],
        "template": "{{ rule_name }} / {{ trigger_entity }}",
        "values": {"rule_name": "Tür", "trigger_entity": "binary_sensor.door"},
    })
    assert len(preview["targets"]) == 1
    assert preview["message"] == "Tür / binary_sensor.door"

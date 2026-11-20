"""Phase 12 runtime acceptance through Home Assistant's official harness."""

import shutil
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from smart_notification_manager.const import CONF_DB_PATH, DOMAIN
from smart_notification_manager.core.adapters import DeliveryRequest, adapter_from_channel
from smart_notification_manager.core.delivery_service import DeliveryService
from smart_notification_manager.core.recipients import Recipient, RecipientDevice


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    source = Path(__file__).parents[1] / "custom_components" / DOMAIN
    target = Path(hass_tmp_config_dir) / "custom_components" / DOMAIN
    shutil.copytree(source, target)
    return hass_tmp_config_dir


@pytest.mark.asyncio
async def test_official_runtime_accepts_only_simulated_authorized_service_delivery(
    hass: HomeAssistant, tmp_path: Path, hass_config_dir: str, enable_custom_integrations
) -> None:
    calls: list[dict] = []

    async def simulated_notify(call: ServiceCall) -> None:
        calls.append(dict(call.data))

    hass.services.async_register("notify", "phase12_test", simulated_notify)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={"language": "de", CONF_DB_PATH: str(tmp_path / "runtime.sqlite3")},
        title="Smart Notification Manager",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "frontend", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    runtime = hass.data[DOMAIN]
    await runtime["recipient_store"].async_save_channel(
        {"channel_id": "notify-test", "channel_type": "notify", "display_name": "Testdienst", "config": {"service": "notify.phase12_test", "target_field": "target"}}
    )
    await runtime["recipient_store"].async_save_recipient(
        Recipient("recipient-owner", "Testempfänger", devices=(RecipientDevice("person-owner", "Owner", "person:owner", primary=True),))
    )
    adapter = adapter_from_channel(
        hass,
        {"channel_type": "notify", "config": {"service": "notify.phase12_test", "target_field": "target"}},
    )
    job = await DeliveryService(runtime["delivery_store"]).async_deliver(
        DeliveryRequest("phase12-runtime-attempt", "recipient-owner", "Türalarm", "Tür geöffnet", {}),
        channel_id="notify-test",
        idempotency_key="phase12-runtime-idempotency",
        adapter=adapter,
        recipient={"enabled": True, "channel_id": "person:owner"},
        authorized=True,
    )
    assert job.state == "accepted"
    assert calls == [{"message": "Tür geöffnet", "title": "Türalarm", "target": "person:owner"}]
    assert (tmp_path / "runtime.sqlite3").exists()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

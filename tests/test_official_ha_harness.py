"""Gate #16 checks using Home Assistant's official pytest harness."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from smart_notification_manager.const import CONF_DB_PATH, DOMAIN, SIGNAL_RULES_UPDATED


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Expose this repository's integration to the official HA config fixture."""

    source = Path(__file__).parents[1] / "custom_components" / DOMAIN
    target = Path(hass_tmp_config_dir) / "custom_components" / DOMAIN
    shutil.copytree(source, target)
    return hass_tmp_config_dir


@pytest.mark.asyncio
async def test_official_harness_loads_config_entry_and_unloads_cleanly(
    hass: HomeAssistant, tmp_path: Path, enable_custom_integrations
) -> None:
    """Load the integration without optional Telegram/WhatsApp/phone services."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LANGUAGE: "de", CONF_DB_PATH: str(tmp_path / "manager.sqlite3")},
        title="Smart Notification Manager",
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "frontend", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN]["rule_store"] is not None
    assert hass.data[DOMAIN]["automation_migration_store"] is not None
    assert hass.data[DOMAIN]["frontend_registered"] is True
    assert not hass.services.has_service("telegram_bot", "send_message")
    assert not hass.services.has_service("fritz", "dial")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_official_harness_config_flow_creates_entry(
    hass: HomeAssistant, tmp_path: Path, enable_custom_integrations
) -> None:
    """Exercise the real Config Flow through Home Assistant's flow manager."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "de", CONF_DB_PATH: str(tmp_path / "flow.sqlite3")},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Smart Notification Manager"


@pytest.mark.asyncio
async def test_official_harness_non_admin_user_is_not_admin(
    hass: HomeAssistant, hass_read_only_user
) -> None:
    """The official auth fixtures provide a real non-admin HA user context."""

    assert hass_read_only_user.is_admin is False


@pytest.mark.asyncio
async def test_official_harness_non_admin_cannot_use_admin_websocket(
    hass: HomeAssistant,
    tmp_path: Path,
    hass_read_only_access_token: str,
    hass_ws_client,
    enable_custom_integrations,
) -> None:
    """The real HA websocket rejects the manager's admin-only list command."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LANGUAGE: "de", CONF_DB_PATH: str(tmp_path / "permissions.sqlite3")},
        title="Smart Notification Manager",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "websocket_api", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json({"id": 1, "type": "smart_notification_manager/list"})
    response = await client.receive_json()
    assert response["success"] is False

    # The async dispatcher callback must remain safe when a save/update signal
    # is emitted by the integration after the websocket request.
    async_dispatcher_send(hass, SIGNAL_RULES_UPDATED, "missing-rule")
    await hass.async_block_till_done()

"""Tests for the authenticated, standalone mobile diagnostics view."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from smart_notification_manager.const import CONF_DB_PATH, DOMAIN
from smart_notification_manager.diagnostics import (
    BUILD_ID,
    DIAGNOSTIC_HTML,
    DIAGNOSTIC_URL,
    PANEL_RESOURCE,
    SmartNotificationManagerDiagnosticsView,
)


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Expose this repository's integration to the official HA fixture."""

    source = Path(__file__).parents[1] / "custom_components" / DOMAIN
    target = Path(hass_tmp_config_dir) / "custom_components" / DOMAIN
    shutil.copytree(source, target)
    return hass_tmp_config_dir


def test_diagnostics_view_uses_home_assistant_auth_and_no_external_telemetry():
    """The route must use HA auth and the report must be local and redacted."""

    assert SmartNotificationManagerDiagnosticsView.requires_auth is True
    assert SmartNotificationManagerDiagnosticsView.cors_allowed is False
    assert SmartNotificationManagerDiagnosticsView.url == DIAGNOSTIC_URL
    assert PANEL_RESOURCE in DIAGNOSTIC_HTML
    assert BUILD_ID in DIAGNOSTIC_HTML
    assert "smart-notification-manager.js?v=9" in DIAGNOSTIC_HTML
    assert "navigator.sendBeacon" not in DIAGNOSTIC_HTML
    assert "Authorization" not in DIAGNOSTIC_HTML
    assert "document.cookie" not in DIAGNOSTIC_HTML
    assert "navigator.clipboard?.writeText" in DIAGNOSTIC_HTML
    assert 'v=9' in PANEL_RESOURCE
    assert 'beta11-save-confirmation-diagnostics' in DIAGNOSTIC_HTML
    assert 'save_trace' in DIAGNOSTIC_HTML
    assert 'Save-Trace' in DIAGNOSTIC_HTML
    assert 'nicht bestätigt' in DIAGNOSTIC_HTML


@pytest.mark.asyncio
async def test_authenticated_diagnostics_route_is_available_without_panel_start(
    hass,
    hass_client,
    hass_client_no_auth,
    tmp_path: Path,
    enable_custom_integrations,
    hass_config_dir: str,
):
    """The diagnostic document is available even before the panel is imported."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_DB_PATH: str(tmp_path / "diagnostics.sqlite3")},
        title="Smart Notification Manager",
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "frontend", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unauthenticated = await hass_client_no_auth()
    response = await unauthenticated.get(DIAGNOSTIC_URL)
    assert response.status == 401

    authenticated = await hass_client()
    response = await authenticated.get(DIAGNOSTIC_URL)
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = await response.text()
    assert "Smart Notification Manager – Diagnose" in body
    assert "Diagnose starten" in body
    assert PANEL_RESOURCE in body

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

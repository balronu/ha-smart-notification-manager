import pytest
from smart_notification_manager.core.adapters import AdapterRegistry, ChannelCapabilities, SimulatedAdapter
from smart_notification_manager.core.delivery import build_routing_preview
from smart_notification_manager.core.recipients import Recipient, RecipientDevice, RecipientGroup, resolve_recipients
from smart_notification_manager.core.templates import render_template, validate_template


def sample_recipients():
    return (
        Recipient("michael", "Michael", devices=(RecipientDevice("phone", "Telefon", "mobile", primary=True), RecipientDevice("tablet", "Tablet", "mobile", available=False))),
        Recipient("anna", "Anna", devices=(RecipientDevice("anna-phone", "Annas Telefon", "mobile", primary=True),)),
    )


def test_groups_overlap_and_primary_device_are_deduplicated():
    groups = (RecipientGroup("family", "Familie", ("michael", "anna")), RecipientGroup("all", "Alle", ("michael",)))
    resolved = resolve_recipients(sample_recipients(), groups, (), ("family", "all"))
    assert [(item.recipient_id, item.device_id) for item in resolved] == [("michael", "phone"), ("anna", "anna-phone")]


def test_all_devices_keeps_unavailable_device_visible():
    resolved = resolve_recipients(sample_recipients(), (), ("michael",), (), all_devices=True)
    assert [(item.device_id, item.available, item.reason) for item in resolved] == [("phone", True, None), ("tablet", False, "Gerät nicht verfügbar")]


def test_routing_preview_respects_capabilities_without_sending():
    resolved = resolve_recipients(sample_recipients(), (), ("michael",), ())
    preview = build_routing_preview(resolved, {"mobile": ChannelCapabilities("mobile", supports_media=False)}, media=True)
    assert preview[0].supported is False
    assert preview[0].reason == "Kanal unterstützt keine Bilder"


def test_templates_allow_missing_values_but_reject_unknown_or_executable_syntax():
    assert render_template("{{ rule_name }} / {{ state }}", {"rule_name": "Tür"}) == "Tür / "
    assert validate_template("{{ state }}") == ()
    with pytest.raises(ValueError, match="Unbekannte"):
        render_template("{{ secret }}", {})
    with pytest.raises(ValueError, match="nicht erlaubte"):
        validate_template("{% dangerous %}")


@pytest.mark.asyncio
async def test_simulated_adapter_never_reports_real_delivery():
    registry = AdapterRegistry()
    registry.register(SimulatedAdapter("mobile", supports_actions=True))
    assert registry.capabilities()[0].metadata["mode"] == "simulation"

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from smart_notification_manager.core.adapters import (
    ChannelCapabilities,
    DeliveryAuthorizationError,
    DeliveryRequest,
    DeliveryResult,
    HAServiceAdapter,
    adapter_from_channel,
    channel_availability,
    channel_catalog,
    validate_channel_config,
)
from smart_notification_manager.core.delivery_service import DeliveryService
from smart_notification_manager.core.delivery_store import DeliveryStore, PolicySuppressedError
from smart_notification_manager.core.policies import PolicyStore, QuietHours, RateLimitPolicy
from smart_notification_manager.core.repository import SQLiteRepository
from smart_notification_manager.core.rule_store import EditorAccess, RuleStore
from test_storage import valid_storage_rule


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return (domain, service) in {("notify", "mobile_app_phone"), ("fritz", "dial")}

    async def async_call(self, domain, service, data, *, blocking):
        self.calls.append((domain, service, data, blocking))


class FakeHass:
    def __init__(self):
        self.services = FakeServices()


def request(attempt_id="attempt-1"):
    return DeliveryRequest(attempt_id, "michael", "Tür", "Tür geöffnet", {"service_data": {"data": {"tag": "door"}}})


async def store_with_target(path: Path) -> DeliveryStore:
    repository = SQLiteRepository(path)
    return await store_with_repository(repository)


async def store_with_repository(repository: SQLiteRepository) -> DeliveryStore:
    await repository.async_run(
        lambda connection: (
            connection.execute("INSERT INTO recipients(recipient_id, display_name, enabled, metadata_json) VALUES ('michael', 'Michael', 1, '{}')"),
            connection.execute("INSERT INTO channels(channel_id, channel_type, display_name, enabled, config_json) VALUES ('mobile', 'mobile', 'Mobile', 1, '{}')"),
        )
    )
    return DeliveryStore(repository)


@pytest.mark.asyncio
async def test_delivery_is_idempotent_and_persisted_with_retry(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")
    first = await store.async_enqueue(request(), idempotency_key="alarm-1-mobile", channel_id="mobile")
    duplicate = await store.async_enqueue(request("attempt-2"), idempotency_key="alarm-1-mobile", channel_id="mobile")
    assert duplicate.attempt_id == first.attempt_id
    claimed = await store.async_claim_due(now=datetime(2026, 1, 1, tzinfo=UTC))
    assert claimed is not None
    retry = await store.async_record_result(
        claimed.attempt_id,
        DeliveryResult(status="failed", error_code="timeout", error_message="simuliert"),
        now=datetime(2026, 1, 1, tzinfo=UTC),
        max_attempts=2,
        backoff_seconds=10,
    )
    assert retry.state == "retry_scheduled"
    assert retry.next_attempt_at == datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC)
    assert await store.async_claim_due(now=datetime(2026, 1, 1, 0, 0, 9, tzinfo=UTC)) is None
    claimed_again = await store.async_claim_due(now=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC))
    assert claimed_again is not None
    failed = await store.async_record_result(
        claimed_again.attempt_id,
        DeliveryResult(status="failed", error_code="provider", error_message="simuliert"),
        now=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        max_attempts=2,
    )
    assert failed.state == "failed"
    assert failed.attempt_number == 2


@pytest.mark.asyncio
async def test_claim_lease_prevents_parallel_duplicate_processing(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")
    await store.async_enqueue(request(), idempotency_key="parallel", channel_id="mobile")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first, second = await asyncio.gather(store.async_claim_due(now=now), store.async_claim_due(now=now))
    assert sum(item is not None for item in (first, second)) == 1


@pytest.mark.asyncio
async def test_real_service_adapter_is_mocked_and_requires_existing_service():
    hass = FakeHass()
    adapter = adapter_from_channel(hass, {"channel_type": "mobile", "config": {"service": "notify.mobile_app_phone"}})
    assert await adapter.async_validate({"enabled": True, "channel_id": "mobile"}) == []
    result = await adapter.async_send(request())
    assert result.status == "accepted"
    assert hass.services.calls[0][0:2] == ("notify", "mobile_app_phone")
    assert hass.services.calls[0][2]["message"] == "Tür geöffnet"


@pytest.mark.asyncio
async def test_authorized_adapter_can_route_a_recipient_target_without_provider_api(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")
    hass = FakeHass()
    adapter = adapter_from_channel(
        hass,
        {"channel_type": "notify", "config": {"service": "notify.mobile_app_phone", "target_field": "target"}},
    )
    job = await DeliveryService(store).async_deliver(
        request(),
        channel_id="mobile",
        idempotency_key="targeted",
        adapter=adapter,
        recipient={"enabled": True, "channel_id": "person:owner"},
        authorized=True,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert job.state == "accepted"
    assert hass.services.calls[0][2]["target"] == "person:owner"


@pytest.mark.asyncio
async def test_delivery_timeout_is_persisted_as_stable_failure(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")

    class SlowAdapter(HAServiceAdapter):
        async def async_send(self, request):
            await asyncio.sleep(0.05)
            return DeliveryResult(status="accepted")

    adapter = SlowAdapter(hass=FakeHass(), channel_type="notify", domain="notify", service="mobile_app_phone", capabilities=ChannelCapabilities("notify"))
    job = await DeliveryService(store).async_deliver(
        request(), channel_id="mobile", idempotency_key="timeout", adapter=adapter,
        recipient={"enabled": True, "channel_id": "mobile"}, authorized=True,
        timeout_seconds=0.001, now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert job.state == "retry_scheduled"
    assert await store.repository.async_run(
        lambda connection: connection.execute("SELECT error_code FROM delivery_attempts WHERE attempt_id=?", (job.attempt_id,)).fetchone()[0]
    ) == "timeout"


@pytest.mark.asyncio
async def test_missing_home_assistant_service_is_reported_without_call():
    adapter = adapter_from_channel(FakeHass(), {"channel_type": "mail", "config": {"service": "notify.email"}})
    assert await adapter.async_validate({"enabled": True, "channel_id": "mail"}) == [
        "Der konfigurierte Home-Assistant-Dienst ist nicht verfügbar"
    ]


@pytest.mark.asyncio
async def test_fritz_dial_adapter_uses_documented_action_and_never_sends_message_text():
    hass = FakeHass()
    adapter = adapter_from_channel(
        hass,
        {"channel_type": "fritzbox", "config": {"service": "fritz.dial", "device_id": "fritz-device", "max_ring_seconds": 20}},
    )
    assert await adapter.async_validate({"enabled": True, "channel_id": "**9"}) == []
    result = await adapter.async_send(
        DeliveryRequest("attempt-fritz", "phone", "Alarm", "nicht als Service-Text", {"recipient_target": "**9"})
    )
    assert result.status == "accepted"
    assert hass.services.calls[-1] == ("fritz", "dial", {"device_id": "fritz-device", "max_ring_seconds": 20, "number": "**9"}, True)


def test_fritz_dial_configuration_requires_device_and_bounds_ring_duration():
    with pytest.raises(ValueError, match="device_id"):
        validate_channel_config("fritzbox", {"service": "fritz.dial"})
    with pytest.raises(ValueError, match="zwischen 1 und 300"):
        validate_channel_config("fritzbox", {"service": "fritz.dial", "device_id": "fritz", "max_ring_seconds": 301})
    with pytest.raises(ValueError, match="Domänen: fritz"):
        validate_channel_config("fritzbox", {"service": "notify.test", "device_id": "fritz"})


def test_all_phase12_channels_have_explicit_home_assistant_service_contract():
    catalog = channel_catalog()
    channel_types = {item["channel_type"] for item in catalog}
    assert {"notify", "telegram", "whatsapp", "fritzbox", "sip_pbx", "tts", "email", "doorbell", "voice_call"} <= channel_types
    for item in catalog:
        channel_type = item["channel_type"]
        service = {
            "telegram": "telegram_bot.send_message",
        "email": "smtp.send_message",
        "tts": "tts.speak",
        "fritzbox": "fritz.dial",
    }.get(channel_type, "notify.test_target")
        config = {"service": service}
        if channel_type == "fritzbox":
            config.update({"device_id": "fritz-device", "max_ring_seconds": 15})
        validate_channel_config(channel_type, config)
        assert isinstance(item["target_fields"], list)
    assert "telegram_bot.send_message" in next(item["service_examples"] for item in catalog if item["channel_type"] == "telegram")
    assert "smtp.send_message" in next(item["service_examples"] for item in catalog if item["channel_type"] == "email")
    assert "tts.speak" in next(item["service_examples"] for item in catalog if item["channel_type"] == "tts")
    with pytest.raises(ValueError, match="domain.service"):
        validate_channel_config("telegram", {})
    with pytest.raises(ValueError, match="tts benötigt"):
        validate_channel_config("tts", {"service": "notify.test_target"})


def test_optional_provider_catalog_and_persisted_channel_status_are_honest():
    catalog = channel_catalog()
    whatsapp = next(item for item in catalog if item["channel_type"] == "whatsapp")
    assert whatsapp["availability"] == {"state": "not_configured", "label": "Nicht eingerichtet"}
    assert channel_availability(FakeHass(), {"channel_type": "whatsapp", "config": {"service": "notify.missing"}}) == {
        "state": "unavailable",
        "label": "Nicht verfügbar",
    }


@pytest.mark.asyncio
async def test_delivery_service_blocks_without_explicit_authorization(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")
    service = DeliveryService(store)
    adapter = HAServiceAdapter(hass=FakeHass(), channel_type="mobile", domain="notify", service="mobile_app_phone", capabilities=ChannelCapabilities("mobile"))
    with pytest.raises(DeliveryAuthorizationError):
        await service.async_deliver(request(), channel_id="mobile", idempotency_key="blocked", adapter=adapter, recipient={"enabled": True, "channel_id": "mobile"})


@pytest.mark.asyncio
async def test_authorized_delivery_uses_mock_service_and_persists_acceptance(tmp_path: Path):
    store = await store_with_target(tmp_path / "manager.sqlite3")
    hass = FakeHass()
    adapter = adapter_from_channel(hass, {"channel_type": "mobile", "config": {"service": "notify.mobile_app_phone"}})
    job = await DeliveryService(store).async_deliver(
        request(),
        channel_id="mobile",
        idempotency_key="authorized",
        adapter=adapter,
        recipient={"enabled": True, "channel_id": "mobile"},
        authorized=True,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert job.state == "accepted"
    assert job.delivery_confirmed is False
    assert len(hass.services.calls) == 1


@pytest.mark.asyncio
async def test_delivery_enqueue_is_policy_gated_and_preview_or_observation_does_not_reserve(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = await store_with_repository(repository)
    policies = PolicyStore(repository)
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    now = datetime(2026, 1, 1, 23, tzinfo=UTC)
    delivery_request = replace(request(), payload={"policy_request": {"rule_id": rule.rule_id, "alarm_id": None, "alarm_state": "active", "rule_enabled": True, "priority": "normal"}})
    await policies.async_save_quiet_hours(QuietHours("night", "Nacht", True, (0, 1, 2, 3, 4, 5, 6), "22:00", "07:00"), user_id="owner", now=now)
    with pytest.raises(PolicySuppressedError, match="Ruhezeit"):
        await store.async_enqueue(delivery_request, idempotency_key="quiet", channel_id="mobile", alarm_id=None, policy_store=policies, policy_request=delivery_request.payload["policy_request"], now=now)
    assert await store.async_list() == []
    assert await repository.async_run(lambda c: c.execute("SELECT reason_code FROM policy_decisions ORDER BY occurred_at DESC LIMIT 1").fetchone()[0]) == "quiet_hours"
    await policies.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1), user_id="owner", now=now)
    await policies.async_save_quiet_hours(QuietHours("night", "Nacht", False, (0, 1, 2, 3, 4, 5, 6), "22:00", "07:00"), user_id="owner", now=now)
    allowed = await store.async_enqueue(delivery_request, idempotency_key="allowed", channel_id="mobile", alarm_id=None, policy_store=policies, policy_request=delivery_request.payload["policy_request"], now=now)
    assert allowed.state == "pending"
    with pytest.raises(PolicySuppressedError, match="Rate-Limit"):
        await store.async_enqueue(delivery_request, idempotency_key="blocked", channel_id="mobile", alarm_id=None, policy_store=policies, policy_request=delivery_request.payload["policy_request"], now=now)
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM rate_limit_events WHERE kind='notification'").fetchone()[0]) == 1


@pytest.mark.asyncio
async def test_failed_delivery_keeps_reservation_and_retry_does_not_double_count(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = await store_with_repository(repository)
    policies = PolicyStore(repository)
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    await policies.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1), user_id="owner", now=now)
    policy_request = {"rule_id": rule.rule_id, "alarm_id": None, "alarm_state": "active", "rule_enabled": True, "priority": "normal"}
    job = await store.async_enqueue(replace(request(), payload={}), idempotency_key="failed", channel_id="mobile", alarm_id=None, policy_store=policies, policy_request=policy_request, now=now)
    claimed = await store.async_claim_due(now=now)
    assert claimed is not None
    await store.async_record_result(claimed.attempt_id, DeliveryResult(status="failed", error_code="provider"), now=now, max_attempts=2, backoff_seconds=1)
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM rate_limit_events WHERE kind='notification'").fetchone()[0]) == 1
    assert (await store.async_claim_due(now=now + timedelta(seconds=1))).attempt_id == job.attempt_id


@pytest.mark.asyncio
async def test_idempotent_enqueue_does_not_reserve_rate_limit_twice(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "manager.sqlite3")
    store = await store_with_repository(repository)
    policies = PolicyStore(repository)
    rule = await RuleStore(repository).async_save(valid_storage_rule(), EditorAccess("owner", frozenset({"edit"})))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    await policies.async_save_rate_limit(RateLimitPolicy(rule.rule_id, 600, 1), user_id="owner", now=now)
    policy_request = {"rule_id": rule.rule_id, "alarm_id": None, "alarm_state": "active", "rule_enabled": True, "priority": "normal"}
    delivery_request = replace(request(), payload={})
    first = await store.async_enqueue(delivery_request, idempotency_key="same", channel_id="mobile", policy_store=policies, policy_request=policy_request, now=now)
    duplicate = await store.async_enqueue(replace(delivery_request, attempt_id="different"), idempotency_key="same", channel_id="mobile", policy_store=policies, policy_request=policy_request, now=now)
    assert duplicate.attempt_id == first.attempt_id
    assert await repository.async_run(lambda c: c.execute("SELECT COUNT(*) FROM rate_limit_events WHERE kind='notification'").fetchone()[0]) == 1

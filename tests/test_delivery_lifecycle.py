import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from smart_notification_manager.core.adapters import (
    ChannelCapabilities,
    DeliveryAuthorizationError,
    DeliveryRequest,
    DeliveryResult,
    HAServiceAdapter,
    adapter_from_channel,
)
from smart_notification_manager.core.delivery_service import DeliveryService
from smart_notification_manager.core.delivery_store import DeliveryStore
from smart_notification_manager.core.repository import SQLiteRepository


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return (domain, service) == ("notify", "mobile_app_phone")

    async def async_call(self, domain, service, data, *, blocking):
        self.calls.append((domain, service, data, blocking))


class FakeHass:
    def __init__(self):
        self.services = FakeServices()


def request(attempt_id="attempt-1"):
    return DeliveryRequest(attempt_id, "michael", "Tür", "Tür geöffnet", {"service_data": {"data": {"tag": "door"}}})


async def store_with_target(path: Path) -> DeliveryStore:
    repository = SQLiteRepository(path)
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
async def test_missing_home_assistant_service_is_reported_without_call():
    adapter = adapter_from_channel(FakeHass(), {"channel_type": "mail", "config": {"service": "notify.email"}})
    assert await adapter.async_validate({"enabled": True, "channel_id": "mail"}) == [
        "Der konfigurierte Home-Assistant-Dienst ist nicht verfügbar"
    ]


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

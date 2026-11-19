"""Recipient and group resolution without provider or Home Assistant side effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecipientDevice:
    device_id: str
    display_name: str
    channel_id: str
    available: bool = True
    primary: bool = False


@dataclass(frozen=True, slots=True)
class Recipient:
    recipient_id: str
    display_name: str
    enabled: bool = True
    devices: tuple[RecipientDevice, ...] = ()


@dataclass(frozen=True, slots=True)
class RecipientGroup:
    group_id: str
    display_name: str
    recipient_ids: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ResolvedRecipient:
    recipient_id: str
    recipient_name: str
    device_id: str
    device_name: str
    channel_id: str
    available: bool
    reason: str | None = None


def resolve_recipients(
    recipients: tuple[Recipient, ...],
    groups: tuple[RecipientGroup, ...],
    selected_recipient_ids: tuple[str, ...],
    selected_group_ids: tuple[str, ...],
    *,
    all_devices: bool = False,
) -> tuple[ResolvedRecipient, ...]:
    """Expand groups and devices deterministically, removing exact overlaps."""

    by_id = {item.recipient_id: item for item in recipients}
    group_by_id = {item.group_id: item for item in groups}
    ids: list[str] = list(selected_recipient_ids)
    for group_id in selected_group_ids:
        group = group_by_id.get(group_id)
        if group and group.enabled:
            ids.extend(group.recipient_ids)
    resolved: list[ResolvedRecipient] = []
    seen: set[tuple[str, str, str]] = set()
    for recipient_id in ids:
        recipient = by_id.get(recipient_id)
        if recipient is None or not recipient.enabled:
            continue
        devices = recipient.devices if all_devices else _primary_devices(recipient.devices)
        if not devices:
            key = (recipient_id, "", "")
            if key not in seen:
                seen.add(key)
                resolved.append(ResolvedRecipient(recipient_id, recipient.display_name, "", "", "", False, "Kein Gerät konfiguriert"))
            continue
        for device in devices:
            key = (recipient_id, device.device_id, device.channel_id)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(
                ResolvedRecipient(
                    recipient_id,
                    recipient.display_name,
                    device.device_id,
                    device.display_name,
                    device.channel_id,
                    device.available,
                    None if device.available else "Gerät nicht verfügbar",
                )
            )
    return tuple(resolved)


def _primary_devices(devices: tuple[RecipientDevice, ...]) -> tuple[RecipientDevice, ...]:
    primary = tuple(device for device in devices if device.primary)
    return primary[:1] or devices[:1]

"""Async persistence for Phase 3 recipients, groups, channels and templates."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .adapters import ChannelCapabilities
from .delivery import build_routing_preview
from .recipients import Recipient, RecipientDevice, RecipientGroup, resolve_recipients
from .repository import SQLiteRepository
from .templates import render_template, validate_template


class RecipientStore:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_list_recipients(self) -> list[Recipient]:
        def operation(connection):
            result = []
            for row in connection.execute("SELECT recipient_id, display_name, enabled, metadata_json FROM recipients ORDER BY display_name COLLATE NOCASE"):
                metadata = json.loads(row[3] or "{}")
                result.append(Recipient(row[0], row[1], bool(row[2]), tuple(RecipientDevice(**device) for device in metadata.get("devices", []))))
            return result

        return await self.repository.async_run(operation)

    async def async_save_recipient(self, recipient: Recipient) -> Recipient:
        payload = json.dumps({"devices": [asdict(device) for device in recipient.devices]}, ensure_ascii=False, sort_keys=True)

        def operation(connection):
            connection.execute(
                """INSERT INTO recipients(recipient_id, display_name, entity_id, enabled, metadata_json)
                VALUES (?, ?, NULL, ?, ?) ON CONFLICT(recipient_id) DO UPDATE SET display_name=excluded.display_name,
                enabled=excluded.enabled, metadata_json=excluded.metadata_json""",
                (recipient.recipient_id, recipient.display_name, int(recipient.enabled), payload),
            )
            return recipient

        return await self.repository.async_run(operation)

    async def async_list_groups(self) -> list[RecipientGroup]:
        def operation(connection):
            groups = []
            for row in connection.execute("SELECT group_id, display_name, enabled FROM recipient_groups ORDER BY display_name COLLATE NOCASE"):
                members = tuple(item[0] for item in connection.execute("SELECT recipient_id FROM recipient_group_members WHERE group_id = ? ORDER BY recipient_id", (row[0],)))
                groups.append(RecipientGroup(row[0], row[1], members, bool(row[2])))
            return groups

        return await self.repository.async_run(operation)

    async def async_save_group(self, group: RecipientGroup) -> RecipientGroup:
        def operation(connection):
            connection.execute("INSERT INTO recipient_groups(group_id, display_name, enabled) VALUES (?, ?, ?) ON CONFLICT(group_id) DO UPDATE SET display_name=excluded.display_name, enabled=excluded.enabled", (group.group_id, group.display_name, int(group.enabled)))
            connection.execute("DELETE FROM recipient_group_members WHERE group_id = ?", (group.group_id,))
            connection.executemany("INSERT INTO recipient_group_members(group_id, recipient_id) VALUES (?, ?)", [(group.group_id, item) for item in dict.fromkeys(group.recipient_ids)])
            return group

        return await self.repository.async_run(operation)

    async def async_delete_recipient(self, recipient_id: str) -> None:
        await self.repository.async_run(lambda connection: connection.execute("DELETE FROM recipients WHERE recipient_id=?", (recipient_id,)))

    async def async_delete_channel_group(self, group_id: str) -> None:
        await self.repository.async_run(lambda connection: connection.execute("DELETE FROM channel_groups WHERE channel_group_id=?", (group_id,)))

    async def async_list_channels(self) -> list[dict[str, Any]]:
        def operation(connection):
            return [{"channel_id": row[0], "channel_type": row[1], "display_name": row[2], "enabled": bool(row[3]), "config": json.loads(row[4] or "{}")} for row in connection.execute("SELECT channel_id, channel_type, display_name, enabled, config_json FROM channels ORDER BY display_name COLLATE NOCASE")]

        return await self.repository.async_run(operation)

    async def async_save_channel(self, channel: dict[str, Any]) -> dict[str, Any]:
        required = {"channel_id", "channel_type", "display_name"}
        if not required <= channel.keys():
            raise ValueError("Kanal benötigt ID, Typ und Anzeigename")
        config = channel.get("config", {})

        def operation(connection):
            connection.execute("INSERT INTO channels(channel_id, channel_type, display_name, enabled, config_json) VALUES (?, ?, ?, ?, ?) ON CONFLICT(channel_id) DO UPDATE SET channel_type=excluded.channel_type, display_name=excluded.display_name, enabled=excluded.enabled, config_json=excluded.config_json", (channel["channel_id"], channel["channel_type"], channel["display_name"], int(channel.get("enabled", True)), json.dumps(config, ensure_ascii=False, sort_keys=True)))
            return {**channel, "config": config, "enabled": bool(channel.get("enabled", True))}

        return await self.repository.async_run(operation)

    async def async_list_channel_groups(self) -> list[dict[str, Any]]:
        def operation(connection):
            groups = []
            for row in connection.execute("SELECT channel_group_id, display_name, enabled FROM channel_groups ORDER BY display_name COLLATE NOCASE"):
                members = tuple(item[0] for item in connection.execute("SELECT channel_id FROM channel_group_members WHERE channel_group_id=? ORDER BY channel_id", (row[0],)))
                groups.append({"channel_group_id": row[0], "display_name": row[1], "enabled": bool(row[2]), "channel_ids": members})
            return groups

        return await self.repository.async_run(operation)

    async def async_save_channel_group(self, group: dict[str, Any]) -> dict[str, Any]:
        required = {"channel_group_id", "display_name"}
        if not required <= group.keys():
            raise ValueError("Kanalgruppe benötigt ID und Anzeigename")
        channel_ids = tuple(dict.fromkeys(group.get("channel_ids", [])))

        def operation(connection):
            connection.execute(
                "INSERT INTO channel_groups(channel_group_id, display_name, enabled) VALUES (?, ?, ?) ON CONFLICT(channel_group_id) DO UPDATE SET display_name=excluded.display_name, enabled=excluded.enabled",
                (group["channel_group_id"], group["display_name"], int(group.get("enabled", True))),
            )
            connection.execute("DELETE FROM channel_group_members WHERE channel_group_id=?", (group["channel_group_id"],))
            connection.executemany("INSERT INTO channel_group_members(channel_group_id, channel_id) VALUES (?, ?)", [(group["channel_group_id"], channel_id) for channel_id in channel_ids])
            return {**group, "enabled": bool(group.get("enabled", True)), "channel_ids": channel_ids}

        return await self.repository.async_run(operation)

    async def async_save_template(self, template: dict[str, Any]) -> dict[str, Any]:
        validate_template(template.get("body", ""))
        now = datetime.now(UTC).isoformat()

        def operation(connection):
            connection.execute("INSERT INTO message_templates(template_id, name, body, language, version, enabled) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(template_id) DO UPDATE SET name=excluded.name, body=excluded.body, language=excluded.language, version=excluded.version, enabled=excluded.enabled", (template["template_id"], template["name"], template["body"], template.get("language", "de"), int(template.get("version", 1)), int(template.get("enabled", True))))
            return {**template, "updated_at": now}

        return await self.repository.async_run(operation)

    async def async_list_templates(self) -> list[dict[str, Any]]:
        return await self.repository.async_run(lambda connection: [{"template_id": row[0], "name": row[1], "body": row[2], "language": row[3], "version": row[4], "enabled": bool(row[5])} for row in connection.execute("SELECT template_id, name, body, language, version, enabled FROM message_templates ORDER BY name COLLATE NOCASE")])

    async def async_delete_template(self, template_id: str) -> None:
        await self.repository.async_run(lambda connection: connection.execute("DELETE FROM message_templates WHERE template_id=?", (template_id,)))

    async def async_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        recipient_values = payload.get("recipients")
        group_values = payload.get("groups")
        if recipient_values is None:
            recipient_values = [asdict(item) for item in await self.async_list_recipients()]
        if group_values is None:
            group_values = [asdict(item) for item in await self.async_list_groups()]
        recipients = tuple(_recipient_from_dict(item) for item in recipient_values)
        groups = tuple(RecipientGroup(item["group_id"], item["display_name"], tuple(item.get("recipient_ids", [])), bool(item.get("enabled", True))) for item in group_values)
        resolved = resolve_recipients(recipients, groups, tuple(payload.get("recipient_ids", [])), tuple(payload.get("group_ids", [])), all_devices=bool(payload.get("all_devices", False)))
        capabilities = {
            item["channel_id"]: ChannelCapabilities(
                item["channel_type"],
                bool(item.get("supports_title", True)),
                bool(item.get("supports_actions", False)),
                bool(item.get("supports_media", False)),
                bool(item.get("supports_feedback", False)),
            )
            for item in payload.get("channels", [])
        }
        targets = build_routing_preview(resolved, capabilities, media=bool(payload.get("media", False)), actions=bool(payload.get("actions", False)))
        rendered = render_template(payload.get("template", ""), payload.get("values", {})) if payload.get("template") is not None else ""
        return {"targets": [asdict(target) for target in targets], "message": rendered}


def _recipient_from_dict(value: dict[str, Any]) -> Recipient:
    return Recipient(value["recipient_id"], value["display_name"], bool(value.get("enabled", True)), tuple(RecipientDevice(**device) for device in value.get("devices", [])))

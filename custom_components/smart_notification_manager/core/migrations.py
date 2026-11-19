"""Versioned SQLite schema migrations."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 1


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive migrations in one transaction."""

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError("database schema is newer than this integration")
    if version == 0:
        _migration_v1(connection)
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")


def _migration_v1(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS rules (
            rule_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rule_versions (
            rule_version_id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL REFERENCES rules(rule_id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            definition_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(rule_id, version)
        );
        CREATE TABLE IF NOT EXISTS alarm_instances (
            alarm_id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL REFERENCES rules(rule_id),
            cause_key TEXT NOT NULL,
            alarm_state TEXT NOT NULL,
            acknowledgement_state TEXT NOT NULL,
            delivery_state TEXT NOT NULL,
            escalation_state TEXT NOT NULL,
            closure_reason TEXT,
            technical_error TEXT,
            started_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_alarm_cause
            ON alarm_instances(rule_id, cause_key)
            WHERE alarm_state IN ('active', 'acknowledged');
        CREATE TABLE IF NOT EXISTS alarm_events (
            event_id TEXT PRIMARY KEY,
            alarm_id TEXT NOT NULL REFERENCES alarm_instances(alarm_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS acknowledgements (
            acknowledgement_id TEXT PRIMARY KEY,
            alarm_id TEXT NOT NULL REFERENCES alarm_instances(alarm_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            acknowledged_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recipients (
            recipient_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            entity_id TEXT,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS recipient_groups (
            group_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS recipient_group_members (
            group_id TEXT NOT NULL REFERENCES recipient_groups(group_id) ON DELETE CASCADE,
            recipient_id TEXT NOT NULL REFERENCES recipients(recipient_id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, recipient_id)
        );
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            config_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS channel_groups (
            channel_group_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS channel_group_members (
            channel_group_id TEXT NOT NULL REFERENCES channel_groups(channel_group_id) ON DELETE CASCADE,
            channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
            PRIMARY KEY (channel_group_id, channel_id)
        );
        CREATE TABLE IF NOT EXISTS delivery_attempts (
            attempt_id TEXT PRIMARY KEY,
            alarm_id TEXT REFERENCES alarm_instances(alarm_id) ON DELETE SET NULL,
            rule_id TEXT REFERENCES rules(rule_id) ON DELETE SET NULL,
            recipient_id TEXT REFERENCES recipients(recipient_id) ON DELETE SET NULL,
            channel_id TEXT REFERENCES channels(channel_id) ON DELETE SET NULL,
            state TEXT NOT NULL,
            provider_message_id TEXT,
            error_code TEXT,
            error_message TEXT,
            attempted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            task_id TEXT PRIMARY KEY,
            rule_id TEXT REFERENCES rules(rule_id) ON DELETE CASCADE,
            run_at TEXT NOT NULL,
            state TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS message_templates (
            template_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'de',
            version INTEGER NOT NULL DEFAULT 1,
            enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS saved_filters (
            filter_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            definition_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS statistics_daily (
            day TEXT NOT NULL,
            key TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(day, key)
        );
        CREATE TABLE IF NOT EXISTS statistics_monthly (
            month TEXT NOT NULL,
            key TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(month, key)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            occurred_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_alarm_events_alarm_time ON alarm_events(alarm_id, occurred_at);
        CREATE INDEX IF NOT EXISTS ix_delivery_attempts_alarm_time ON delivery_attempts(alarm_id, attempted_at);
        CREATE INDEX IF NOT EXISTS ix_audit_log_time ON audit_log(occurred_at);
        """
    )


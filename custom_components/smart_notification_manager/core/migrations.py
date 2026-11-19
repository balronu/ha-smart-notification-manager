"""Versioned SQLite schema migrations."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 6


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive migrations atomically.

    ``sqlite3.Connection.executescript`` implicitly commits before running a
    script.  Migration statements are therefore executed one at a time inside
    an explicit transaction so a failed migration cannot leave a partial
    schema behind.
    """

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError("database schema is newer than this integration")
    while version < CURRENT_SCHEMA_VERSION:
        try:
            connection.execute("BEGIN")
            next_version = version + 1
            if next_version == 1:
                _migration_v1(connection)
            elif next_version == 2:
                _migration_v2(connection)
            elif next_version == 3:
                _migration_v3(connection)
            elif next_version == 4:
                _migration_v4(connection)
            elif next_version == 5:
                _migration_v5(connection)
            elif next_version == 6:
                _migration_v6(connection)
            else:  # pragma: no cover - guarded by CURRENT_SCHEMA_VERSION
                raise RuntimeError(f"missing migration {next_version}")
            connection.execute(f"PRAGMA user_version = {next_version}")
            connection.commit()
            version = next_version
        except BaseException:
            connection.rollback()
            raise


def _migration_v1(connection: sqlite3.Connection) -> None:
    _execute_sql_statements(
        connection,
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
        """,
    )


def _migration_v2(connection: sqlite3.Connection) -> None:
    """Add editable rule metadata without touching existing alarm history."""

    _execute_sql_statements(
        connection,
        """
        ALTER TABLE rules ADD COLUMN description TEXT NOT NULL DEFAULT '';
        ALTER TABLE rules ADD COLUMN area_id TEXT;
        ALTER TABLE rules ADD COLUMN area_name TEXT;
        ALTER TABLE rules ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
            CHECK (priority IN ('info', 'normal', 'warning', 'critical'));
        ALTER TABLE rules ADD COLUMN deleted_at TEXT;
        CREATE INDEX IF NOT EXISTS ix_rules_enabled ON rules(enabled, deleted_at);
        """,
    )


def _migration_v3(connection: sqlite3.Connection) -> None:
    """Add idempotent delivery-job state without changing alarm history."""

    _execute_sql_statements(
        connection,
        """
        ALTER TABLE delivery_attempts ADD COLUMN idempotency_key TEXT;
        ALTER TABLE delivery_attempts ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE delivery_attempts ADD COLUMN next_attempt_at TEXT;
        ALTER TABLE delivery_attempts ADD COLUMN lease_until TEXT;
        ALTER TABLE delivery_attempts ADD COLUMN delivery_confirmed INTEGER NOT NULL DEFAULT 0
            CHECK (delivery_confirmed IN (0, 1));
        ALTER TABLE delivery_attempts ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_delivery_idempotency
            ON delivery_attempts(idempotency_key) WHERE idempotency_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ix_delivery_due
            ON delivery_attempts(state, next_attempt_at, lease_until);
        """,
    )


def _migration_v4(connection: sqlite3.Connection) -> None:
    """Add durable Phase-4 alarm lifecycle, acknowledgement and escalation data."""

    _execute_sql_statements(
        connection,
        """
        ALTER TABLE alarm_instances ADD COLUMN entity_id TEXT NOT NULL DEFAULT '';
        ALTER TABLE alarm_instances ADD COLUMN friendly_name TEXT NOT NULL DEFAULT '';
        ALTER TABLE alarm_instances ADD COLUMN area_id TEXT;
        ALTER TABLE alarm_instances ADD COLUMN area_name TEXT;
        ALTER TABLE alarm_instances ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal';
        ALTER TABLE alarm_instances ADD COLUMN previous_state TEXT;
        ALTER TABLE alarm_instances ADD COLUMN current_state TEXT;
        ALTER TABLE alarm_instances ADD COLUMN pending_until TEXT;
        ALTER TABLE alarm_instances ADD COLUMN acknowledged_by TEXT;
        ALTER TABLE alarm_instances ADD COLUMN acknowledged_at TEXT;
        ALTER TABLE alarm_instances ADD COLUMN acknowledgement_scope TEXT NOT NULL DEFAULT 'all';
        ALTER TABLE alarm_instances ADD COLUMN critical_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (critical_confirmed IN (0, 1));
        ALTER TABLE alarm_instances ADD COLUMN escalation_level INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE alarm_instances ADD COLUMN overdue_at TEXT;
        ALTER TABLE alarm_instances ADD COLUMN closed_at TEXT;
        ALTER TABLE alarm_instances ADD COLUMN closed_by TEXT;
        ALTER TABLE alarm_instances ADD COLUMN updated_at TEXT;
        ALTER TABLE alarm_instances ADD COLUMN repeat_interval_seconds INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE alarm_instances ADD COLUMN max_repeats INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE alarm_instances ADD COLUMN repeat_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE alarm_instances ADD COLUMN next_repeat_at TEXT;
        ALTER TABLE alarm_instances ADD COLUMN repeat_only_unacknowledged INTEGER NOT NULL DEFAULT 0 CHECK (repeat_only_unacknowledged IN (0, 1));
        ALTER TABLE alarm_instances ADD COLUMN max_duration_seconds INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE alarm_instances ADD COLUMN escalation_json TEXT NOT NULL DEFAULT '[]';
        ALTER TABLE alarm_instances ADD COLUMN parent_alarm_id TEXT;
        ALTER TABLE acknowledgements ADD COLUMN scope TEXT NOT NULL DEFAULT 'all';
        ALTER TABLE acknowledgements ADD COLUMN critical_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (critical_confirmed IN (0, 1));
        DROP INDEX IF EXISTS uq_active_alarm_cause;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_alarm_cause
            ON alarm_instances(rule_id, cause_key)
            WHERE alarm_state IN ('pending', 'active', 'overdue');
        CREATE INDEX IF NOT EXISTS ix_alarm_state_due ON alarm_instances(alarm_state, pending_until, next_repeat_at, overdue_at);
        """,
    )


def _migration_v5(connection: sqlite3.Connection) -> None:
    """Pin the triggering rule and persist per-recipient acknowledgement policy."""

    _execute_sql_statements(
        connection,
        """
        ALTER TABLE alarm_instances ADD COLUMN rule_version INTEGER;
        ALTER TABLE alarm_instances ADD COLUMN acknowledgement_mode TEXT NOT NULL DEFAULT 'any'
            CHECK (acknowledgement_mode IN ('any', 'all_required'));
        ALTER TABLE alarm_instances ADD COLUMN required_recipient_ids_json TEXT NOT NULL DEFAULT '[]';
        CREATE INDEX IF NOT EXISTS ix_acknowledgements_alarm_user
            ON acknowledgements(alarm_id, user_id);
        """,
    )


def _migration_v6(connection: sqlite3.Connection) -> None:
    """Persist Phase-5 notification policies without changing alarm state."""

    _execute_sql_statements(
        connection,
        """
        CREATE TABLE IF NOT EXISTS quiet_hours (
            quiet_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            weekdays_json TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]',
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'UTC',
            rule_exceptions_json TEXT NOT NULL DEFAULT '[]',
            priority_exceptions_json TEXT NOT NULL DEFAULT '["critical"]',
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notification_pauses (
            pause_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK (scope_type IN ('global','rule','category','entity')),
            scope_id TEXT,
            starts_at TEXT NOT NULL,
            ends_at TEXT,
            reason TEXT NOT NULL,
            user_id TEXT NOT NULL,
            critical_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (critical_confirmed IN (0, 1)),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_notification_pauses_active ON notification_pauses(active, starts_at, ends_at);
        CREATE TABLE IF NOT EXISTS rate_limit_policies (
            rule_id TEXT PRIMARY KEY REFERENCES rules(rule_id) ON DELETE CASCADE,
            window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
            max_notifications INTEGER NOT NULL CHECK (max_notifications > 0),
            critical_exempt INTEGER NOT NULL DEFAULT 1 CHECK (critical_exempt IN (0, 1)),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            event_id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL REFERENCES rules(rule_id) ON DELETE CASCADE,
            alarm_id TEXT,
            occurred_at TEXT NOT NULL,
            kind TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_rate_limit_events_rule_time ON rate_limit_events(rule_id, occurred_at);
        CREATE TABLE IF NOT EXISTS rule_dependencies (
            rule_id TEXT NOT NULL REFERENCES rules(rule_id) ON DELETE CASCADE,
            depends_on_rule_id TEXT NOT NULL REFERENCES rules(rule_id) ON DELETE CASCADE,
            expected_state TEXT NOT NULL CHECK (expected_state IN ('active','inactive')),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(rule_id, depends_on_rule_id)
        );
        CREATE TABLE IF NOT EXISTS observation_modes (
            rule_id TEXT PRIMARY KEY REFERENCES rules(rule_id) ON DELETE CASCADE,
            enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
            critical_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (critical_confirmed IN (0, 1)),
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS policy_decisions (
            decision_id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            alarm_id TEXT,
            action TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            reason_de TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_policy_decisions_rule_time ON policy_decisions(rule_id, occurred_at);
        """,
    )


def _execute_sql_statements(connection: sqlite3.Connection, script: str) -> None:
    """Execute a SQL script without ``executescript``'s implicit commit."""

    statement_lines: list[str] = []
    for line in script.splitlines(keepends=True):
        statement_lines.append(line)
        statement = "".join(statement_lines)
        if sqlite3.complete_statement(statement):
            if statement.strip():
                connection.execute(statement)
            statement_lines.clear()
    remainder = "".join(statement_lines).strip()
    if remainder:
        raise sqlite3.ProgrammingError("incomplete migration statement")

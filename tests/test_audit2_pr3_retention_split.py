# SPDX-FileCopyrightText: 2026 Nav-Prak <naveenprakaasam@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Raw-payload retention is split from aggregate-metric (row) retention.

Raw free-text columns (trace/span input/output/error, session raw_line) expire
on their own column-level TTL, separate from the row TTL that governs metrics.

Imports are deferred into the tests because other suites mock
``services.clickhouse`` at import time, which would break a module-level import.
"""


def test_raw_retention_default_is_registered_and_separate():
    from services.dynamic_settings import DEFAULTS

    assert DEFAULTS["data.raw_retention_days"] == "30"
    # Distinct from the aggregate-metric/row retention default.
    assert "data.retention_days" in DEFAULTS
    assert DEFAULTS["data.raw_retention_days"] != DEFAULTS["data.retention_days"]


def test_raw_payload_ttl_targets_only_payload_columns():
    from services.clickhouse.schema import _raw_payload_ttl_statements

    stmts = _raw_payload_ttl_statements(7)
    blob = "\n".join(stmts)

    # The raw free-text payload columns are targeted...
    assert "ALTER TABLE traces MODIFY COLUMN input" in blob
    assert "ALTER TABLE traces MODIFY COLUMN output" in blob
    assert "ALTER TABLE spans MODIFY COLUMN input" in blob
    assert "ALTER TABLE spans MODIFY COLUMN output" in blob
    assert "ALTER TABLE spans MODIFY COLUMN error" in blob
    assert "ALTER TABLE session_events MODIFY COLUMN raw_line" in blob

    # ...as column TTLs (not a row-level MODIFY TTL) with the requested interval,
    # leaving metric/identifier columns untouched.
    assert all("INTERVAL 7 DAY" in s for s in stmts)
    assert "MODIFY TTL" not in blob
    assert "token_count" not in blob


def test_raw_payload_ttl_interval_tracks_days():
    from services.clickhouse.schema import _raw_payload_ttl_statements

    assert all("INTERVAL 1 DAY" in s for s in _raw_payload_ttl_statements(1))
    assert all("INTERVAL 365 DAY" in s for s in _raw_payload_ttl_statements(365))

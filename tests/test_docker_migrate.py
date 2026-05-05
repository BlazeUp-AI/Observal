"""Tests for docker/migrate.py — smart database migration script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add docker/ to path so we can import migrate
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
import migrate


# ── Helpers ──────────────────────────────────────────────────────────

class AsyncCM:
    """Async context manager mock."""
    def __init__(self, value):
        self.value = value
    async def __aenter__(self):
        return self.value
    async def __aexit__(self, *args):
        pass


class AsyncConnMock:
    """Mock async connection where run_sync returns a coroutine."""
    def __init__(self, sync_return=None):
        self._sync_return = sync_return
        self.run_sync_calls = []

    async def run_sync(self, fn):
        self.run_sync_calls.append(fn)
        if self._sync_return is not None:
            return self._sync_return
        return fn(MagicMock())


async def _coro(val):
    return val


def make_mock_conn(state="empty"):
    """Create a mock connection that returns the given state from detect_state_sync."""
    conn = MagicMock()
    if state == "managed":
        r1 = MagicMock(); r1.scalar.return_value = 1
        conn.execute.side_effect = [r1]
    elif state == "unmanaged":
        r1 = MagicMock(); r1.scalar.return_value = None
        r2 = MagicMock(); r2.scalar.return_value = 5
        conn.execute.side_effect = [r1, r2]
    else:  # empty
        r1 = MagicMock(); r1.scalar.return_value = None
        r2 = MagicMock(); r2.scalar.return_value = 0
        conn.execute.side_effect = [r1, r2]
    return conn


# ── detect_state_sync tests ──────────────────────────────────────────

class TestDetectState:
    def test_empty_database(self):
        conn = make_mock_conn("empty")
        assert migrate.detect_state_sync(conn) == "empty"

    def test_managed_database(self):
        conn = make_mock_conn("managed")
        assert migrate.detect_state_sync(conn) == "managed"

    def test_unmanaged_database(self):
        conn = make_mock_conn("unmanaged")
        assert migrate.detect_state_sync(conn) == "unmanaged"

    def test_null_table_count_treated_as_empty(self):
        """Edge case: COUNT returns NULL (shouldn't happen but defensive)."""
        conn = MagicMock()
        r1 = MagicMock(); r1.scalar.return_value = None
        r2 = MagicMock(); r2.scalar.return_value = None
        conn.execute.side_effect = [r1, r2]
        assert migrate.detect_state_sync(conn) == "empty"

    def test_db_error_propagates(self):
        """Adversarial: DB connection error should propagate, not be swallowed."""
        conn = MagicMock()
        conn.execute.side_effect = Exception("connection refused")
        with pytest.raises(Exception, match="connection refused"):
            migrate.detect_state_sync(conn)

    def test_single_table_is_unmanaged(self):
        """Edge case: just 1 table (not alembic_version) → unmanaged."""
        conn = MagicMock()
        r1 = MagicMock(); r1.scalar.return_value = None
        r2 = MagicMock(); r2.scalar.return_value = 1
        conn.execute.side_effect = [r1, r2]
        assert migrate.detect_state_sync(conn) == "unmanaged"


# ── sync_missing_columns tests ───────────────────────────────────────

class TestSyncMissingColumns:
    def _make_conn_and_insp(self, live_columns, table_exists=True):
        conn = MagicMock()
        conn.engine = MagicMock()
        conn.engine.dialect = MagicMock()
        insp = MagicMock()
        insp.has_table.return_value = table_exists
        insp.get_columns.return_value = [{"name": c} for c in live_columns]
        return conn, insp

    def _make_model_col(self, name, col_type="JSONB", nullable=True, default=None):
        col = MagicMock()
        col.name = name
        col.type = MagicMock()
        col.type.compile.return_value = col_type
        col.nullable = nullable
        col.server_default = default
        return col

    def test_no_missing_columns(self):
        conn, insp = self._make_conn_and_insp(["id", "name"])
        col1 = self._make_model_col("id")
        col2 = self._make_model_col("name")
        table = MagicMock(); table.columns = [col1, col2]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                assert migrate.sync_missing_columns(conn) == 0
        conn.execute.assert_not_called()

    def test_adds_missing_nullable_column(self):
        conn, insp = self._make_conn_and_insp(["id"])
        col_missing = self._make_model_col("gaming_flags", "JSONB", nullable=True)
        table = MagicMock(); table.columns = [self._make_model_col("id"), col_missing]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"agent_versions": table}
                assert migrate.sync_missing_columns(conn) == 1
        sql_text = conn.execute.call_args[0][0].text
        assert "ADD COLUMN IF NOT EXISTS" in sql_text
        assert "gaming_flags" in sql_text
        assert "JSONB" in sql_text

    def test_adds_column_with_server_default(self):
        default = MagicMock()
        default.arg = MagicMock()
        default.arg.text = "'false'"
        col = self._make_model_col("is_editing", "BOOLEAN", nullable=False, default=default)
        conn, insp = self._make_conn_and_insp(["id"])
        table = MagicMock(); table.columns = [self._make_model_col("id"), col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                assert migrate.sync_missing_columns(conn) == 1
        sql_text = conn.execute.call_args[0][0].text
        assert "DEFAULT 'false'" in sql_text

    def test_skips_nonexistent_table(self):
        conn, insp = self._make_conn_and_insp([], table_exists=False)
        table = MagicMock(); table.columns = [self._make_model_col("id")]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"ghost": table}
                assert migrate.sync_missing_columns(conn) == 0
        insp.get_columns.assert_not_called()

    def test_not_null_fallback_to_nullable(self):
        """NOT NULL without default on non-empty table → retry as nullable."""
        conn, insp = self._make_conn_and_insp(["id"])
        col = self._make_model_col("required", "VARCHAR(255)", nullable=False)
        table = MagicMock(); table.columns = [self._make_model_col("id"), col]
        conn.execute.side_effect = [Exception("null value in column"), None]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                assert migrate.sync_missing_columns(conn) == 1
        assert conn.execute.call_count == 2

    def test_multiple_missing_columns(self):
        conn, insp = self._make_conn_and_insp(["id"])
        col_a = self._make_model_col("col_a", "TEXT")
        col_b = self._make_model_col("col_b", "INTEGER")
        table = MagicMock(); table.columns = [self._make_model_col("id"), col_a, col_b]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                assert migrate.sync_missing_columns(conn) == 2

    def test_column_with_special_characters_quoted(self):
        """Column names are quoted to handle reserved words."""
        conn, insp = self._make_conn_and_insp([])
        col = self._make_model_col("order", "INTEGER")
        table = MagicMock(); table.columns = [col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                migrate.sync_missing_columns(conn)
        sql_text = conn.execute.call_args[0][0].text
        assert '"order"' in sql_text

    def test_both_retries_fail_warns_but_continues(self):
        """If both attempts fail, warn and continue without crashing."""
        conn, insp = self._make_conn_and_insp(["id"])
        col = self._make_model_col("broken", "BADTYPE", nullable=False)
        table = MagicMock(); table.columns = [self._make_model_col("id"), col]
        conn.execute.side_effect = [Exception("type error"), Exception("still broken")]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                assert migrate.sync_missing_columns(conn) == 0

    def test_server_default_without_text_attr(self):
        """Edge case: server_default.arg is a plain string, not a text clause."""
        default = MagicMock(spec=[])
        default.arg = "42"
        col = self._make_model_col("priority", "INTEGER", nullable=False, default=default)
        conn, insp = self._make_conn_and_insp([])
        table = MagicMock(); table.columns = [col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                migrate.sync_missing_columns(conn)
        sql_text = conn.execute.call_args[0][0].text
        assert "DEFAULT 42" in sql_text


# ── run_alembic tests ────────────────────────────────────────────────

class TestRunAlembic:
    def test_returns_zero_on_success(self):
        with patch("migrate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert migrate.run_alembic(["stamp", "head"]) == 0

    def test_returns_nonzero_on_failure(self):
        with patch("migrate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert migrate.run_alembic(["upgrade", "head"]) == 1

    def test_passes_correct_args(self):
        with patch("migrate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            migrate.run_alembic(["upgrade", "head"])
            args = mock_run.call_args[0][0]
            assert args[-2:] == ["upgrade", "head"]
            assert "alembic" in args[-3]

    def test_subprocess_exception_propagates(self):
        """Adversarial: subprocess crashes → exception propagates."""
        with patch("migrate.subprocess.run", side_effect=OSError("no such file")):
            with pytest.raises(OSError, match="no such file"):
                migrate.run_alembic(["upgrade", "head"])


# ── main() integration tests ─────────────────────────────────────────

class TestMainFlow:
    def _setup_engine(self, state):
        mock_engine = MagicMock()
        detect_conn = AsyncConnMock(sync_return=state)
        begin_conn = AsyncConnMock()
        mock_engine.connect.return_value = AsyncCM(detect_conn)
        mock_engine.begin.return_value = AsyncCM(begin_conn)
        mock_engine.dispose = lambda: _coro(None)
        return mock_engine

    @pytest.mark.asyncio
    async def test_empty_creates_and_stamps(self):
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("empty")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                with patch("migrate.Base") as mb:
                    mb.metadata.create_all = MagicMock()
                    with patch("migrate.run_alembic", return_value=0) as mock_alembic:
                        await migrate.main()
                        mock_alembic.assert_called_once_with(["stamp", "head"])
                        mb.metadata.create_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_managed_upgrades(self):
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("managed")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                with patch("migrate.run_alembic", return_value=0) as mock_alembic:
                    await migrate.main()
                    mock_alembic.assert_called_once_with(["upgrade", "head"])

    @pytest.mark.asyncio
    async def test_managed_failure_exits_nonzero(self):
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("managed")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                with patch("migrate.run_alembic", return_value=1):
                    with pytest.raises(SystemExit) as exc:
                        await migrate.main()
                    assert exc.value.code == 1

    @pytest.mark.asyncio
    async def test_unmanaged_syncs_and_stamps(self):
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("unmanaged")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                mock_sync_engine = MagicMock()
                mock_sync_conn = MagicMock()
                mock_sync_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_sync_conn)
                mock_sync_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
                with patch("migrate.create_engine", return_value=mock_sync_engine):
                    with patch("migrate.sync_missing_columns", return_value=3) as mock_sync:
                        with patch("migrate.run_alembic", return_value=0) as mock_alembic:
                            with patch("migrate.Base") as mb:
                                mb.metadata.create_all = MagicMock()
                                await migrate.main()
                                mock_sync.assert_called_once()
                                mock_alembic.assert_called_once_with(["stamp", "head"])

    @pytest.mark.asyncio
    async def test_unmanaged_stamp_failure_exits(self):
        """Adversarial: stamp fails after sync → exit 1."""
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("unmanaged")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                mock_sync_engine = MagicMock()
                mock_sync_conn = MagicMock()
                mock_sync_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_sync_conn)
                mock_sync_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
                with patch("migrate.create_engine", return_value=mock_sync_engine):
                    with patch("migrate.sync_missing_columns", return_value=0):
                        with patch("migrate.run_alembic", return_value=1):
                            with patch("migrate.Base") as mb:
                                mb.metadata.create_all = MagicMock()
                                with pytest.raises(SystemExit) as exc:
                                    await migrate.main()
                                assert exc.value.code == 1

    @pytest.mark.asyncio
    async def test_empty_stamp_failure_exits(self):
        """Adversarial: fresh install but stamp fails → exit 1."""
        with patch("migrate.create_async_engine") as mock_aef:
            mock_aef.return_value = self._setup_engine("empty")
            with patch("migrate.settings") as ms:
                ms.DATABASE_URL = "postgresql+asyncpg://x/y"
                with patch("migrate.Base") as mb:
                    mb.metadata.create_all = MagicMock()
                    with patch("migrate.run_alembic", return_value=1):
                        with pytest.raises(SystemExit) as exc:
                            await migrate.main()
                        assert exc.value.code == 1


# ── Adversarial / edge case tests ────────────────────────────────────

class TestAdversarial:
    def test_sql_injection_in_column_name_is_quoted(self):
        """Column names are quoted, preventing SQL injection via model definitions."""
        conn = MagicMock()
        conn.engine = MagicMock()
        conn.engine.dialect = MagicMock()

        insp = MagicMock()
        insp.has_table.return_value = True
        insp.get_columns.return_value = []

        col = MagicMock()
        col.name = "x; DROP TABLE users; --"
        col.type = MagicMock()
        col.type.compile.return_value = "TEXT"
        col.nullable = True
        col.server_default = None
        table = MagicMock(); table.columns = [col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                migrate.sync_missing_columns(conn)

        sql_text = conn.execute.call_args[0][0].text
        # The malicious name is quoted, not executed as separate SQL
        assert '"x; DROP TABLE users; --"' in sql_text

    def test_empty_table_metadata(self):
        """Edge case: Base.metadata.tables is empty → no-op."""
        conn = MagicMock()
        conn.engine = MagicMock()

        with patch("migrate.inspect") as mock_insp:
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {}
                result = migrate.sync_missing_columns(conn)
        assert result == 0

    def test_large_number_of_tables(self):
        """Stress: many tables with many columns — should not crash."""
        conn = MagicMock()
        conn.engine = MagicMock()
        conn.engine.dialect = MagicMock()

        insp = MagicMock()
        insp.has_table.return_value = True
        insp.get_columns.return_value = [{"name": "id"}]

        tables = {}
        for i in range(50):
            cols = []
            id_col = MagicMock(); id_col.name = "id"
            cols.append(id_col)
            for j in range(10):
                c = MagicMock()
                c.name = f"col_{j}"
                c.type = MagicMock()
                c.type.compile.return_value = "TEXT"
                c.nullable = True
                c.server_default = None
                cols.append(c)
            t = MagicMock(); t.columns = cols
            tables[f"table_{i}"] = t

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = tables
                result = migrate.sync_missing_columns(conn)
        # 50 tables × 10 missing columns each = 500
        assert result == 500

    def test_concurrent_column_add_is_idempotent(self):
        """IF NOT EXISTS makes concurrent adds safe."""
        conn = MagicMock()
        conn.engine = MagicMock()
        conn.engine.dialect = MagicMock()

        insp = MagicMock()
        insp.has_table.return_value = True
        insp.get_columns.return_value = []

        col = MagicMock()
        col.name = "new_col"
        col.type = MagicMock()
        col.type.compile.return_value = "TEXT"
        col.nullable = True
        col.server_default = None
        table = MagicMock(); table.columns = [col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": table}
                migrate.sync_missing_columns(conn)
        sql_text = conn.execute.call_args[0][0].text
        assert "IF NOT EXISTS" in sql_text

    def test_table_name_with_special_chars(self):
        """Edge case: table name with unusual characters."""
        conn = MagicMock()
        conn.engine = MagicMock()
        conn.engine.dialect = MagicMock()

        insp = MagicMock()
        insp.has_table.return_value = True
        insp.get_columns.return_value = []

        col = MagicMock()
        col.name = "val"
        col.type = MagicMock()
        col.type.compile.return_value = "TEXT"
        col.nullable = True
        col.server_default = None
        table = MagicMock(); table.columns = [col]

        with patch("migrate.inspect", return_value=insp):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"my-table_v2": table}
                migrate.sync_missing_columns(conn)
        sql_text = conn.execute.call_args[0][0].text
        assert "my-table_v2" in sql_text

    def test_inspect_raises_does_not_swallow(self):
        """Adversarial: inspect() failure propagates."""
        conn = MagicMock()
        conn.engine = MagicMock()

        with patch("migrate.inspect", side_effect=RuntimeError("inspect failed")):
            with patch("migrate.Base") as mock_base:
                mock_base.metadata.tables = {"t": MagicMock()}
                with pytest.raises(RuntimeError, match="inspect failed"):
                    migrate.sync_missing_columns(conn)

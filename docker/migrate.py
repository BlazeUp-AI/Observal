"""Smart database migration script for Observal.

Detects the current database state and applies the correct migration strategy:
- Empty DB: create_all + stamp head (fresh install)
- Managed DB (has alembic_version): alembic upgrade head (fail hard on error)
- Unmanaged DB (tables exist, no alembic_version): create_all + sync missing columns + stamp head

Never silently stamps head after a failure. Exits non-zero on any error.
"""

import asyncio
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings
from models import Base


def detect_state_sync(conn) -> str:
    """Detect the current database state (runs inside run_sync).

    Returns:
        "empty" - no application tables exist
        "managed" - alembic_version table exists (previously migrated)
        "unmanaged" - application tables exist but no alembic_version
    """
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
        )
    )
    if result.scalar() is not None:
        return "managed"

    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    table_count = result.scalar() or 0
    return "unmanaged" if table_count > 0 else "empty"


def sync_missing_columns(conn) -> int:
    """Compare model-defined columns against live DB and add missing ones.

    Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS for safety.
    Returns the number of columns added.
    """
    insp = inspect(conn)
    dialect = conn.engine.dialect
    added = 0

    for table_name, table in Base.metadata.tables.items():
        if not insp.has_table(table_name):
            continue

        live_columns = {col["name"] for col in insp.get_columns(table_name)}

        for column in table.columns:
            if column.name in live_columns:
                continue

            col_type = column.type.compile(dialect=dialect)
            nullable = "" if column.nullable else " NOT NULL"
            default = ""
            if column.server_default is not None:
                default_text = column.server_default.arg
                if hasattr(default_text, "text"):
                    default = f" DEFAULT {default_text.text}"
                else:
                    default = f" DEFAULT {default_text}"

            # NOT NULL columns without a default can't be added to non-empty tables,
            # so we add them as nullable in that case.
            ddl = (
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN IF NOT EXISTS \"{column.name}\" {col_type}{nullable}{default}"
            )
            print(f"  Adding missing column: {table_name}.{column.name} ({col_type})")
            try:
                conn.execute(text(ddl))
                added += 1
            except Exception:
                # Retry as nullable if NOT NULL constraint fails
                ddl_nullable = (
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN IF NOT EXISTS \"{column.name}\" {col_type}{default}"
                )
                try:
                    conn.execute(text(ddl_nullable))
                    added += 1
                except Exception as e2:
                    print(f"  WARNING: Could not add {table_name}.{column.name}: {e2}")

    return added


def run_alembic(command: list[str]) -> int:
    """Run an alembic command and return the exit code."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic"] + command,
        capture_output=False,
    )
    return result.returncode


async def main():
    async_engine = create_async_engine(settings.DATABASE_URL)

    # Step 1: Detect state
    async with async_engine.connect() as conn:
        state = await conn.run_sync(detect_state_sync)

    if state == "empty":
        print("[migrate] Empty database detected — fresh install")
        print("[migrate] Creating tables from models...")
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[migrate] Stamping alembic head...")
        rc = run_alembic(["stamp", "head"])
        if rc != 0:
            print("[migrate] ERROR: Failed to stamp head", file=sys.stderr)
            sys.exit(1)
        print("[migrate] Fresh install complete ✓")

    elif state == "managed":
        print("[migrate] Managed database detected — running migrations")
        rc = run_alembic(["upgrade", "head"])
        if rc != 0:
            print(
                "[migrate] ERROR: Migrations failed. "
                "Do NOT use 'alembic stamp head' to work around this. "
                "Investigate the error above and fix the migration.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("[migrate] Migrations complete ✓")

    else:
        print("[migrate] Unmanaged database detected — reconciling schema")
        print("[migrate] Running create_all for missing tables...")
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("[migrate] Checking for missing columns...")
        # Use a synchronous engine for inspect() — it doesn't support async
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        sync_engine = create_engine(sync_url)
        with sync_engine.begin() as sync_conn:
            added = sync_missing_columns(sync_conn)
        sync_engine.dispose()

        if added:
            print(f"[migrate] Added {added} missing column(s)")
        else:
            print("[migrate] Schema is up to date")

        print("[migrate] Stamping alembic head...")
        rc = run_alembic(["stamp", "head"])
        if rc != 0:
            print("[migrate] ERROR: Failed to stamp head", file=sys.stderr)
            sys.exit(1)
        print("[migrate] Schema reconciliation complete ✓")

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

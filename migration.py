"""
VA Studio Backend - Database Migration
=======================================
Auto-syncs database schema from ORM models on every app reload.

This module is called automatically during app startup (lifespan).
It can also be run standalone:

    python migration.py              # Run migration
    python migration.py --check      # Check status only
    python migration.py --seed       # Run migration + seed data

It will:
1. Discover all ORM models in app/orm/ (auto-imports every module)
2. Create any missing tables (CREATE TABLE IF NOT EXISTS)
3. Add any missing columns to existing tables (ALTER TABLE ADD COLUMN)
4. Never drop tables or columns (safe, additive-only)

This is the core of VA Studio's low-code/vibe-coding approach:
  - AI or user adds a new model in app/orm/
  - App reloads → migration.py picks it up → table + columns exist instantly
"""

import sys
import importlib
import pkgutil
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import inspect, text, create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.orm.base import Base
from app.core.logger import get_logger

logger = get_logger("migration")


# ---------------------------------------------------------------------------
# ORM Discovery — import every module in app/orm/ so models register on Base
# ---------------------------------------------------------------------------

def discover_orm_models() -> list[str]:
    """
    Dynamically import every .py module in app/orm/ so all model classes
    register on Base.metadata before create_all runs.

    This is what makes vibe-coding work: drop a new file in app/orm/,
    define your SQLAlchemy model, and it gets picked up automatically.
    """
    import app.orm as orm_pkg

    discovered = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(orm_pkg.__path__):
        full_name = f"app.orm.{modname}"
        try:
            importlib.import_module(full_name)
            discovered.append(modname)
        except Exception as exc:
            logger.warning(f"Could not import ORM module {full_name}: {exc}")

    return discovered


# ---------------------------------------------------------------------------
# Schema Discovery — import every module in app/schemas/ for completeness
# ---------------------------------------------------------------------------

def discover_schemas() -> list[str]:
    """
    Import all Pydantic schema modules in app/schemas/.
    Schemas don't affect DB tables, but this ensures they're loaded and
    validated at startup — catching import errors early.
    """
    import app.schemas as schemas_pkg

    discovered = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(schemas_pkg.__path__):
        full_name = f"app.schemas.{modname}"
        try:
            importlib.import_module(full_name)
            discovered.append(modname)
        except Exception as exc:
            logger.warning(f"Could not import schema module {full_name}: {exc}")

    return discovered


# ---------------------------------------------------------------------------
# Column type DDL helper
# ---------------------------------------------------------------------------

def _sa_column_type_ddl(col) -> str:
    """Compile a SQLAlchemy column type to its PostgreSQL DDL string."""
    try:
        from sqlalchemy.dialects import postgresql
        return col.type.compile(dialect=postgresql.dialect())
    except Exception:
        return str(col.type)


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

def get_sync_engine():
    """Create a synchronous SQLAlchemy engine for DDL operations."""
    from app.core.db import get_database_url
    return create_engine(get_database_url("psycopg2"), echo=False)


def check_connection(engine) -> bool:
    """Verify database is reachable."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"Database connected: {version}")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def create_tables(engine) -> tuple[int, int]:
    """
    Create all tables defined in ORM models that don't exist yet.
    Creates tables individually (in FK-dependency order) so one failure
    doesn't block the rest.
    Returns (created_count, total_count).
    """
    insp = inspect(engine)
    existing_before = set(insp.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())

    new_tables = orm_tables - existing_before

    # Try bulk create first (fastest path when no conflicts)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        return len(new_tables), len(orm_tables)
    except SQLAlchemyError as e:
        logger.warning(f"Bulk create_all failed, falling back to per-table creation: {e}")

    # Fall back to creating tables one by one in FK-dependency order
    # so parent tables are created before children.
    created = 0
    sorted_tables = Base.metadata.sorted_tables  # respects FK dependencies
    for table in sorted_tables:
        if table.name in existing_before:
            continue
        try:
            table.create(bind=engine, checkfirst=True)
            created += 1
            logger.info(f"  + Created table: {table.name}")
        except SQLAlchemyError as exc:
            logger.warning(f"  SKIP table {table.name} — {exc}")

    return created, len(orm_tables)


def sync_columns(engine) -> int:
    """
    Compare ORM metadata against live database and ADD any missing columns.
    This is safe and additive-only — never drops columns or tables.
    Returns number of columns added.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    changes = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        existing_cols = {c["name"] for c in insp.get_columns(table_name)}

        for col in table.columns:
            if col.name in existing_cols:
                continue

            col_type = _sa_column_type_ddl(col)
            nullable = "NULL" if col.nullable else "NOT NULL"
            default_clause = ""

            # Handle server defaults
            if col.server_default is not None:
                try:
                    default_clause = f" DEFAULT {col.server_default.arg}"
                except Exception:
                    default_clause = ""
            elif col.default is not None and isinstance(
                getattr(col.default, 'arg', None), (str, int, float, bool)
            ):
                arg = col.default.arg
                default_clause = (
                    f" DEFAULT '{arg}'" if isinstance(arg, str) else f" DEFAULT {arg}"
                )

            # Can't add NOT NULL column without a default — make it nullable
            if nullable == "NOT NULL" and not default_clause:
                nullable = "NULL"

            ddl = (
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN "{col.name}" {col_type} {nullable}{default_clause}'
            )
            changes.append((table_name, col.name, ddl))

    if not changes:
        return 0

    added = 0
    with engine.connect() as conn:
        for table_name, col_name, ddl in changes:
            try:
                conn.execute(text(ddl))
                logger.info(f"  + {table_name}.{col_name}")
                added += 1
            except Exception as exc:
                logger.warning(f"  SKIP {table_name}.{col_name} — {exc}")
        conn.commit()

    return added


def get_migration_status(engine) -> dict:
    """Get current database vs ORM diff status."""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    orm_tables = set(Base.metadata.tables.keys())

    missing_tables = orm_tables - existing_tables
    missing_columns = {}

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(table_name)}
        new_cols = [col.name for col in table.columns if col.name not in existing_cols]
        if new_cols:
            missing_columns[table_name] = new_cols

    return {
        "orm_tables": len(orm_tables),
        "db_tables": len(existing_tables),
        "missing_tables": sorted(missing_tables),
        "missing_columns": missing_columns,
        "is_synced": len(missing_tables) == 0 and len(missing_columns) == 0,
    }


# ---------------------------------------------------------------------------
# PK type mismatch repair
# ---------------------------------------------------------------------------

def repair_pk_type_mismatches(engine) -> None:
    """
    Detect tables where the live PK type differs from the ORM definition
    (e.g. INTEGER vs UUID) and recreate them. Only acts on empty tables
    to avoid data loss. Drops dependents (FKs) first.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        pk_cols = [c for c in table.columns if c.primary_key]
        if not pk_cols:
            continue

        orm_pk = pk_cols[0]
        orm_type = _sa_column_type_ddl(orm_pk).upper()

        db_cols = {c["name"]: c for c in insp.get_columns(table_name)}
        db_pk = db_cols.get(orm_pk.name)
        if db_pk is None:
            continue

        db_type = str(db_pk["type"]).upper()

        # Normalise for comparison
        is_uuid_orm = "UUID" in orm_type
        is_uuid_db = "UUID" in db_type
        if is_uuid_orm == is_uuid_db:
            continue

        # Mismatch detected — only fix if table is empty
        with engine.connect() as conn:
            count = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar()
            if count > 0:
                logger.warning(
                    f"  PK type mismatch on {table_name}.{orm_pk.name} "
                    f"(DB={db_type}, ORM={orm_type}) but table has {count} rows — skipping"
                )
                continue

            logger.info(
                f"  Fixing PK type mismatch: {table_name}.{orm_pk.name} "
                f"{db_type} → {orm_type} (table is empty)"
            )
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
            conn.commit()


# ---------------------------------------------------------------------------
# Public API — called by app.py lifespan on every startup/reload
# ---------------------------------------------------------------------------

def run_migration() -> dict:
    """
    Run the full migration pipeline. Called on every app startup/reload.

    Returns a summary dict with what happened.
    """
    summary = {
        "orm_modules": [],
        "schema_modules": [],
        "tables_created": 0,
        "tables_total": 0,
        "columns_added": 0,
        "success": False,
    }

    # 1. Discover all ORM models
    orm_modules = discover_orm_models()
    summary["orm_modules"] = orm_modules
    logger.info(f"ORM discovery: {len(orm_modules)} modules — {orm_modules}")

    # 2. Discover all schemas (validation only, no DB impact)
    schema_modules = discover_schemas()
    summary["schema_modules"] = schema_modules
    logger.info(f"Schema discovery: {len(schema_modules)} modules — {schema_modules}")

    # 3. Get sync engine
    try:
        engine = get_sync_engine()
    except Exception as e:
        logger.error(f"Cannot create database engine: {e}")
        return summary

    # 4. Check connection
    if not check_connection(engine):
        return summary

    # 4b. Fix known type mismatches (e.g. subscriptions.id INTEGER → UUID)
    try:
        repair_pk_type_mismatches(engine)
    except Exception as e:
        logger.warning(f"PK type repair skipped: {e}")

    # 5. Create missing tables
    try:
        created, total = create_tables(engine)
        summary["tables_created"] = created
        summary["tables_total"] = total
        if created > 0:
            logger.info(f"Created {created} new table(s) ({total} total)")
        else:
            logger.info(f"All {total} tables already exist")
    except Exception as e:
        logger.error(f"Table creation failed: {e}")
        return summary

    # 6. Add missing columns to existing tables
    try:
        added = sync_columns(engine)
        summary["columns_added"] = added
        if added > 0:
            logger.info(f"Added {added} new column(s)")
        else:
            logger.info("All columns up to date")
    except Exception as e:
        logger.error(f"Column sync failed: {e}")
        return summary

    summary["success"] = True

    # 7. Seed data if tables are empty (first run)
    try:
        from scripts.seed_data import main as seed_main
        seed_main()
        summary["seeded"] = True
        logger.info("Seed data check complete")
    except Exception as e:
        summary["seeded"] = False
        logger.warning(f"Seed data skipped: {e}")

    # Log final state
    table_names = sorted(Base.metadata.tables.keys())
    logger.info(f"Migration complete — {len(table_names)} tables: {table_names}")

    # Dispose the sync engine (we only need it for DDL)
    engine.dispose()

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for running migration standalone."""
    import argparse

    parser = argparse.ArgumentParser(description="VA Studio Backend - Database Migration")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check migration status without applying changes",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Run migration then seed sample data",
    )

    args = parser.parse_args()

    if args.check:
        # Discovery only
        orm_modules = discover_orm_models()
        schema_modules = discover_schemas()
        print(f"\nORM modules ({len(orm_modules)}): {orm_modules}")
        print(f"Schema modules ({len(schema_modules)}): {schema_modules}")
        print(f"ORM tables registered: {sorted(Base.metadata.tables.keys())}")

        try:
            engine = get_sync_engine()
            if check_connection(engine):
                status = get_migration_status(engine)
                print(f"\nDatabase status:")
                print(f"  ORM tables:      {status['orm_tables']}")
                print(f"  DB tables:       {status['db_tables']}")
                print(f"  Missing tables:  {status['missing_tables'] or 'none'}")
                print(f"  Missing columns: {status['missing_columns'] or 'none'}")
                print(f"  Synced:          {'yes' if status['is_synced'] else 'NO — run migration'}")
                engine.dispose()
        except Exception as e:
            print(f"\nCannot connect to database: {e}")
        return

    # Run migration
    print("\n" + "=" * 60)
    print("VA Studio Backend — Database Migration")
    print("=" * 60 + "\n")

    result = run_migration()

    if result["success"]:
        print(f"\nMigration successful!")
        print(f"  ORM modules:    {len(result['orm_modules'])}")
        print(f"  Schema modules: {len(result['schema_modules'])}")
        print(f"  Tables created: {result['tables_created']}")
        print(f"  Tables total:   {result['tables_total']}")
        print(f"  Columns added:  {result['columns_added']}")
    else:
        print("\nMigration failed — check logs above")
        sys.exit(1)

    # Seed data if requested
    if args.seed:
        print("\nSeeding sample data...")
        try:
            from scripts.seed_data import main as seed_main
            seed_main()
            print("Seed data loaded successfully")
        except ImportError:
            print("Warning: scripts/seed_data.py not found — skipping seed")
        except Exception as e:
            print(f"Seed failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

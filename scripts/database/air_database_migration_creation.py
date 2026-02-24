"""
Air Database Migration Creation Script
======================================
Create or update tables and columns if missing based on ORM models.

This script compares ORM models with the actual database schema and
creates missing tables or adds missing columns.

Features:
---------
- Creates missing tables from ORM models
- Adds missing columns to existing tables
- Supports dry-run mode to preview changes
- Shows migration summary with created/updated/skipped tables
- Uses ORM models and schemas for validation

Usage:
------
    # Dry run first (preview changes)
    python scripts/database/air_database_migration_creation.py --dry-run

    # Apply changes
    python scripts/database/air_database_migration_creation.py

Arguments:
----------
    --dry-run    Show what would be done without making changes

Output:
-------
- Console output showing migration progress
- Summary of created/updated/skipped tables

Related Scripts:
----------------
1. air_database_validation_schemas.py - Preview schemas
2. air_database_schema_comparison.py - Compare schemas
3. air_database_sync.py - Comprehensive sync (recommended)
"""

import sys
import os
from pathlib import Path
from urllib.parse import quote_plus

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import SQLAlchemyError
from app.core.db import get_db_config
from app.orm_models.base import Base
# Public schema (root) models only
from app.orm_models import (
    User, Lead, Job, Campaign,
    SalesRepresentative, AIChatSession, AIChatMessage,
    SalesFollowUp, EmailProviderReport, Setting, Tenant, AISystemSetting,
    Notification,
    NotificationPreferences,
    NotificationChannel,
    NotificationTemplate,
    NotificationCategory,
    NotificationOutbox,
    NotificationEventsLog,
    QueueMessage,
)
# Philippines ERP schema
from app.orm_models.philippines import PHILIPPINES_MODELS
# Canada staffing schema
from app.orm_models.canada import CANADA_MODELS

# Public (root) + Philippines + Canada
ALL_MODELS = [
    User, Lead, Job, Campaign,
    SalesRepresentative, AIChatSession, AIChatMessage,
    SalesFollowUp, EmailProviderReport, Setting, Tenant, AISystemSetting,
    Notification,
    NotificationPreferences,
    NotificationChannel,
    NotificationTemplate,
    NotificationCategory,
    NotificationOutbox,
    NotificationEventsLog,
    QueueMessage,
] + list(PHILIPPINES_MODELS) + list(CANADA_MODELS)


def get_database_engine():
    """Create SQLAlchemy engine from database config."""
    config = get_db_config()
    # URL-encode user and password so that @ or other special chars in password don't break the URL
    user = quote_plus(str(config["user"]))
    password = quote_plus(str(config["password"]))
    connection_string = (
        f"postgresql://{user}:{password}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    return create_engine(connection_string, echo=False)


def ensure_schema(engine, schema_name: str):
    """Create a PostgreSQL schema if it does not exist."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        conn.commit()
    print(f"  ✅ Schema {schema_name} ensured")


def table_exists(engine, table_name: str, schema: str | None = None) -> bool:
    """Check if a table exists in the database (optionally in the given schema)."""
    inspector = inspect(engine)
    names = inspector.get_table_names(schema=schema) if schema else inspector.get_table_names()
    return table_name in names


def get_table_columns(engine, table_name: str, schema: str | None = None) -> dict:
    """Get all columns for a table from the database (optionally in the given schema)."""
    inspector = inspect(engine)
    columns = {}
    for col in inspector.get_columns(table_name, schema=schema):
        columns[col['name']] = {
            'type': str(col['type']),
            'nullable': col['nullable'],
            'default': col.get('default'),
            'autoincrement': col.get('autoincrement', False)
        }
    return columns


def get_model_columns(model) -> dict:
    """Get all columns from an ORM model."""
    columns = {}
    for column in model.__table__.columns:
        # Get the actual database column name (handles name parameter)
        db_name = column.name
        columns[db_name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'default': column.default,
            'autoincrement': column.autoincrement
        }
    return columns


def create_table(engine, model):
    """Create a table from an ORM model."""
    table_name = model.__tablename__
    try:
        # Generate CREATE TABLE statement
        create_sql = str(CreateTable(model.__table__).compile(engine))
        
        # Execute the CREATE TABLE statement
        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
        
        print(f"  ✅ Created table: {table_name}")
        return True
    except SQLAlchemyError as e:
        print(f"  ❌ Error creating table {table_name}: {e}")
        return False


def add_missing_columns(engine, model, db_columns: dict, model_columns: dict, schema: str | None = None):
    """Add missing columns to an existing table. Returns (success, list of added column names)."""
    table_name = model.__tablename__
    table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    missing_columns = []
    
    for col_name, col_info in model_columns.items():
        if col_name not in db_columns:
            missing_columns.append((col_name, col_info))
    
    if not missing_columns:
        return True, []
    
    added_names = []
    try:
        with engine.connect() as conn:
            for col_name, col_info in missing_columns:
                # Build ALTER TABLE ADD COLUMN statement
                col_type = col_info['type']
                nullable = "NULL" if col_info['nullable'] else "NOT NULL"
                
                # Handle default values
                default_clause = ""
                if col_info.get('default') is not None:
                    default_value = col_info['default']
                    if hasattr(default_value, 'arg'):
                        # SQLAlchemy default function
                        if 'now()' in str(default_value.arg):
                            default_clause = "DEFAULT now()"
                        else:
                            default_clause = f"DEFAULT {default_value.arg}"
                    else:
                        default_clause = f"DEFAULT {default_value}"
                
                alter_sql = (
                    f'ALTER TABLE {table_ref} '
                    f'ADD COLUMN "{col_name}" {col_type} {nullable}'
                )
                if default_clause:
                    alter_sql += f" {default_clause}"
                
                conn.execute(text(alter_sql))
                added_names.append(col_name)
                print(f"    ✅ Added column: {col_name} ({col_type})")
            
            conn.commit()
        return True, added_names
    except SQLAlchemyError as e:
        print(f"  ❌ Error adding columns to {table_name}: {e}")
        return False, []


def migrate_database(dry_run: bool = False):
    """
    Migrate database: create missing tables and add missing columns.
    
    Args:
        dry_run: If True, only show what would be done without making changes
    """
    print("=" * 80)
    print("AIR DATABASE MIGRATION")
    print("=" * 80)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    try:
        engine = get_database_engine()
        inspector = inspect(engine)
        
        created_tables = []
        updated_tables = []  # list of (table_name, [added_columns])
        skipped_tables = []
        # Per-table report: table_name -> "created" | ("updated", [cols]) | "in_sync"
        report = []
        
        # Ensure philippines and canada schemas exist before creating tables
        for schema_name in ("philippines", "canada"):
            if not dry_run:
                ensure_schema(engine, schema_name)
            else:
                print(f"  [DRY RUN] Would ensure schema: {schema_name}")
        print()

        for model in ALL_MODELS:
            if not hasattr(model, '__tablename__'):
                continue

            table_name = model.__tablename__
            schema = getattr(model.__table__, "schema", None)

            if not table_exists(engine, table_name, schema=schema):
                # Table doesn't exist - create it
                qual = f"{schema}.{table_name}" if schema else table_name
                print(f"📋 Table missing: {qual}")
                if not dry_run:
                    if create_table(engine, model):
                        created_tables.append(qual)
                        report.append((qual, "created", []))
                else:
                    print(f"  [DRY RUN] Would create table: {qual}")
                    created_tables.append(qual)
                    report.append((qual, "created", []))
            else:
                # Table exists - check for missing columns
                db_columns = get_table_columns(engine, table_name, schema=schema)
                model_columns = get_model_columns(model)

                missing_cols = [col for col in model_columns.keys() if col not in db_columns]

                qual = f"{schema}.{table_name}" if schema else table_name
                if missing_cols:
                    print(f"📋 Table exists, missing columns: {qual}")
                    print(f"   Missing: {', '.join(missing_cols)}")
                    if not dry_run:
                        ok, added = add_missing_columns(engine, model, db_columns, model_columns, schema=schema)
                        if ok:
                            updated_tables.append((qual, added))
                            report.append((qual, "updated", added))
                    else:
                        print(f"  [DRY RUN] Would add columns: {', '.join(missing_cols)}")
                        updated_tables.append((qual, missing_cols))
                        report.append((qual, "updated", missing_cols))
                else:
                    skipped_tables.append(qual)
                    report.append((qual, "in_sync", []))
        
        # --- TABLE-BY-TABLE REPORT (what changed / what was checked) ---
        print()
        print("=" * 80)
        print("TABLE-BY-TABLE REPORT (changes and status)")
        print("=" * 80)
        for table_name, status, details in report:
            if status == "created":
                print(f"  {table_name:<40} CREATED (new table)")
            elif status == "updated":
                cols = details if isinstance(details, list) else []
                if cols:
                    print(f"  {table_name:<40} UPDATED (added columns: {', '.join(cols)})")
                else:
                    print(f"  {table_name:<40} UPDATED")
            else:
                print(f"  {table_name:<40} In sync (no changes)")
        print()
        
        # --- SUMMARY ---
        print("=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"✅ Created tables: {len(created_tables)}")
        if created_tables:
            for t in created_tables:
                print(f"   - {t}")
        print()
        num_updated = len(updated_tables)
        print(f"🔄 Updated tables (columns added): {num_updated}")
        if updated_tables:
            for item in updated_tables:
                if isinstance(item, tuple):
                    t, cols = item
                    print(f"   - {t}: added {', '.join(cols)}")
                else:
                    print(f"   - {item}")
        print()
        print(f"⏭️  In sync (no changes needed): {len(skipped_tables)}")
        if skipped_tables and len(skipped_tables) <= 15:
            print(f"   Tables: {', '.join(sorted(skipped_tables))}")
        elif skipped_tables:
            print(f"   (See TABLE-BY-TABLE REPORT above for full list)")
        print()
        
        if dry_run:
            print("💡 Run without --dry-run to apply changes")
        else:
            print("✅ Migration complete!")
            # ERP seed: auto-populate reference data when ids do not exist (Canada + Philippines)
            try:
                from app.services.erp.common.seed_data import seed_all
                print()
                print("=" * 80)
                print("ERP SEED DATA")
                print("=" * 80)
                seed_all()
                print("✅ ERP seed complete (reference data populated if missing)")
            except Exception as seed_err:
                print(f"⚠️  ERP seed skipped or partial: {seed_err}")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Air Database Migration Script')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    print("\n🚀 Air Database Migration\n")
    migrate_database(dry_run=args.dry_run)


if __name__ == "__main__":
    main()


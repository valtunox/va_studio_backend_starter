"""
Air Database Sync Script
========================
Synchronize ORM models with database - create missing tables and columns.

This script is a comprehensive sync tool that:
1. Creates missing tables
2. Adds missing columns
3. Generates detailed sync report
4. Handles errors gracefully

Supports 3 database schemas:
- Public (default) - Core application models
- Canada - Staffing management system
- Philippines - ERP system with payroll, taxes, deductions

Features:
---------
- Creates missing tables from ORM models
- Adds missing columns to existing tables
- Generates detailed sync report
- Supports dry-run and verbose modes
- Saves sync report to file
- Handles errors gracefully
- Multi-schema support (public, canada, philippines)

Usage:
------
    # Dry run with verbose output
    python scripts/database/air_database_sync.py --dry-run --verbose

    # Apply changes with report
    python scripts/database/air_database_sync.py --verbose --report sync_report.txt

    # Simple sync
    python scripts/database/air_database_sync.py

Arguments:
----------
    --dry-run    Show what would be done without making changes
    --verbose    Show detailed information for each operation
    --report     Save report to file (default: auto-generated name)

Output:
-------
- Console output showing sync progress
- Summary of created/updated/skipped tables
- Sync report file (if --report specified or not dry-run)

Related Scripts:
----------------
1. air_database_validation_schemas.py - Preview schemas
2. air_database_migration_creation.py - Create/update tables
3. air_database_schema_comparison.py - Compare schemas
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
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
    print(f"  Schema {schema_name} ensured")


def table_exists(engine, table_name: str, schema: str | None = None) -> bool:
    """Check if a table exists in the database (optionally in the given schema)."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names(schema=schema) if schema else inspector.get_table_names()
    # Check both exact match and case-insensitive match
    return table_name in existing_tables or table_name.lower() in [t.lower() for t in existing_tables]


def get_table_columns(engine, table_name: str, schema: str | None = None) -> Dict:
    """Get all columns for a table from the database (optionally in the given schema)."""
    inspector = inspect(engine)
    columns = {}
    try:
        for col in inspector.get_columns(table_name, schema=schema):
            columns[col['name']] = {
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': col.get('default'),
                'autoincrement': col.get('autoincrement', False)
            }
    except Exception as e:
        print(f"  Error reading columns: {e}")
    return columns


def get_model_columns(model) -> Dict:
    """Get all columns from an ORM model."""
    columns = {}
    for column in model.__table__.columns:
        db_name = column.name
        columns[db_name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'default': column.default,
            'autoincrement': column.autoincrement
        }
    return columns


def create_table_safe(engine, model, schema: str | None = None) -> bool:
    """Safely create a table from an ORM model (optionally in the given schema)."""
    table_name = model.__tablename__
    qual = f"{schema}.{table_name}" if schema else table_name
    try:
        # Double-check table doesn't exist (case-insensitive)
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names(schema=schema) if schema else inspector.get_table_names()
        if table_name.lower() in [t.lower() for t in existing_tables]:
            print(f"  Table {qual} already exists (case-insensitive match), skipping creation")
            return True

        create_sql = str(CreateTable(model.__table__).compile(engine))

        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()

        return True
    except SQLAlchemyError as e:
        error_msg = str(e)
        print(f"  Error creating table {qual}: {error_msg}")
        # Check if error is because table already exists
        if 'already exists' in error_msg.lower() or 'duplicate' in error_msg.lower():
            print(f"  Table {qual} already exists, treating as success")
            return True
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"  Unexpected error creating table {qual}: {error_msg}")
        import traceback
        traceback.print_exc()
        return False


def normalize_postgres_type(col_type: str) -> str:
    """Normalize SQLAlchemy type to PostgreSQL type."""
    col_type_str = str(col_type).upper()
    # Fix DATETIME to TIMESTAMP WITH TIME ZONE for PostgreSQL
    if 'DATETIME' in col_type_str:
        if 'TIMEZONE' in col_type_str or 'TIME ZONE' in col_type_str:
            return 'TIMESTAMP WITH TIME ZONE'
        else:
            return 'TIMESTAMP WITH TIME ZONE'
    return col_type_str


def get_default_value_sql(default_value, col_type: str) -> str:
    """Convert default value to SQL string."""
    if default_value is None:
        return ""
    
    if hasattr(default_value, 'arg'):
        # SQLAlchemy default function
        arg_str = str(default_value.arg)
        if 'now()' in arg_str or 'CURRENT_TIMESTAMP' in arg_str:
            return "DEFAULT now()"
        elif 'func.now()' in arg_str:
            return "DEFAULT now()"
        else:
            # Try to extract the value - check if it needs quotes
            col_type_upper = str(col_type).upper()
            if any(t in col_type_upper for t in ['VARCHAR', 'TEXT', 'CHAR', 'STRING']):
                # String type - quote the value
                return f"DEFAULT '{arg_str}'"
            else:
                return f"DEFAULT {arg_str}"
    else:
        # Direct value
        default_str = str(default_value)
        # Check if it's a string literal that needs quotes
        col_type_upper = str(col_type).upper()
        if any(t in col_type_upper for t in ['VARCHAR', 'TEXT', 'CHAR', 'STRING']):
            # String type - quote the value
            # Escape single quotes in the string
            escaped_value = default_str.replace("'", "''")
            return f"DEFAULT '{escaped_value}'"
        elif default_str.lower() in ['true', 'false']:
            # Boolean
            return f"DEFAULT {default_str.upper()}"
        elif default_str.replace('.', '').replace('-', '').isdigit():
            # Number
            return f"DEFAULT {default_str}"
        else:
            # Unknown type - quote it to be safe (likely a string)
            escaped_value = default_str.replace("'", "''")
            return f"DEFAULT '{escaped_value}'"


def table_has_data(engine, table_name: str, schema: str | None = None) -> bool:
    """Check if table has any rows (optionally in the given schema)."""
    try:
        table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT COUNT(*) FROM {table_ref}'))
            count = result.scalar()
            return count > 0
    except Exception:
        return False


def add_column_safe(engine, table_name: str, col_name: str, col_info: Dict, schema: str | None = None) -> bool:
    """Safely add a column to a table, handling existing data (optionally in the given schema)."""
    try:
        col_type = normalize_postgres_type(col_info['type'])
        is_nullable = col_info['nullable']
        has_data = table_has_data(engine, table_name, schema=schema)
        table_ref = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'

        # If adding NOT NULL column to table with existing data, use two-step process
        if not is_nullable and has_data:
            # Step 1: Add column as nullable
            default_clause = get_default_value_sql(col_info.get('default'), col_type)
            alter_sql = f'ALTER TABLE {table_ref} ADD COLUMN "{col_name}" {col_type} NULL'
            if default_clause:
                alter_sql += f" {default_clause}"

            with engine.connect() as conn:
                conn.execute(text(alter_sql))
                conn.commit()

            # Step 2: Update existing rows with default value
            default_value = col_info.get('default')
            if default_value is not None:
                default_sql = get_default_value_sql(default_value, col_type)
                if default_sql:
                    # Extract just the value part (after DEFAULT)
                    default_val = default_sql.replace('DEFAULT ', '').strip()
                    update_sql = f'UPDATE {table_ref} SET "{col_name}" = {default_val} WHERE "{col_name}" IS NULL'
                    with engine.connect() as conn:
                        conn.execute(text(update_sql))
                        conn.commit()

            # Step 3: Set NOT NULL constraint
            alter_not_null_sql = f'ALTER TABLE {table_ref} ALTER COLUMN "{col_name}" SET NOT NULL'
            with engine.connect() as conn:
                conn.execute(text(alter_not_null_sql))
                conn.commit()
        else:
            # Normal case: table is empty or column is nullable
            nullable = "NULL" if is_nullable else "NOT NULL"
            default_clause = get_default_value_sql(col_info.get('default'), col_type)

            alter_sql = f'ALTER TABLE {table_ref} ADD COLUMN "{col_name}" {col_type} {nullable}'
            if default_clause:
                alter_sql += f" {default_clause}"

            with engine.connect() as conn:
                conn.execute(text(alter_sql))
                conn.commit()

        return True
    except SQLAlchemyError as e:
        print(f"  Error: {e}")
        return False


def sync_database(dry_run: bool = False, verbose: bool = False) -> Dict:
    """
    Synchronize database with ORM models.

    Supports 3 database schemas:
    - Public (default) - Core application models
    - Canada - Staffing management system
    - Philippines - ERP system

    Args:
        dry_run: If True, only show what would be done
        verbose: If True, show detailed information

    Returns:
        Dictionary with sync results
    """
    print("=" * 80)
    print("AIR DATABASE SYNC")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print()

    results = {
        'created_tables': [],
        'updated_tables': [],
        'skipped_tables': [],
        'errors': []
    }

    try:
        engine = get_database_engine()
        inspector = inspect(engine)

        # Ensure philippines and canada schemas exist before creating tables
        print("Ensuring database schemas exist...")
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
            # Get schema from model table args (for canada/philippines models)
            schema = getattr(model.__table__, "schema", None)
            qual = f"{schema}.{table_name}" if schema else table_name

            if not table_exists(engine, table_name, schema=schema):
                # Create missing table
                if verbose:
                    print(f"Creating table: {qual}")

                if not dry_run:
                    if create_table_safe(engine, model, schema=schema):
                        results['created_tables'].append(qual)
                        print(f"  Created: {qual}")
                    else:
                        # Check if table actually exists (might have been created by another process)
                        if table_exists(engine, table_name, schema=schema):
                            print(f"  Table {qual} exists, treating as success")
                            results['created_tables'].append(qual)
                        else:
                            results['errors'].append(f"Failed to create table: {qual}")
                            print(f"  Failed: {qual}")
                else:
                    print(f"  [DRY RUN] Would create: {qual}")
                    results['created_tables'].append(qual)
            else:
                # Check for missing columns
                db_columns = get_table_columns(engine, table_name, schema=schema)
                model_columns = get_model_columns(model)

                missing_cols = {
                    name: info
                    for name, info in model_columns.items()
                    if name not in db_columns
                }

                if missing_cols:
                    if verbose:
                        print(f"Updating table: {qual}")
                        print(f"   Missing columns: {list(missing_cols.keys())}")

                    if not dry_run:
                        success = True
                        for col_name, col_info in missing_cols.items():
                            if add_column_safe(engine, table_name, col_name, col_info, schema=schema):
                                if verbose:
                                    print(f"    Added: {col_name}")
                            else:
                                success = False
                                results['errors'].append(
                                    f"Failed to add column {col_name} to {qual}"
                                )

                        if success:
                            results['updated_tables'].append(qual)
                            print(f"  Updated: {qual}")
                        else:
                            print(f"  Partially updated: {qual}")
                    else:
                        print(f"  [DRY RUN] Would update: {qual}")
                        print(f"    Would add: {', '.join(missing_cols.keys())}")
                        results['updated_tables'].append(qual)
                else:
                    results['skipped_tables'].append(qual)
                    if verbose:
                        print(f"Up to date: {qual}")

        return results

    except Exception as e:
        print(f"\nError during sync: {e}")
        import traceback
        traceback.print_exc()
        results['errors'].append(str(e))
        return results


def print_summary(results: Dict, dry_run: bool = False):
    """Print sync summary."""
    print()
    print("=" * 80)
    print("SYNC SUMMARY")
    print("=" * 80)
    print()
    
    print(f"✅ Created tables: {len(results['created_tables'])}")
    if results['created_tables']:
        for table in results['created_tables']:
            print(f"   - {table}")
    print()
    
    print(f"🔄 Updated tables: {len(results['updated_tables'])}")
    if results['updated_tables']:
        for table in results['updated_tables']:
            print(f"   - {table}")
    print()
    
    print(f"⏭️  Skipped (up to date): {len(results['skipped_tables'])}")
    print()
    
    if results['errors']:
        print(f"❌ Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"   - {error}")
        print()
    
    if dry_run:
        print("💡 Run without --dry-run to apply changes")
    else:
        print("✅ Sync complete!")


def save_report(results: Dict, output_file: str = None):
    """Save sync report to file."""
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"air_database_sync_report_{timestamp}.txt"

    output_path = Path(__file__).parent / output_file

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("Air Database Sync Report\n")
        f.write("=" * 80 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
        f.write("Schemas: public (default), philippines, canada\n")
        f.write("\n")

        f.write(f"Created tables: {len(results['created_tables'])}\n")
        for table in results['created_tables']:
            f.write(f"  - {table}\n")
        f.write("\n")

        f.write(f"Updated tables: {len(results['updated_tables'])}\n")
        for table in results['updated_tables']:
            f.write(f"  - {table}\n")
        f.write("\n")

        f.write(f"Skipped tables: {len(results['skipped_tables'])}\n")
        f.write("\n")

        if results['errors']:
            f.write(f"Errors: {len(results['errors'])}\n")
            for error in results['errors']:
                f.write(f"  - {error}\n")

    print(f"Report saved to: {output_path}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Air Database Sync Script')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )
    parser.add_argument(
        '--report',
        type=str,
        help='Save report to file (default: auto-generated name)'
    )
    
    args = parser.parse_args()
    
    print("\n🚀 Air Database Sync\n")
    
    results = sync_database(dry_run=args.dry_run, verbose=args.verbose)
    print_summary(results, dry_run=args.dry_run)
    
    if args.report or not args.dry_run:
        save_report(results, args.report)
    
    # Exit with error code if there were errors
    if results['errors']:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()


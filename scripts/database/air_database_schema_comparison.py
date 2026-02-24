"""
Air Database Schema Comparison Script
=====================================
Compare ORM models with actual database schema to identify differences.

This script helps validate that the database matches the ORM models
by comparing table structures, columns, and data types.

Features:
---------
- Identifies missing tables in database
- Detects missing columns in existing tables
- Finds type mismatches between ORM and database
- Detects nullable constraint differences
- Finds extra tables in database (not in ORM)
- Exits with error code if differences found

Usage:
------
    # Compare schemas
    python scripts/database/air_database_schema_comparison.py

Output:
-------
- Console output showing all differences
- Summary of matching/missing/different tables
- Exit code 0 if schemas match, 1 if differences found

Related Scripts:
----------------
1. air_database_validation_schemas.py - Preview schemas
2. air_database_migration_creation.py - Create/update tables
3. air_database_sync.py - Comprehensive sync (recommended)
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.db import get_db_config
from app.orm_models.base import Base
from app.orm_models import (
    # Base models
    User, Lead, Candidate, Client, Job, Campaign,
    SalesRepresentative, AIChatSession, AIChatMessage,
    SalesFollowUp, EmailProviderReport, Setting, Tenant, AISystemSetting,
    # Old system models
    Shift, ShiftCandidate, ShiftCalendar, ShiftSchedule, ShiftRate, ShiftAddon,
    PunchCard, PunchCardRecord, PunchCardAddon,
    # Additional old system models
    Addon, CandidateAddress, CandidateBankInfo,
    CandidateJobWanted, CandidateSchedule, CandidateWorkArea,
    ClientAddress, CriteriaJobWanted, CriteriaSchedule, CriteriaWorkArea,
    Invoice, InvoiceItem, InvoicePunchCard,
    Menu, UserMenu, Payroll, TaxOption,
    # Philippines/recruitment models (tenant default groupnb-philippines)
    CandidateAccount, CandidateDeduction, CandidateSkill,
    Deduction, Government, InvoiceCandidate,
    PagIbig, PhilHealth, PunchCardDeduction, PunchCardRate, PunchCardTimeRecord,
    Receipt, SSSTable, ShiftAccountManager,
    ShiftSkill, ShiftSkillLocation, ShiftSupervisor,
    Skill, Tax,
)

# Get all models
ALL_MODELS = [
    User, Lead, Candidate, Client, Job, Campaign,
    SalesRepresentative, AIChatSession, AIChatMessage,
    SalesFollowUp, EmailProviderReport, Setting, Tenant, AISystemSetting,
    Shift, ShiftCandidate, ShiftCalendar, ShiftSchedule, ShiftRate, ShiftAddon,
    PunchCard, PunchCardRecord, PunchCardAddon,
    Addon, CandidateAddress, CandidateBankInfo,
    CandidateJobWanted, CandidateSchedule, CandidateWorkArea,
    ClientAddress, CriteriaJobWanted, CriteriaSchedule, CriteriaWorkArea,
    Invoice, InvoiceItem, InvoicePunchCard,
    Menu, UserMenu, Payroll, TaxOption,
    # Philippines/recruitment models
    CandidateAccount, CandidateDeduction, CandidateSkill,
    Deduction, Government, InvoiceCandidate,
    PagIbig, PhilHealth, PunchCardDeduction, PunchCardRate, PunchCardTimeRecord,
    Receipt, SSSTable, ShiftAccountManager,
    ShiftSkill, ShiftSkillLocation, ShiftSupervisor,
    Skill, Tax,
]


def get_database_engine():
    """Create SQLAlchemy engine from database config."""
    config = get_db_config()
    connection_string = (
        f"postgresql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    return create_engine(connection_string, echo=False)


def normalize_type(type_str: str) -> str:
    """Normalize SQL type string for comparison."""
    # Remove extra whitespace and convert to lowercase
    type_str = str(type_str).lower().strip()
    # Remove length specifications for comparison
    if '(' in type_str:
        type_str = type_str.split('(')[0]
    return type_str


def get_table_columns(engine, table_name: str) -> Dict:
    """Get all columns for a table from the database."""
    inspector = inspect(engine)
    columns = {}
    try:
        for col in inspector.get_columns(table_name):
            columns[col['name']] = {
                'type': normalize_type(str(col['type'])),
                'nullable': col['nullable'],
                'default': col.get('default'),
                'autoincrement': col.get('autoincrement', False)
            }
    except Exception as e:
        print(f"  ⚠️  Error reading columns for {table_name}: {e}")
    return columns


def get_model_columns(model) -> Dict:
    """Get all columns from an ORM model."""
    columns = {}
    for column in model.__table__.columns:
        db_name = column.name
        columns[db_name] = {
            'type': normalize_type(str(column.type)),
            'nullable': column.nullable,
            'default': column.default,
            'autoincrement': column.autoincrement
        }
    return columns


def compare_schemas() -> Dict:
    """
    Compare ORM models with database schema.
    
    Returns:
        Dictionary with comparison results
    """
    print("=" * 80)
    print("AIR DATABASE SCHEMA COMPARISON")
    print("=" * 80)
    print()
    
    try:
        engine = get_database_engine()
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names())
        
        results = {
            'missing_tables': [],
            'extra_tables': [],
            'table_differences': {},
            'matching_tables': []
        }
        
        orm_tables = set()
        
        # Check each ORM model
        for model in ALL_MODELS:
            if not hasattr(model, '__tablename__'):
                continue
            
            table_name = model.__tablename__
            orm_tables.add(table_name)
            
            if table_name not in db_tables:
                results['missing_tables'].append(table_name)
                print(f"❌ Missing table: {table_name}")
            else:
                # Compare columns
                db_columns = get_table_columns(engine, table_name)
                model_columns = get_model_columns(model)
                
                differences = {
                    'missing_columns': [],
                    'extra_columns': [],
                    'type_mismatches': [],
                    'nullable_mismatches': []
                }
                
                # Check for missing columns in DB
                for col_name, col_info in model_columns.items():
                    if col_name not in db_columns:
                        differences['missing_columns'].append({
                            'name': col_name,
                            'type': col_info['type'],
                            'nullable': col_info['nullable']
                        })
                
                # Check for extra columns in DB
                for col_name in db_columns:
                    if col_name not in model_columns:
                        differences['extra_columns'].append({
                            'name': col_name,
                            'type': db_columns[col_name]['type']
                        })
                
                # Check for type/nullable mismatches
                for col_name in model_columns:
                    if col_name in db_columns:
                        model_col = model_columns[col_name]
                        db_col = db_columns[col_name]
                        
                        if model_col['type'] != db_col['type']:
                            differences['type_mismatches'].append({
                                'name': col_name,
                                'model_type': model_col['type'],
                                'db_type': db_col['type']
                            })
                        
                        if model_col['nullable'] != db_col['nullable']:
                            differences['nullable_mismatches'].append({
                                'name': col_name,
                                'model_nullable': model_col['nullable'],
                                'db_nullable': db_col['nullable']
                            })
                
                # Report differences
                has_differences = any([
                    differences['missing_columns'],
                    differences['extra_columns'],
                    differences['type_mismatches'],
                    differences['nullable_mismatches']
                ])
                
                if has_differences:
                    results['table_differences'][table_name] = differences
                    print(f"⚠️  Differences in table: {table_name}")
                    if differences['missing_columns']:
                        print(f"   Missing columns: {[c['name'] for c in differences['missing_columns']]}")
                    if differences['extra_columns']:
                        print(f"   Extra columns: {[c['name'] for c in differences['extra_columns']]}")
                    if differences['type_mismatches']:
                        for mismatch in differences['type_mismatches']:
                            print(f"   Type mismatch '{mismatch['name']}': "
                                  f"model={mismatch['model_type']}, db={mismatch['db_type']}")
                    if differences['nullable_mismatches']:
                        for mismatch in differences['nullable_mismatches']:
                            print(f"   Nullable mismatch '{mismatch['name']}': "
                                  f"model={mismatch['model_nullable']}, db={mismatch['db_nullable']}")
                else:
                    results['matching_tables'].append(table_name)
                    print(f"✅ Table matches: {table_name}")
        
        # Check for extra tables in database
        for table_name in db_tables:
            if table_name not in orm_tables:
                results['extra_tables'].append(table_name)
                print(f"ℹ️  Extra table in DB (not in ORM): {table_name}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during comparison: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def print_summary(results: Dict):
    """Print comparison summary."""
    print()
    print("=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print()
    
    print(f"✅ Matching tables: {len(results['matching_tables'])}")
    print(f"❌ Missing tables: {len(results['missing_tables'])}")
    print(f"⚠️  Tables with differences: {len(results['table_differences'])}")
    print(f"ℹ️  Extra tables in DB: {len(results['extra_tables'])}")
    print()
    
    if results['missing_tables']:
        print("Missing tables:")
        for table in results['missing_tables']:
            print(f"  - {table}")
        print()
    
    if results['table_differences']:
        print("Tables with differences:")
        for table, diffs in results['table_differences'].items():
            total_diffs = (
                len(diffs['missing_columns']) +
                len(diffs['extra_columns']) +
                len(diffs['type_mismatches']) +
                len(diffs['nullable_mismatches'])
            )
            print(f"  - {table} ({total_diffs} differences)")
        print()
    
    if results['extra_tables']:
        print("Extra tables in database:")
        for table in results['extra_tables']:
            print(f"  - {table}")
        print()


def main():
    """Main function."""
    print("\n🔍 Air Database Schema Comparison\n")
    
    results = compare_schemas()
    print_summary(results)
    
    # Exit with error code if there are differences
    if results['missing_tables'] or results['table_differences']:
        print("⚠️  Schema differences detected!")
        sys.exit(1)
    else:
        print("✅ All schemas match!")
        sys.exit(0)


if __name__ == "__main__":
    main()


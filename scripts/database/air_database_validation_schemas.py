"""
Air Database Validation Schemas Script
========================================
Preview all tables from ORM models in SQL format for validation.

This script generates SQL CREATE TABLE statements from all ORM models
to help validate that the schemas match the expected database structure.

Features:
---------
- Generates SQL CREATE TABLE statements for all ORM models
- Shows table summary (new system vs old system tables)
- Saves SQL to file for review
- Validates that schemas are correctly defined

Usage:
------
    # Preview all schemas in SQL format
    python scripts/database/air_database_validation_schemas.py

Output:
-------
- Console output with all table definitions
- SQL file: air_database_schemas.sql (saved in scripts directory)

Related Scripts:
----------------
1. air_database_migration_creation.py - Create/update tables
2. air_database_schema_comparison.py - Compare schemas
3. air_database_sync.py - Sync database (recommended)
"""

import sys
import os
from pathlib import Path

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateTable
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


def generate_sql_for_all_tables():
    """
    Generate SQL CREATE TABLE statements for all ORM models.
    
    Returns:
        dict: Dictionary mapping table names to SQL CREATE TABLE statements
    """
    # Create a dummy engine (we don't need to connect, just generate SQL)
    engine = create_engine('postgresql://dummy:dummy@dummy/dummy')
    
    sql_statements = {}
    
    print("=" * 80)
    print("AIR DATABASE VALIDATION - SQL SCHEMA PREVIEW")
    print("=" * 80)
    print()
    
    for model in ALL_MODELS:
        if hasattr(model, '__tablename__'):
            table_name = model.__tablename__
            try:
                # Generate CREATE TABLE statement
                create_table_sql = str(CreateTable(model.__table__).compile(engine))
                sql_statements[table_name] = create_table_sql
                
                print(f"Table: {table_name}")
                print("-" * 80)
                print(create_table_sql)
                print()
            except Exception as e:
                print(f"❌ Error generating SQL for {table_name}: {e}")
                print()
    
    return sql_statements


def save_sql_to_file(sql_statements: dict, output_file: str = "air_database_schemas.sql"):
    """
    Save all SQL statements to a file.
    
    Args:
        sql_statements: Dictionary of table names to SQL statements
        output_file: Output file path
    """
    output_path = Path(__file__).parent / output_file
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("-- Air Database Schema Preview\n")
        f.write("-- Generated from ORM models\n")
        f.write("-- " + "=" * 76 + "\n\n")
        
        for table_name, sql in sql_statements.items():
            f.write(f"-- Table: {table_name}\n")
            f.write("-- " + "-" * 76 + "\n")
            f.write(sql)
            f.write("\n\n")
    
    print(f"✅ SQL schemas saved to: {output_path}")
    print(f"   Total tables: {len(sql_statements)}")


def preview_table_summary():
    """Print a summary of all tables."""
    print("=" * 80)
    print("TABLE SUMMARY")
    print("=" * 80)
    print()
    
    old_system_tables = []
    new_system_tables = []
    
    for model in ALL_MODELS:
        if hasattr(model, '__tablename__'):
            table_name = model.__tablename__
            # Check if it's an old system model (uses OldSystemBaseModel)
            if hasattr(model, '__bases__'):
                if any('OldSystemBaseModel' in str(base) for base in model.__bases__):
                    old_system_tables.append(table_name)
                else:
                    new_system_tables.append(table_name)
            else:
                new_system_tables.append(table_name)
    
    print(f"New System Tables ({len(new_system_tables)}):")
    for table in sorted(new_system_tables):
        print(f"  - {table}")
    
    print()
    print(f"Old System Tables ({len(old_system_tables)}):")
    for table in sorted(old_system_tables):
        print(f"  - {table}")
    
    print()
    print(f"Total Tables: {len(new_system_tables) + len(old_system_tables)}")
    print()


def main():
    """Main function to run the validation script."""
    print("\n🔍 Air Database Validation - Schema Preview\n")
    
    try:
        # Preview summary
        preview_table_summary()
        
        # Generate SQL for all tables
        sql_statements = generate_sql_for_all_tables()
        
        # Save to file
        save_sql_to_file(sql_statements)
        
        print()
        print("=" * 80)
        print("✅ Validation complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


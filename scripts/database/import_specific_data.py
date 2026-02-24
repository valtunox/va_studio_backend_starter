"""
Import Specific Data Script
===========================
Import users and leads data from CSV files.

This script imports data from CSV files back into the database, handling
column name mappings for the users table (first_name -> firstname, etc.)
while maintaining the exact format for leads table.

Important:
----------
- Leads table: Columns are imported as-is (maintains format)
- Users table: Column names are mapped (first_name -> firstname, etc.)

Usage:
------
    # CSV files are expected under: app/data/exports/
    # You can pass just the filename (script looks in app/data/exports first):
    python scripts/import_specific_data.py --file leads_20260204_174242.csv --table users
    python scripts/import_specific_data.py --file leads_20260205_164816.csv --table leads
    python scripts/import_specific_data.py --file users_20260205_164808.csv --table users

    # Or full path: app/data/exports/yourfile.csv
    python scripts/import_specific_data.py --file app/data/exports/users.csv --table users

    # Dry run (preview changes)
    python scripts/import_specific_data.py --file users.csv --table users --dry-run

    # Skip existing records
    python scripts/import_specific_data.py --file users.csv --table users --skip-existing
"""

import sys
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection


# Column name mapping for users table (CSV column -> Database column)
# Maps old column names to new lowercase column names
USERS_COLUMN_MAPPING = {
    'first_name': 'firstname',
    'last_name': 'lastname',
    'middle_name': 'middlename',
    'full_name': 'fullname',  # If exists in CSV
    'user_name': 'username',
    'pass_word': 'password',
    'password_hash': 'password',  # Map password_hash to password
    'pass_word_hash': 'password',
    'email_address': 'email',
    'phone_number': 'phone',
    'contact_number': 'contactnumber',
    'is_active': 'is_active',  # Keep as-is if exists
    'is_verified': 'is_verified',
    'is_superuser': 'is_superuser',
    'created_at': 'createddate',
    'updated_at': 'modifieddate',
    'created_by': 'createdby',
    'updated_by': 'modifiedby',
    # Map any other common variations
    'firstname': 'firstname',  # Already correct
    'lastname': 'lastname',    # Already correct
    'middlename': 'middlename' # Already correct
}

# Reverse mapping for display purposes
USERS_REVERSE_MAPPING = {v: k for k, v in USERS_COLUMN_MAPPING.items()}


def get_table_columns(conn, table_name: str) -> Set[str]:
    """Get all column names for a table from database."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
    """, (table_name,))
    columns = {row[0] for row in cursor.fetchall()}
    cursor.close()
    return columns


def map_users_columns(csv_columns: List[str], db_columns: Set[str]) -> Dict[str, str]:
    """
    Map CSV column names to database column names for users table.
    
    Args:
        csv_columns: List of column names from CSV
        db_columns: Set of column names in database
    
    Returns:
        Dictionary mapping CSV column name to database column name
    """
    column_mapping = {}
    
    for csv_col in csv_columns:
        # Check if direct mapping exists
        if csv_col.lower() in USERS_COLUMN_MAPPING:
            db_col = USERS_COLUMN_MAPPING[csv_col.lower()]
            if db_col in db_columns:
                column_mapping[csv_col] = db_col
                continue
        
        # Check if column already matches (case-insensitive)
        csv_lower = csv_col.lower()
        for db_col in db_columns:
            if db_col.lower() == csv_lower:
                column_mapping[csv_col] = db_col
                break
        
        # If no mapping found, try to use as-is (might be new column)
        if csv_col not in column_mapping:
            # Try lowercase version
            if csv_col.lower() in db_columns:
                column_mapping[csv_col] = csv_col.lower()
            else:
                # Keep original, will be skipped if not in DB
                column_mapping[csv_col] = csv_col
    
    return column_mapping


def import_users_from_csv(conn, csv_file: Path, dry_run: bool = False, skip_existing: bool = False) -> Dict[str, Any]:
    """
    Import users data from CSV file.
    
    Args:
        conn: Database connection
        csv_file: Path to CSV file
        dry_run: If True, only preview changes
        skip_existing: If True, skip records that already exist
    
    Returns:
        Dictionary with import results
    """
    print("📋 Importing users from CSV...")
    
    results = {
        'total_rows': 0,
        'imported': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': []
    }
    
    try:
        # Get database columns
        db_columns = get_table_columns(conn, "users")
        
        # Read CSV file
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            csv_columns = reader.fieldnames
            
            if not csv_columns:
                print("  ❌ CSV file has no columns")
                return results
            
            # Map CSV columns to database columns
            column_mapping = map_users_columns(csv_columns, db_columns)
            
            print(f"  📊 Column mapping:")
            for csv_col, db_col in column_mapping.items():
                if csv_col != db_col:
                    print(f"     {csv_col} -> {db_col}")
            
            print()
            
            cursor = conn.cursor()
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                results['total_rows'] += 1
                
                try:
                    # Map row data using column mapping
                    mapped_data = {}
                    password_hash_value = None
                    
                    for csv_col, value in row.items():
                        if csv_col in column_mapping:
                            db_col = column_mapping[csv_col]
                            if db_col in db_columns:
                                # Convert empty string to None
                                mapped_data[db_col] = value if value else None
                        
                        # Also capture password_hash separately for priority handling
                        if csv_col.lower() == 'password_hash' and value:
                            password_hash_value = value
                    
                    # Handle password: prioritize password_hash if available
                    if password_hash_value and 'password' in db_columns:
                        mapped_data['password'] = password_hash_value
                    elif 'password' not in mapped_data or not mapped_data.get('password'):
                        # If password is missing/null, set a temporary password (users can reset)
                        if 'password' in db_columns:
                            mapped_data['password'] = '$2b$12$TemporaryPasswordForImport.PleaseReset'
                            if not dry_run:
                                print(f"    ⚠️  Row {row_num}: Setting temporary password (user should reset)")
                    
                    # Handle required name fields for users table
                    # If firstname is missing/null, use username as fallback
                    if 'firstname' in db_columns:
                        if not mapped_data.get('firstname'):
                            username = mapped_data.get('username') or row.get('username') or f'user_{row_num}'
                            mapped_data['firstname'] = username
                            if not dry_run:
                                print(f"    ⚠️  Row {row_num}: firstname missing, using username: {username}")
                    
                    # If lastname is missing/null, use a default value
                    if 'lastname' in db_columns:
                        if not mapped_data.get('lastname'):
                            mapped_data['lastname'] = 'User'
                            if not dry_run:
                                print(f"    ⚠️  Row {row_num}: lastname missing, using default: 'User'")
                    
                    # Handle required createdby field (default to 1 if missing)
                    if 'createdby' in db_columns:
                        if not mapped_data.get('createdby'):
                            mapped_data['createdby'] = 1  # Default system user
                            if not dry_run:
                                print(f"    ⚠️  Row {row_num}: createdby missing, using default: 1")
                    
                    # Handle required createddate field (default to current timestamp if missing)
                    if 'createddate' in db_columns:
                        if not mapped_data.get('createddate'):
                            from datetime import datetime
                            mapped_data['createddate'] = datetime.now()
                            if not dry_run:
                                print(f"    ⚠️  Row {row_num}: createddate missing, using current timestamp")
                    
                    # Skip if no valid data
                    if not mapped_data:
                        results['skipped'] += 1
                        continue
                    
                    # Check if record exists (by email or username)
                    if skip_existing:
                        email = mapped_data.get('email')
                        username = mapped_data.get('username')
                        
                        if email:
                            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
                        elif username:
                            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
                        else:
                            cursor.execute('SELECT id FROM users WHERE id = %s', (mapped_data.get('id'),))
                        
                        if cursor.fetchone():
                            results['skipped'] += 1
                            if dry_run:
                                print(f"    [DRY RUN] Would skip existing record (row {row_num})")
                            continue
                    
                    # Build INSERT statement
                    columns = list(mapped_data.keys())
                    placeholders = ['%s'] * len(columns)
                    values = [mapped_data[col] for col in columns]
                    
                    # Handle id - if provided, use it; otherwise let DB generate
                    if 'id' in mapped_data and mapped_data['id']:
                        insert_sql = f'''
                            INSERT INTO users ({', '.join(f'"{col}"' for col in columns)})
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT (id) DO NOTHING
                        '''
                    else:
                        # Remove id from columns if it's None/empty
                        if 'id' in columns and not mapped_data.get('id'):
                            idx = columns.index('id')
                            columns.pop(idx)
                            placeholders.pop(idx)
                            values.pop(idx)
                        
                        insert_sql = f'''
                            INSERT INTO users ({', '.join(f'"{col}"' for col in columns)})
                            VALUES ({', '.join(placeholders)})
                        '''
                    
                    if dry_run:
                        print(f"    [DRY RUN] Would insert row {row_num}: {mapped_data.get('email') or mapped_data.get('username', 'N/A')}")
                    else:
                        cursor.execute(insert_sql, values)
                        results['imported'] += 1
                
                except Exception as e:
                    results['errors'] += 1
                    error_msg = f"Row {row_num}: {str(e)}"
                    results['error_details'].append(error_msg)
                    print(f"    ❌ Error on row {row_num}: {e}")
            
            if not dry_run:
                conn.commit()
            
            cursor.close()
            
    except Exception as e:
        print(f"  ❌ Error importing users: {e}")
        import traceback
        traceback.print_exc()
        results['errors'] += 1
        results['error_details'].append(str(e))
    
    return results


def import_leads_from_csv(conn, csv_file: Path, dry_run: bool = False, skip_existing: bool = False) -> Dict[str, Any]:
    """
    Import leads data from CSV file (maintains exact column format).
    
    Args:
        conn: Database connection
        csv_file: Path to CSV file
        dry_run: If True, only preview changes
        skip_existing: If True, skip records that already exist
    
    Returns:
        Dictionary with import results
    """
    print("📋 Importing leads from CSV...")
    
    results = {
        'total_rows': 0,
        'imported': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': []
    }
    
    try:
        # Get database columns
        db_columns = get_table_columns(conn, "leads")
        
        # Read CSV file
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            csv_columns = reader.fieldnames
            
            if not csv_columns:
                print("  ❌ CSV file has no columns")
                return results
            
            # For leads, use columns as-is (no mapping needed)
            # Filter to only include columns that exist in database
            valid_columns = [col for col in csv_columns if col.lower() in [c.lower() for c in db_columns]]
            
            if not valid_columns:
                print("  ⚠️  No valid columns found in CSV matching database")
                return results
            
            print(f"  📊 Using {len(valid_columns)} columns (as-is from CSV)")
            print()
            
            cursor = conn.cursor()
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                results['total_rows'] += 1
                
                try:
                    # Map row data - use exact column names from CSV
                    mapped_data = {}
                    for col in valid_columns:
                        value = row.get(col)
                        # Find matching database column (case-insensitive)
                        db_col = None
                        for db_c in db_columns:
                            if db_c.lower() == col.lower():
                                db_col = db_c
                                break
                        
                        if db_col:
                            # Convert empty string to None
                            mapped_data[db_col] = value if value else None
                    
                    # Skip if no valid data
                    if not mapped_data:
                        results['skipped'] += 1
                        continue
                    
                    # Check if record exists (by email or id)
                    if skip_existing:
                        email = mapped_data.get('email')
                        record_id = mapped_data.get('id')
                        
                        if email:
                            cursor.execute('SELECT id FROM leads WHERE email = %s', (email,))
                        elif record_id:
                            cursor.execute('SELECT id FROM leads WHERE id = %s', (record_id,))
                        else:
                            # No unique identifier, skip check
                            pass
                        
                        if cursor.fetchone():
                            results['skipped'] += 1
                            if dry_run:
                                print(f"    [DRY RUN] Would skip existing record (row {row_num})")
                            continue
                    
                    # Build INSERT statement
                    columns = list(mapped_data.keys())
                    placeholders = ['%s'] * len(columns)
                    values = [mapped_data[col] for col in columns]
                    
                    # Handle id - if provided, use it; otherwise let DB generate
                    if 'id' in mapped_data and mapped_data['id']:
                        insert_sql = f'''
                            INSERT INTO leads ({', '.join(f'"{col}"' for col in columns)})
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT (id) DO NOTHING
                        '''
                    else:
                        # Remove id from columns if it's None/empty
                        if 'id' in columns and not mapped_data.get('id'):
                            idx = columns.index('id')
                            columns.pop(idx)
                            placeholders.pop(idx)
                            values.pop(idx)
                        
                        insert_sql = f'''
                            INSERT INTO leads ({', '.join(f'"{col}"' for col in columns)})
                            VALUES ({', '.join(placeholders)})
                        '''
                    
                    if dry_run:
                        print(f"    [DRY RUN] Would insert row {row_num}: {mapped_data.get('email') or mapped_data.get('id', 'N/A')}")
                    else:
                        cursor.execute(insert_sql, values)
                        results['imported'] += 1
                
                except Exception as e:
                    results['errors'] += 1
                    error_msg = f"Row {row_num}: {str(e)}"
                    results['error_details'].append(error_msg)
                    print(f"    ❌ Error on row {row_num}: {e}")
            
            if not dry_run:
                conn.commit()
            
            cursor.close()
            
    except Exception as e:
        print(f"  ❌ Error importing leads: {e}")
        import traceback
        traceback.print_exc()
        results['errors'] += 1
        results['error_details'].append(str(e))
    
    return results


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import specific tables from CSV')
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to CSV file to import'
    )
    parser.add_argument(
        '--table',
        choices=['users', 'leads'],
        required=True,
        help='Target table name'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without importing'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip records that already exist (by email/username for users, email/id for leads)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("IMPORT SPECIFIC DATA")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"File: {args.file}")
    print(f"Table: {args.table}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    csv_file = Path(args.file)
    # Use project_root already resolved at module level
    exports_dir = project_root / "app" / "data" / "exports"

    # If path is not absolute and file doesn't exist, look in app/data/exports and other locations
    if not csv_file.is_absolute() and not csv_file.exists():
        possible_paths = [
            exports_dir / csv_file.name,
            project_root / "exports" / csv_file.name,
            project_root / csv_file.name,
            Path.cwd() / "app" / "data" / "exports" / csv_file.name,
            Path.cwd() / csv_file.name,
        ]
        found = False
        for possible_path in possible_paths:
            if possible_path.exists():
                csv_file = possible_path.resolve()
                found = True
                print(f"📁 Found file at: {csv_file}")
                break
        if not found:
            print(f"❌ CSV file not found: {args.file}")
            print(f"   Export directory (place your CSV here): {exports_dir}")
            print(f"   Searched:")
            for p in possible_paths:
                print(f"     - {p}")
            sys.exit(1)
    elif csv_file.exists():
        csv_file = csv_file.resolve()
    else:
        print(f"❌ CSV file not found: {args.file}")
        print(f"   Export directory: {exports_dir}")
        sys.exit(1)
    
    try:
        conn = get_db_connection()
        
        if args.table == 'users':
            results = import_users_from_csv(conn, csv_file, dry_run=args.dry_run, skip_existing=args.skip_existing)
        elif args.table == 'leads':
            results = import_leads_from_csv(conn, csv_file, dry_run=args.dry_run, skip_existing=args.skip_existing)
        else:
            print(f"❌ Unknown table: {args.table}")
            sys.exit(1)
        
        conn.close()
        
        print()
        print("=" * 80)
        print("IMPORT SUMMARY")
        print("=" * 80)
        print(f"Total rows processed: {results['total_rows']}")
        print(f"✅ Imported: {results['imported']}")
        print(f"⏭️  Skipped: {results['skipped']}")
        print(f"❌ Errors: {results['errors']}")
        
        if results['error_details']:
            print()
            print("Error details:")
            for error in results['error_details'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(results['error_details']) > 10:
                print(f"  ... and {len(results['error_details']) - 10} more errors")
        
        print()
        
        if args.dry_run:
            print("💡 Run without --dry-run to import data")
        else:
            print("✅ Import complete!")
        
        # Exit with error code if there were errors
        if results['errors'] > 0:
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


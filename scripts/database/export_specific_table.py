"""
Export Specific Table Script
============================
Export users and leads tables to CSV format.

This script exports data from specific tables (users, leads) to CSV files
for backup, migration, or data transfer purposes.

Usage:
------
    # Export users and leads tables
    python scripts/export_specific_table.py

    # Export specific table only
    python scripts/export_specific_table.py --table users
    python scripts/export_specific_table.py --table leads

    # Specify output directory
    python scripts/export_specific_table.py --output app/data/exports
"""

import sys
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection


# Column name mapping for users table (old -> new)
# This is used during import, but we export with current database column names
USERS_COLUMN_MAPPING = {
    'first_name': 'firstname',
    'last_name': 'lastname',
    'middle_name': 'middlename',
    'firstname': 'firstname',
    'lastname': 'lastname',
    'middlename': 'middlename'
}


def get_table_columns(conn, table_name: str) -> List[str]:
    """Get all column names for a table."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s 
        ORDER BY ordinal_position
    """, (table_name,))
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return columns


def export_table_to_csv(conn, table_name: str, output_dir: Path, include_headers: bool = True) -> str:
    """
    Export a table to CSV file.
    
    Args:
        conn: Database connection
        table_name: Name of the table to export
        output_dir: Directory to save CSV file
        include_headers: Whether to include column headers
    
    Returns:
        Path to the exported CSV file
    """
    cursor = conn.cursor()
    
    try:
        # Get column names
        columns = get_table_columns(conn, table_name)
        
        if not columns:
            print(f"  ⚠️  Table {table_name} has no columns or doesn't exist")
            return None
        
        # Create output file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"{table_name}_{timestamp}.csv"
        
        # Query all data
        query = f'SELECT * FROM "{table_name}"'
        cursor.execute(query)
        
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Write to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers if requested
            if include_headers:
                writer.writerow(columns)
            
            # Write data rows
            for row in rows:
                # Convert None to empty string for CSV compatibility
                cleaned_row = ['' if val is None else val for val in row]
                writer.writerow(cleaned_row)
        
        print(f"  ✅ Exported {len(rows)} rows to: {output_file.name}")
        return str(output_file)
        
    except Exception as e:
        print(f"  ❌ Error exporting {table_name}: {e}")
        return None
    finally:
        cursor.close()


def export_users_table(conn, output_dir: Path) -> Optional[str]:
    """Export users table to CSV."""
    print("📋 Exporting users table...")
    return export_table_to_csv(conn, "users", output_dir)


def export_leads_table(conn, output_dir: Path) -> Optional[str]:
    """Export leads table to CSV."""
    print("📋 Exporting leads table...")
    return export_table_to_csv(conn, "leads", output_dir)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export specific tables to CSV')
    parser.add_argument(
        '--table',
        choices=['users', 'leads', 'both'],
        default='both',
        help='Table to export (default: both)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for CSV files (default: app/data/exports)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("EXPORT SPECIFIC TABLES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create output directory (default: app/data/exports relative to project root)
    if args.output:
        output_dir = Path(args.output)
    else:
        # Default to app/data/exports relative to project root
        output_dir = project_root / "app" / "data" / "exports"

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir.absolute()}")
    print()
    
    try:
        conn = get_db_connection()
        
        exported_files = []
        
        if args.table in ['users', 'both']:
            file_path = export_users_table(conn, output_dir)
            if file_path:
                exported_files.append(file_path)
        
        if args.table in ['leads', 'both']:
            file_path = export_leads_table(conn, output_dir)
            if file_path:
                exported_files.append(file_path)
        
        conn.close()
        
        print()
        print("=" * 80)
        print("EXPORT SUMMARY")
        print("=" * 80)
        print(f"✅ Exported {len(exported_files)} file(s):")
        for file_path in exported_files:
            print(f"   - {file_path}")
        print()
        print("✅ Export complete!")
        
    except Exception as e:
        print(f"\n❌ Error during export: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


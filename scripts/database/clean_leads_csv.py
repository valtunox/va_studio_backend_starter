"""
Clean Leads CSV Script
======================

This script cleans the leads CSV file by setting sales_representative
and follow_up columns to empty/null values.

Usage:
    python scripts/database/clean_leads_csv.py
    python scripts/database/clean_leads_csv.py --file leads_20260126_190838.csv
"""

import sys
import csv
from pathlib import Path

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent


def clean_leads_csv(csv_file_path: Path = None):
    """
    Clean leads CSV by setting sales_representative and follow_up to empty.
    
    Args:
        csv_file_path: Path to CSV file (default: searches in exports directory)
    """
    if csv_file_path is None:
        # Try to find CSV file in exports directory
        csv_file_path = project_root / 'app' / 'data' / 'exports' / 'leads_20260126_190838.csv'
    else:
        csv_file_path = Path(csv_file_path)
        if not csv_file_path.exists():
            # Try common locations
            possible_paths = [
                project_root / 'app' / 'data' / 'exports' / csv_file_path.name,
                project_root / 'exports' / csv_file_path.name,
                project_root / csv_file_path.name,
                Path('.') / csv_file_path.name
            ]
            
            found = False
            for possible_path in possible_paths:
                if possible_path.exists():
                    csv_file_path = possible_path
                    found = True
                    print(f"📁 Found file at: {csv_file_path.absolute()}")
                    break
            
            if not found:
                print(f"❌ CSV file not found: {csv_file_path}")
                return False
    
    if not csv_file_path.exists():
        print(f"❌ CSV file not found: {csv_file_path}")
        return False
    
    # Create backup
    backup_path = csv_file_path.with_suffix('.csv.backup')
    print(f"📋 Creating backup: {backup_path.name}")
    
    import shutil
    shutil.copy2(csv_file_path, backup_path)
    
    # Read and clean CSV
    print(f"🧹 Cleaning CSV: {csv_file_path.name}")
    
    rows = []
    sales_rep_col_idx = None
    follow_up_col_idx = None
    
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Read header
        header = next(reader)
        
        # Find column indices
        try:
            sales_rep_col_idx = header.index('sales_representative')
        except ValueError:
            print("  ⚠️  Column 'sales_representative' not found")
        
        try:
            follow_up_col_idx = header.index('follow_up')
        except ValueError:
            print("  ⚠️  Column 'follow_up' not found")
        
        if sales_rep_col_idx is None and follow_up_col_idx is None:
            print("  ❌ Neither column found. Nothing to clean.")
            return False
        
        rows.append(header)
        
        # Process rows
        updated_count = 0
        for row in reader:
            # Ensure row has enough columns
            while len(row) < len(header):
                row.append('')
            
            # Set sales_representative to empty
            if sales_rep_col_idx is not None:
                if row[sales_rep_col_idx] and row[sales_rep_col_idx].strip():
                    row[sales_rep_col_idx] = ''
                    updated_count += 1
            
            # Set follow_up to empty
            if follow_up_col_idx is not None:
                if row[follow_up_col_idx] and row[follow_up_col_idx].strip():
                    row[follow_up_col_idx] = ''
                    updated_count += 1
            
            rows.append(row)
    
    # Write cleaned CSV
    print(f"💾 Writing cleaned CSV...")
    with open(csv_file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"✅ Cleaned {updated_count} rows")
    print(f"✅ Backup saved: {backup_path.name}")
    print(f"✅ CSV file updated: {csv_file_path.name}")
    
    return True


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean leads CSV file')
    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='Path to CSV file (default: searches in exports directory)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("CLEAN LEADS CSV")
    print("=" * 80)
    print()
    
    success = clean_leads_csv(args.file)
    
    print()
    print("=" * 80)
    if success:
        print("✅ Script completed successfully!")
        sys.exit(0)
    else:
        print("❌ Script completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()


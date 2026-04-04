#!/usr/bin/env python3
"""
Forced Sales Tracker Update Script
===================================

This script reads veronica's sales tracker Excel file and updates the leads table
with follow-up and call information. It handles:
- Matching existing leads by email or business_name
- Updating called, follow_up, and notes fields
- Inserting new leads if they don't exist
- Logic: if called is YES, follow_up must be YES (and vice versa)

Usage:
    python forced_sales_tracker_updated.py [--excel-file path/to/veronica_tracker.xlsx]
    python forced_sales_tracker_updated.py --dry-run  # Preview changes without updating
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import pandas as pd

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection
import psycopg2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_bool(value) -> str:
    """
    Normalize various boolean/yes/no representations to 'YES' or 'NO'
    
    Handles: yes, YES, true, True, TRUE, 1, '1', 'yes', 'YES', etc.
    """
    if value is None or value == '' or pd.isna(value):
        return ''
    
    # Convert to string and strip whitespace
    str_value = str(value).strip().upper()
    
    # Check for positive values
    if str_value in ['YES', 'TRUE', '1', 'Y', 'T']:
        return 'YES'
    
    # Check for negative values
    if str_value in ['NO', 'FALSE', '0', 'N', 'F']:
        return 'NO'
    
    # Default to empty string if unclear
    return ''


def normalize_text(value) -> str:
    """Normalize text fields, handling NaN and None"""
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


def find_lead_by_email_or_business(conn, email: str, business_name: str) -> Optional[Dict]:
    """
    Find a lead by email or business_name
    
    Returns the lead record if found, None otherwise
    """
    cursor = conn.cursor()
    
    try:
        # First try to find by email (if email is valid)
        if email and email.strip() and email.lower() not in ['not found', 'none', '']:
            cursor.execute("""
                SELECT id, business_name, email, phone_number, called, follow_up, notes,
                       sales_rep_id, sales_representative
                FROM leads
                WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s))
                LIMIT 1
            """, (email,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'business_name': result[1],
                    'email': result[2],
                    'phone_number': result[3],
                    'called': result[4],
                    'follow_up': result[5],
                    'notes': result[6],
                    'sales_rep_id': result[7],
                    'sales_representative': result[8]
                }
        
        # If not found by email, try business_name
        if business_name and business_name.strip():
            cursor.execute("""
                SELECT id, business_name, email, phone_number, called, follow_up, notes,
                       sales_rep_id, sales_representative
                FROM leads
                WHERE LOWER(TRIM(business_name)) = LOWER(TRIM(%s))
                LIMIT 1
            """, (business_name,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'business_name': result[1],
                    'email': result[2],
                    'phone_number': result[3],
                    'called': result[4],
                    'follow_up': result[5],
                    'notes': result[6],
                    'sales_rep_id': result[7],
                    'sales_representative': result[8]
                }
        
        return None
        
    finally:
        cursor.close()


def get_veronica_sales_rep_id(conn) -> Optional[int]:
    """Get veronica's sales representative ID"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM sales_representatives 
            WHERE LOWER(name) = 'veronica' OR LOWER(email) = 'vfabian@valtunox.ca'
            LIMIT 1
        """)
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()


def update_existing_lead(conn, lead_id: int, row_data: Dict, veronica_rep_id: Optional[int], dry_run: bool = False) -> bool:
    """
    Update an existing lead with sales tracker information
    
    Handles logic: if called is YES, follow_up must be YES (and vice versa)
    Also assigns lead to veronica if not already assigned
    """
    cursor = conn.cursor()
    
    try:
        # Get current values including sales_rep_id
        cursor.execute("""
            SELECT called, follow_up, notes, sales_rep_id, sales_representative FROM leads WHERE id = %s
        """, (lead_id,))
        current = cursor.fetchone()
        current_called = current[0] if current else ''
        current_follow_up = current[1] if current else ''
        current_notes = current[2] if current else ''
        current_sales_rep_id = current[3] if current else None
        current_sales_representative = current[4] if current else ''
        
        # Normalize new values
        new_called = normalize_bool(row_data.get('called', ''))
        new_follow_up = normalize_bool(row_data.get('follow_up', ''))
        new_notes = normalize_text(row_data.get('notes', ''))
        
        # Apply logic: if called is YES, follow_up must be YES
        if new_called == 'YES':
            new_follow_up = 'YES'
        elif new_follow_up == 'YES' and new_called == '':
            # If follow_up is YES but called is not set, set called to YES
            new_called = 'YES'
        
        # Merge notes (append if both exist)
        if current_notes and new_notes:
            final_notes = f"{current_notes}\n\n[Updated from tracker]: {new_notes}"
        elif new_notes:
            final_notes = new_notes
        else:
            final_notes = current_notes
        
        # Check if we need to assign to veronica
        assign_to_veronica = False
        if veronica_rep_id and (current_sales_rep_id is None or current_sales_rep_id != veronica_rep_id):
            assign_to_veronica = True
        
        # Determine what changed
        changed = False
        updates = []
        
        if new_called and new_called != current_called:
            updates.append(f"called: '{current_called}' -> '{new_called}'")
            changed = True
        
        if new_follow_up and new_follow_up != current_follow_up:
            updates.append(f"follow_up: '{current_follow_up}' -> '{new_follow_up}'")
            changed = True
        
        if new_notes and new_notes != current_notes:
            updates.append("notes updated")
            changed = True
        
        if assign_to_veronica:
            updates.append(f"assigned to veronica (sales_rep_id: {veronica_rep_id})")
            changed = True
        
        if not changed:
            logger.debug(f"  No changes needed for lead ID {lead_id}")
            return False
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would update lead ID {lead_id}: {', '.join(updates)}")
            return True
        
        # Update the lead
        if assign_to_veronica:
            cursor.execute("""
                UPDATE leads
                SET called = %s,
                    follow_up = %s,
                    notes = %s,
                    sales_rep_id = %s,
                    sales_representative = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_called, new_follow_up, final_notes, veronica_rep_id, 'veronica', lead_id))
        else:
            cursor.execute("""
                UPDATE leads
                SET called = %s,
                    follow_up = %s,
                    notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_called, new_follow_up, final_notes, lead_id))
        
        logger.info(f"  ✓ Updated lead ID {lead_id}: {', '.join(updates)}")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error updating lead ID {lead_id}: {e}")
        return False
    finally:
        cursor.close()


def insert_new_lead(conn, row_data: Dict, veronica_rep_id: Optional[int], dry_run: bool = False) -> bool:
    """
    Insert a new lead if it doesn't exist in the database
    
    Requires minimal data: business_name (required), email (preferred)
    """
    cursor = conn.cursor()
    
    try:
        business_name = normalize_text(row_data.get('business_name', ''))
        email = normalize_text(row_data.get('email', ''))
        
        # Business name is required
        if not business_name:
            logger.warning(f"  ⚠️  Skipping row: missing business_name")
            return False
        
        # Normalize called and follow_up
        new_called = normalize_bool(row_data.get('called', ''))
        new_follow_up = normalize_bool(row_data.get('follow_up', ''))
        
        # Apply logic: if called is YES, follow_up must be YES
        if new_called == 'YES':
            new_follow_up = 'YES'
        elif new_follow_up == 'YES' and new_called == '':
            new_called = 'YES'
        
        # Get other fields
        phone_number = normalize_text(row_data.get('phone_number', ''))
        contact_person = normalize_text(row_data.get('contact_person', ''))
        address = normalize_text(row_data.get('address', ''))
        city = normalize_text(row_data.get('city', ''))
        state = normalize_text(row_data.get('state', ''))
        postal = normalize_text(row_data.get('postal', ''))
        country = normalize_text(row_data.get('country', ''))
        industry = normalize_text(row_data.get('industry', ''))
        category = normalize_text(row_data.get('category', ''))
        notes = normalize_text(row_data.get('notes', ''))
        website = normalize_text(row_data.get('website', ''))
        
        # Set default values if empty
        if not email:
            email = 'not found'
        if not phone_number:
            phone_number = 'not found'
        if not country:
            country = 'USA'  # Default country
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would insert new lead: {business_name} ({email})")
            return True
        
        # Insert the new lead
        cursor.execute("""
            INSERT INTO leads (
                business_name, contact_person, email, phone_number, website,
                address, city, state, postal, country,
                category, industry,
                called, follow_up, notes,
                sales_rep_id, sales_representative,
                date_generated, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            business_name, contact_person, email, phone_number, website,
            address, city, state, postal, country,
            category, industry,
            new_called, new_follow_up, notes,
            veronica_rep_id, 'veronica' if veronica_rep_id else '',
        ))
        
        logger.info(f"  ✓ Inserted new lead: {business_name} ({email})")
        return True
        
    except psycopg2.IntegrityError as e:
        # Handle unique constraint violations (business_name or email)
        logger.warning(f"  ⚠️  Lead already exists (unique constraint): {business_name}")
        return False
    except Exception as e:
        logger.error(f"  ❌ Error inserting lead {business_name}: {e}")
        return False
    finally:
        cursor.close()


def process_excel_file(excel_path: Path, dry_run: bool = False) -> Dict:
    """
    Process the Excel file and update/insert leads
    
    Returns statistics about the operation
    """
    logger.info("=" * 70)
    logger.info("FORCED SALES TRACKER UPDATE")
    logger.info("=" * 70)
    logger.info(f"Excel file: {excel_path}")
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
    logger.info("=" * 70)
    
    # Read Excel file
    try:
        logger.info(f"\n📖 Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path, engine='openpyxl')
        logger.info(f"✓ Loaded {len(df)} rows from Excel")
        
        # Show column names for debugging
        logger.info(f"Columns found: {', '.join(df.columns.tolist())}")
        
    except Exception as e:
        logger.error(f"❌ Error reading Excel file: {e}")
        return {'success': False, 'error': str(e)}
    
    # Connect to database
    try:
        logger.info("\n🔌 Connecting to database...")
        conn = get_db_connection()
        logger.info("✓ Database connection established")
    except Exception as e:
        logger.error(f"❌ Error connecting to database: {e}")
        return {'success': False, 'error': str(e)}
    
    # Get veronica's sales rep ID
    veronica_rep_id = get_veronica_sales_rep_id(conn)
    if veronica_rep_id:
        logger.info(f"✓ Found veronica's sales rep ID: {veronica_rep_id}")
    else:
        logger.warning("⚠️  veronica's sales rep ID not found, leads will be inserted without sales_rep_id")
    
    # Statistics
    stats = {
        'total_rows': len(df),
        'updated': 0,
        'inserted': 0,
        'skipped': 0,
        'errors': 0
    }
    
    # Process each row
    logger.info(f"\n📊 Processing {len(df)} rows...")
    logger.info("-" * 70)
    
    # Build column mapping (case-insensitive, flexible matching)
    column_map = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        
        # Map columns to our data structure
        if 'business' in col_lower or ('company' in col_lower and 'name' in col_lower):
            if 'business_name' not in column_map:
                column_map['business_name'] = col
        elif 'email' in col_lower:
            column_map['email'] = col
        elif ('phone' in col_lower or 'telephone' in col_lower) and 'phone_number' not in column_map:
            column_map['phone_number'] = col
        elif 'called' in col_lower:
            column_map['called'] = col
        elif 'follow' in col_lower and 'up' in col_lower:
            column_map['follow_up'] = col
        elif 'note' in col_lower and 'notes' not in column_map:
            column_map['notes'] = col
        elif 'contact' in col_lower and 'person' in col_lower:
            column_map['contact_person'] = col
        elif 'address' in col_lower:
            column_map['address'] = col
        elif 'city' in col_lower:
            column_map['city'] = col
        elif 'state' in col_lower:
            column_map['state'] = col
        elif ('postal' in col_lower or 'zip' in col_lower) and 'postal' not in column_map:
            column_map['postal'] = col
        elif 'country' in col_lower:
            column_map['country'] = col
        elif 'industry' in col_lower:
            column_map['industry'] = col
        elif 'category' in col_lower:
            column_map['category'] = col
        elif ('website' in col_lower or 'url' in col_lower) and 'website' not in column_map:
            column_map['website'] = col
    
    # Log column mapping for debugging
    if column_map:
        logger.info(f"Column mapping: {column_map}")
    else:
        logger.warning("⚠️  No columns mapped - using first column as business_name")
    
    for idx, row in df.iterrows():
        try:
            # Extract data from row using column mapping
            row_data = {}
            
            # Use mapped columns
            for key, col_name in column_map.items():
                if col_name in row:
                    row_data[key] = row[col_name]
            
            # Fallback: if no mapping found, try to use column names directly
            if not row_data.get('business_name'):
                # Try to find any column that might be business name
                for col in df.columns:
                    if 'name' in col.lower() or 'business' in col.lower() or 'company' in col.lower():
                        row_data['business_name'] = row[col]
                        break
            
            # Get essential fields
            email = normalize_text(row_data.get('email', ''))
            business_name = normalize_text(row_data.get('business_name', ''))
            
            if not email and not business_name:
                logger.warning(f"  Row {idx + 1}: Skipping - no email or business_name")
                stats['skipped'] += 1
                continue
            
            # Try to find existing lead
            existing_lead = find_lead_by_email_or_business(conn, email, business_name)
            
            if existing_lead:
                # Update existing lead
                logger.info(f"  Row {idx + 1}: Found existing lead (ID: {existing_lead['id']}) - {business_name or email}")
                if update_existing_lead(conn, existing_lead['id'], row_data, veronica_rep_id, dry_run):
                    stats['updated'] += 1
                    if not dry_run:
                        conn.commit()
                else:
                    stats['skipped'] += 1
            else:
                # Insert new lead
                logger.info(f"  Row {idx + 1}: New lead - {business_name or email}")
                if insert_new_lead(conn, row_data, veronica_rep_id, dry_run):
                    stats['inserted'] += 1
                    if not dry_run:
                        conn.commit()
                else:
                    stats['skipped'] += 1
                    
        except Exception as e:
            logger.error(f"  Row {idx + 1}: Error processing row - {e}")
            stats['errors'] += 1
            if not dry_run:
                conn.rollback()
    
    # Final commit if not dry run
    if not dry_run:
        try:
            conn.commit()
            logger.info("\n✓ All changes committed to database")
        except Exception as e:
            logger.error(f"\n❌ Error committing changes: {e}")
            conn.rollback()
    
    conn.close()
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total rows processed: {stats['total_rows']}")
    logger.info(f"  ✓ Updated: {stats['updated']}")
    logger.info(f"  ✓ Inserted: {stats['inserted']}")
    logger.info(f"  ⊘ Skipped: {stats['skipped']}")
    logger.info(f"  ❌ Errors: {stats['errors']}")
    logger.info("=" * 70)
    
    stats['success'] = True
    return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Update leads database from veronica sales tracker Excel file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python forced_sales_tracker_updated.py
  python forced_sales_tracker_updated.py --excel-file path/to/veronica_tracker.xlsx
  python forced_sales_tracker_updated.py --dry-run  # Preview changes without updating
        """
    )
    
    parser.add_argument(
        '--excel-file',
        type=str,
        default=None,
        help='Path to veronica_tracker.xlsx file (default: scripts/veronica_tracker.xlsx)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    
    args = parser.parse_args()
    
    # Determine Excel file path
    if args.excel_file:
        excel_path = Path(args.excel_file)
    else:
        # Default to scripts/veronica_tracker.xlsx
        excel_path = script_dir / 'veronica_tracker.xlsx'
    
    if not excel_path.exists():
        logger.error(f"❌ Excel file not found: {excel_path}")
        logger.error("   Please provide the correct path using --excel-file argument")
        sys.exit(1)
    
    # Process the file
    try:
        result = process_excel_file(excel_path, dry_run=args.dry_run)
        
        if result.get('success'):
            sys.exit(0)
        else:
            logger.error(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


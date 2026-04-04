"""
Create Sales Representatives from Users CSV
=============================================

This script reads users from CSV and creates sales representatives.

Usage:
    python scripts/database/create_sales_reps_from_csv.py
    python scripts/database/create_sales_reps_from_csv.py --file users_20260126_190757.csv
    python scripts/database/create_sales_reps_from_csv.py --dry-run
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_users_from_csv(csv_file_path: Path = None):
    """Load users from CSV file."""
    if csv_file_path is None:
        # Try to find CSV file in exports directory
        csv_file_path = project_root / 'app' / 'data' / 'exports' / 'users_20260126_190757.csv'
    else:
        # If path provided, check if it exists, if not search common locations
        csv_file_path = Path(csv_file_path)
        if not csv_file_path.exists():
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
                    logger.info(f"📁 Found file at: {csv_file_path.absolute()}")
                    break
            
            if not found:
                logger.error(f"❌ CSV file not found: {csv_file_path}")
                logger.error(f"   Searched in:")
                for possible_path in possible_paths:
                    logger.error(f"     - {possible_path.absolute()}")
                return []
    
    users = []
    
    if not csv_file_path.exists():
        logger.error(f"❌ CSV file not found: {csv_file_path}")
        return []
    
    try:
        logger.info(f"📋 Loading users from CSV: {csv_file_path}")
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                username = row.get('username', '').strip()
                if not username:
                    continue
                
                # Get firstname and lastname
                firstname = row.get('firstname') or row.get('first_name', '').strip()
                lastname = row.get('lastname') or row.get('last_name', '').strip()
                
                # If missing, use username as fallback
                if not firstname:
                    firstname = username
                if not lastname:
                    lastname = 'User'
                
                email = row.get('email', '').strip()
                if not email:
                    continue
                
                user = {
                    'username': username,
                    'firstname': firstname,
                    'lastname': lastname,
                    'email': email,
                    'telephone': row.get('telephone', '').strip() or row.get('phone', '').strip(),
                    'role': row.get('role', 'User').strip()
                }
                
                users.append(user)
        
        logger.info(f"✅ Loaded {len(users)} users from CSV")
        return users
        
    except Exception as e:
        logger.error(f"❌ Error loading CSV: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_sales_reps_from_users(users, dry_run=False):
    """
    Create sales representatives from users list.
    Only creates reps for users with valid emails.
    """
    try:
        logger.info("=" * 70)
        logger.info("CREATING SALES REPRESENTATIVES FROM CSV USERS")
        logger.info("=" * 70)
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
            logger.info()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        created_count = 0
        skipped_count = 0
        
        for user in users:
            try:
                email = user.get('email', '').strip()
                if not email:
                    continue
                
                # Use firstname + lastname as name, or username
                name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
                if not name or name == ' ':
                    name = user.get('username', '')
                
                # Check if sales rep already exists (by email)
                cursor.execute("""
                    SELECT id, name, email FROM sales_representatives 
                    WHERE email = %s
                """, (email,))
                
                existing = cursor.fetchone()
                if existing:
                    logger.info(f"  ⏭️  Skipped (exists): {name} - {email}")
                    skipped_count += 1
                    continue
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would create: {name} - {email}")
                    created_count += 1
                else:
                    # Get phone number - use NULL if empty
                    phone_number = user.get('telephone', '').strip()
                    if not phone_number:
                        phone_number = None
                    
                    # Insert sales representative with all required numeric fields set to 0
                    cursor.execute("""
                        INSERT INTO sales_representatives 
                        (name, email, phone_number, commission_rate, notes, active, 
                         total_leads, total_calls, total_meetings_booked, total_deals_closed, total_revenue)
                        VALUES (%s, %s, %s, %s, %s, TRUE, 0, 0, 0, 0, 0.00)
                        RETURNING id, name, email
                    """, (
                        name,
                        email,
                        phone_number,  # NULL if empty
                        0.1,  # Default commission rate
                        f"Sales Representative - Imported from CSV (User: {user.get('username', 'N/A')})"
                    ))
                    
                    result = cursor.fetchone()
                    if result:
                        rep_id, rep_name, rep_email = result
                        logger.info(f"  ✅ Created: {rep_name} (ID: {rep_id}, Email: {rep_email})")
                        created_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ Failed to create sales rep for {user.get('email', 'unknown')}: {e}")
                if not dry_run:
                    conn.rollback()
                continue
        
        if not dry_run:
            conn.commit()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Created: {created_count}")
        logger.info(f"⏭️  Skipped: {skipped_count}")
        logger.info(f"📊 Total processed: {created_count + skipped_count}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating sales reps: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create sales representatives from users CSV')
    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='Path to CSV file (default: searches in exports directory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without creating sales reps'
    )
    
    args = parser.parse_args()
    
    csv_file = None
    if args.file:
        csv_file = Path(args.file)
    
    # Load users from CSV
    users = load_users_from_csv(csv_file)
    
    if not users:
        logger.error("❌ No users loaded from CSV. Exiting.")
        sys.exit(1)
    
    # Create sales reps
    success = create_sales_reps_from_users(users, dry_run=args.dry_run)
    
    if success:
        logger.info("")
        logger.info("✅ Script completed successfully!")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("❌ Script completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()


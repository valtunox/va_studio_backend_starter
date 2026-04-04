#!/usr/bin/env python3
"""
Create New Users Script - Add Users and Sales Representatives
==============================================================

This script creates new users and their corresponding sales representative records.
It adds both user accounts and sales rep profiles in a single operation.

Usage:
    python create_new_user.py
"""

import sys
from pathlib import Path

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection
from core.auth import get_password_hash
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# NEW USERS DATA
# ============================================================================

NEW_USERS = [
    {
        'username': 'tresrtsue23232',
        'first_name': 'Terry',
        'last_name': 'Heffernan',
        'email': 'theffernan@valtunox.ca',
        'telephone': '+1 (555) 200-0000',
        'organization': 'Group NB',
        'password': 'SalesNBGroupVP@2024!',
        'role': 'VP of Sales Management'
    }
]

# ============================================================================
# NEW SALES REPRESENTATIVES DATA
# ============================================================================

NEW_SALES_REPS = [
    {
        'name': 'Terry Heffernan',
        'email': 'theffernan@valtunox.ca',
        'phone_number': '+1 (555) 200-0000',
        'commission_rate': 0.15,
        'notes': 'VP of Sales Management'
    }
]


# ============================================================================
# CREATE USERS
# ============================================================================

def create_users():
    """
    Insert new users into the database
    Uses ON CONFLICT to avoid duplicates
    """
    try:
        logger.info("=" * 70)
        logger.info("Creating New Users")
        logger.info("=" * 70)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert each user
        created_count = 0
        updated_count = 0
        
        for user in NEW_USERS:
            try:
                # Hash the password
                password_hash = get_password_hash(user['password'])
                
                cursor.execute("""
                    INSERT INTO users 
                    (username, first_name, last_name, email, telephone, organization, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (username) 
                    DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        telephone = EXCLUDED.telephone,
                        organization = EXCLUDED.organization,
                        password_hash = EXCLUDED.password_hash
                    RETURNING id, username, email,
                              (xmax = 0) AS inserted
                """, (
                    user['username'],
                    user['first_name'],
                    user['last_name'],
                    user['email'],
                    user['telephone'],
                    user['organization'],
                    password_hash
                ))
                
                result = cursor.fetchone()
                if result:
                    user_id, username, email, was_inserted = result
                    role_indicator = "👤"
                    
                    if was_inserted:
                        logger.info(f"  {role_indicator} Created: {username} ({user['role']}) - {email}")
                        created_count += 1
                    else:
                        logger.info(f"  ↻ Updated: {username} ({user['role']}) - {email}")
                        updated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to insert {user['username']}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        logger.info(f"\n✅ Users created: {created_count} created, {updated_count} updated")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ User creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# CREATE SALES REPRESENTATIVES
# ============================================================================

def create_sales_reps():
    """
    Insert new sales representatives into the database
    Uses ON CONFLICT to avoid duplicates
    """
    try:
        logger.info("=" * 70)
        logger.info("Creating Sales Representatives")
        logger.info("=" * 70)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert each sales representative
        created_count = 0
        updated_count = 0
        
        for rep in NEW_SALES_REPS:
            try:
                cursor.execute("""
                    INSERT INTO sales_representatives 
                    (name, email, phone_number, commission_rate, notes, active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (email) 
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        phone_number = EXCLUDED.phone_number,
                        commission_rate = EXCLUDED.commission_rate,
                        notes = EXCLUDED.notes,
                        active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, name, email, 
                              (xmax = 0) AS inserted
                """, (
                    rep['name'],
                    rep['email'],
                    rep['phone_number'],
                    rep['commission_rate'],
                    rep['notes']
                ))
                
                result = cursor.fetchone()
                if result:
                    rep_id, name, email, was_inserted = result
                    if was_inserted:
                        logger.info(f"  ✓ Created: {name} (ID: {rep_id}, Email: {email})")
                        created_count += 1
                    else:
                        logger.info(f"  ↻ Updated: {name} (ID: {rep_id}, Email: {email})")
                        updated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to insert {rep['name']}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        logger.info(f"\n✅ Sales representatives created: {created_count} created, {updated_count} updated")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Sales rep creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution function - creates users and sales representatives
    """
    logger.info("\n" + "=" * 70)
    logger.info("NEW USER & SALES REP CREATION SCRIPT")
    logger.info("=" * 70 + "\n")
    
    # Step 1: Create users
    if not create_users():
        logger.error("❌ Failed to create users. Stopping.")
        return False
    
    # Step 2: Create sales representatives
    if not create_sales_reps():
        logger.error("❌ Failed to create sales representatives. Stopping.")
        return False
    
    # Success summary
    logger.info("\n" + "=" * 70)
    logger.info("✅ ALL OPERATIONS COMPLETED SUCCESSFULLY!")
    logger.info("=" * 70)
    logger.info("\n🔐 LOGIN CREDENTIALS")
    logger.info("=" * 70)
    logger.info("\nTerry Heffernan:")
    logger.info("  Username: tresrtsue23232")
    logger.info("  Email: theffernan@valtunox.ca")
    logger.info("  Password: SalesVP@2024!")
    logger.info("  Role: VP of Sales Management")
    logger.info("\n⚠️  User should change password after first login!")
    logger.info("=" * 70 + "\n")
    
    return True


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

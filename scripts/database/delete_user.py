#!/usr/bin/env python3
"""
Delete User Script - Remove User from Users Table Only
========================================================

This script deletes a user from the users table by username.
It does NOT delete from the sales_representatives table.

Usage:
    python delete_user.py                    # Uses default username from script
    python delete_user.py --username veronica  # Specify username via command line
    python delete_user.py --username veronica --force  # Skip confirmation
"""

import sys
from pathlib import Path
import argparse

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

# ============================================================================
# DEFAULT USERNAME TO DELETE (change this if running without arguments)
# ============================================================================

DEFAULT_USERNAME = 'veronica'


# ============================================================================
# DELETE USER BY USERNAME
# ============================================================================

def get_user_by_username(username: str):
    """
    Retrieve user details by username
    Returns user info or None if not found
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, first_name, last_name, email, telephone, organization, created_at
            FROM users
            WHERE username = %s
        """, (username,))
        
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'email': result[4],
                'telephone': result[5],
                'organization': result[6],
                'created_at': result[7]
            }
        return None
        
    except Exception as e:
        logger.error(f"❌ Error fetching user: {e}")
        return None


def delete_user_by_username(username: str, force: bool = False):
    """
    Delete a user from the users table by username.
    Does NOT delete from sales_representatives table.
    
    Args:
        username: The username to delete
        force: If True, skip confirmation prompt
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        logger.info("=" * 70)
        logger.info("DELETE USER FROM USERS TABLE")
        logger.info("=" * 70)
        logger.info(f"Target username: {username}")
        logger.info("⚠️  NOTE: This only deletes from 'users' table, NOT 'sales_representatives'")
        logger.info("=" * 70)
        
        # Step 1: Find the user
        user = get_user_by_username(username)
        
        if not user:
            logger.error(f"\n❌ User with username '{username}' NOT FOUND in users table!")
            logger.info("\nAvailable users in the database:")
            list_all_users()
            return False
        
        # Step 2: Display user info
        logger.info("\n📋 USER FOUND:")
        logger.info("-" * 70)
        logger.info(f"  ID:           {user['id']}")
        logger.info(f"  Username:     {user['username']}")
        logger.info(f"  First Name:   {user['first_name']}")
        logger.info(f"  Last Name:    {user['last_name']}")
        logger.info(f"  Email:        {user['email']}")
        logger.info(f"  Telephone:    {user['telephone']}")
        logger.info(f"  Organization: {user['organization']}")
        logger.info(f"  Created At:   {user['created_at']}")
        logger.info("-" * 70)
        
        # Step 3: Confirmation (unless force is True)
        if not force:
            logger.info("\n⚠️  WARNING: This action cannot be undone!")
            confirmation = input(f"\nAre you sure you want to delete user '{username}'? (yes/no): ")
            
            if confirmation.lower() not in ['yes', 'y']:
                logger.info("\n❌ Deletion cancelled by user.")
                return False
        
        # Step 4: Delete the user
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM users
            WHERE username = %s
            RETURNING id, username, email
        """, (username,))
        
        deleted = cursor.fetchone()
        
        if deleted:
            conn.commit()
            logger.info(f"\n✅ SUCCESS: User deleted from users table!")
            logger.info(f"   Deleted ID: {deleted[0]}")
            logger.info(f"   Username:   {deleted[1]}")
            logger.info(f"   Email:      {deleted[2]}")
            logger.info("\n⚠️  NOTE: Sales representative record (if any) was NOT deleted.")
        else:
            logger.error(f"\n❌ Failed to delete user '{username}'")
            conn.rollback()
            cursor.close()
            conn.close()
            return False
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error deleting user: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_all_users():
    """
    List all users in the users table
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, first_name, last_name, email
            FROM users
            ORDER BY id
        """)
        
        users = cursor.fetchall()
        
        if users:
            logger.info("-" * 70)
            logger.info(f"{'ID':<5} {'Username':<20} {'Name':<25} {'Email':<30}")
            logger.info("-" * 70)
            for user in users:
                full_name = f"{user[2]} {user[3]}"
                logger.info(f"{user[0]:<5} {user[1]:<20} {full_name:<25} {user[4]:<30}")
            logger.info("-" * 70)
            logger.info(f"Total users: {len(users)}")
        else:
            logger.info("No users found in the database.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution with command line arguments"""
    parser = argparse.ArgumentParser(
        description='Delete User Script - Remove user from users table only',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python delete_user.py                         # Delete default user (veronica)
  python delete_user.py --username veronica     # Delete user by username
  python delete_user.py --username veronica --force  # Skip confirmation
  python delete_user.py --list                  # List all users
        """
    )
    
    parser.add_argument(
        '--username', '-u',
        type=str,
        default=DEFAULT_USERNAME,
        help=f'Username to delete (default: {DEFAULT_USERNAME})'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all users in the database'
    )
    
    args = parser.parse_args()
    
    try:
        if args.list:
            # List all users
            logger.info("\n" + "=" * 70)
            logger.info("ALL USERS IN DATABASE")
            logger.info("=" * 70)
            list_all_users()
            sys.exit(0)
        
        # Delete user
        success = delete_user_by_username(args.username, force=args.force)
        
        if success:
            logger.info("\n" + "=" * 70)
            logger.info("✅ USER DELETION COMPLETED")
            logger.info("=" * 70 + "\n")
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


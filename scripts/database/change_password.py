#!/usr/bin/env python3
"""
Change Password Script - Update User Password
===============================================

This script changes a user's password by looking them up via:
- Username only
- Email only
- Both username and email

Usage:
    python change_password.py --username veronica --password NewPass@123
    python change_password.py --email lpalma@groupnb.ca --password Admin@123456
    python change_password.py --email admin@nbgroupnewsletter.com --password Admin@123456
    python change_password.py --username veronica --email vfabian@groupnb.ca --password NewPass@123
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
from core.auth import get_password_hash
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# FIND USER BY USERNAME AND/OR EMAIL
# ============================================================================

def find_user(username: str = None, email: str = None):
    """
    Find user by username and/or email
    
    Args:
        username: Optional username to search
        email: Optional email to search
        
    Returns:
        User dict or None if not found
    """
    if not username and not email:
        logger.error("❌ Must provide at least username or email")
        return None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query based on provided parameters
        if username and email:
            # Search by both
            cursor.execute("""
                SELECT id, username, firstname, lastname, email, type, status, createddate
                FROM users
                WHERE username = %s AND email = %s
            """, (username, email))
        elif username:
            # Search by username only
            cursor.execute("""
                SELECT id, username, firstname, lastname, email, type, status, createddate
                FROM users
                WHERE username = %s
            """, (username,))
        else:
            # Search by email only
            cursor.execute("""
                SELECT id, username, firstname, lastname, email, type, status, createddate
                FROM users
                WHERE email = %s
            """, (email,))
        
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'username': result[1],
                'firstname': result[2],
                'lastname': result[3],
                'email': result[4],
                'type': result[5],
                'status': result[6],
                'createddate': result[7]
            }
        return None
        
    except Exception as e:
        logger.error(f"❌ Error finding user: {e}")
        return None


# ============================================================================
# CHANGE PASSWORD
# ============================================================================

def change_password(username: str = None, email: str = None, new_password: str = None, force: bool = False):
    """
    Change a user's password
    
    Args:
        username: Optional username to identify user
        email: Optional email to identify user
        new_password: The new password to set
        force: If True, skip confirmation prompt
        
    Returns:
        True if password changed successfully, False otherwise
    """
    try:
        logger.info("=" * 70)
        logger.info("CHANGE USER PASSWORD")
        logger.info("=" * 70)
        
        # Validate inputs
        if not username and not email:
            logger.error("❌ Must provide at least --username or --email")
            return False
        
        if not new_password:
            logger.error("❌ Must provide --password with the new password")
            return False
        
        # Display search criteria
        if username and email:
            logger.info(f"Searching by: username='{username}' AND email='{email}'")
        elif username:
            logger.info(f"Searching by: username='{username}'")
        else:
            logger.info(f"Searching by: email='{email}'")
        
        logger.info("=" * 70)
        
        # Step 1: Find the user
        user = find_user(username=username, email=email)
        
        if not user:
            logger.error(f"\n❌ User NOT FOUND!")
            if username:
                logger.error(f"   Username: {username}")
            if email:
                logger.error(f"   Email: {email}")
            logger.info("\nAvailable users in the database:")
            list_all_users()
            return False
        
        # Step 2: Display user info
        logger.info("\n📋 USER FOUND:")
        logger.info("-" * 70)
        logger.info(f"  ID:           {user['id']}")
        logger.info(f"  Username:     {user['username']}")
        logger.info(f"  First Name:   {user['firstname']}")
        logger.info(f"  Last Name:    {user['lastname']}")
        logger.info(f"  Email:        {user['email']}")
        logger.info(f"  Type:         {user['type']}")
        logger.info(f"  Status:       {user['status']}")
        logger.info("-" * 70)
        
        # Step 3: Confirmation (unless force is True)
        if not force:
            logger.info(f"\n⚠️  You are about to change the password for user '{user['username']}'")
            confirmation = input(f"\nProceed with password change? (yes/no): ")
            
            if confirmation.lower() not in ['yes', 'y']:
                logger.info("\n❌ Password change cancelled by user.")
                return False
        
        # Step 4: Hash the new password
        password_hash = get_password_hash(new_password)
        
        # Step 5: Update the password
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users
            SET password = %s
            WHERE id = %s
            RETURNING id, username, email
        """, (password_hash, user['id']))
        
        updated = cursor.fetchone()
        
        if updated:
            conn.commit()
            logger.info(f"\n✅ SUCCESS: Password changed!")
            logger.info(f"   User ID:    {updated[0]}")
            logger.info(f"   Username:   {updated[1]}")
            logger.info(f"   Email:      {updated[2]}")
            logger.info(f"\n🔐 New password has been set successfully!")
            logger.info("   ⚠️  Make sure to securely communicate the new password to the user.")
        else:
            logger.error(f"\n❌ Failed to update password")
            conn.rollback()
            cursor.close()
            conn.close()
            return False
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error changing password: {e}")
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
            SELECT id, username, firstname, lastname, email
            FROM users
            ORDER BY id
        """)
        
        users = cursor.fetchall()
        
        if users:
            logger.info("-" * 70)
            logger.info(f"{'ID':<5} {'Username':<20} {'Name':<25} {'Email':<30}")
            logger.info("-" * 70)
            for user in users:
                full_name = f"{user[2] or ''} {user[3] or ''}".strip()
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
        description='Change Password Script - Update user password',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Change password by username
  python change_password.py --username veronica --password NewPass@123
  
  # Change password by email
  python change_password.py --email vfabian@groupnb.ca --password NewPass@123
  
  # Change password by both username and email (more precise)
  python change_password.py --username veronica --email vfabian@groupnb.ca --password NewPass@123
  
  # Skip confirmation prompt
  python change_password.py --username veronica --password NewPass@123 --force
  
  # List all users
  python change_password.py --list
        """
    )
    
    parser.add_argument(
        '--username', '-u',
        type=str,
        default=None,
        help='Username to identify the user'
    )
    
    parser.add_argument(
        '--email', '-e',
        type=str,
        default=None,
        help='Email to identify the user'
    )
    
    parser.add_argument(
        '--password', '-p',
        type=str,
        default=None,
        help='New password to set'
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
        
        # Validate required arguments
        if not args.username and not args.email:
            parser.error("Must provide at least --username or --email")
        
        if not args.password:
            parser.error("Must provide --password with the new password")
        
        # Change password
        success = change_password(
            username=args.username,
            email=args.email,
            new_password=args.password,
            force=args.force
        )
        
        if success:
            logger.info("\n" + "=" * 70)
            logger.info("✅ PASSWORD CHANGE COMPLETED")
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


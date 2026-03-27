#!/usr/bin/env python3
"""
Migration Script: Update Existing Users with Subscription Fields
================================================================

This script updates existing users who were created before the subscription
system was implemented. It will:

1. Create default tenant 'valtunox' (if not exists)
2. Generate subscription_id for users without one
3. Create subscription records in subscriptions table
4. Create default workspace for users without one
5. Set default values for KYC, account_type, referral_code, etc.
6. Link all existing users to the 'valtunox' tenant
7. Add users as workspace owners in workspace_members table

Usage:
    python scripts/migrate_existing_users.py
    
    # Dry run (preview changes without applying):
    python scripts/migrate_existing_users.py --dry-run
    
    # Verbose output:
    python scripts/migrate_existing_users.py --verbose

Author: valtunox AI HR & Recruitment Platform
Date: 2025-12-03
"""

import os
import sys
import uuid
import re
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add app directory to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from core.db import get_db_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_subscription_id() -> str:
    """Generate a unique subscription ID"""
    return f"sub_{uuid.uuid4().hex[:16]}"


def generate_workspace_id() -> str:
    """Generate a unique workspace ID"""
    return f"ws_{uuid.uuid4().hex[:16]}"


def generate_referral_code() -> str:
    """Generate a unique referral code"""
    return f"ref_{uuid.uuid4().hex[:8].upper()}"


def create_workspace_slug(username: str) -> str:
    """Create a URL-friendly workspace slug from username"""
    slug = username.lower().strip()
    slug = re.sub(r'[^a-z0-9\-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:100] if len(slug) > 100 else slug


def ensure_unique_slug(cursor, base_slug: str) -> str:
    """Ensure the workspace slug is unique by appending a number if needed"""
    slug = base_slug
    counter = 1
    
    while True:
        cursor.execute(
            "SELECT COUNT(*) FROM workspaces WHERE workspace_slug = %s",
            (slug,)
        )
        count = cursor.fetchone()[0]
        
        if count == 0:
            return slug
        
        slug = f"{base_slug}-{counter}"
        counter += 1
        
        if counter > 100:  # Safety limit
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            return slug


def generate_tenant_id() -> str:
    """Generate a unique tenant ID"""
    return f"tenant_{uuid.uuid4().hex[:16]}"


# ============================================================================
# TENANT & SUBSCRIPTION FUNCTIONS
# ============================================================================

def get_or_create_default_tenant(cursor, dry_run: bool = False) -> int:
    """Get or create the default 'valtunox' tenant"""
    
    # Check if valtunox tenant already exists
    cursor.execute("""
        SELECT id, tenant_id, tenant_name FROM tenants 
        WHERE tenant_slug = 'valtunox' OR tenant_name = 'valtunox'
        LIMIT 1
    """)
    result = cursor.fetchone()
    
    if result:
        logger.info(f"  Found existing tenant: {result[2]} (ID: {result[0]})")
        return result[0]
    
    if dry_run:
        logger.info("  [DRY RUN] Would create default tenant 'valtunox'")
        return -1  # Placeholder for dry run
    
    # Create the default valtunox tenant
    tenant_id = generate_tenant_id()
    
    cursor.execute("""
        INSERT INTO tenants (
            tenant_id, tenant_name, tenant_slug, tenant_type,
            contact_email, billing_email, country,
            is_active, is_verified, status,
            max_users, max_workspaces, max_leads, max_campaigns,
            activated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
    """, (
        tenant_id,
        'valtunox',
        'valtunox',
        'internal',  # Internal tenant type
        'admin@valtunox.com',
        'billing@valtunox.com',
        'Canada',
        True,   # is_active
        True,   # is_verified
        'active',
        -1,     # max_users (-1 = unlimited)
        -1,     # max_workspaces
        -1,     # max_leads
        -1,     # max_campaigns
    ))
    
    tenant_db_id = cursor.fetchone()[0]
    logger.info(f"  ✅ Created default tenant 'valtunox' with ID: {tenant_db_id}")
    return tenant_db_id


def get_free_plan_id(cursor) -> int:
    """Get the ID of the free subscription plan"""
    cursor.execute("""
        SELECT id FROM subscription_plans 
        WHERE plan_code = 'free' AND is_active = TRUE
        LIMIT 1
    """)
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # If no free plan exists, return None
    logger.warning("  ⚠️  No 'free' subscription plan found!")
    return None


def get_users_without_subscription_record(cursor) -> list:
    """Get all users who don't have a subscription record"""
    cursor.execute("""
        SELECT u.id, u.username, u.email, u.subscription_id, u.created_at
        FROM users u
        LEFT JOIN subscriptions s ON u.id = s.user_id
        WHERE s.id IS NULL
        ORDER BY u.id
    """)
    
    columns = ['id', 'username', 'email', 'subscription_id', 'created_at']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_subscription_for_user(cursor, user_id: int, user_subscription_id: str,
                                  tenant_db_id: int, plan_id: int, dry_run: bool = False) -> bool:
    """Create a subscription record for a user"""
    
    if dry_run:
        logger.info(f"  [DRY RUN] Would create subscription for user {user_id}")
        return True
    
    try:
        # Generate subscription_id if user doesn't have one
        if not user_subscription_id:
            user_subscription_id = generate_subscription_id()
        
        cursor.execute("""
            INSERT INTO subscriptions (
                subscription_id, user_id, tenant_id, plan_id,
                status, billing_cycle,
                current_period_start, current_period_end,
                is_trial, amount, currency
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 
                    CURRENT_TIMESTAMP + INTERVAL '1 year', %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (
            user_subscription_id,
            user_id,
            tenant_db_id,
            plan_id,
            'active',
            'yearly',  # Free plan is yearly by default
            False,     # is_trial
            0.00,      # amount (free)
            'CAD'
        ))
        
        result = cursor.fetchone()
        return result is not None
        
    except Exception as e:
        logger.error(f"  Error creating subscription for user {user_id}: {e}")
        return False


def update_user_tenant_id(cursor, user_id: int, tenant_db_id: int, dry_run: bool = False) -> bool:
    """Update user's tenant_id field"""
    
    if dry_run:
        return True
    
    try:
        cursor.execute("""
            UPDATE users SET tenant_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (tenant_id IS NULL OR tenant_id != %s)
        """, (tenant_db_id, user_id, tenant_db_id))
        return True
    except Exception as e:
        logger.error(f"  Error updating tenant_id for user {user_id}: {e}")
        return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def check_tables_exist(cursor) -> dict:
    """Check which required tables exist"""
    tables_to_check = ['users', 'workspaces', 'workspace_members', 'subscriptions', 'tenants', 'subscription_plans']
    results = {}
    
    for table in tables_to_check:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        results[table] = cursor.fetchone()[0]
    
    return results


def check_columns_exist(cursor) -> dict:
    """Check which new columns exist in users table"""
    columns_to_check = [
        'subscription_id', 'tenant_id', 'kyc_status', 'account_type',
        'referral_code', 'email_verified', 'stripe_customer_id'
    ]
    results = {}
    
    for column in columns_to_check:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = %s
            )
        """, (column,))
        results[column] = cursor.fetchone()[0]
    
    return results


def get_users_without_subscription(cursor) -> list:
    """Get all users who don't have a subscription_id"""
    cursor.execute("""
        SELECT id, username, email, first_name, last_name, organization, role, created_at
        FROM users
        WHERE subscription_id IS NULL OR subscription_id = ''
        ORDER BY id
    """)
    
    columns = ['id', 'username', 'email', 'first_name', 'last_name', 'organization', 'role', 'created_at']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_users_without_workspace(cursor) -> list:
    """Get all users who don't have a default workspace"""
    cursor.execute("""
        SELECT u.id, u.username, u.email
        FROM users u
        LEFT JOIN workspaces w ON u.id = w.owner_id AND w.is_default = TRUE
        WHERE w.id IS NULL
        ORDER BY u.id
    """)
    
    columns = ['id', 'username', 'email']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def update_user_subscription_fields(cursor, user_id: int, subscription_id: str, 
                                    referral_code: str, dry_run: bool = False) -> bool:
    """Update a user with subscription-related fields"""
    if dry_run:
        logger.info(f"  [DRY RUN] Would update user {user_id} with subscription_id={subscription_id}")
        return True
    
    try:
        cursor.execute("""
            UPDATE users
            SET 
                subscription_id = %s,
                account_type = COALESCE(account_type, 'free'),
                referral_code = COALESCE(referral_code, %s),
                kyc_status = COALESCE(kyc_status, 'pending'),
                email_verified = COALESCE(email_verified, FALSE),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (subscription_id IS NULL OR subscription_id = '')
            RETURNING id
        """, (subscription_id, referral_code, user_id))
        
        result = cursor.fetchone()
        return result is not None
        
    except Exception as e:
        logger.error(f"  Error updating user {user_id}: {e}")
        return False


def create_workspace_for_user(cursor, user_id: int, username: str, dry_run: bool = False) -> bool:
    """Create a default workspace for a user"""
    workspace_id = generate_workspace_id()
    base_slug = create_workspace_slug(username)
    
    if dry_run:
        logger.info(f"  [DRY RUN] Would create workspace '{username}' (slug: {base_slug}) for user {user_id}")
        return True
    
    try:
        # Ensure unique slug
        workspace_slug = ensure_unique_slug(cursor, base_slug)
        
        # Create workspace
        cursor.execute("""
            INSERT INTO workspaces (
                workspace_id, owner_id, workspace_name, workspace_slug,
                workspace_type, is_default, is_active, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            workspace_id,
            user_id,
            username,  # workspace_name = username
            workspace_slug,
            'personal',
            True,  # is_default
            True,  # is_active
            'active'
        ))
        
        workspace_db_id = cursor.fetchone()[0]
        
        # Add user as owner in workspace_members
        cursor.execute("""
            INSERT INTO workspace_members (workspace_id, user_id, role, is_active, joined_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (workspace_id, user_id) DO NOTHING
        """, (workspace_db_id, user_id, 'owner', True))
        
        return True
        
    except Exception as e:
        logger.error(f"  Error creating workspace for user {user_id}: {e}")
        return False


# ============================================================================
# MAIN MIGRATION
# ============================================================================

def run_migration(dry_run: bool = False, verbose: bool = False):
    """Run the migration to update existing users"""
    
    print("=" * 70)
    print("Migration Script: Update Existing Users with Subscription Fields")
    print("=" * 70)
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ====================================================================
        # Step 1: Check prerequisites
        # ====================================================================
        print("\n📋 Step 1: Checking prerequisites...")
        
        # Check tables
        tables = check_tables_exist(cursor)
        print(f"  Tables exist: {tables}")
        
        if not tables.get('users'):
            print("  ❌ ERROR: users table does not exist!")
            return False
        
        if not tables.get('workspaces'):
            print("  ⚠️  WARNING: workspaces table does not exist. Run subscription_schema.sql first!")
            print("       Skipping workspace creation...")
            create_workspaces = False
        else:
            create_workspaces = True
        
        if not tables.get('tenants'):
            print("  ⚠️  WARNING: tenants table does not exist. Run subscription_schema.sql first!")
            print("       Skipping tenant creation...")
            create_tenants = False
        else:
            create_tenants = True
        
        if not tables.get('subscriptions'):
            print("  ⚠️  WARNING: subscriptions table does not exist. Run subscription_schema.sql first!")
            print("       Skipping subscription creation...")
            create_subscriptions = False
        else:
            create_subscriptions = True
        
        # Check columns
        columns = check_columns_exist(cursor)
        print(f"  User columns exist: {columns}")
        
        if not columns.get('subscription_id'):
            print("  ⚠️  WARNING: subscription_id column does not exist in users table.")
            print("       Run subscription_schema.sql first to add the column!")
            update_subscription = False
        else:
            update_subscription = True
        
        if not update_subscription and not create_workspaces and not create_tenants:
            print("\n  ❌ No migration needed or tables not ready. Exiting.")
            return False
        
        # ====================================================================
        # Step 2: Create/Get default tenant (valtunox)
        # ====================================================================
        tenant_db_id = None
        if create_tenants:
            print("\n🏢 Step 2: Setting up default tenant 'valtunox'...")
            tenant_db_id = get_or_create_default_tenant(cursor, dry_run)
            if tenant_db_id and tenant_db_id != -1:
                print(f"  Tenant ID: {tenant_db_id}")
        else:
            print("\n⏭️  Step 2: Skipped (tenants table not available)")
        
        # ====================================================================
        # Step 3: Get subscription plan
        # ====================================================================
        plan_id = None
        if create_subscriptions and tables.get('subscription_plans'):
            print("\n📋 Step 3: Getting free subscription plan...")
            plan_id = get_free_plan_id(cursor)
            if plan_id:
                print(f"  Free plan ID: {plan_id}")
            else:
                print("  ⚠️  No free plan found - will skip subscription creation")
                create_subscriptions = False
        else:
            print("\n⏭️  Step 3: Skipped (subscription_plans table not available)")
        
        # ====================================================================
        # Step 4: Analyze users to migrate
        # ====================================================================
        print("\n📊 Step 4: Analyzing users to migrate...")
        
        users_without_subscription = []
        users_without_workspace = []
        users_without_subscription_record = []
        
        if update_subscription:
            users_without_subscription = get_users_without_subscription(cursor)
            print(f"  Users without subscription_id field: {len(users_without_subscription)}")
        
        if create_workspaces:
            users_without_workspace = get_users_without_workspace(cursor)
            print(f"  Users without default workspace: {len(users_without_workspace)}")
        
        if create_subscriptions:
            users_without_subscription_record = get_users_without_subscription_record(cursor)
            print(f"  Users without subscription record: {len(users_without_subscription_record)}")
        
        total_to_migrate = (len(users_without_subscription) + 
                           len(users_without_workspace) + 
                           len(users_without_subscription_record))
        
        if total_to_migrate == 0:
            print("\n✅ All users already have subscription fields, workspaces, and subscription records!")
            return True
        
        # ====================================================================
        # Step 5: Update subscription fields on users table
        # ====================================================================
        if users_without_subscription and update_subscription:
            print(f"\n🔄 Step 5: Updating subscription fields for {len(users_without_subscription)} users...")
            
            success_count = 0
            fail_count = 0
            
            for user in users_without_subscription:
                subscription_id = generate_subscription_id()
                referral_code = generate_referral_code()
                
                if verbose:
                    print(f"  Processing user {user['id']}: {user['username']} ({user['email']})")
                
                if update_user_subscription_fields(cursor, user['id'], subscription_id, referral_code, dry_run):
                    success_count += 1
                    # Also update tenant_id
                    if tenant_db_id and tenant_db_id != -1:
                        update_user_tenant_id(cursor, user['id'], tenant_db_id, dry_run)
                    if verbose:
                        print(f"    ✓ Updated with subscription_id: {subscription_id}")
                else:
                    fail_count += 1
                    if verbose:
                        print(f"    ✗ Failed to update")
            
            print(f"  ✅ Updated: {success_count}, ❌ Failed: {fail_count}")
        else:
            print("\n⏭️  Step 5: Skipped (no users need subscription_id update)")
        
        # ====================================================================
        # Step 6: Create subscription records in subscriptions table
        # ====================================================================
        if users_without_subscription_record and create_subscriptions and plan_id:
            print(f"\n📝 Step 6: Creating subscription records for {len(users_without_subscription_record)} users...")
            
            success_count = 0
            fail_count = 0
            
            for user in users_without_subscription_record:
                if verbose:
                    print(f"  Processing user {user['id']}: {user['username']}")
                
                user_sub_id = user.get('subscription_id') or generate_subscription_id()
                
                if create_subscription_for_user(cursor, user['id'], user_sub_id, 
                                                 tenant_db_id, plan_id, dry_run):
                    success_count += 1
                    # Also update tenant_id on user if not set
                    if tenant_db_id and tenant_db_id != -1:
                        update_user_tenant_id(cursor, user['id'], tenant_db_id, dry_run)
                    if verbose:
                        print(f"    ✓ Created subscription record")
                else:
                    fail_count += 1
                    if verbose:
                        print(f"    ✗ Failed to create subscription")
            
            print(f"  ✅ Created: {success_count}, ❌ Failed: {fail_count}")
        else:
            print("\n⏭️  Step 6: Skipped (no users need subscription records)")
        
        # ====================================================================
        # Step 7: Create workspaces
        # ====================================================================
        if users_without_workspace and create_workspaces:
            print(f"\n🏠 Step 7: Creating workspaces for {len(users_without_workspace)} users...")
            
            success_count = 0
            fail_count = 0
            
            for user in users_without_workspace:
                if verbose:
                    print(f"  Processing user {user['id']}: {user['username']}")
                
                if create_workspace_for_user(cursor, user['id'], user['username'], dry_run):
                    success_count += 1
                    if verbose:
                        print(f"    ✓ Created workspace '{user['username']}'")
                else:
                    fail_count += 1
                    if verbose:
                        print(f"    ✗ Failed to create workspace")
            
            print(f"  ✅ Created: {success_count}, ❌ Failed: {fail_count}")
        else:
            print("\n⏭️  Step 7: Skipped (no users need workspace)")
        
        # ====================================================================
        # Step 8: Commit changes
        # ====================================================================
        if not dry_run:
            print("\n💾 Step 8: Committing changes...")
            conn.commit()
            print("  ✅ Changes committed successfully!")
        else:
            print("\n💾 Step 8: Rolling back (dry run)...")
            conn.rollback()
            print("  ✅ No changes were made (dry run)")
        
        # ====================================================================
        # Summary
        # ====================================================================
        print("\n" + "=" * 70)
        print("Migration Complete!")
        print("=" * 70)
        
        if dry_run:
            print("\n🔍 This was a DRY RUN. To apply changes, run without --dry-run flag.")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if conn:
            conn.close()


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Migrate existing users to add subscription fields and workspaces'
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output for each user'
    )
    
    args = parser.parse_args()
    
    try:
        success = run_migration(dry_run=args.dry_run, verbose=args.verbose)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


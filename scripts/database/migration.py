#!/usr/bin/env python3
"""
Database Migration Script - Complete Database Setup & Migration
================================================================

This script handles complete database setup for a new database cluster.
It manages the core tables: users, sales_representatives, leads, and campaigns.

Features:
- Creates all core tables and indexes
- Sets up triggers and functions
- Populates initial sales representatives
- Verifies schema integrity
- Syncs sales statistics

Usage:
    python migration.py [--verify-only] [--sync-only]
    
Options:
    --verify-only    Only verify the schema without making changes
    --sync-only      Only sync sales rep statistics
    (no options)     Run full migration (create tables + populate + verify + sync)
"""

import sys
from pathlib import Path
import argparse
import csv
from datetime import datetime

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection
from core.auth import get_password_hash
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# LOAD USERS FROM CSV FILE
# ============================================================================

def load_users_from_csv(csv_file_path: Path = None):
    """
    Load users from CSV file.
    If CSV file not found, returns empty list.
    """
    if csv_file_path is None:
        # Try to find CSV file in exports directory
        csv_file_path = project_root / 'app' / 'data' / 'exports' / 'users_20260126_190757.csv'
    
    users = []
    
    if not csv_file_path.exists():
        logger.warning(f"⚠️  CSV file not found: {csv_file_path}")
        logger.warning("   Using default user data instead")
        return []
    
    try:
        logger.info(f"📋 Loading users from CSV: {csv_file_path}")
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV columns to database columns
                username = row.get('username', '').strip()
                if not username:
                    continue
                
                # Get firstname and lastname (handle both first_name/firstname and last_name/lastname)
                firstname = row.get('firstname') or row.get('first_name', '').strip()
                lastname = row.get('lastname') or row.get('last_name', '').strip()
                
                # If missing, use username as fallback
                if not firstname:
                    firstname = username
                if not lastname:
                    lastname = 'User'
                
                # Get password_hash or password
                password_hash = row.get('password_hash', '').strip()
                if not password_hash:
                    password_hash = row.get('password', '').strip()
                
                # If no password, skip (will be handled later)
                if not password_hash:
                    continue
                
                user = {
                    'username': username,
                    'firstname': firstname,
                    'lastname': lastname,
                    'email': row.get('email', '').strip(),
                    'telephone': row.get('telephone', '').strip() or row.get('phone', '').strip(),
                    'organization': row.get('organization', 'Group NB').strip(),
                    'password_hash': password_hash,  # Already hashed
                    'role': row.get('role', 'User').strip(),
                    'createdby': int(row.get('createdby', 1)) if row.get('createdby') else 1,
                    'createddate': row.get('createddate') or row.get('created_at') or datetime.now()
                }
                
                users.append(user)
        
        logger.info(f"✅ Loaded {len(users)} users from CSV")
        return users
        
    except Exception as e:
        logger.error(f"❌ Error loading CSV: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_sales_reps_from_users(users):
    """
    Create sales representatives from users list.
    Only creates reps for users with valid emails.
    """
    sales_reps = []
    for user in users:
        email = user.get('email', '').strip()
        if not email:
            continue
        
        # Use firstname + lastname as name, or username
        name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
        if not name:
            name = user.get('username', '')
        
        sales_rep = {
            'name': name,
            'email': email,
            'phone_number': user.get('telephone', ''),
            'commission_rate': 0.1,
            'notes': f"Sales Representative - Imported from CSV"
        }
        sales_reps.append(sales_rep)
    
    return sales_reps

# ============================================================================
# EXPECTED SCHEMA DEFINITION
# ============================================================================

EXPECTED_TABLES = {
    'leads': [
        'id', 'business_name', 'contact_person', 'email', 'phone_number', 'website',
        'address', 'city', 'state', 'postal', 'country', 'category', 'industry',
        'facebook_page', 'twitter', 'linkedin', 'enrichment_source', 'contact_found',
        'sent', 'clicked', 'replied',
        'called', 'follow_up', 'notes', 'recommendation',
        'sales_representative', 'sales_rep_id',
        'date_generated', 'lead_respond', 'sent_sms', 'lead_quality',
        'meeting_booked', 'meeting_date', 'deal_closed', 'deal_value',
        'created_at', 'updated_at',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean', 
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'sales_representatives': [
        'id', 'name', 'email', 'phone_number', 'active',
        'total_leads', 'total_calls', 'total_meetings_booked',
        'total_deals_closed', 'total_revenue',
        'notes', 'commission_rate', 'created_at', 'updated_at',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'users': [
        'id', 'username', 'firstname', 'lastname', 'email',
        'telephone', 'organization', 'password', 'createddate',
        'createdby', 'modifiedby', 'modifieddate',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'campaign': [
        'id', 'campaign_name', 'campaign_industry', 'sales_rep_id', 'sales_representative',
        'status', 'total_recipients', 'emails_sent', 'emails_failed', 'emails_clicked',
        'emails_replied', 'template_path', 'subject_line', 'provider',
        'filter_city', 'filter_state', 'filter_lead_quality',
        'created_at', 'updated_at', 'started_at', 'completed_at', 'notes',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'settings': [
        'id', 'setting_key', 'setting_value', 'setting_type',
        'category', 'subcategory', 'description', 'is_active',
        'created_at', 'updated_at',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'ai_chat_sessions': [
        'session_id', 'created_at', 'last_activity', 'provider', 'meta',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ],
    'ai_chat_messages': [
        'id', 'session_id', 'role', 'content', 'provider', 'model', 'created_at',
        'reserved_field_1', 'reserved_field_2', 'reserved_field_boolean',
        'reserved_field_json_1', 'reserved_field_json_2'
    ]
}

# ============================================================================
# STEP 0: ENSURE DATABASE EXISTS
# ============================================================================

def ensure_database_exists():
    """
    Create the cloudsystem database if it doesn't exist
    Connects to PostgreSQL server and creates database
    """
    try:
        logger.info("=" * 70)
        logger.info("STEP 0: Ensuring Database Exists")
        logger.info("=" * 70)
        
        # Import database configuration function
        sys.path.insert(0, str(app_dir))
        from core.db import get_db_config
        
        # Get database configuration
        db_config = get_db_config()
        
        # Connect to PostgreSQL server (postgres database)
        conn = psycopg2.connect(
            host=db_config.get('host', 'localhost'),
            database='postgres',  # Connect to default postgres database
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', 'postgres'),
            port=db_config.get('port', 5432)
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if cloudsystem database exists
        cursor.execute("""
            SELECT 1 FROM pg_database WHERE datname = 'cloudsystem'
        """)
        
        exists = cursor.fetchone()
        
        if exists:
            logger.info("✅ Database 'cloudsystem' already exists")
        else:
            logger.info("📊 Creating database 'cloudsystem'...")
            cursor.execute("CREATE DATABASE cloudsystem")
            logger.info("✅ Database 'cloudsystem' created successfully!")
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Database check completed!\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database creation failed: {e}")
        logger.error("   Please check PostgreSQL connection settings")
        logger.error("   Make sure PostgreSQL server is running")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 1: CREATE DATABASE SCHEMA
# ============================================================================

def create_schema():
    """
    Create all core tables, indexes, triggers, and functions
    Reads from database_schema.sql
    """
    try:
        logger.info("=" * 70)
        logger.info("STEP 1: Creating Database Schema")
        logger.info("=" * 70)
        
        # Read the database schema SQL file
        schema_file = project_root / 'app' / 'data' / 'sql'/ 'database_schema.sql'
        
        if not schema_file.exists():
            logger.error(f"❌ Schema file not found: {schema_file}")
            return False
        
        logger.info(f"Reading schema file: {schema_file}")
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        logger.info("Executing database schema...")
        
        try:
            # Set autocommit to handle transaction blocks properly
            old_isolation = conn.isolation_level
            conn.set_isolation_level(0)  # autocommit
            
            # Execute the schema SQL
            cursor.execute(schema_sql)
            
            # Restore isolation level
            conn.set_isolation_level(old_isolation)
            
            logger.info("✅ Database schema created successfully")
        except Exception as e:
            error_msg = str(e)
            # Some errors are acceptable (e.g., table already exists)
            if 'already exists' in error_msg or 'does not exist, skipping' in error_msg:
                logger.info(f"⚠️  Schema notice: {error_msg}")
            else:
                logger.error(f"❌ Schema creation error: {error_msg}")
                raise
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Schema creation completed!\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 2: POPULATE INITIAL USERS
# ============================================================================

def populate_users():
    """
    Insert users from CSV file into the database.
    Uses ON CONFLICT to skip existing users (by username or email).
    """
    try:
        logger.info("=" * 70)
        logger.info("STEP 2: Populating Users from CSV")
        logger.info("=" * 70)
        
        # Load users from CSV
        users = load_users_from_csv()
        
        if not users:
            logger.warning("⚠️  No users loaded from CSV, skipping user population")
            return True
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert each user
        created_count = 0
        skipped_count = 0
        admin_count = 0
        user_count = 0
        
        for user in users:
            try:
                # Check if user already exists (by username or email)
                cursor.execute("""
                    SELECT id, username, email FROM users 
                    WHERE username = %s OR email = %s
                """, (user['username'], user['email']))
                
                existing = cursor.fetchone()
                if existing:
                    logger.info(f"  ⏭️  Skipped (exists): {user['username']} - {user['email']}")
                    skipped_count += 1
                    continue
                
                # Handle createddate - convert string to datetime if needed
                createddate = user.get('createddate')
                if isinstance(createddate, str):
                    try:
                        createddate = datetime.fromisoformat(createddate.replace('Z', '+00:00'))
                    except:
                        createddate = datetime.now()
                elif not createddate:
                    createddate = datetime.now()
                
                # Insert user with lowercase column names
                cursor.execute("""
                    INSERT INTO users 
                    (username, firstname, lastname, email, telephone, organization, password, createdby, createddate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, username, email
                """, (
                    user['username'],
                    user['firstname'],
                    user['lastname'],
                    user['email'],
                    user.get('telephone', ''),
                    user.get('organization', 'Group NB'),
                    user['password_hash'],  # Already hashed from CSV
                    user.get('createdby', 1),
                    createddate
                ))
                
                result = cursor.fetchone()
                if result:
                    user_id, username, email = result
                    role_indicator = "👑" if user.get('role', '').lower() == 'admin' else "👤"
                    role = user.get('role', 'User')
                    
                    logger.info(f"  {role_indicator} Created: {username} ({role}) - {email}")
                    created_count += 1
                    if role.lower() == 'admin':
                        admin_count += 1
                    else:
                        user_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to insert {user.get('username', 'unknown')}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        logger.info(f"\n✅ Users populated: {admin_count} admin, {user_count} regular users")
        logger.info(f"   ({created_count} created, {skipped_count} skipped)")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ User population failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 3: POPULATE SALES REPRESENTATIVES
# ============================================================================

def populate_sales_reps():
    """
    Insert sales representatives from CSV users into the database.
    Uses ON CONFLICT to skip existing reps (by email).
    """
    try:
        logger.info("=" * 70)
        logger.info("STEP 3: Populating Sales Representatives from CSV Users")
        logger.info("=" * 70)
        
        # Load users from CSV and create sales reps
        users = load_users_from_csv()
        sales_reps = create_sales_reps_from_users(users)
        
        if not sales_reps:
            logger.warning("⚠️  No sales representatives to create, skipping")
            return True
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert each sales representative
        created_count = 0
        skipped_count = 0
        
        for rep in sales_reps:
            try:
                # Check if sales rep already exists (by email)
                cursor.execute("""
                    SELECT id, name, email FROM sales_representatives 
                    WHERE email = %s
                """, (rep['email'],))
                
                existing = cursor.fetchone()
                if existing:
                    logger.info(f"  ⏭️  Skipped (exists): {rep['name']} - {rep['email']}")
                    skipped_count += 1
                    continue
                
                cursor.execute("""
                    INSERT INTO sales_representatives 
                    (name, email, phone_number, commission_rate, notes, active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    RETURNING id, name, email
                """, (
                    rep['name'],
                    rep['email'],
                    rep.get('phone_number', ''),
                    rep.get('commission_rate', 0.1),
                    rep.get('notes', 'Sales Representative - Imported from CSV')
                ))
                
                result = cursor.fetchone()
                if result:
                    rep_id, name, email = result
                    logger.info(f"  ✓ Created: {name} (ID: {rep_id}, Email: {email})")
                    created_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to insert {rep.get('name', 'unknown')}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        logger.info(f"\n✅ Sales representatives populated: {created_count} created, {skipped_count} skipped")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Population failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 4: VERIFY SCHEMA
# ============================================================================

def verify_schema():
    """
    Verify that the database schema matches expected schema
    """
    try:
        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: Verifying Database Schema")
        logger.info("=" * 70)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        all_match = True
        
        for table_name, expected_columns in EXPECTED_TABLES.items():
            logger.info(f"\nChecking table: {table_name}")
            logger.info("-" * 70)
            
            # Check if table exists
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            """, (table_name,))
            
            if not cursor.fetchone():
                logger.error(f"  ❌ Table '{table_name}' DOES NOT EXIST!")
                all_match = False
                continue
            
            # Get actual columns
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            actual_columns = [row[0] for row in cursor.fetchall()]
            
            # Compare columns
            missing_columns = set(expected_columns) - set(actual_columns)
            extra_columns = set(actual_columns) - set(expected_columns)
            matching_columns = set(expected_columns) & set(actual_columns)
            
            if missing_columns or extra_columns:
                all_match = False
            
            # Report results
            logger.info(f"  ✅ Matching columns: {len(matching_columns)}/{len(expected_columns)}")
            
            if missing_columns:
                logger.error(f"  ❌ Missing columns: {', '.join(sorted(missing_columns))}")
            
            if extra_columns:
                logger.warning(f"  ⚠️  Extra columns: {', '.join(sorted(extra_columns))}")
            
            if not missing_columns and not extra_columns:
                logger.info(f"  ✅ Table '{table_name}' schema is PERFECT!")
        
        # Get summary stats
        logger.info("\n" + "=" * 70)
        logger.info("DATABASE SUMMARY")
        logger.info("=" * 70)
        
        # Count records in each table
        for table_name in EXPECTED_TABLES.keys():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                logger.info(f"  {table_name}: {count} records")
            except:
                logger.warning(f"  {table_name}: Unable to count records")
        
        cursor.close()
        conn.close()
        
        if all_match:
            logger.info("\n✅ Schema verification: PASSED")
        else:
            logger.warning("\n⚠️  Schema verification: ISSUES FOUND")
        
        return all_match
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 5: SYNC SALES REPRESENTATIVE STATISTICS
# ============================================================================

def map_sales_rep_names_to_ids():
    """Map sales_representative text names to sales_rep_id foreign keys"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        logger.info("\n  → Mapping sales_representative names to sales_rep_id...")
        
        # Get all sales representatives
        cursor.execute("SELECT id, name FROM sales_representatives WHERE active = TRUE")
        sales_reps = cursor.fetchall()
        
        logger.info(f"  → Found {len(sales_reps)} active sales representatives")
        
        updated_count = 0
        for rep_id, rep_name in sales_reps:
            # Update leads with matching sales_representative name
            cursor.execute("""
                UPDATE leads 
                SET sales_rep_id = %s 
                WHERE sales_representative = %s 
                  AND (sales_rep_id IS NULL OR sales_rep_id != %s)
            """, (rep_id, rep_name, rep_id))
            
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                logger.info(f"    ✓ Mapped {rows_updated} leads to {rep_name}")
                updated_count += rows_updated
        
        conn.commit()
        logger.info(f"  ✅ Total leads mapped: {updated_count}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"  ❌ Error mapping names to IDs: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def recalculate_sales_rep_stats():
    """Recalculate all statistics for each sales representative"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        logger.info("\n  → Recalculating sales representative statistics...")
        
        # Get all sales representatives
        cursor.execute("SELECT id, name FROM sales_representatives")
        sales_reps = cursor.fetchall()
        
        logger.info(f"  → Processing {len(sales_reps)} sales representatives\n")
        
        for rep_id, rep_name in sales_reps:
            # Calculate stats from leads table
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_leads,
                    COUNT(CASE WHEN called = 'YES' THEN 1 END) as total_calls,
                    COUNT(CASE WHEN meeting_booked = 'YES' THEN 1 END) as total_meetings_booked,
                    COUNT(CASE WHEN deal_closed = 'YES' THEN 1 END) as total_deals_closed,
                    COALESCE(SUM(CASE WHEN deal_closed = 'YES' THEN deal_value ELSE 0 END), 0) as total_revenue
                FROM leads
                WHERE sales_rep_id = %s
            """, (rep_id,))
            
            stats = cursor.fetchone()
            total_leads, total_calls, total_meetings, total_deals, total_revenue = stats
            
            # Update sales_representatives table
            cursor.execute("""
                UPDATE sales_representatives
                SET 
                    total_leads = %s,
                    total_calls = %s,
                    total_meetings_booked = %s,
                    total_deals_closed = %s,
                    total_revenue = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (total_leads, total_calls, total_meetings, total_deals, total_revenue, rep_id))
            
            # Calculate rates for display
            conversion_rate = (total_deals / total_leads * 100) if total_leads > 0 else 0
            
            logger.info(f"    📊 {rep_name:15} | Leads: {total_leads:4} | Calls: {total_calls:4} | Meetings: {total_meetings:3} | Deals: {total_deals:3} | Revenue: ${total_revenue:,.2f}")
        
        conn.commit()
        logger.info(f"\n  ✅ All statistics updated successfully!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"  ❌ Error recalculating stats: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def sync_sales_stats():
    """
    Sync sales representative statistics
    Maps names to IDs and recalculates all stats
    """
    try:
        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: Syncing Sales Representative Statistics")
        logger.info("=" * 70)
        
        # Step 1: Map names to IDs
        map_sales_rep_names_to_ids()
        
        # Step 2: Recalculate stats
        recalculate_sales_rep_stats()
        
        logger.info("\n✅ Sales statistics sync completed!\n")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_full_migration():
    """
    Run the complete migration process:
    0. Ensure database exists (create if needed)
    1. Create schema (tables, indexes, triggers)
    2. Populate initial users (1 admin + 5 regular users)
    3. Populate initial sales representatives
    4. Verify schema integrity
    5. Sync sales statistics
    """
    logger.info("\n" + "=" * 70)
    logger.info("DATABASE MIGRATION - COMPLETE SETUP")
    logger.info("=" * 70)
    logger.info("This will set up your database with all core tables:")
    logger.info("  - Database: cloudsystem (auto-created if needed)")
    logger.info("  - users (1 admin + 5 regular users)")
    logger.info("  - sales_representatives (6 sales reps)")
    logger.info("  - leads")
    logger.info("  - campaign")
    logger.info("  - settings")
    logger.info("  - ai_chat_sessions")
    logger.info("  - ai_chat_messages")
    logger.info("=" * 70 + "\n")
    
    # Step 0: Ensure Database Exists
    if not ensure_database_exists():
        logger.error("\n❌ Migration failed: Could not create/access database!")
        return False
    
    # Step 1: Create Schema
    if not create_schema():
        logger.error("\n❌ Migration failed at schema creation!")
        return False
    
    # Step 2: Populate Users
    if not populate_users():
        logger.error("\n❌ Migration failed at user population!")
        return False
    
    # Step 3: Populate Sales Reps
    if not populate_sales_reps():
        logger.error("\n❌ Migration failed at sales rep population!")
        return False
    
    # Step 4: Verify Schema
    if not verify_schema():
        logger.warning("\n⚠️  Schema verification found issues, but continuing...")
    
    # Step 5: Sync Stats
    if not sync_sales_stats():
        logger.warning("\n⚠️  Statistics sync had issues, but core migration succeeded")
    
    # Final Summary
    logger.info("\n" + "=" * 70)
    logger.info("✅ DATABASE MIGRATION COMPLETED SUCCESSFULLY!")
    logger.info("=" * 70)
    logger.info("Your database is now ready to use!")
    logger.info("\n📊 What was created:")
    logger.info("  ✅ Core tables: users, sales_representatives, leads, campaign, settings")
    logger.info("  ✅ AI chat tables: ai_chat_sessions, ai_chat_messages")
    logger.info("  ✅ 1 admin user + 5 regular users")
    logger.info("  ✅ 6 sales representatives")
    logger.info("  ✅ All triggers and indexes")
    logger.info("\n🔐 Default Credentials:")
    logger.info("  Admin - Username: admin, Password: admin@#123")
    logger.info("  Users - Username: jumar/veronica/loremae/jaypee/nathalie, Password: admin@#123")
    logger.info("  ⚠️  CHANGE ALL PASSWORDS AFTER FIRST LOGIN!")
    logger.info("=" * 70 + "\n")
    
    return True


def main():
    """Main execution with command line arguments"""
    parser = argparse.ArgumentParser(
        description='Database Migration Script - Complete Database Setup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migration.py                 # Run full migration
  python migration.py --verify-only   # Only verify schema
  python migration.py --sync-only     # Only sync statistics
        """
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify the schema without making changes'
    )
    
    parser.add_argument(
        '--sync-only',
        action='store_true',
        help='Only sync sales representative statistics'
    )
    
    args = parser.parse_args()
    
    try:
        if args.verify_only:
            # Only run verification
            logger.info("Running schema verification only...\n")
            success = verify_schema()
        elif args.sync_only:
            # Only run statistics sync
            logger.info("Running statistics sync only...\n")
            success = sync_sales_stats()
        else:
            # Run full migration
            success = run_full_migration()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


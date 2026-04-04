#!/usr/bin/env python3
"""
Migration Script: Expand meeting_booked and deal_closed columns
================================================================

This script migrates the meeting_booked and deal_closed columns
from VARCHAR(10) to VARCHAR(20) to support longer status values
like "In Progress", "Rescheduled", "Pending Payment", etc.

Usage:
    python scripts/migrate_meeting_deal_columns.py
"""

import sys
from pathlib import Path
import logging

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


def migrate_columns():
    """
    Alter the meeting_booked and deal_closed columns to VARCHAR(20)
    """
    try:
        logger.info("=" * 70)
        logger.info("Migration: Expanding meeting_booked and deal_closed columns")
        logger.info("=" * 70)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check current column types
        logger.info("\nChecking current column types...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'leads'
              AND column_name IN ('meeting_booked', 'deal_closed')
            ORDER BY column_name
        """)
        
        current_types = cursor.fetchall()
        for col_name, data_type, max_length in current_types:
            logger.info(f"  {col_name}: {data_type}({max_length})")
        
        # Alter columns
        logger.info("\nAltering columns to VARCHAR(20)...")
        
        try:
            cursor.execute("""
                ALTER TABLE leads
                ALTER COLUMN meeting_booked TYPE VARCHAR(20)
            """)
            logger.info("  ✅ meeting_booked column updated to VARCHAR(20)")
        except Exception as e:
            logger.warning(f"  ⚠️  meeting_booked: {e}")
        
        try:
            cursor.execute("""
                ALTER TABLE leads
                ALTER COLUMN deal_closed TYPE VARCHAR(20)
            """)
            logger.info("  ✅ deal_closed column updated to VARCHAR(20)")
        except Exception as e:
            logger.warning(f"  ⚠️  deal_closed: {e}")
        
        conn.commit()
        
        # Verify the changes
        logger.info("\nVerifying column types...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'leads'
              AND column_name IN ('meeting_booked', 'deal_closed')
            ORDER BY column_name
        """)
        
        updated_types = cursor.fetchall()
        for col_name, data_type, max_length in updated_types:
            logger.info(f"  {col_name}: {data_type}({max_length})")
            if max_length and max_length < 20:
                logger.warning(f"  ⚠️  {col_name} is still {max_length}, expected 20")
            else:
                logger.info(f"  ✅ {col_name} is correctly set to VARCHAR(20)")
        
        cursor.close()
        conn.close()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 70)
        logger.info("\nThe columns can now store longer status values like:")
        logger.info("  - 'In Progress' (11 characters)")
        logger.info("  - 'Rescheduled' (12 characters)")
        logger.info("  - 'Pending Payment' (15 characters)")
        logger.info("  - 'Transferred' (11 characters)")
        logger.info("=" * 70 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = migrate_columns()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


"""
Fix Sales Rep ID Mapping - Link Leads to Sales Representatives
================================================================

This script fixes sales_rep_id foreign key mapping for all leads.
It matches leads to sales representatives by name and sets the
corresponding sales_rep_id where it is missing or incorrect.

Usage:
    python scripts/database/fix_sales_rep_id_mapping.py
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import sys

# Add project root to path to import app modules
from pathlib import Path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))
from core.db import get_db_connection

def fix_sales_rep_mapping():
    """Map all sales_representative names to their corresponding sales_rep_id"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all sales representatives
        print("\n=== Fetching Sales Representatives ===")
        cursor.execute("""
            SELECT id, name FROM sales_representatives 
            WHERE active = true
            ORDER BY id
        """)
        sales_reps = cursor.fetchall()
        
        print(f"Found {len(sales_reps)} active sales representatives")
        for rep in sales_reps:
            print(f"  - ID {rep['id']}: {rep['name']}")
        
        # For each sales rep, update leads where name matches but ID is null
        total_updated = 0
        for rep in sales_reps:
            rep_id = rep['id']
            rep_name = rep['name']
            
            # First check how many leads match
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM leads
                WHERE LOWER(TRIM(COALESCE(sales_representative, ''))) = LOWER(TRIM(%s))
                  AND (sales_rep_id IS NULL OR sales_rep_id != %s)
            """, (rep_name, rep_id))
            match_count = cursor.fetchone()['count']
            
            if match_count > 0:
                print(f"\nFound {match_count} leads for {rep_name} (ID: {rep_id}) to update...")
                
                # Update leads with matching name but missing or incorrect sales_rep_id
                cursor.execute("""
                    UPDATE leads 
                    SET sales_rep_id = %s
                    WHERE LOWER(TRIM(COALESCE(sales_representative, ''))) = LOWER(TRIM(%s))
                      AND (sales_rep_id IS NULL OR sales_rep_id != %s)
                """, (rep_id, rep_name, rep_id))
                
                updated_count = cursor.rowcount
                print(f"✓ Updated {updated_count} leads for {rep_name} (ID: {rep_id})")
                total_updated += updated_count
        
        # Commit the changes
        conn.commit()
        print(f"\n{'='*60}")
        print(f"✓ Total leads updated: {total_updated}")
        print(f"{'='*60}")
        
        # Verify the update for Jumar specifically
        print("\n=== Verification for Jumar ===")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN meeting_booked = 'YES' THEN 1 END) as meetings,
                COUNT(CASE WHEN deal_closed = 'YES' THEN 1 END) as deals
            FROM leads
            WHERE sales_rep_id = 2
        """)
        stats = cursor.fetchone()
        print(f"Leads with sales_rep_id=2 (Jumar): {stats['total']}")
        print(f"Meetings booked: {stats['meetings']}")
        print(f"Deals closed: {stats['deals']}")
        
        # Show sample leads with bookings/deals
        cursor.execute("""
            SELECT id, business_name, contact_person, meeting_booked, deal_closed, deal_value
            FROM leads
            WHERE sales_rep_id = 2 
              AND (meeting_booked = 'YES' OR deal_closed = 'YES')
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        sample_leads = cursor.fetchall()
        
        if sample_leads:
            print("\nSample leads with bookings/deals:")
            for lead in sample_leads:
                print(f"  - {lead['business_name']}: Meeting={lead['meeting_booked']}, Deal={lead['deal_closed']}, Value=${lead['deal_value'] or 0}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("="*60)
    print("Sales Rep ID Mapping Fix")
    print("="*60)
    fix_sales_rep_mapping()
    print("\n✓ Script completed successfully!")

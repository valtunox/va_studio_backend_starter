#!/usr/bin/env python3
"""
Update USA Country References to "usa"
======================================

This script normalizes all USA country references in the leads table to "usa" (lowercase).
It handles:
- "USA" → "usa"
- "United States of America" → "usa"
- "United States" → "usa"
- "US" → "usa"
- "U.S." → "usa"
- "U.S.A." → "usa"
- "America" → "usa"
- US state names in country field → "usa"
- US city names in country field → "usa"

The target field is "country", not "location".

Usage:
    python update_usa_country.py [--dry-run] [--batch-size 1000] [--limit 100]
    
Options:
    --dry-run        Preview changes without updating database
    --batch-size     Number of records to process per batch (default: 1000)
    --limit          Limit number of records to process (for testing)
"""

import sys
import os
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Set
import psycopg2

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# USA COUNTRY VARIATIONS
# ============================================================================

# USA country name variations (case-insensitive)
USA_COUNTRY_VARIATIONS: Set[str] = {
    'usa', 'us', 'united states', 'united states of america',
    'u.s.', 'u.s.a.', 'america', 'united states of amertica',  # Note: typo "amertica" included
    'united state', 'united state of america',  # Singular variations
    'usa.', 'us.', 'america.',  # With trailing period
}

# US State codes (2-letter abbreviations)
US_STATE_CODES: Set[str] = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC'  # District of Columbia
}

# US State full names (case-insensitive)
US_STATE_NAMES: Set[str] = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
    # Common variations
    'calif', 'calif.', 'n.y.', 'n.y', 'n.c.', 'n.c', 's.c.', 's.c',
    'n.d.', 'n.d', 's.d.', 's.d', 'w.va', 'w.va.', 'west va'
}

# Major US cities (case-insensitive) - common cities that might appear in country field
US_MAJOR_CITIES: Set[str] = {
    'new york', 'los angeles', 'chicago', 'houston', 'phoenix',
    'philadelphia', 'san antonio', 'san diego', 'dallas', 'san jose',
    'austin', 'jacksonville', 'fort worth', 'columbus', 'charlotte',
    'san francisco', 'indianapolis', 'seattle', 'denver', 'washington',
    'boston', 'el paso', 'detroit', 'nashville', 'portland',
    'oklahoma city', 'las vegas', 'memphis', 'louisville', 'baltimore',
    'milwaukee', 'albuquerque', 'tucson', 'fresno', 'sacramento',
    'kansas city', 'mesa', 'atlanta', 'omaha', 'colorado springs',
    'raleigh', 'virginia beach', 'miami', 'oakland', 'minneapolis',
    'tulsa', 'cleveland', 'wichita', 'arlington', 'new orleans',
    'tampa', 'honolulu', 'miami beach', 'long beach', 'oakland',
    'bakersfield', 'anaheim', 'santa ana', 'st. louis', 'corpus christi',
    'riverside', 'lexington', 'stockton', 'henderson', 'saint paul',
    'st. paul', 'cincinnati', 'st. petersburg', 'greensboro', 'lincoln',
    'plano', 'anchorage', 'orlando', 'irvine', 'newark', 'durham',
    'chula vista', 'toledo', 'fort wayne', 'st. petersburg', 'laredo',
    'jersey city', 'chandler', 'madison', 'lubbock', 'scottsdale',
    'reno', 'buffalo', 'glendale', 'north las vegas', 'fremont',
    'gilbert', 'chesapeake', 'garland', 'norfolk', 'boise', 'richmond',
    'spokane', 'baton rouge', 'tacoma', 'san bernardino', 'hialeah',
    'fontana', 'des moines', 'modesto', 'fayetteville', 'shreveport',
    'tacoma', 'aurora', 'montgomery', 'moreno valley', 'shreveport',
    'augusta', 'columbus', 'little rock', 'akron', 'amarillo',
    'huntington beach', 'glendale', 'grand rapids', 'salt lake city',
    'tallahassee', 'huntsville', 'grand prairie', 'knoxville', 'worcester',
    'newport news', 'brownsville', 'overland park', 'santa clarita',
    'providence', 'garden grove', 'chattanooga', 'oceanside', 'jackson',
    'fort lauderdale', 'santa rosa', 'rancho cucamonga', 'port st. lucie',
    'ontario', 'vancouver', 'sioux falls', 'chula vista', 'peoria',
    'eugene', 'corona', 'palmdale', 'salem', 'elk grove', 'lancaster',
    'pembroke pines', 'pomona', 'paterson', 'rockford', 'joliet',
    'torrance', 'bridgeport', 'hollywood', 'napa', 'hampton', 'lakewood',
    'sunnyvale', 'escondido', 'pomona', 'pasadena', 'savannah',
    'orange', 'fullerton', 'dayton', 'mesquite', 'syracuse', 'carrollton',
    'cary', 'mckinney', 'warren', 'roseville', 'thornton', 'beaumont',
    'allentown', 'aberdeen', 'bellevue', 'west valley city', 'richardson',
    'pueblo', 'pearland', 'round rock', 'norman', 'columbia', 'elgin',
    'sterling heights', 'westminster', 'clearwater', 'waterbury',
    'fairfield', 'billings', 'murrieta', 'lowell', 'san angelo',
    'high point', 'west covina', 'richmond', 'murrieta', 'cambridge',
    'antioch', 'temecula', 'richmond', 'killeen', 'concord', 'lakeland',
    'topeka', 'daly city', 'el cajon', 'santa clara', 'st. petersburg',
    'thousand oaks', 'vallejo', 'palmdale', 'columbia', 'athens',
    'ventura', 'allentown', 'evansville', 'richmond', 'sterling heights',
    'fargo', 'wilmington', 'arlington', 'clovis', 'beaumont', 'independence',
    'ann arbor', 'provo', 'peoria', 'norman', 'berkeley', 'lansing',
    'pasadena', 'pomona', 'chula vista', 'santa monica', 'santa barbara',
    'santa cruz', 'santa fe', 'santa clara', 'santa rosa', 'santa ana',
    'san francisco', 'san diego', 'san jose', 'san antonio', 'san bernardino',
    'san angelo', 'st. louis', 'st. paul', 'st. petersburg', 'new york city',
    'new orleans', 'newark', 'newport news', 'newport beach', 'new haven',
    'new bedford', 'new london', 'new britain', 'new rochelle', 'new brunswick',
    'new castle', 'new smyrna beach', 'new iberia', 'new port richey',
    'new albany', 'new castle', 'new philadelphia', 'new ulm', 'new braunfels',
    'new bedford', 'new london', 'new britain', 'new rochelle', 'new brunswick',
    'new castle', 'new smyrna beach', 'new iberia', 'new port richey',
    'new albany', 'new castle', 'new philadelphia', 'new ulm', 'new braunfels'
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_text(value) -> str:
    """Normalize text fields, handling None and empty strings"""
    if value is None:
        return ''
    return str(value).strip()


def normalize_for_matching(text: str) -> str:
    """Normalize text for case-insensitive matching"""
    if not text:
        return ''
    # Convert to lowercase, remove extra spaces, remove punctuation
    text = text.lower().strip()
    # Remove common punctuation
    text = re.sub(r'[.,;:!?]', '', text)
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)
    return text


def is_usa_country_reference(country: str) -> bool:
    """
    Check if a country value represents USA.
    
    Returns True if the country field contains:
    - USA country name variations (USA, United States, etc.)
    - US state codes (CA, NY, TX, etc.)
    - US state names (California, New York, etc.)
    - US city names (New York, Los Angeles, etc.)
    
    Args:
        country: Country field value to check
        
    Returns:
        True if this is a USA reference, False otherwise
    """
    if not country:
        return False
    
    country_stripped = country.strip()
    if not country_stripped:
        return False
    
    country_normalized = normalize_for_matching(country_stripped)
    country_upper = country_stripped.upper()
    country_lower = country_stripped.lower()
    
    # First, check for exact "USA" match (any case) - most common case
    if country_upper == "USA" or country_lower == "usa":
        return True
    
    # Check USA country name variations (normalized)
    if country_normalized in USA_COUNTRY_VARIATIONS:
        return True
    
    # Check exact match with variations (case-insensitive, original)
    if country_lower in USA_COUNTRY_VARIATIONS:
        return True
    
    # Check US state codes (exact match, case-insensitive)
    if country_upper in US_STATE_CODES:
        return True
    
    # Check US state names (normalized, case-insensitive)
    if country_normalized in US_STATE_NAMES:
        return True
    
    # Check US major cities (normalized, case-insensitive)
    if country_normalized in US_MAJOR_CITIES:
        return True
    
    # Check for partial matches (e.g., "United States" in "United States of America")
    for variation in USA_COUNTRY_VARIATIONS:
        if variation in country_normalized:
            return True
    
    # Check for state name partial matches (e.g., "California" in "California, USA")
    for state_name in US_STATE_NAMES:
        if state_name in country_normalized:
            return True
    
    # Check for city name partial matches (e.g., "New York" in "New York, NY")
    for city_name in US_MAJOR_CITIES:
        if city_name in country_normalized:
            return True
    
    return False


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_leads_with_usa_country(conn, limit: Optional[int] = None, batch_size: int = 1000):
    """
    Get leads where country field contains USA-related values.
    Returns a generator that yields batches of leads.
    
    Uses a two-phase approach:
    1. First, get all records that might be USA (broad SQL filter)
    2. Then filter in Python using the robust matching function
    """
    cursor = conn.cursor()
    
    try:
        # Get all leads with non-null, non-empty country
        # We'll do the detailed matching in Python to catch all variations
        # This ensures we don't miss any edge cases
        cursor.execute("""
            SELECT id, country
            FROM leads 
            WHERE country IS NOT NULL 
              AND TRIM(COALESCE(country, '')) != ''
            ORDER BY id
        """)
        
        # Process in batches to avoid loading everything into memory
        batch = []
        processed = 0
        
        while True:
            row = cursor.fetchone()
            if row is None:
                # Yield remaining batch
                if batch:
                    yield batch
                break
            
            lead_id, country = row
            
            # Check if this is a USA reference
            if is_usa_country_reference(country):
                batch.append((lead_id, country))
                processed += 1
                
                # Yield batch when it reaches batch_size
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
                
                # Check limit
                if limit and processed >= limit:
                    # Yield remaining batch
                    if batch:
                        yield batch
                    break
                
    finally:
        cursor.close()


def update_lead_country(conn, lead_id: int, country: str, dry_run: bool = False) -> bool:
    """Update country for a single lead"""
    if dry_run:
        return True
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE leads
            SET country = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (country, lead_id))
        return True
    except Exception as e:
        logger.error(f"Error updating lead {lead_id}: {e}")
        return False
    finally:
        cursor.close()


def update_exact_usa_matches(conn, dry_run: bool = False) -> int:
    """
    Directly update exact "USA" matches (case-insensitive) via SQL.
    This is faster and more reliable for the most common case.
    
    Returns:
        Number of records updated
    """
    cursor = conn.cursor()
    try:
        # Count exact USA matches (case-insensitive)
        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE country IS NOT NULL
              AND UPPER(TRIM(country)) = 'USA'
              AND LOWER(TRIM(country)) != 'usa'
        """)
        count = cursor.fetchone()[0]
        
        if count > 0:
            if not dry_run:
                cursor.execute("""
                    UPDATE leads
                    SET country = 'usa', updated_at = CURRENT_TIMESTAMP
                    WHERE country IS NOT NULL
                      AND UPPER(TRIM(country)) = 'USA'
                      AND LOWER(TRIM(country)) != 'usa'
                """)
                conn.commit()
                logger.info(f"✓ Directly updated {count:,} exact 'USA' matches to 'usa'")
            else:
                logger.info(f"  [DRY RUN] Would update {count:,} exact 'USA' matches to 'usa'")
        
        return count
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating exact USA matches: {e}")
        return 0
    finally:
        cursor.close()


def process_leads(conn, dry_run: bool = False, batch_size: int = 1000, limit: Optional[int] = None):
    """
    Process all leads with USA-related country values and update them to "usa"
    """
    logger.info("=" * 70)
    logger.info("UPDATE USA COUNTRY REFERENCES TO 'usa'")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
    logger.info(f"Batch size: {batch_size}")
    if limit:
        logger.info(f"Limit: {limit} records")
    logger.info("=" * 70)
    
    # First, handle exact "USA" matches directly (fastest)
    logger.info("\n📋 Phase 1: Updating exact 'USA' matches...")
    exact_usa_count = update_exact_usa_matches(conn, dry_run=dry_run)
    
    logger.info("\n📋 Phase 2: Processing other USA variations...")
    
    stats = {
        'total_processed': 0,
        'updated': 0,
        'exact_usa_updates': exact_usa_count,  # Direct SQL updates for exact "USA"
        'errors': 0,
        'skipped': 0,
        'sample_changes': []  # Store sample changes for dry-run display
    }
    
    # Get total count for progress tracking (estimate)
    # We'll count as we process, but get an initial estimate
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM leads 
            WHERE country IS NOT NULL 
              AND TRIM(COALESCE(country, '')) != ''
        """)
        total_with_country = cursor.fetchone()[0]
        logger.info(f"Total leads with country values: {total_with_country:,}")
        logger.info("Scanning for USA-related country values...")
        # We'll update total_to_process as we process
        total_to_process = None  # Will be determined during processing
    finally:
        cursor.close()
    
    # Process in batches
    batch_num = 0
    processed_count = 0
    total_usa_found = 0
    
    for batch in get_leads_with_usa_country(conn, limit=limit, batch_size=batch_size):
        batch_num += 1
        total_usa_found += len(batch)
        
        # Update total_to_process on first batch
        if total_to_process is None:
            if limit:
                total_to_process = limit
            else:
                # Estimate based on first batch (rough estimate)
                total_to_process = total_usa_found * 2  # Will be updated as we go
        
        processed_count += len(batch)
        progress_pct = (processed_count / total_to_process * 100) if total_to_process and total_to_process > 0 else 0
        logger.info(f"\nProcessing batch {batch_num} ({len(batch)} records) - Progress: {processed_count:,} processed...")
        
        batch_updates = []
        for lead_id, old_country in batch:
            try:
                # Always update to "usa" (lowercase)
                new_country = "usa"
                
                # Skip if already "usa"
                if old_country and old_country.strip().lower() == "usa":
                    stats['skipped'] += 1
                    continue
                
                batch_updates.append((lead_id, new_country, old_country))
                stats['total_processed'] += 1
                stats['updated'] += 1
                
                # Store sample changes for dry-run display
                if len(stats['sample_changes']) < 10:
                    stats['sample_changes'].append((lead_id, old_country, new_country))
                
            except Exception as e:
                logger.error(f"Error processing lead {lead_id}: {e}")
                stats['errors'] += 1
        
        # Update batch
        if not dry_run and batch_updates:
            cursor = conn.cursor()
            try:
                for lead_id, new_country, old_country in batch_updates:
                    cursor.execute("""
                        UPDATE leads
                        SET country = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (new_country, lead_id))
                
                conn.commit()
                logger.info(f"  ✓ Updated {len(batch_updates)} leads in batch {batch_num}")
            except Exception as e:
                conn.rollback()
                logger.error(f"  ❌ Error updating batch {batch_num}: {e}")
                stats['errors'] += len(batch_updates)
            finally:
                cursor.close()
        elif dry_run:
            # Show sample updates
            logger.info(f"  [DRY RUN] Would update {len(batch_updates)} leads")
            for lead_id, old_country, new_country in batch_updates[:5]:
                logger.info(f"    Lead {lead_id}: '{old_country}' → '{new_country}'")
            if len(batch_updates) > 5:
                logger.info(f"    ... and {len(batch_updates) - 5} more")
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total processed: {stats['total_processed']:,}")
    total_updated = stats['updated'] + stats['exact_usa_updates']
    logger.info(f"  → Updated to 'usa': {total_updated:,}")
    if stats['exact_usa_updates'] > 0:
        logger.info(f"    (Direct 'USA' updates: {stats['exact_usa_updates']:,})")
    logger.info(f"  → Skipped (already 'usa'): {stats['skipped']:,}")
    logger.info(f"  → Errors: {stats['errors']:,}")
    
    if dry_run and stats['sample_changes']:
        logger.info("\nSample changes that would be made:")
        for lead_id, old_country, new_country in stats['sample_changes']:
            logger.info(f"  Lead {lead_id}: '{old_country}' → '{new_country}'")
    
    logger.info("=" * 70)
    
    return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Update USA country references in leads table to "usa"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_usa_country.py --dry-run
  python update_usa_country.py --batch-size 500
  python update_usa_country.py --limit 100 --dry-run
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of records to process per batch (default: 1000)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of records to process (for testing)'
    )
    
    args = parser.parse_args()
    
    # Connect to database
    try:
        logger.info("\n🔌 Connecting to database...")
        conn = get_db_connection()
        logger.info("✓ Database connection established")
    except Exception as e:
        logger.error(f"❌ Error connecting to database: {e}")
        sys.exit(1)
    
    try:
        # Process leads
        stats = process_leads(
            conn,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit
        )
        
        if args.dry_run:
            logger.info("\n⚠️  This was a DRY RUN. No changes were made to the database.")
            logger.info("   Run without --dry-run to apply changes.")
        else:
            logger.info("\n✅ USA country updates completed successfully!")
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Process interrupted by user")
        conn.rollback()
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()


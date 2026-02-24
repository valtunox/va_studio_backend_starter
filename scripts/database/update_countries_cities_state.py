#!/usr/bin/env python3
"""
Update Countries Based on Cities and States
============================================

This script updates the country field in the leads table based on city and state information.
It handles:
- Canadian provinces/territories (ON, QC, BC, AB, etc.) → Canada
- US states (NY, CA, TX, etc.) → USA
- Australian states/territories (QLD, NSW, VIC, etc.) → Australia
- Major cities mapped to their countries
- Edge cases like "Ottawa, ON" (city with state code in city field)
- Default to Canada if both city and state are null

Usage:
    python update_countries_cities_state.py [--dry-run] [--batch-size 1000] [--limit 100]
    
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
from typing import Dict, Optional, Tuple
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
# COUNTRY MAPPINGS
# ============================================================================

# Canadian Provinces and Territories (codes and full names)
CANADIAN_PROVINCES: Dict[str, str] = {
    # Province codes
    'ON': 'Canada', 'QC': 'Canada', 'BC': 'Canada', 'AB': 'Canada',
    'MB': 'Canada', 'SK': 'Canada', 'NS': 'Canada', 'NB': 'Canada',
    'NL': 'Canada', 'PE': 'Canada', 'YT': 'Canada', 'NT': 'Canada', 'NU': 'Canada',
    # Full province names (case-insensitive matching)
    'ontario': 'Canada', 'quebec': 'Canada', 'british columbia': 'Canada',
    'alberta': 'Canada', 'manitoba': 'Canada', 'saskatchewan': 'Canada',
    'nova scotia': 'Canada', 'new brunswick': 'Canada', 'newfoundland': 'Canada',
    'newfoundland and labrador': 'Canada', 'prince edward island': 'Canada',
    'yukon': 'Canada', 'northwest territories': 'Canada', 'nunavut': 'Canada',
    # Common variations
    'b.c.': 'Canada', 'b.c': 'Canada', 'p.e.i.': 'Canada', 'pei': 'Canada',
    'n.b.': 'Canada', 'n.s.': 'Canada', 'n.l.': 'Canada',
}

# US States (codes and full names)
US_STATES: Dict[str, str] = {
    # State codes
    'AL': 'USA', 'AK': 'USA', 'AZ': 'USA', 'AR': 'USA', 'CA': 'USA',
    'CO': 'USA', 'CT': 'USA', 'DE': 'USA', 'FL': 'USA', 'GA': 'USA',
    'HI': 'USA', 'ID': 'USA', 'IL': 'USA', 'IN': 'USA', 'IA': 'USA',
    'KS': 'USA', 'KY': 'USA', 'LA': 'USA', 'ME': 'USA', 'MD': 'USA',
    'MA': 'USA', 'MI': 'USA', 'MN': 'USA', 'MS': 'USA', 'MO': 'USA',
    'MT': 'USA', 'NE': 'USA', 'NV': 'USA', 'NH': 'USA', 'NJ': 'USA',
    'NM': 'USA', 'NY': 'USA', 'NC': 'USA', 'ND': 'USA', 'OH': 'USA',
    'OK': 'USA', 'OR': 'USA', 'PA': 'USA', 'RI': 'USA', 'SC': 'USA',
    'SD': 'USA', 'TN': 'USA', 'TX': 'USA', 'UT': 'USA', 'VT': 'USA',
    'VA': 'USA', 'WA': 'USA', 'WV': 'USA', 'WI': 'USA', 'WY': 'USA',
    'DC': 'USA',  # District of Columbia
    # Full state names (case-insensitive matching)
    'alabama': 'USA', 'alaska': 'USA', 'arizona': 'USA', 'arkansas': 'USA',
    'california': 'USA', 'colorado': 'USA', 'connecticut': 'USA', 'delaware': 'USA',
    'florida': 'USA', 'georgia': 'USA', 'hawaii': 'USA', 'idaho': 'USA',
    'illinois': 'USA', 'indiana': 'USA', 'iowa': 'USA', 'kansas': 'USA',
    'kentucky': 'USA', 'louisiana': 'USA', 'maine': 'USA', 'maryland': 'USA',
    'massachusetts': 'USA', 'michigan': 'USA', 'minnesota': 'USA', 'mississippi': 'USA',
    'missouri': 'USA', 'montana': 'USA', 'nebraska': 'USA', 'nevada': 'USA',
    'new hampshire': 'USA', 'new jersey': 'USA', 'new mexico': 'USA', 'new york': 'USA',
    'north carolina': 'USA', 'north dakota': 'USA', 'ohio': 'USA', 'oklahoma': 'USA',
    'oregon': 'USA', 'pennsylvania': 'USA', 'rhode island': 'USA', 'south carolina': 'USA',
    'south dakota': 'USA', 'tennessee': 'USA', 'texas': 'USA', 'utah': 'USA',
    'vermont': 'USA', 'virginia': 'USA', 'washington': 'USA', 'west virginia': 'USA',
    'wisconsin': 'USA', 'wyoming': 'USA', 'district of columbia': 'USA',
    # Common variations
    'calif': 'USA', 'calif.': 'USA', 'california': 'USA',
    'n.y.': 'USA', 'n.y': 'USA', 'ny': 'USA',
    'n.c.': 'USA', 'n.c': 'USA', 's.c.': 'USA', 's.c': 'USA',
    'n.d.': 'USA', 'n.d': 'USA', 's.d.': 'USA', 's.d': 'USA',
    'w.va': 'USA', 'w.va.': 'USA', 'west va': 'USA',
}

# Australian States and Territories (codes and full names)
AUSTRALIAN_STATES: Dict[str, str] = {
    # State/Territory codes
    'NSW': 'Australia', 'VIC': 'Australia', 'QLD': 'Australia', 'WA': 'Australia',
    'SA': 'Australia', 'TAS': 'Australia', 'ACT': 'Australia', 'NT': 'Australia',
    # Full state names (case-insensitive matching)
    'new south wales': 'Australia', 'victoria': 'Australia', 'queensland': 'Australia',
    'western australia': 'Australia', 'south australia': 'Australia', 'tasmania': 'Australia',
    'australian capital territory': 'Australia', 'northern territory': 'Australia',
    # Common variations
    'n.s.w.': 'Australia', 'nsw': 'Australia',
    'qld': 'Australia', 'q.l.d.': 'Australia',
    'w.a.': 'Australia', 'wa': 'Australia',
    's.a.': 'Australia', 'sa': 'Australia',
    't.a.s.': 'Australia', 'tas': 'Australia',
    'a.c.t.': 'Australia', 'act': 'Australia',
}

# Major Cities Mapping (case-insensitive)
MAJOR_CITIES: Dict[str, str] = {
    # Canadian cities
    'toronto': 'Canada', 'vancouver': 'Canada', 'montreal': 'Canada', 'calgary': 'Canada',
    'ottawa': 'Canada', 'edmonton': 'Canada', 'winnipeg': 'Canada', 'quebec city': 'Canada',
    'quebec': 'Canada', 'hamilton': 'Canada', 'kitchener': 'Canada', 'london': 'Canada',
    'halifax': 'Canada', 'victoria': 'Canada', 'windsor': 'Canada', 'saskatoon': 'Canada',
    'regina': 'Canada', 'sherbrooke': 'Canada', 'st. john\'s': 'Canada', 'st john\'s': 'Canada',
    'st. johns': 'Canada', 'st johns': 'Canada', 'barrie': 'Canada', 'kelowna': 'Canada',
    'abbotsford': 'Canada', 'sudbury': 'Canada', 'kingston': 'Canada', 'saguenay': 'Canada',
    'trois-rivières': 'Canada', 'trois rivieres': 'Canada', 'guelph': 'Canada',
    'cambridge': 'Canada', 'coquitlam': 'Canada', 'richmond': 'Canada', 'burlington': 'Canada',
    'oshawa': 'Canada', 'saint john': 'Canada', 'laval': 'Canada', 'surrey': 'Canada',
    'mississauga': 'Canada', 'brampton': 'Canada', 'markham': 'Canada', 'ajax': 'Canada',
    'pickering': 'Canada', 'whitby': 'Canada', 'oakville': 'Canada', 'burlington': 'Canada',
    
    # US cities
    'new york': 'USA', 'los angeles': 'USA', 'chicago': 'USA', 'houston': 'USA',
    'phoenix': 'USA', 'philadelphia': 'USA', 'san antonio': 'USA', 'san diego': 'USA',
    'dallas': 'USA', 'san jose': 'USA', 'austin': 'USA', 'jacksonville': 'USA',
    'fort worth': 'USA', 'columbus': 'USA', 'charlotte': 'USA', 'san francisco': 'USA',
    'indianapolis': 'USA', 'seattle': 'USA', 'denver': 'USA', 'washington': 'USA',
    'boston': 'USA', 'el paso': 'USA', 'detroit': 'USA', 'nashville': 'USA',
    'portland': 'USA', 'oklahoma city': 'USA', 'las vegas': 'USA', 'memphis': 'USA',
    'louisville': 'USA', 'baltimore': 'USA', 'milwaukee': 'USA', 'albuquerque': 'USA',
    'tucson': 'USA', 'fresno': 'USA', 'sacramento': 'USA', 'kansas city': 'USA',
    'mesa': 'USA', 'atlanta': 'USA', 'omaha': 'USA', 'colorado springs': 'USA',
    'raleigh': 'USA', 'virginia beach': 'USA', 'miami': 'USA', 'oakland': 'USA',
    'minneapolis': 'USA', 'tulsa': 'USA', 'cleveland': 'USA', 'wichita': 'USA',
    'arlington': 'USA', 'new orleans': 'USA', 'tampa': 'USA', 'honolulu': 'USA',
    
    # Australian cities
    'sydney': 'Australia', 'melbourne': 'Australia', 'brisbane': 'Australia', 'perth': 'Australia',
    'adelaide': 'Australia', 'gold coast': 'Australia', 'newcastle': 'Australia', 'canberra': 'Australia',
    'sunshine coast': 'Australia', 'wollongong': 'Australia', 'hobart': 'Australia', 'geelong': 'Australia',
    'townsville': 'Australia', 'cairns': 'Australia', 'darwin': 'Australia', 'toowoomba': 'Australia',
    'ballarat': 'Australia', 'bendigo': 'Australia', 'albury': 'Australia', 'launceston': 'Australia',
    'mackay': 'Australia', 'rockhampton': 'Australia', 'bunbury': 'Australia', 'bundaberg': 'Australia',
    'coffs harbour': 'Australia', 'wagga wagga': 'Australia', 'hervey bay': 'Australia',
    'port macquarie': 'Australia', 'shepparton': 'Australia', 'mildura': 'Australia',
    'woolloongabba': 'Australia', 'woolloongabba qld': 'Australia',
    # Note: "Woolloongabba, QLD" will be handled by extract_state_from_city function
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


def extract_state_from_city(city: str) -> Optional[Tuple[str, str]]:
    """
    Extract state code from city field if it contains something like "Ottawa, ON"
    Returns (city_name, state_code) or None
    """
    if not city:
        return None
    
    city_trimmed = city.strip()
    
    # Pattern: "City, STATE" or "City STATE" or "City, State" or "City,STATE"
    patterns = [
        r'^(.+?),\s*([A-Z]{2,3})$',      # "Ottawa, ON"
        r'^(.+?),\s*([A-Z]{2,3})\s*$',   # "Ottawa, ON " (with trailing space)
        r'^(.+?)\s+([A-Z]{2,3})$',       # "Ottawa ON"
        r'^(.+?)\s+([A-Z]{2,3})\s*$',    # "Ottawa ON " (with trailing space)
        r'^(.+?),\s*([A-Za-z\s]+?)$',    # "Ottawa, Ontario"
        r'^(.+?),\s*([A-Za-z\s]+?)\s*$', # "Ottawa, Ontario " (with trailing space)
    ]
    
    for pattern in patterns:
        match = re.match(pattern, city_trimmed, re.IGNORECASE)
        if match:
            city_name = match.group(1).strip()
            state_part = match.group(2).strip()
            # Only return if we have both city and state parts
            if city_name and state_part:
                return (city_name, state_part)
    
    return None


def determine_country_from_state(state: str) -> Optional[str]:
    """
    Determine country from state code or name
    Returns 'Canada', 'USA', 'Australia', or None
    """
    if not state:
        return None
    
    state_normalized = normalize_for_matching(state)
    state_upper = state.strip().upper()
    
    # Check Canadian provinces
    if state_upper in CANADIAN_PROVINCES or state_normalized in CANADIAN_PROVINCES:
        return 'Canada'
    
    # Check US states
    if state_upper in US_STATES or state_normalized in US_STATES:
        return 'USA'
    
    # Check Australian states
    if state_upper in AUSTRALIAN_STATES or state_normalized in AUSTRALIAN_STATES:
        return 'Australia'
    
    return None


def determine_country_from_city(city: str) -> Optional[str]:
    """
    Determine country from city name
    Returns 'Canada', 'USA', 'Australia', or None
    """
    if not city:
        return None
    
    # First, try to extract state from city field (e.g., "Ottawa, ON")
    extracted = extract_state_from_city(city)
    if extracted:
        city_name, state_code = extracted
        # Check if state code indicates a country
        country_from_state = determine_country_from_state(state_code)
        if country_from_state:
            return country_from_state
        # If state didn't match, try city name
        city = city_name
    
    city_normalized = normalize_for_matching(city)
    
    # Check major cities
    if city_normalized in MAJOR_CITIES:
        return MAJOR_CITIES[city_normalized]
    
    return None


def determine_country(city: Optional[str], state: Optional[str]) -> str:
    """
    Determine country from city and state information
    Priority:
    1. State code/name (most reliable) - if state exists, use it
    2. City name (including extracting state from city field like "Ottawa, ON")
    3. Default to Canada if both are null
    
    Returns: 'Canada', 'USA', or 'Australia'
    """
    city_str = normalize_text(city)
    state_str = normalize_text(state)
    
    # Priority 1: Check state first (most reliable)
    # This handles cases where city is null but state is "ON" → Canada
    if state_str:
        country = determine_country_from_state(state_str)
        if country:
            return country
    
    # Priority 2: Check city
    # This handles cases like "Ottawa, ON" where state is in city field
    # or cases like "Toronto" where city name indicates country
    if city_str:
        country = determine_country_from_city(city_str)
        if country:
            return country
    
    # Priority 3: Default to Canada if both are null
    # As per requirements: "if null null (city, and state) = canada by default"
    if not city_str and not state_str:
        return 'Canada'
    
    # If we have data but couldn't determine country, default to Canada
    # This is a safe fallback to avoid leaving country as null
    return 'Canada'


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_leads_with_null_country(conn, limit: Optional[int] = None, batch_size: int = 1000):
    """
    Get leads where country is NULL or empty
    Returns a generator that yields batches of leads
    """
    cursor = conn.cursor()
    
    try:
        # Get total count - only count records where country is actually NULL or empty
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE country IS NULL OR TRIM(COALESCE(country, '')) = ''
        """)
        total_count = cursor.fetchone()[0]
        logger.info(f"Found {total_count:,} leads with null/empty country")
        
        if limit:
            total_count = min(total_count, limit)
            logger.info(f"Processing limited to {limit:,} records")
        
        # Fetch in batches
        offset = 0
        while True:
            query = """
                SELECT id, city, state, country
                FROM leads
                WHERE country IS NULL OR TRIM(COALESCE(country, '')) = ''
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            
            limit_value = batch_size
            if limit and (offset + batch_size) > limit:
                limit_value = limit - offset
            
            if limit_value <= 0:
                break
            
            cursor.execute(query, (limit_value, offset))
            batch = cursor.fetchall()
            
            if not batch:
                break
            
            yield batch
            offset += len(batch)
            
            if limit and offset >= limit:
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


def process_leads(conn, dry_run: bool = False, batch_size: int = 1000, limit: Optional[int] = None):
    """
    Process all leads with null country and update them
    """
    logger.info("=" * 70)
    logger.info("UPDATE COUNTRIES FROM CITIES AND STATES")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
    logger.info(f"Batch size: {batch_size}")
    if limit:
        logger.info(f"Limit: {limit} records")
    logger.info("=" * 70)
    
    stats = {
        'total_processed': 0,
        'updated_canada': 0,
        'updated_usa': 0,
        'updated_australia': 0,
        'errors': 0,
        'skipped': 0
    }
    
    # Get total count for progress tracking
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE country IS NULL OR TRIM(COALESCE(country, '')) = ''
        """)
        total_to_process = cursor.fetchone()[0]
        if limit:
            total_to_process = min(total_to_process, limit)
    finally:
        cursor.close()
    
    # Process in batches
    batch_num = 0
    processed_count = 0
    for batch in get_leads_with_null_country(conn, limit=limit, batch_size=batch_size):
        batch_num += 1
        processed_count += len(batch)
        progress_pct = (processed_count / total_to_process * 100) if total_to_process > 0 else 0
        logger.info(f"\nProcessing batch {batch_num} ({len(batch)} records) - Progress: {processed_count:,}/{total_to_process:,} ({progress_pct:.1f}%)...")
        
        batch_updates = []
        for lead_id, city, state, country in batch:
            try:
                # Determine country
                determined_country = determine_country(city, state)
                
                # Track statistics
                if determined_country == 'Canada':
                    stats['updated_canada'] += 1
                elif determined_country == 'USA':
                    stats['updated_usa'] += 1
                elif determined_country == 'Australia':
                    stats['updated_australia'] += 1
                
                batch_updates.append((lead_id, determined_country, city, state))
                stats['total_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing lead {lead_id}: {e}")
                stats['errors'] += 1
        
        # Update batch
        if not dry_run and batch_updates:
            cursor = conn.cursor()
            try:
                for lead_id, country, city, state in batch_updates:
                    cursor.execute("""
                        UPDATE leads
                        SET country = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (country, lead_id))
                
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
            sample_size = min(5, len(batch_updates))
            logger.info(f"  [DRY RUN] Would update {len(batch_updates)} leads")
            for lead_id, country, city, state in batch_updates[:sample_size]:
                logger.info(f"    Lead {lead_id}: city='{city}', state='{state}' → country='{country}'")
            if len(batch_updates) > sample_size:
                logger.info(f"    ... and {len(batch_updates) - sample_size} more")
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total processed: {stats['total_processed']:,}")
    
    if stats['total_processed'] > 0:
        canada_pct = (stats['updated_canada'] / stats['total_processed'] * 100)
        usa_pct = (stats['updated_usa'] / stats['total_processed'] * 100)
        aus_pct = (stats['updated_australia'] / stats['total_processed'] * 100)
        logger.info(f"  → Canada: {stats['updated_canada']:,} ({canada_pct:.1f}%)")
        logger.info(f"  → USA: {stats['updated_usa']:,} ({usa_pct:.1f}%)")
        logger.info(f"  → Australia: {stats['updated_australia']:,} ({aus_pct:.1f}%)")
    else:
        logger.info(f"  → Canada: 0")
        logger.info(f"  → USA: 0")
        logger.info(f"  → Australia: 0")
    
    logger.info(f"  → Errors: {stats['errors']:,}")
    logger.info(f"  → Skipped: {stats['skipped']:,}")
    logger.info("=" * 70)
    
    return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Update country fields in leads table based on city and state',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_countries_cities_state.py --dry-run
  python update_countries_cities_state.py --batch-size 500
  python update_countries_cities_state.py --limit 100 --dry-run
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
            logger.info("\n✅ Country updates completed successfully!")
        
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


#!/usr/bin/env python3
"""
Data Mutation Changes - Fix Misplaced Email/Phone Fields
=========================================================

This script identifies and corrects data entry errors where:
- Email addresses were entered in the phone_number field
- Phone numbers were entered in the email field

It will:
1. Scan all leads in the database
2. Detect misplaced data using pattern matching
3. Move data to the correct fields
4. Log all occurrences (both existing issues and those fixed)
5. Generate a detailed report

Usage:
    python data_mutation_changes.py [--dry-run] [--batch-size 1000] [--limit 100]
    
Options:
    --dry-run        Preview changes without updating database
    --batch-size     Number of records to process per batch (default: 1000)
    --limit          Limit number of records to process (for testing)
    --report-file    Path to save the report file (default: data_mutation_report.txt)
"""

import sys
import os
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
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
# EMAIL AND PHONE PATTERN DETECTION
# ============================================================================

# Email pattern - matches most standard email formats
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    re.IGNORECASE
)

# More lenient email pattern for detection (allows some common typos)
EMAIL_PATTERN_LENIENT = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Phone number patterns - various formats
PHONE_PATTERNS = [
    # North American: (123) 456-7890, 123-456-7890, 123.456.7890, 123 456 7890
    re.compile(r'^\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$'),
    # International: +1-123-456-7890, +1 123 456 7890
    re.compile(r'^\+?[0-9]{1,3}[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$'),
    # Simple 10+ digit phone number
    re.compile(r'^[+]?[0-9]{10,15}$'),
    # With country code: +1234567890
    re.compile(r'^\+[0-9]{11,15}$'),
    # European formats: 01onal phone 123 456, +44 7911 123456
    re.compile(r'^\+?[0-9]{2,4}[-.\s]?[0-9]{4,5}[-.\s]?[0-9]{4,6}$'),
    # Toll-free: 1-800-123-4567, 800-123-4567
    re.compile(r'^1?[-.\s]?8[0-9]{2}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$'),
    # Local with extension: 123-4567 x890
    re.compile(r'^[0-9]{3}[-.\s]?[0-9]{4}(\s*(x|ext\.?|extension)\s*[0-9]+)?$', re.IGNORECASE),
]


def normalize_text(value) -> str:
    """Normalize text fields, handling None and empty strings"""
    if value is None:
        return ''
    return str(value).strip()


def is_email(value: str) -> bool:
    """
    Check if a value looks like an email address.
    
    Args:
        value: String to check
        
    Returns:
        True if the value matches email pattern
    """
    if not value:
        return False
    
    value = value.strip()
    
    # Skip common placeholder values
    if value.lower() in ['not found', 'n/a', 'none', '-', '']:
        return False
    
    # Check with lenient pattern (allows partial matches)
    if EMAIL_PATTERN_LENIENT.search(value):
        return True
    
    return False


def is_phone_number(value: str) -> bool:
    """
    Check if a value looks like a phone number.
    
    Args:
        value: String to check
        
    Returns:
        True if the value matches phone number patterns
    """
    if not value:
        return False
    
    value = value.strip()
    
    # Skip common placeholder values
    if value.lower() in ['not found', 'n/a', 'none', '-', '']:
        return False
    
    # Remove common formatting characters for digit count check
    digits_only = re.sub(r'[^0-9]', '', value)
    
    # Phone numbers typically have 7-15 digits
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False
    
    # If it contains @ symbol, it's likely an email, not a phone
    if '@' in value:
        return False
    
    # Check against phone patterns
    for pattern in PHONE_PATTERNS:
        if pattern.match(value):
            return True
    
    # Additional check: if mostly digits with some separators, likely a phone
    # Allow -, ., (, ), +, space as separators
    if re.match(r'^[\d\s\-\.\(\)\+]+$', value) and len(digits_only) >= 7:
        return True
    
    return False


def extract_email_from_string(value: str) -> Optional[str]:
    """
    Extract an email address from a string that might contain other text.
    
    Args:
        value: String that might contain an email
        
    Returns:
        Extracted email or None
    """
    if not value:
        return None
    
    match = EMAIL_PATTERN_LENIENT.search(value)
    if match:
        return match.group(0).lower()
    
    return None


def extract_phone_from_string(value: str) -> Optional[str]:
    """
    Extract a phone number from a string that might contain other text.
    
    Args:
        value: String that might contain a phone number
        
    Returns:
        Extracted phone number or None
    """
    if not value:
        return None
    
    # Remove common text prefixes
    value_clean = value.strip()
    
    # Extract digits and common separators
    for pattern in PHONE_PATTERNS:
        match = pattern.search(value_clean)
        if match:
            return match.group(0)
    
    # Try to extract just the numeric part with common separators
    phone_match = re.search(r'[\d\s\-\.\(\)\+]{7,20}', value_clean)
    if phone_match:
        extracted = phone_match.group(0).strip()
        # Verify it has enough digits
        digits = re.sub(r'[^0-9]', '', extracted)
        if 7 <= len(digits) <= 15:
            return extracted
    
    return None


# ============================================================================
# DATA ANALYSIS AND MUTATION DETECTION
# ============================================================================

class DataMutationIssue:
    """Represents a data mutation issue found in a lead"""
    
    def __init__(
        self,
        lead_id: int,
        business_name: str,
        issue_type: str,
        current_email: str,
        current_phone: str,
        suggested_email: str,
        suggested_phone: str,
        description: str
    ):
        self.lead_id = lead_id
        self.business_name = business_name
        self.issue_type = issue_type
        self.current_email = current_email
        self.current_phone = current_phone
        self.suggested_email = suggested_email
        self.suggested_phone = suggested_phone
        self.description = description
    
    def __repr__(self):
        return f"DataMutationIssue(lead_id={self.lead_id}, type='{self.issue_type}')"


def analyze_lead(
    lead_id: int,
    business_name: str,
    email: str,
    phone_number: str
) -> Optional[DataMutationIssue]:
    """
    Analyze a lead record for data mutation issues.
    
    Checks if:
    1. Email field contains a phone number
    2. Phone number field contains an email
    
    Args:
        lead_id: Lead ID
        business_name: Business name
        email: Current email field value
        phone_number: Current phone_number field value
        
    Returns:
        DataMutationIssue if an issue is found, None otherwise
    """
    email = normalize_text(email)
    phone_number = normalize_text(phone_number)
    business_name = normalize_text(business_name)
    
    # Case 1: Email in phone field, phone in email field (swap needed)
    if is_email(phone_number) and is_phone_number(email):
        return DataMutationIssue(
            lead_id=lead_id,
            business_name=business_name,
            issue_type="SWAP_BOTH",
            current_email=email,
            current_phone=phone_number,
            suggested_email=phone_number,  # Move email from phone field
            suggested_phone=email,  # Move phone from email field
            description=f"Email and phone are swapped. Email field has phone '{email}', Phone field has email '{phone_number}'"
        )
    
    # Case 2: Email in phone field only
    if is_email(phone_number):
        extracted_email = extract_email_from_string(phone_number)
        if extracted_email:
            # Determine what to put in email field
            new_email = extracted_email
            # If email field is empty or placeholder, use the extracted email
            if not email or email.lower() in ['not found', 'n/a', 'none', '-', '']:
                return DataMutationIssue(
                    lead_id=lead_id,
                    business_name=business_name,
                    issue_type="EMAIL_IN_PHONE_FIELD",
                    current_email=email,
                    current_phone=phone_number,
                    suggested_email=new_email,
                    suggested_phone='not found',  # Clear the phone field
                    description=f"Email '{phone_number}' found in phone field. Email field was '{email}'"
                )
            else:
                # Email field already has a value, just log and clear phone
                return DataMutationIssue(
                    lead_id=lead_id,
                    business_name=business_name,
                    issue_type="EMAIL_IN_PHONE_FIELD_DUPLICATE",
                    current_email=email,
                    current_phone=phone_number,
                    suggested_email=email,  # Keep existing email
                    suggested_phone='not found',  # Clear invalid phone
                    description=f"Email '{phone_number}' found in phone field but email field already has '{email}'"
                )
    
    # Case 3: Phone number in email field only
    if is_phone_number(email):
        extracted_phone = extract_phone_from_string(email)
        if extracted_phone:
            # Determine what to put in phone field
            new_phone = extracted_phone
            # If phone field is empty or placeholder, use the extracted phone
            if not phone_number or phone_number.lower() in ['not found', 'n/a', 'none', '-', '']:
                return DataMutationIssue(
                    lead_id=lead_id,
                    business_name=business_name,
                    issue_type="PHONE_IN_EMAIL_FIELD",
                    current_email=email,
                    current_phone=phone_number,
                    suggested_email='not found',  # Clear the email field
                    suggested_phone=new_phone,
                    description=f"Phone '{email}' found in email field. Phone field was '{phone_number}'"
                )
            else:
                # Phone field already has a value, just log and clear email
                return DataMutationIssue(
                    lead_id=lead_id,
                    business_name=business_name,
                    issue_type="PHONE_IN_EMAIL_FIELD_DUPLICATE",
                    current_email=email,
                    current_phone=phone_number,
                    suggested_email='not found',  # Clear invalid email
                    suggested_phone=phone_number,  # Keep existing phone
                    description=f"Phone '{email}' found in email field but phone field already has '{phone_number}'"
                )
    
    return None


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_all_leads(conn, limit: Optional[int] = None, batch_size: int = 1000):
    """
    Get all leads with email and phone_number fields.
    Returns a generator that yields batches of leads.
    """
    cursor = conn.cursor()
    
    try:
        # Get all leads with email or phone data
        query = """
            SELECT id, business_name, email, phone_number
            FROM leads 
            ORDER BY id
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        
        batch = []
        while True:
            row = cursor.fetchone()
            if row is None:
                if batch:
                    yield batch
                break
            
            batch.append(row)
            
            if len(batch) >= batch_size:
                yield batch
                batch = []
                
    finally:
        cursor.close()


def update_lead_fields(
    conn,
    lead_id: int,
    new_email: str,
    new_phone: str,
    dry_run: bool = False
) -> bool:
    """Update email and phone_number for a single lead"""
    if dry_run:
        return True
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE leads
            SET email = %s, phone_number = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_email, new_phone, lead_id))
        return True
    except Exception as e:
        logger.error(f"Error updating lead {lead_id}: {e}")
        return False
    finally:
        cursor.close()


def process_leads(
    conn,
    dry_run: bool = False,
    batch_size: int = 1000,
    limit: Optional[int] = None,
    report_file: Optional[str] = None
) -> Dict:
    """
    Process all leads to find and fix data mutation issues.
    """
    logger.info("=" * 70)
    logger.info("DATA MUTATION CHANGES - FIX MISPLACED EMAIL/PHONE FIELDS")
    logger.info("=" * 70)
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
    logger.info(f"Batch size: {batch_size}")
    if limit:
        logger.info(f"Limit: {limit} records")
    logger.info("=" * 70)
    
    stats = {
        'total_leads_scanned': 0,
        'issues_found': 0,
        'issues_fixed': 0,
        'swap_both': 0,
        'email_in_phone': 0,
        'phone_in_email': 0,
        'duplicates_handled': 0,
        'errors': 0,
        'issues': []  # Store all issues for reporting
    }
    
    # Get total count for progress tracking
    cursor = conn.cursor()
    try:
        count_query = "SELECT COUNT(*) FROM leads"
        if limit:
            count_query = f"SELECT LEAST(COUNT(*), {limit}) FROM leads"
        cursor.execute(count_query)
        total_leads = cursor.fetchone()[0]
        logger.info(f"Total leads to scan: {total_leads:,}")
    finally:
        cursor.close()
    
    logger.info("\n📋 Scanning leads for data mutation issues...\n")
    
    # Process in batches
    batch_num = 0
    
    for batch in get_all_leads(conn, limit=limit, batch_size=batch_size):
        batch_num += 1
        stats['total_leads_scanned'] += len(batch)
        
        progress_pct = (stats['total_leads_scanned'] / total_leads * 100) if total_leads > 0 else 0
        logger.info(f"Processing batch {batch_num} ({len(batch)} records) - Progress: {stats['total_leads_scanned']:,}/{total_leads:,} ({progress_pct:.1f}%)")
        
        batch_issues = []
        
        for lead_id, business_name, email, phone_number in batch:
            issue = analyze_lead(lead_id, business_name, email, phone_number)
            
            if issue:
                batch_issues.append(issue)
                stats['issues_found'] += 1
                stats['issues'].append(issue)
                
                # Track issue types
                if issue.issue_type == "SWAP_BOTH":
                    stats['swap_both'] += 1
                elif issue.issue_type in ["EMAIL_IN_PHONE_FIELD", "EMAIL_IN_PHONE_FIELD_DUPLICATE"]:
                    stats['email_in_phone'] += 1
                    if "DUPLICATE" in issue.issue_type:
                        stats['duplicates_handled'] += 1
                elif issue.issue_type in ["PHONE_IN_EMAIL_FIELD", "PHONE_IN_EMAIL_FIELD_DUPLICATE"]:
                    stats['phone_in_email'] += 1
                    if "DUPLICATE" in issue.issue_type:
                        stats['duplicates_handled'] += 1
                
                # Log the issue
                logger.info(f"  ⚠️  Lead {issue.lead_id} ({issue.business_name[:30]}...): {issue.issue_type}")
                logger.info(f"      Current: email='{issue.current_email}', phone='{issue.current_phone}'")
                logger.info(f"      Suggested: email='{issue.suggested_email}', phone='{issue.suggested_phone}'")
        
        # Apply fixes
        if batch_issues and not dry_run:
            for issue in batch_issues:
                success = update_lead_fields(
                    conn,
                    issue.lead_id,
                    issue.suggested_email,
                    issue.suggested_phone,
                    dry_run=False
                )
                if success:
                    stats['issues_fixed'] += 1
                else:
                    stats['errors'] += 1
            
            conn.commit()
            logger.info(f"  ✓ Fixed {len(batch_issues)} issues in batch {batch_num}")
        elif batch_issues and dry_run:
            logger.info(f"  [DRY RUN] Would fix {len(batch_issues)} issues in batch {batch_num}")
    
    # Generate report
    report_content = generate_report(stats, dry_run)
    
    # Save report to file
    if report_file:
        save_report(report_content, report_file)
    
    # Print summary
    print_summary(stats, dry_run)
    
    return stats


def generate_report(stats: Dict, dry_run: bool) -> str:
    """Generate a detailed report of all issues found"""
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("DATA MUTATION CHANGES REPORT")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE UPDATE'}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    report_lines.append("SUMMARY")
    report_lines.append("-" * 40)
    report_lines.append(f"Total leads scanned: {stats['total_leads_scanned']:,}")
    report_lines.append(f"Issues found: {stats['issues_found']:,}")
    report_lines.append(f"Issues fixed: {stats['issues_fixed']:,}")
    report_lines.append(f"Errors: {stats['errors']:,}")
    report_lines.append("")
    
    report_lines.append("ISSUE BREAKDOWN")
    report_lines.append("-" * 40)
    report_lines.append(f"Swap both fields needed: {stats['swap_both']:,}")
    report_lines.append(f"Email found in phone field: {stats['email_in_phone']:,}")
    report_lines.append(f"Phone found in email field: {stats['phone_in_email']:,}")
    report_lines.append(f"Duplicate values handled: {stats['duplicates_handled']:,}")
    report_lines.append("")
    
    report_lines.append("DETAILED ISSUE LIST")
    report_lines.append("-" * 40)
    
    for issue in stats['issues']:
        report_lines.append("")
        report_lines.append(f"Lead ID: {issue.lead_id}")
        report_lines.append(f"Business: {issue.business_name}")
        report_lines.append(f"Issue Type: {issue.issue_type}")
        report_lines.append(f"Current Email: {issue.current_email}")
        report_lines.append(f"Current Phone: {issue.current_phone}")
        report_lines.append(f"Suggested Email: {issue.suggested_email}")
        report_lines.append(f"Suggested Phone: {issue.suggested_phone}")
        report_lines.append(f"Description: {issue.description}")
        report_lines.append("-" * 40)
    
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)


def save_report(report_content: str, report_file: str):
    """Save the report to a file"""
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"\n📄 Report saved to: {report_file}")
    except Exception as e:
        logger.error(f"Error saving report to {report_file}: {e}")


def print_summary(stats: Dict, dry_run: bool):
    """Print the summary to console"""
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total leads scanned: {stats['total_leads_scanned']:,}")
    logger.info(f"Issues found: {stats['issues_found']:,}")
    logger.info("")
    logger.info("Issue breakdown:")
    logger.info(f"  → Swap both fields (email↔phone): {stats['swap_both']:,}")
    logger.info(f"  → Email in phone field: {stats['email_in_phone']:,}")
    logger.info(f"  → Phone in email field: {stats['phone_in_email']:,}")
    logger.info(f"  → Duplicate values handled: {stats['duplicates_handled']:,}")
    logger.info("")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would fix: {stats['issues_found']:,} issues")
    else:
        logger.info(f"Issues fixed: {stats['issues_fixed']:,}")
        logger.info(f"Errors: {stats['errors']:,}")
    
    logger.info("=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Fix misplaced email/phone data in leads table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_mutation_changes.py --dry-run
  python data_mutation_changes.py --batch-size 500
  python data_mutation_changes.py --limit 100 --dry-run
  python data_mutation_changes.py --report-file my_report.txt
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
    
    parser.add_argument(
        '--report-file',
        type=str,
        default=None,
        help='Path to save the report file (default: data_mutation_report_TIMESTAMP.txt)'
    )
    
    args = parser.parse_args()
    
    # Set default report file if not specified
    if args.report_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.report_file = f"data_mutation_report_{timestamp}.txt"
    
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
            limit=args.limit,
            report_file=args.report_file
        )
        
        if args.dry_run:
            logger.info("\n⚠️  This was a DRY RUN. No changes were made to the database.")
            logger.info("   Run without --dry-run to apply changes.")
        else:
            logger.info("\n✅ Data mutation fixes completed successfully!")
        
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


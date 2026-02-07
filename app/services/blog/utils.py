"""
Blog Utilities

Helper functions for blog operations.
"""

import re
from typing import Optional
from datetime import datetime


def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def generate_excerpt(content: str, max_length: int = 200) -> str:
    """Generate excerpt from content."""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", content)
    # Normalize whitespace
    clean = " ".join(clean.split())
    # Truncate
    if len(clean) <= max_length:
        return clean
    return clean[:max_length].rsplit(" ", 1)[0] + "..."


def calculate_read_time(content: str, words_per_minute: int = 200) -> int:
    """Calculate estimated read time in minutes."""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", content)
    # Count words
    word_count = len(clean.split())
    # Calculate time
    return max(1, round(word_count / words_per_minute))


def generate_meta_description(content: str, max_length: int = 160) -> str:
    """Generate SEO meta description from content."""
    return generate_excerpt(content, max_length)


def validate_slug(slug: str) -> tuple[bool, Optional[str]]:
    """Validate slug format."""
    if len(slug) < 3:
        return False, "Slug must be at least 3 characters"
    if len(slug) > 255:
        return False, "Slug must be at most 255 characters"
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", slug):
        return False, "Slug must contain only lowercase letters, numbers, and hyphens"
    if "--" in slug:
        return False, "Slug cannot contain consecutive hyphens"
    return True, None


def format_date(dt: datetime, format_str: str = "%B %d, %Y") -> str:
    """Format datetime for display."""
    return dt.strftime(format_str)

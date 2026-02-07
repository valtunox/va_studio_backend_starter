"""
Project Utilities

Helper functions for project operations.
"""

import re
from typing import Optional


def validate_slug(slug: str) -> tuple[bool, Optional[str]]:
    """
    Validate project slug format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(slug) < 3:
        return False, "Slug must be at least 3 characters"

    if len(slug) > 255:
        return False, "Slug must be at most 255 characters"

    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", slug):
        return False, "Slug must contain only lowercase letters, numbers, and hyphens"

    if "--" in slug:
        return False, "Slug cannot contain consecutive hyphens"

    return True, None


def sanitize_name(name: str) -> str:
    """Sanitize project name."""
    # Remove excess whitespace
    name = " ".join(name.split())
    # Limit length
    return name[:255]

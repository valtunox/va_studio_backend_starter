"""
User Utilities

Helper functions for user operations.
"""

import re
from typing import Optional


def generate_username(email: str) -> str:
    """Generate username from email."""
    local_part = email.split("@")[0]
    # Remove special characters
    username = re.sub(r"[^a-zA-Z0-9_]", "", local_part)
    return username.lower()


def validate_username(username: str) -> tuple[bool, Optional[str]]:
    """
    Validate username format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 100:
        return False, "Username must be at most 100 characters"

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", username):
        return False, "Username must start with a letter and contain only letters, numbers, and underscores"

    return True, None


def mask_email(email: str) -> str:
    """Mask email for privacy."""
    local, domain = email.split("@")
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"

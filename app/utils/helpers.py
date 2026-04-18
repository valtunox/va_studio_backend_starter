"""Helper utilities."""

import re
import html
from typing import Optional
from uuid import uuid4


def generate_slug(text: str, unique: bool = True) -> str:
    """
    Generate URL-friendly slug from text.

    Args:
        text: Text to convert to slug
        unique: Add unique suffix to prevent collisions

    Returns:
        URL-friendly slug
    """
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")

    if unique:
        slug = f"{slug}-{uuid4().hex[:6]}"

    return slug


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML by escaping special characters.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    return html.escape(text)


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)].rsplit(" ", 1)[0] + suffix


def mask_email(email: str) -> str:
    """
    Mask email address for privacy.

    Args:
        email: Email address to mask

    Returns:
        Masked email
    """
    local, domain = email.split("@")
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def is_valid_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def generate_random_string(length: int = 32) -> str:
    """
    Generate random string.

    Args:
        length: Length of string

    Returns:
        Random string
    """
    import secrets
    return secrets.token_urlsafe(length)[:length]

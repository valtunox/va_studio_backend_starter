"""Pagination utilities."""

from typing import TypeVar, Generic, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def paginate(
    db: AsyncSession,
    query,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[T], int]:
    """
    Paginate a SQLAlchemy query.

    Args:
        db: Database session
        query: SQLAlchemy select query
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Tuple of (items, total_count)
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Get paginated results
    offset = (page - 1) * per_page
    paginated_query = query.offset(offset).limit(per_page)
    result = await db.execute(paginated_query)
    items = list(result.scalars().all())

    return items, total


def calculate_pages(total: int, per_page: int) -> int:
    """Calculate total number of pages."""
    if per_page <= 0:
        return 0
    return (total + per_page - 1) // per_page


def get_offset(page: int, per_page: int) -> int:
    """Calculate offset from page number."""
    return (max(1, page) - 1) * per_page

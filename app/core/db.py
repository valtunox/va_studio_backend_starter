"""
Database Configuration for InfinityAI Platform
===============================================
Supports:
  - asyncpg connection pool (raw async queries)
  - psycopg2 synchronous connections (legacy)
  - SQLAlchemy async engine + sessions (ORM)
"""

import os
import asyncio

import psycopg2

from app.core.logger import get_logger

logger = get_logger(__name__)
try:
    import asyncpg
except ImportError:
    asyncpg = None
    logger.warning("asyncpg not installed. Asynchronous database operations will not work.")

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ImportError:
    create_async_engine = None
    AsyncSession = None
    async_sessionmaker = None
    create_engine = None
    sessionmaker = None
    logger.warning("SQLAlchemy not installed. ORM operations will not work.")


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

load_env()


# ---------------------------------------------------------------------------
# Shared config helper
# ---------------------------------------------------------------------------

def get_db_config():
    """Return database configuration from environment variables."""
    logger.debug("Loading database configuration from environment variables")
    return {
        'database': os.environ.get('POSTGRES_DB', 'vacloudopsdb2'),
        'user': os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'host': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'port': int(os.environ.get('POSTGRES_PORT', 5432)),
    }


def get_database_url(driver: str = "asyncpg") -> str:
    """Build a SQLAlchemy database URL from environment variables."""
    logger.debug(f"Building database URL with driver={driver}")
    cfg = get_db_config()
    return (
        f"postgresql+{driver}://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


# ---------------------------------------------------------------------------
# asyncpg raw connection pool (existing functionality)
# ---------------------------------------------------------------------------

async def create_async_connection_pool():
    cfg = get_db_config()
    connection_timeout = float(os.environ.get('DB_CONNECTION_TIMEOUT', '5.0'))

    try:
        pool = await asyncio.wait_for(
            asyncpg.create_pool(
                database=cfg['database'],
                user=cfg['user'],
                password=cfg['password'],
                host=cfg['host'],
                port=cfg['port'],
                min_size=1,
                max_size=10,
                command_timeout=10.0
            ),
            timeout=connection_timeout
        )
        logger.info("Async connection pool created successfully")
        return pool
    except asyncio.TimeoutError:
        logger.warning(f"Database connection timeout after {connection_timeout}s. Database may be unavailable.")
        return None
    except Exception as e:
        logger.error(f"Error creating async connection pool: {e}")
        return None

async_pool = None

async def async_postgres_connection():
    global async_pool
    if async_pool is None:
        logger.info("Initializing async connection pool")
        async_pool = await create_async_connection_pool()
    if async_pool:
        logger.debug("Acquiring connection from async pool")
        return await async_pool.acquire()
    else:
        logger.error("Database connection pool is not initialized")
        raise ConnectionError("Database connection pool is not initialized.")


async def release_async_connection(conn):
    """Release an asyncpg connection back to the pool. Call after async_postgres_connection()."""
    global async_pool
    if async_pool and conn:
        await async_pool.release(conn)


async def get_async_db_connection():
    """
    Get a single asyncpg connection (not from pool). Caller must await conn.close() when done.
    Use when a pool is not available or when you need a standalone connection.
    """
    if asyncpg is None:
        raise RuntimeError("asyncpg not installed")
    cfg = get_db_config()
    return await asyncpg.connect(
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )


async def close_db_connection_pool():
    global async_pool
    if async_pool:
        await async_pool.close()
        async_pool = None
        logger.info("Async connection pool closed")


# ---------------------------------------------------------------------------
# psycopg2 synchronous connection (legacy / migration scripts)
# ---------------------------------------------------------------------------

def basic_postgres_connection():
    logger.debug("Creating basic psycopg2 connection")
    cfg = get_db_config()
    return psycopg2.connect(
        dbname=cfg['database'],
        user=cfg['user'],
        password=cfg['password'],
        host=cfg['host'],
        port=cfg['port']
    )

# Alias used by migration.py
get_db_connection = basic_postgres_connection


# ---------------------------------------------------------------------------
# SQLAlchemy ORM engine & session (NEW)
# ---------------------------------------------------------------------------

_async_engine = None
_async_session_factory = None
_sync_engine = None
_sync_session_factory = None


def get_async_engine():
    """Lazy-initialised SQLAlchemy async engine."""
    global _async_engine
    if _async_engine is None and create_async_engine is not None:
        logger.info("Creating SQLAlchemy async engine")
        _async_engine = create_async_engine(
            get_database_url("asyncpg"),
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _async_engine


def get_async_session_factory():
    """Lazy-initialised async session factory."""
    global _async_session_factory
    if _async_session_factory is None and async_sessionmaker is not None:
        engine = get_async_engine()
        if engine:
            _async_session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
    return _async_session_factory


async def get_async_session():
    """FastAPI dependency – yields an async SQLAlchemy session."""
    factory = get_async_session_factory()
    if factory is None:
        logger.error("SQLAlchemy async session factory is not available")
        raise RuntimeError("SQLAlchemy async session factory is not available.")
    async with factory() as session:
        yield session


def get_sync_engine():
    """Lazy-initialised SQLAlchemy sync engine (for migrations/scripts)."""
    global _sync_engine
    if _sync_engine is None and create_engine is not None:
        _sync_engine = create_engine(
            get_database_url("psycopg2"),
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _sync_engine


def get_sync_session_factory():
    """Lazy-initialised sync session factory."""
    global _sync_session_factory
    if _sync_session_factory is None and sessionmaker is not None:
        engine = get_sync_engine()
        if engine:
            _sync_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _sync_session_factory


def get_sync_session():
    """Yields a sync SQLAlchemy session (for scripts/migrations)."""
    factory = get_sync_session_factory()
    if factory is None:
        raise RuntimeError("SQLAlchemy sync session factory is not available.")
    session = factory()
    try:
        yield session
    finally:
        session.close()


async def close_sqlalchemy_engine():
    """Dispose the async engine (call on app shutdown)."""
    global _async_engine
    if _async_engine:
        logger.info("Disposing SQLAlchemy async engine")
        await _async_engine.dispose()
        _async_engine = None


# ---------------------------------------------------------------------------
# Compatibility aliases (migrated from database.py)
# ---------------------------------------------------------------------------

from app.orm.base import Base

get_db = get_async_session

async_session_maker = get_async_session_factory


engine = None  # lazily set; use get_async_engine() directly


async def init_db():
    """Initialise connection pool + SQLAlchemy engine on app startup."""
    global engine
    await create_async_connection_pool()
    engine = get_async_engine()
    logger.info("Database initialised (pool + engine)")


async def close_db():
    """Tear down pool + engine on app shutdown."""
    await close_db_connection_pool()
    await close_sqlalchemy_engine()
    logger.info("Database connections closed")

"""db_to_db_database_migration_pipeline
======================================

End-to-end database migration pipeline between two PostgreSQL instances.

Main capabilities
-----------------
1. **Safety backup of source database**
   - Creates both `.dump` (custom) and `.sql` (plain) backups using the same
     logic as `scripts/backup_database.py`.
   - Stores backups under `app/data/backups/postgres` by default.
   - Creates `*_latest_updated.dump` / `*_latest_updated.sql` copies.

2. **Optional upload of backups to S3**
   - Uses `boto3` to upload `.dump` and `.sql` files to an S3 bucket.
   - Metadata is aligned with `.github/workflows/DatabaseBackupWorkflow.yml`.

3. **DB-to-DB comparison & conditional data migration**
   - Connects to a *source* and *destination* PostgreSQL database.
   - If the destination database does **not** exist:
       * Creates the database on the destination host.
       * Restores it from the fresh source backup (prefers `.dump`).
   - If the destination database **does** exist:
       * Compares row counts for key tables: `users`,
         `sales_representatives`, and `leads`.
       * If counts differ, **truncates and re-copies** the whole table from
         source to destination (via psycopg2, no dblink required).
       * Produces a detailed summary of what changed.

The script only uses the Python standard library, `boto3`, `psycopg2`,
`psycopg2-binary` (or compatible), and other broadly available packages so it
can run in typical environments (local, CI, or GitHub Actions).

Example usage
-------------

    python scripts/db_to_db_database_migration_pipeline.py \
      --source-host 127.0.0.1 \
      --source-db cloudsystem \
      --source-user postgres \
      --source-password 'password@12345' \
      --dest-host 127.0.0.1 \
      --dest-db cloudsystem \
      --dest-user postgres \
      --dest-password 'password@12345' \
      --s3-bucket aideveloper-sales-leads \
      --s3-prefix database-backups

Note: When passwords contain special characters (like !), use single quotes
      to prevent shell expansion. CLI arguments always take precedence over
      environment variables from .env file.

Notes
-----
- This script is **idempotent** with respect to the destination tables: when
  a table's row counts differ, the destination table is fully replaced with
  the source table's contents.
- Only `users`, `sales_representatives`, and `leads` are synchronized.
- The script prints a concise, structured summary at the end.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import boto3
import psycopg2
from psycopg2.extras import execute_values

# Scripts live under `scripts/database/`, so we navigate up two levels to reach
# the project root and the `app` package.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
APP_DIR = PROJECT_ROOT / "app"

# All pipeline logs (INFO/DEBUG/ERROR) are written both to stdout and this file.
LOG_FILE_PATH = PROJECT_ROOT / "db_pipeline_logs.txt"

sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

# Reuse backup helpers so behavior is consistent with backup_database.py
from backup_database import resolve_pg_dump, run_pg_dump  # type: ignore
from restore_database import (  # type: ignore
    detect_backup_type,
    resolve_pg_restore,
    resolve_psql,
    run_pg_restore,
    run_psql_restore,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DbConfig:
    """Connection parameters for a PostgreSQL database."""

    host: str
    port: int
    database: str
    user: str
    password: Optional[str]


@dataclass
class BackupResult:
    """Metadata about created backup files for a database."""

    database: str
    timestamp: str
    dump_path: Optional[Path]
    sql_path: Optional[Path]
    latest_dump_path: Optional[Path]
    latest_sql_path: Optional[Path]


@dataclass
class TableSyncSummary:
    """Summary of synchronization for a single table."""

    table: str
    source_rows: int
    dest_rows_before: Optional[int]
    dest_rows_after: Optional[int]
    action: str
    notes: str


@dataclass
class PipelineSummary:
    """High-level summary of the entire pipeline run."""

    backup: BackupResult
    s3_bucket: Optional[str]
    s3_prefix: Optional[str]
    destination_db_created: bool
    table_summaries: List[TableSyncSummary]
    # Trust-test metadata
    trust_test_username: Optional[str]
    trust_test_passed: Optional[bool]
    trust_test_details: Optional[str]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _configure_logging(verbose: bool = False) -> None:
    """Configure logging to both stdout and a log file.

    All log records go to:
    - Standard output (for interactive use / CI logs).
    - ``db_pipeline_logs.txt`` in the project root, with timestamps.
    """

    level = logging.DEBUG if verbose else logging.INFO

    # Get root logger and reset any pre-existing handlers so we do not
    # accidentally duplicate log output if this function is called multiple
    # times.
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler (append mode so historical runs are preserved)
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True) if LOG_FILE_PATH.parent != PROJECT_ROOT else None
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


logger = logging.getLogger(__name__)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for the migration pipeline.

    This defines configuration for source/destination databases and S3.
    """

    default_backup_dir = PROJECT_ROOT / "app" / "data" / "backups" / "postgres"

    parser = argparse.ArgumentParser(
        description=(
            "Database-to-database migration pipeline with safety backup and "
            "optional S3 upload."
        )
    )

    # Source DB (where data is read from and backed up)
    parser.add_argument("--source-host", required=True, help="Source DB host")
    parser.add_argument("--source-port", type=int, default=5432, help="Source DB port")
    parser.add_argument("--source-db", required=True, help="Source DB name")
    parser.add_argument("--source-user", required=True, help="Source DB user")
    parser.add_argument(
        "--source-password",
        default=None,
        help="Source DB password (or SOURCE_DB_PASSWORD env variable)",
    )

    # Destination DB (where data is written)
    parser.add_argument("--dest-host", required=True, help="Destination DB host")
    parser.add_argument("--dest-port", type=int, default=5432, help="Destination DB port")
    parser.add_argument("--dest-db", required=True, help="Destination DB name")
    parser.add_argument("--dest-user", required=True, help="Destination DB user")
    parser.add_argument(
        "--dest-password",
        default=None,
        help="Destination DB password (or DEST_DB_PASSWORD env variable)",
    )

    # Backup configuration
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=default_backup_dir,
        help=f"Directory to store backups (default: {default_backup_dir})",
    )
    parser.add_argument(
        "--pg-dump",
        dest="pg_dump",
        default=None,
        help="Optional path to pg_dump (defaults to PATH lookup)",
    )

    # S3 configuration
    parser.add_argument(
        "--s3-bucket",
        default=None,
        help=(
            "S3 bucket to upload backups to (if omitted, S3 upload is skipped). "
            "Default in GitHub Actions is 'aideveloper-sales-leads'."
        ),
    )
    parser.add_argument(
        "--s3-prefix",
        default="database-backups",
        help="S3 prefix/path under the bucket (default: 'database-backups')",
    )
    parser.add_argument(
        "--aws-region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region for S3 client (default: us-east-1)",
    )

    # Tables to sync when destination DB already exists
    parser.add_argument(
        "--tables",
        nargs="+",
        default=["users", "sales_representatives", "leads"],
        help="Tables to compare and synchronize when dest DB exists",
    )

    parser.add_argument(
        "--skip-trust-test",
        action="store_true",
        help=(
            "Skip the automatic trust test (temporary dummy user creation "
            "and verification). Enabled by default for extra assurance."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    # Only use environment variables if CLI arguments were not provided
    # This ensures CLI arguments always take precedence over .env file
    if args.source_password is None:
        args.source_password = os.getenv("SOURCE_DB_PASSWORD")
    if args.dest_password is None:
        args.dest_password = os.getenv("DEST_DB_PASSWORD")

    if not args.source_password:
        parser.error("--source-password or SOURCE_DB_PASSWORD env variable is required")
    if not args.dest_password:
        parser.error("--dest-password or DEST_DB_PASSWORD env variable is required")

    return args


def db_config_from_args(prefix: str, args: argparse.Namespace) -> DbConfig:
    """Build a :class:`DbConfig` from the parsed arguments.

    Parameters
    ----------
    prefix:
        Either ``"source"`` or ``"dest"``.
    args:
        Parsed CLI arguments.
    """

    if prefix not in {"source", "dest"}:
        raise ValueError("prefix must be 'source' or 'dest'")

    return DbConfig(
        host=getattr(args, f"{prefix}_host"),
        port=int(getattr(args, f"{prefix}_port")),
        database=getattr(args, f"{prefix}_db"),
        user=getattr(args, f"{prefix}_user"),
        password=getattr(args, f"{prefix}_password"),
    )


def connect_db(cfg: DbConfig, database_override: Optional[str] = None) -> psycopg2.extensions.connection:
    """Create a psycopg2 connection to PostgreSQL.

    Parameters
    ----------
    cfg:
        Database configuration.
    database_override:
        If provided, connect to this database name instead of ``cfg.database``.
    """

    dbname = database_override or cfg.database

    logger.debug(
        "Connecting to PostgreSQL: host=%s port=%s db=%s user=%s",
        cfg.host,
        cfg.port,
        dbname,
        cfg.user,
    )

    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        database=dbname,
        user=cfg.user,
        password=cfg.password,
    )
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# Trust-test helpers (dummy user creation / verification)
# ---------------------------------------------------------------------------


def create_trust_test_user(cfg: DbConfig) -> str:
    """Create a temporary dummy user in the source DB for trust testing.

    The user is identified by a unique username that embeds a timestamp. This
    user is used to verify that data has been correctly migrated from source
    to destination and is **always deleted** at the end of the pipeline.

    Returns
    -------
    str
        The unique username of the dummy user.
    """

    conn = connect_db(cfg)
    try:
        username = f"pipeline_trust_test_{int(time.time())}"
        email = f"{username}@example.local"
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")

        logger.info("STEP 0: Creating trust-test user '%s' on source DB", username)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users
                    (username, first_name, last_name, email, telephone,
                     organization, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                """,
                (
                    username,
                    "Pipeline",
                    "TrustTest",
                    email,
                    "+0000000000",
                    "Pipeline Trust Org",
                    f"TEMP_HASH_{username}",
                ),
            )
        logger.info("STEP 0 COMPLETE: Trust-test user '%s' created on source", username)
        return username
    finally:
        conn.close()


def _user_exists(conn: psycopg2.extensions.connection, username: str) -> bool:
    """Return True if a user with the given username exists in the DB."""

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM public.users WHERE username = %s",
            (username,),
        )
        return cur.fetchone() is not None


def verify_trust_test_user(source_cfg: DbConfig, dest_cfg: DbConfig, username: str) -> Tuple[bool, str]:
    """Verify that the dummy user exists on both source and destination.

    Returns
    -------
    (passed, details)
        ``passed`` is ``True`` if the user exists in both databases.
        ``details`` contains a human-readable explanation.
    """

    logger.info("STEP 5: Verifying trust-test user '%s' on both databases", username)

    source_conn = connect_db(source_cfg)
    dest_conn = connect_db(dest_cfg)
    try:
        on_source = _user_exists(source_conn, username)
        on_dest = _user_exists(dest_conn, username)

        if on_source and on_dest:
            details = (
                "Trust test PASSED: dummy user is present on both source and "
                "destination."
            )
            logger.info("  ✓ %s", details)
            return True, details

        details_parts = []
        if not on_source:
            details_parts.append("missing on source")
        if not on_dest:
            details_parts.append("missing on destination")
        details = "Trust test FAILED: " + ", ".join(details_parts)
        logger.error("  ❌ %s", details)
        return False, details
    finally:
        source_conn.close()
        dest_conn.close()


def cleanup_trust_test_user(source_cfg: DbConfig, dest_cfg: DbConfig, username: str) -> None:
    """Delete the dummy user from both source and destination databases."""

    logger.info("STEP 6: Cleaning up trust-test user '%s' from both databases", username)

    for cfg, label in ((source_cfg, "source"), (dest_cfg, "destination")):
        conn = connect_db(cfg)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.users WHERE username = %s",
                    (username,),
                )
            logger.info("  - Deleted trust-test user from %s DB (if existed)", label)
        finally:
            conn.close()

    logger.info("STEP 6 COMPLETE: Trust-test user cleanup finished")


# ---------------------------------------------------------------------------
# Backup & S3 upload
# ---------------------------------------------------------------------------


def create_source_backup(cfg: DbConfig, backup_dir: Path, pg_dump_path: Optional[str]) -> BackupResult:
    """Create `.dump` and `.sql` backups for the source database.

    This function reuses :func:`backup_database.resolve_pg_dump` and
    :func:`backup_database.run_pg_dump` so that behavior is consistent
    with the existing backup script and GitHub workflow.
    """

    backup_dir = backup_dir.expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    formats = ["custom", "plain"]  # Always produce both
    ext_for_format = {"custom": ".dump", "plain": ".sql"}

    resolved_pg_dump = resolve_pg_dump(pg_dump_path)

    logger.info("STEP 1: Creating backup of source database '%s'", cfg.database)

    latest_sql_path: Optional[Path] = None
    latest_dump_path: Optional[Path] = None
    dump_path: Optional[Path] = None
    sql_path: Optional[Path] = None

    for fmt in formats:
        ext = ext_for_format[fmt]
        destination = backup_dir / f"{cfg.database}_{timestamp}{ext}"
        logger.info("  - Creating %s backup at %s", fmt, destination)
        run_pg_dump(
            pg_dump_path=resolved_pg_dump,
            host=cfg.host,
            port=str(cfg.port),
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            schema=None,
            fmt=fmt,
            destination=destination,
        )
        logger.info("  ✓ Wrote %s", destination.name)

        if fmt == "plain":
            latest_sql_path = destination
            sql_path = destination
        elif fmt == "custom":
            latest_dump_path = destination
            dump_path = destination

    # Create *_latest_updated.{sql,dump} copies, mirroring backup_database.py
    if latest_sql_path is not None:
        latest_sql_copy = backup_dir / f"{cfg.database}_latest_updated.sql"
        if latest_sql_copy.exists():
            latest_sql_copy.unlink()
        shutil.copy2(latest_sql_path, latest_sql_copy)
        logger.info("  ✓ Updated latest SQL copy: %s", latest_sql_copy.name)
        latest_sql_path = latest_sql_copy

    if latest_dump_path is not None:
        latest_dump_copy = backup_dir / f"{cfg.database}_latest_updated.dump"
        if latest_dump_copy.exists():
            latest_dump_copy.unlink()
        shutil.copy2(latest_dump_path, latest_dump_copy)
        logger.info("  ✓ Updated latest DUMP copy: %s", latest_dump_copy.name)
        latest_dump_path = latest_dump_copy

    logger.info("STEP 1 COMPLETE: Source backup created successfully")

    return BackupResult(
        database=cfg.database,
        timestamp=timestamp,
        dump_path=dump_path,
        sql_path=sql_path,
        latest_dump_path=latest_dump_path,
        latest_sql_path=latest_sql_path,
    )


def upload_backups_to_s3(
    backup: BackupResult,
    bucket: Optional[str],
    prefix: str,
    region: str,
) -> None:
    """Upload `.dump` and `.sql` backup files to S3 using boto3.

    Parameters
    ----------
    backup:
        Backup metadata (paths may be ``None`` if not produced).
    bucket:
        Name of the S3 bucket. If ``None``, this function does nothing.
    prefix:
        Prefix (folder path) inside the bucket.
    region:
        AWS region for the S3 client.
    """

    if not bucket:
        logger.info("STEP 2: S3 upload skipped (no --s3-bucket provided)")
        return

    s3 = boto3.client("s3", region_name=region)
    prefix = prefix.strip("/")

    logger.info(
        "STEP 2: Uploading backups to S3 bucket='%s', prefix='%s'", bucket, prefix
    )

    files_to_upload: List[Tuple[str, Path]] = []

    if backup.latest_dump_path is not None:
        files_to_upload.append(("dump", backup.latest_dump_path))
    if backup.latest_sql_path is not None:
        files_to_upload.append(("sql", backup.latest_sql_path))

    if not files_to_upload:
        logger.warning("  ⚠ No backup files found to upload")
        return

    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for kind, path in files_to_upload:
        key = f"{prefix}/{path.name}"
        extra_args = {
            "Metadata": {
                "uploaded-by": "db-to-db-database-migration-pipeline",
                "kind": kind,
                "timestamp": now_iso,
                "database": backup.database,
            }
        }

        logger.info("  - Uploading %s as s3://%s/%s", path.name, bucket, key)
        s3.upload_file(str(path), bucket, key, ExtraArgs=extra_args)
        logger.info("    ✓ Uploaded %s", key)

    logger.info("STEP 2 COMPLETE: Backups uploaded to S3")


# ---------------------------------------------------------------------------
# Destination database existence & optional initial restore
# ---------------------------------------------------------------------------


def database_exists(dest_cfg: DbConfig) -> bool:
    """Check whether the destination database already exists on the server."""

    conn = connect_db(dest_cfg, database_override="postgres")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dest_cfg.database,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def create_database(dest_cfg: DbConfig) -> None:
    """Create the destination database on the target server if it does not exist."""

    logger.info("  - Creating destination database '%s'", dest_cfg.database)
    conn = connect_db(dest_cfg, database_override="postgres")
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE {psycopg2.extensions.AsIs(dest_cfg.database)}")
    finally:
        conn.close()
    logger.info("  ✓ Destination database created")


def initial_restore_to_destination(dest_cfg: DbConfig, backup: BackupResult) -> None:
    """Restore the destination database from the latest backup.

    This is used **only** when the destination database did not exist prior to
    running the pipeline. It restores from the latest `.dump` if available,
    otherwise the latest `.sql`.
    """

    backup_file: Optional[Path] = backup.latest_dump_path or backup.latest_sql_path
    if backup_file is None:
        raise RuntimeError("No backup file available for initial restore")

    backup_type = detect_backup_type(backup_file)
    logger.info(
        "STEP 3: Initial restore of destination DB from %s (%s)",
        backup_file.name,
        backup_type,
    )

    if backup_type == "dump":
        pg_restore_path = resolve_pg_restore(None)
        run_pg_restore(
            pg_restore_path=pg_restore_path,
            host=dest_cfg.host,
            port=str(dest_cfg.port),
            user=dest_cfg.user,
            password=dest_cfg.password,
            database=dest_cfg.database,
            backup_file=backup_file,
            clean=False,
            create=False,
        )
    elif backup_type == "sql":
        psql_path = resolve_psql(None)
        run_psql_restore(
            psql_path=psql_path,
            host=dest_cfg.host,
            port=str(dest_cfg.port),
            user=dest_cfg.user,
            password=dest_cfg.password,
            database=dest_cfg.database,
            backup_file=backup_file,
        )
    else:
        raise RuntimeError(f"Unsupported backup type: {backup_type}")

    logger.info("STEP 3 COMPLETE: Destination database restored from backup")


# ---------------------------------------------------------------------------
# Table comparison & synchronization
# ---------------------------------------------------------------------------


def table_exists(conn: psycopg2.extensions.connection, table: str) -> bool:
    """Return ``True`` if the given table exists in the public schema."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return cur.fetchone() is not None


def get_row_count(conn: psycopg2.extensions.connection, table: str) -> int:
    """Return the number of rows in ``public.<table>``.

    If the table does not exist, returns ``0``.
    """

    if not table_exists(conn, table):
        return 0

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM public.{table}")
        (count,) = cur.fetchone()
        return int(count)


def get_table_columns(conn: psycopg2.extensions.connection, table: str) -> List[str]:
    """Return the ordered list of column names for the given table in ``public``.

    The order is by ``ordinal_position`` so that it matches the natural
    ``SELECT *`` column order.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = cur.fetchall()
    return [r[0] for r in rows]


def sync_single_table(
    source_conn: psycopg2.extensions.connection,
    dest_conn: psycopg2.extensions.connection,
    table: str,
) -> TableSyncSummary:
    """Compare row counts and optionally replace the destination table.

    Strategy
    --------
    1. If the table is missing on source, no action is taken (recorded in
       ``notes``).
    2. If the table is missing on destination, we treat row count as 0 and
       perform a full copy from source.
    3. If row counts differ between source and destination, we **truncate** the
       destination table and then bulk-insert all rows from source.
    4. If row counts match, we report ``action='none'`` and do nothing.

    This keeps the logic simple and predictable while guaranteeing that the
    destination table is an exact copy of the source table whenever a
    difference is detected.
    """

    logger.info("STEP 4: Checking table '%s'", table)

    if not table_exists(source_conn, table):
        notes = f"Source table '{table}' does not exist; skipping."
        logger.warning("  ⚠ %s", notes)
        return TableSyncSummary(
            table=table,
            source_rows=0,
            dest_rows_before=None,
            dest_rows_after=None,
            action="skipped",
            notes=notes,
        )

    source_rows = get_row_count(source_conn, table)
    dest_has_table = table_exists(dest_conn, table)
    dest_rows_before = get_row_count(dest_conn, table) if dest_has_table else 0

    logger.info(
        "  - Source rows: %s | Dest rows: %s",
        source_rows,
        dest_rows_before,
    )

    if source_rows == dest_rows_before and dest_has_table:
        notes = "Row counts match; no migration required."
        logger.info("  ✓ %s", notes)
        return TableSyncSummary(
            table=table,
            source_rows=source_rows,
            dest_rows_before=dest_rows_before,
            dest_rows_after=dest_rows_before,
            action="none",
            notes=notes,
        )

    # At this point, we need to do a full replacement of the destination table.
    # First, check that schemas are compatible (same set of columns).
    source_cols = get_table_columns(source_conn, table)
    dest_cols = get_table_columns(dest_conn, table) if dest_has_table else []

    if dest_has_table and set(source_cols) != set(dest_cols):
        notes = (
            "Schema mismatch between source and destination; "
            "table will not be migrated."
        )
        logger.error("  ❌ %s", notes)
        logger.error("     Source columns: %s", ", ".join(source_cols))
        logger.error("     Dest columns:   %s", ", ".join(dest_cols))
        return TableSyncSummary(
            table=table,
            source_rows=source_rows,
            dest_rows_before=dest_rows_before,
            dest_rows_after=dest_rows_before,
            action="schema-mismatch",
            notes=notes,
        )

    # Destination either has the table with compatible schema or is missing it
    # (missing => we will rely on existing schema having been created ahead of
    # time; if it truly does not exist, this TRUNCATE will raise, surfacing the
    # configuration problem clearly).
    logger.info("  → Replacing destination table '%s' with source data", table)

    with dest_conn.cursor() as dcur:
        dcur.execute(f"TRUNCATE TABLE public.{table} RESTART IDENTITY CASCADE")

    # Bulk copy from source to destination in batches
    placeholders_cols = ", ".join(source_cols)
    select_sql = f"SELECT {placeholders_cols} FROM public.{table}"

    rows_copied = 0
    batch_size = 1000

    with source_conn.cursor(name=f"src_{table}_cursor") as scur:  # server-side cursor
        scur.itersize = batch_size
        scur.execute(select_sql)

        while True:
            batch = scur.fetchmany(batch_size)
            if not batch:
                break
            with dest_conn.cursor() as dcur:
                insert_sql = f"INSERT INTO public.{table} ({placeholders_cols}) VALUES %s"
                execute_values(dcur, insert_sql, batch)
            rows_copied += len(batch)
            logger.debug("    Copied %d rows so far for table '%s'", rows_copied, table)

    dest_rows_after = get_row_count(dest_conn, table)
    notes = f"Replaced destination table with {rows_copied} rows from source."
    logger.info("  ✓ %s (dest now has %s rows)", notes, dest_rows_after)

    return TableSyncSummary(
        table=table,
        source_rows=source_rows,
        dest_rows_before=dest_rows_before,
        dest_rows_after=dest_rows_after,
        action="replaced",
        notes=notes,
    )


def compare_and_migrate_tables(
    source_cfg: DbConfig,
    dest_cfg: DbConfig,
    tables: List[str],
) -> List[TableSyncSummary]:
    """Compare and, if needed, migrate a list of tables from source to dest."""

    logger.info("STEP 4: Comparing and synchronizing key tables")

    source_conn = connect_db(source_cfg)
    dest_conn = connect_db(dest_cfg)

    try:
        summaries: List[TableSyncSummary] = []
        for table in tables:
            summaries.append(sync_single_table(source_conn, dest_conn, table))
        logger.info("STEP 4 COMPLETE: Table comparison and synchronization done")
        return summaries
    finally:
        source_conn.close()
        dest_conn.close()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(args: argparse.Namespace) -> PipelineSummary:
    """Run the full db-to-db migration pipeline.

    Steps
    -----
    0. Optionally create a temporary trust-test user on the source DB.
    1. Backup source database to `.dump` and `.sql` (+ latest copies).
    2. Optionally upload backups to S3.
    3. If destination database does **not** exist:
         a. Create it.
         b. Restore from the latest backup.
       Else:
         a. Compare and synchronize key tables.
    4. Verify that the trust-test user exists on both DBs.
    5. Delete the trust-test user from both DBs.
    6. Return a structured summary of operations.
    """

    source_cfg = db_config_from_args("source", args)
    dest_cfg = db_config_from_args("dest", args)

    trust_username: Optional[str] = None
    trust_passed: Optional[bool] = None
    trust_details: Optional[str] = None

    try:
        # Step 0: create trust-test user (unless explicitly skipped)
        if args.skip_trust_test:
            logger.info("STEP 0: Trust test skipped by --skip-trust-test flag")
        else:
            trust_username = create_trust_test_user(source_cfg)

        # Step 1: backup source DB
        backup = create_source_backup(source_cfg, args.backup_dir, args.pg_dump)

        # Step 2: upload to S3 (optional)
        upload_backups_to_s3(backup, args.s3_bucket, args.s3_prefix, args.aws_region)

        # Step 3 / 4: handle destination DB
        dest_exists = database_exists(dest_cfg)
        destination_db_created = False
        table_summaries: List[TableSyncSummary] = []

        if not dest_exists:
            logger.info(
                "STEP 3: Destination database '%s' does not exist; it will be created and restored",
                dest_cfg.database,
            )
            create_database(dest_cfg)
            destination_db_created = True
            initial_restore_to_destination(dest_cfg, backup)
        else:
            logger.info(
                "STEP 3: Destination database '%s' already exists; skipping full restore",
                dest_cfg.database,
            )
            # Step 4: compare and migrate key tables only
            table_summaries = compare_and_migrate_tables(source_cfg, dest_cfg, args.tables)

        # Step 5: verify trust-test user (if created)
        if trust_username is not None:
            trust_passed, trust_details = verify_trust_test_user(
                source_cfg,
                dest_cfg,
                trust_username,
            )
        else:
            trust_passed = None
            trust_details = "Trust test was skipped."

        return PipelineSummary(
            backup=backup,
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix,
            destination_db_created=destination_db_created,
            table_summaries=table_summaries,
            trust_test_username=trust_username,
            trust_test_passed=trust_passed,
            trust_test_details=trust_details,
        )

    finally:
        # Step 6: clean up trust-test user from both DBs
        if trust_username is not None:
            try:
                cleanup_trust_test_user(source_cfg, dest_cfg, trust_username)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.exception(
                    "Failed to clean up trust-test user '%s': %s",
                    trust_username,
                    cleanup_exc,
                )


def print_summary(summary: PipelineSummary) -> None:
    """Print a human-readable summary and a JSON blob for programmatic use."""

    logger.info("=" * 72)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 72)

    # Backup summary
    b = summary.backup
    logger.info("Backup:")
    logger.info("  - Database: %s", b.database)
    logger.info("  - Timestamp: %s", b.timestamp)
    logger.info("  - Dump file: %s", b.latest_dump_path or "<none>")
    logger.info("  - SQL file : %s", b.latest_sql_path or "<none>")

    # S3
    if summary.s3_bucket:
        logger.info("S3:")
        logger.info("  - Bucket: %s", summary.s3_bucket)
        logger.info("  - Prefix: %s", summary.s3_prefix)

    # Destination
    logger.info("Destination database:")
    logger.info("  - Created this run: %s", "yes" if summary.destination_db_created else "no")

    # Tables
    if summary.table_summaries:
        logger.info("Table synchronization:")
        for t in summary.table_summaries:
            logger.info(
                "  - %s: action=%s src_rows=%s dest_before=%s dest_after=%s",
                t.table,
                t.action,
                t.source_rows,
                t.dest_rows_before,
                t.dest_rows_after,
            )
            logger.info("      %s", t.notes)
    else:
        logger.info("Table synchronization: <not run (destination was freshly restored)>")

    # Also emit a compact JSON summary for easier parsing by other tools
    data = asdict(summary)

    # Convert Paths to strings for JSON serialization
    def _normalize(obj):  # type: ignore[override]
        if isinstance(obj, Path):
            return str(obj)
        return obj

    json_summary = json.dumps(data, default=_normalize, indent=2, sort_keys=True)

    print("\nJSON_SUMMARY_START")
    print(json_summary)
    print("JSON_SUMMARY_END\n")


def main(argv: Optional[Iterable[str]] = None) -> None:
    """CLI entry point for the db-to-db database migration pipeline."""

    args = parse_args(argv)
    _configure_logging(verbose=args.verbose)

    try:
        summary = run_pipeline(args)
        print_summary(summary)
    except KeyboardInterrupt:
        logger.error("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
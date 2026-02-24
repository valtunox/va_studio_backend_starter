"""
Restore Database Script - PostgreSQL Database Restore
======================================================

This script restores a PostgreSQL database from .dump or .sql backup files.
It auto-detects the backup type and uses the appropriate tool (pg_restore or psql).

Database connection defaults are loaded from the .env file via core.db.get_db_config.

Usage:
    python scripts/database/restore_database.py --backup-file path/to/backup.dump
    python scripts/database/restore_database.py --backup-file path/to/backup.sql
    python scripts/database/restore_database.py --backup-file backup.dump --clean
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_config


def resolve_pg_restore(explicit_path: Optional[str]) -> Path:
    """Return the pg_restore executable path, honoring an explicit override."""
    if explicit_path:
        candidate = Path(explicit_path)
        if not candidate.exists():
            print(f"[ERROR] pg_restore not found at provided path: {candidate}")
            sys.exit(1)
        return candidate

    found = shutil.which("pg_restore")
    if not found:
        print("[ERROR] Could not locate pg_restore in PATH. Install PostgreSQL client tools or pass --pg-restore.")
        sys.exit(1)
    return Path(found)


def resolve_psql(explicit_path: Optional[str]) -> Path:
    """Return the psql executable path, honoring an explicit override."""
    if explicit_path:
        candidate = Path(explicit_path)
        if not candidate.exists():
            print(f"[ERROR] psql not found at provided path: {candidate}")
            sys.exit(1)
        return candidate

    found = shutil.which("psql")
    if not found:
        print("[ERROR] Could not locate psql in PATH. Install PostgreSQL client tools or pass --psql.")
        sys.exit(1)
    return Path(found)


def run_pg_restore(
    pg_restore_path: Path,
    host: str,
    port: str,
    user: str,
    password: Optional[str],
    database: str,
    backup_file: Path,
    clean: bool = False,
    create: bool = False,
):
    """Restore a database from a .dump file using pg_restore."""
    if not backup_file.exists():
        print(f"[ERROR] Backup file not found: {backup_file}")
        sys.exit(1)

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        str(pg_restore_path),
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database,
        "--no-owner",
        "--no-privileges",
        "--verbose",
    ]

    if clean:
        cmd.append("--clean")
    
    if create:
        cmd.append("--create")

    cmd.append(str(backup_file))

    try:
        print(f"[INFO] Running pg_restore on {backup_file.name}")
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        print(f"[ERROR] pg_restore executable missing: {pg_restore_path}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] pg_restore exited with status {exc.returncode}")
        sys.exit(exc.returncode or 1)


def run_psql_restore(
    psql_path: Path,
    host: str,
    port: str,
    user: str,
    password: Optional[str],
    database: str,
    backup_file: Path,
):
    """Restore a database from a .sql file using psql."""
    if not backup_file.exists():
        print(f"[ERROR] Backup file not found: {backup_file}")
        sys.exit(1)

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        str(psql_path),
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database,
        "-f",
        str(backup_file),
    ]

    try:
        print(f"[INFO] Running psql restore on {backup_file.name}")
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        print(f"[ERROR] psql executable missing: {psql_path}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] psql exited with status {exc.returncode}")
        sys.exit(exc.returncode or 1)


def detect_backup_type(backup_file: Path) -> str:
    """Detect whether the backup is a .dump or .sql file."""
    suffix = backup_file.suffix.lower()
    if suffix == ".dump":
        return "dump"
    elif suffix == ".sql":
        return "sql"
    else:
        print(f"[ERROR] Unknown backup file type: {suffix}. Expected .dump or .sql")
        sys.exit(1)


def main():
    # Get database configuration from environment variables (.env file)
    try:
        db_config = get_db_config()
    except ValueError as e:
        print(f"[ERROR] {e}")
        print("[INFO] Please ensure all required database configuration is set in .env file:")
        print("       - POSTGRES_HOST")
        print("       - POSTGRES_DB")
        print("       - POSTGRES_USER")
        print("       - POSTGRES_PASSWORD")
        print("       - POSTGRES_PORT (optional, defaults to 5432)")
        sys.exit(1)

    # Default backup file path
    default_backup_file = project_root / "app" / "data" / "backups" / "postgres" / "recruitment_latest_updated.dump"

    parser = argparse.ArgumentParser(description="Restore a PostgreSQL database from .dump or .sql file")
    parser.add_argument("--backup-file", default=str(default_backup_file), help=f"Path to the backup file (.dump or .sql) (default: {default_backup_file})")
    parser.add_argument("--pg-restore", dest="pg_restore", help="Path to pg_restore executable (defaults to PATH lookup)")
    parser.add_argument("--psql", dest="psql", help="Path to psql executable (defaults to PATH lookup)")
    parser.add_argument("--host", default=db_config.get("host"), help="Database host (from .env file)")
    parser.add_argument("--port", default=str(db_config.get("port")), help="Database port (from .env file)")
    parser.add_argument("--database", default=db_config.get("database"), help="Database name (from .env file)")
    parser.add_argument("--user", default=db_config.get("user"), help="Database user (from .env file)")
    parser.add_argument("--password", default=db_config.get("password"), help="Database password (from .env file)")
    parser.add_argument("--clean", action="store_true", help="Clean (drop) database objects before recreating (only for .dump)")
    parser.add_argument("--create", action="store_true", help="Create the database before restoring (only for .dump)")
    args = parser.parse_args()

    backup_file = Path(args.backup_file)
    if not backup_file.exists():
        print(f"[ERROR] Backup file does not exist: {backup_file}")
        sys.exit(1)

    backup_type = detect_backup_type(backup_file)
    
    print(f"[INFO] Detected backup type: {backup_type}")
    print(f"[INFO] Target host: {args.host}:{args.port}")
    print(f"[INFO] Restoring database '{args.database}' from {backup_file}")
    
    if backup_type == "dump":
        pg_restore_path = resolve_pg_restore(args.pg_restore)
        run_pg_restore(
            pg_restore_path=pg_restore_path,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            backup_file=backup_file,
            clean=args.clean,
            create=args.create,
        )
        print(f"[OK] Successfully restored database from {backup_file.name}")
    
    elif backup_type == "sql":
        psql_path = resolve_psql(args.psql)
        if args.clean or args.create:
            print("[WARN] --clean and --create flags are ignored for .sql files")
        run_psql_restore(
            psql_path=psql_path,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            backup_file=backup_file,
        )
        print(f"[OK] Successfully restored database from {backup_file.name}")
    
    print("[DONE] Database restore completed successfully")


if __name__ == "__main__":
    main()


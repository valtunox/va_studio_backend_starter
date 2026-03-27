import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add parent directory to path to import core modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / 'app'
sys.path.insert(0, str(app_dir))

from core.db import get_db_config


def resolve_pg_dump(explicit_path: Optional[str]) -> Path:
    """Return the pg_dump executable path, honoring an explicit override."""
    if explicit_path:
        candidate = Path(explicit_path)
        if not candidate.exists():
            print(f"[ERROR] pg_dump not found at provided path: {candidate}")
            sys.exit(1)
        return candidate

    found = shutil.which("pg_dump")
    if not found:
        print("[ERROR] Could not locate pg_dump in PATH. Install PostgreSQL client tools or pass --pg-dump.")
        sys.exit(1)
    return Path(found)


def run_pg_dump(
    pg_dump_path: Path,
    host: str,
    port: str,
    user: str,
    password: Optional[str],
    database: str,
    schema: Optional[str],
    fmt: str,
    destination: Path,
):
    destination.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        str(pg_dump_path),
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database,
        "--format",
        fmt,
        "--no-owner",
        "--no-privileges",
        "-f",
        str(destination),
    ]

    if schema:
        cmd.extend(["--schema", schema])

    try:
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        print(f"[ERROR] pg_dump executable missing: {pg_dump_path}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] pg_dump exited with status {exc.returncode} while creating {destination.name}")
        sys.exit(exc.returncode or 1)


def get_tables(conn, schema: str) -> List[str]:
    import psycopg2
    with conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (schema,))
        rows = cur.fetchall()
    return [row[0] for row in rows]


def export_tables_to_csv(conn, schema: str, tables: List[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        destination = out_dir / f"{table}.csv"
        sql = f'COPY "{schema}"."{table}" TO STDOUT WITH CSV HEADER'
        with destination.open("w", encoding="utf-8", newline="") as handle:
            with conn.cursor() as cur:
                cur.copy_expert(sql, handle)
        print(f"[OK] Exported {table} to {destination}")


def export_tables_to_excel(conn, schema: str, tables: List[str], workbook: Path) -> None:
    import pandas as pd
    workbook.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for table in tables:
            query = f'SELECT * FROM "{schema}"."{table}"'
            frame = pd.read_sql_query(query, conn)
            base = (table[:31] or f"table_{len(seen) + 1}").rstrip()
            name = base
            suffix = 1
            while name in seen:
                trimmed = base[:25].rstrip() or "tbl"
                name = f"{trimmed}_{suffix}"
                suffix += 1
            seen.add(name)
            frame.to_excel(writer, sheet_name=name, index=False)
            print(f"[OK] Added {table} to {workbook} as sheet {name}")


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
    
    parser = argparse.ArgumentParser(description="Backup a PostgreSQL database to .dump, .sql, .csv, and .excel files")
    parser.add_argument("--pg-dump", dest="pg_dump", help="Path to pg_dump executable (defaults to PATH lookup)")
    parser.add_argument("--host", default=db_config.get("host"), help="Database host (from .env file)")
    parser.add_argument("--port", default=str(db_config.get("port")), help="Database port (from .env file)")
    parser.add_argument("--database", default=db_config.get("database"), help="Database name (from .env file)")
    parser.add_argument("--user", default=db_config.get("user"), help="Database user (from .env file)")
    parser.add_argument("--password", default=db_config.get("password"), help="Database password (from .env file)")
    parser.add_argument("--schema", default=None, help="Optional schema to dump (defaults to entire database)")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: app/data/backups/postgres)")
    parser.add_argument("--skip-csv", action="store_true", help="Skip CSV export (enabled by default)")
    parser.add_argument("--skip-excel", action="store_true", help="Skip Excel export (enabled by default)")
    parser.add_argument("--tables", nargs="+", default=None, help="Optional list of tables to export")
    parser.add_argument("--csv-out-dir", default=None, help="Directory for CSV exports")
    parser.add_argument("--excel-out-dir", default=None, help="Directory for Excel exports")
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["custom", "plain"],
        choices=("custom", "plain"),
        help="Backup formats to produce (default: custom plain)",
    )
    args = parser.parse_args()

    backups_root = project_root / "app" / "data" / "backups"
    out_dir = Path(args.out_dir) if args.out_dir else (backups_root / "postgres")

    formats = list(dict.fromkeys(args.formats))
    ext_for_format = {"custom": ".dump", "plain": ".sql"}

    pg_dump_path = resolve_pg_dump(args.pg_dump)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    latest_sql_path = None
    latest_dump_path = None

    for fmt in formats:
        ext = ext_for_format[fmt]
        destination = out_dir / f"{args.database}_{timestamp}{ext}"
        print(f"[INFO] Creating {fmt} backup at {destination}")
        run_pg_dump(
            pg_dump_path=pg_dump_path,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            schema=args.schema,
            fmt=fmt,
            destination=destination,
        )
        print(f"[OK] Wrote {destination}")
        
        # Track latest files for creating symlinks
        if fmt == "plain":
            latest_sql_path = destination
        elif fmt == "custom":
            latest_dump_path = destination

    # Create cloudsystem_latest_updated.sql and cloudsystem_latest_updated.dump copies
    if latest_sql_path:
        latest_sql_link = out_dir / f"{args.database}_latest_updated.sql"
        if latest_sql_link.exists():
            latest_sql_link.unlink()
        shutil.copy2(latest_sql_path, latest_sql_link)
        print(f"[OK] Created/updated latest SQL file: {latest_sql_link}")
    
    if latest_dump_path:
        latest_dump_link = out_dir / f"{args.database}_latest_updated.dump"
        if latest_dump_link.exists():
            latest_dump_link.unlink()
        shutil.copy2(latest_dump_path, latest_dump_link)
        print(f"[OK] Created/updated latest dump file: {latest_dump_link}")

    print("[DONE] PostgreSQL backups (.dump and .sql) completed successfully")

    # Export CSV and Excel by default unless explicitly skipped
    export_csv = not args.skip_csv
    export_excel = not args.skip_excel

    if not (export_csv or export_excel):
        print("[INFO] Skipping CSV and Excel exports")
        return

    import psycopg2
    conn = psycopg2.connect(
        host=args.host,
        port=int(args.port),
        database=args.database,
        user=args.user,
        password=args.password,
    )
    conn.autocommit = True
    try:
        schema = args.schema or "public"
        tables = args.tables or get_tables(conn, schema)
        if not tables:
            print("[WARN] No tables found for export")
            return

        if export_csv:
            csv_dir = (
                Path(args.csv_out_dir)
                if args.csv_out_dir
                else backups_root / "csv" / timestamp
            )
            print(f"[INFO] Exporting tables to CSV at {csv_dir}")
            export_tables_to_csv(conn, schema, tables, csv_dir)
            print("[DONE] CSV exports completed successfully")

        if export_excel:
            excel_dir = (
                Path(args.excel_out_dir)
                if args.excel_out_dir
                else backups_root / "excel"
            )
            excel_dir.mkdir(parents=True, exist_ok=True)
            excel_path = excel_dir / f"{args.database}_{timestamp}.xlsx"
            print(f"[INFO] Exporting tables to Excel at {excel_path}")
            export_tables_to_excel(conn, schema, tables, excel_path)
            print("[DONE] Excel export completed successfully")
        
        print("[DONE] All 4 backup formats (.dump, .sql, .csv, .xlsx) completed successfully")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

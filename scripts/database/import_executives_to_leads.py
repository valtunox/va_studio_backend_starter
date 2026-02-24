#!/usr/bin/env python3
"""
Import Executives to Leads - CSV Data Import
==============================================

This script imports executive contact data from CSV files into the leads table.
It handles deduplication, column mapping, and batch insertion.

Usage:
    python scripts/database/import_executives_to_leads.py --file data.csv [--dry-run]
"""

import argparse
import csv
import io
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / "app"
sys.path.insert(0, str(app_dir))

from core.db import get_db_connection  # noqa: E402


try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _canon(s: str) -> str:
    s = (s or "").strip().lower()
    return "".join(ch for ch in s if ch.isalnum())


_HEADER_MAP = {
    "businessname": "business_name",
    "business_name": "business_name",
    "business": "business_name",
    "company": "business_name",
    "companyname": "business_name",
    "company_name": "business_name",
    "organisation": "business_name",
    "organization": "business_name",
    "org": "business_name",
    "firm": "business_name",
    "employer": "business_name",
    "account": "business_name",
    "accountname": "business_name",
    "contactperson": "contact_person",
    "contact_person": "contact_person",
    "contactname": "contact_person",
    "contact_name": "contact_person",
    "contact": "contact_person",
    "name": "contact_person",
    "fullname": "contact_person",
    "full_name": "contact_person",
    "firstname": "first_name",
    "first_name": "first_name",
    "lastname": "last_name",
    "last_name": "last_name",
    "email": "email",
    "emailaddress": "email",
    "email_address": "email",
    "workemail": "email",
    "businessemail": "email",
    "phonenumber": "phone_number",
    "phone_number": "phone_number",
    "phone": "phone_number",
    "telephone": "phone_number",
    "mobile": "phone_number",
    "website": "website",
    "web": "website",
    "url": "website",
    "linkedin": "linkedin",
    "linkedinurl": "linkedin",
    "linkedin_url": "linkedin",
    "linkedinprofile": "linkedin",
    "city": "city",
    "state": "state",
    "province": "state",
    "region": "state",
    "country": "country",
    "address": "address",
    "street": "address",
    "postal": "postal",
    "zip": "postal",
    "zipcode": "postal",
    "industry": "industry",
    "category": "category",
    "sector": "industry",
    "jobtitle": "job_title",
    "job_title": "job_title",
    "title": "job_title",
    "position": "job_title",
    "role": "job_title",
    "designation": "job_title",
}


_BOOL_FIELDS = {"sent", "clicked", "replied"}
_YESNO_FIELDS = {"called", "follow_up", "lead_respond", "sent_sms", "contact_found", "meeting_booked", "deal_closed"}


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "t")


def _to_yesno(v: Any) -> str:
    if v is None or str(v).strip() == "":
        return ""
    s = str(v).strip().upper()
    if s in ("YES", "NO"):
        return s
    return "YES" if _to_bool(v) else "NO"


def _parse_csv_file(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace").lstrip("\ufeff")

    sample = text[:2048]
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except Exception:
        pass

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter, skipinitialspace=True)
    rows: List[Dict[str, Any]] = []
    for row in reader:
        cleaned: Dict[str, Any] = {}
        for k, v in (row or {}).items():
            if k is None:
                continue
            kk = str(k).strip().strip('"\'')
            vv = "" if v is None else str(v).strip().strip('"\'')
            cleaned[kk] = vv
        if any(str(v).strip() for v in cleaned.values()):
            rows.append(cleaned)
    return rows


def _normalize_row(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    out: Dict[str, Any] = {}
    extras: Dict[str, str] = {}

    for rk, rv in raw.items():
        canon_key = _canon(str(rk))
        key = _HEADER_MAP.get(canon_key)
        if not key:
            continue

        if rv is None:
            continue
        val = str(rv).strip()
        if not val:
            continue

        if key in _BOOL_FIELDS:
            out[key] = _to_bool(val)
        elif key in _YESNO_FIELDS:
            out[key] = _to_yesno(val)
        elif key == "first_name":
            extras["first_name"] = val
        elif key == "last_name":
            extras["last_name"] = val
        elif key == "job_title":
            extras["job_title"] = val
        else:
            out[key] = val

    if "contact_person" not in out or not str(out.get("contact_person") or "").strip():
        first_name = extras.get("first_name", "").strip()
        last_name = extras.get("last_name", "").strip()
        full = " ".join(p for p in [first_name, last_name] if p)
        if full:
            out["contact_person"] = full

    if "email" in out and out["email"]:
        out["email"] = str(out["email"]).strip().lower()

    if "industry" not in out and "category" in out:
        out["industry"] = out["category"]

    return out, extras


def _get_table_columns(conn, table: str = "leads") -> List[str]:
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


def _business_name_unique(conn, business_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM leads WHERE business_name = %s LIMIT 1", (business_name,))
        return cur.fetchone() is None


def _make_unique_business_name(conn, base: str, contact_person: str, job_title: str) -> str:
    base = (base or "").strip()
    contact_person = (contact_person or "").strip()
    job_title = (job_title or "").strip()

    suffix_parts = [p for p in [contact_person, job_title] if p]
    suffix = " - ".join(suffix_parts)
    candidate = base
    if suffix:
        candidate = f"{base} - {suffix}"

    candidate = candidate[:255]
    if _business_name_unique(conn, candidate):
        return candidate

    for i in range(2, 1000):
        c = f"{candidate[:240]}-{i}"[:255]
        if _business_name_unique(conn, c):
            return c

    return f"{candidate[:240]}-X"[:255]


def import_executives(
    path: Path,
    limit: Optional[int],
    dry_run: bool,
    allow_multiple_per_company: bool,
    enrichment_source: str,
) -> int:
    rows = _parse_csv_file(path)
    if not rows:
        logger.error("No rows parsed from CSV")
        return 1

    conn = get_db_connection()
    conn.autocommit = True
    table_cols = set(_get_table_columns(conn, table="leads"))

    processed = 0
    inserted = 0
    updated = 0
    skipped = 0

    cur = conn.cursor()

    def _reconnect(reason: str) -> None:
        nonlocal conn, cur
        logger.warning("Database connection reset (%s). Reconnecting...", reason)
        try:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()
        except Exception:
            pass
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()

    try:
        for idx, raw in enumerate(rows, start=1):
            if limit is not None and processed >= limit:
                break

            processed += 1
            data, extras = _normalize_row(raw)

            business_name = str(data.get("business_name") or "").strip()
            if not business_name:
                skipped += 1
                continue

            data.setdefault("enrichment_source", enrichment_source)

            job_title = extras.get("job_title", "").strip()
            if job_title:
                existing_notes = str(data.get("notes") or "").strip()
                title_note = f"Title: {job_title}"
                data["notes"] = (existing_notes + "\n" + title_note).strip() if existing_notes else title_note

            if "contact_found" in table_cols and "contact_found" not in data:
                has_contact = bool(
                    str(data.get("email") or "").strip()
                    or str(data.get("phone_number") or "").strip()
                    or str(data.get("linkedin") or "").strip()
                )
                data["contact_found"] = "YES" if has_contact else "NO"

            if allow_multiple_per_company:
                try:
                    business_name = _make_unique_business_name(
                        conn,
                        base=business_name,
                        contact_person=str(data.get("contact_person") or "").strip(),
                        job_title=job_title,
                    )
                    data["business_name"] = business_name
                except Exception as e:
                    if psycopg2 and isinstance(e, (psycopg2.InterfaceError, psycopg2.OperationalError)):
                        _reconnect(f"unique-name-check: {e}")
                        try:
                            business_name = _make_unique_business_name(
                                conn,
                                base=business_name,
                                contact_person=str(data.get("contact_person") or "").strip(),
                                job_title=job_title,
                            )
                            data["business_name"] = business_name
                        except Exception as e2:
                            logger.error(f"Row {idx} failed (business_name={business_name}): {e2}")
                            skipped += 1
                            continue
                    else:
                        logger.error(f"Row {idx} failed (business_name={business_name}): {e}")
                        skipped += 1
                        continue

            filtered = {k: v for k, v in data.items() if k in table_cols}

            cols = list(filtered.keys())
            if "business_name" not in cols:
                cols.insert(0, "business_name")

            placeholders = ", ".join(["%s"] * len(cols))
            set_cols = [c for c in cols if c != "business_name"]
            set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols]) if set_cols else "business_name = EXCLUDED.business_name"

            sql = (
                f"INSERT INTO leads ({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT (business_name) DO UPDATE SET {set_clause} "
                f"RETURNING (xmax = 0) AS inserted"
            )
            vals = [filtered.get(c) for c in cols]

            if dry_run:
                continue

            try:
                cur.execute(sql, vals)
                res = cur.fetchone()
                if res and bool(res[0]):
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                if psycopg2 and isinstance(e, (psycopg2.InterfaceError, psycopg2.OperationalError)):
                    _reconnect(f"execute: {e}")
                    try:
                        cur.execute(sql, vals)
                        res = cur.fetchone()
                        if res and bool(res[0]):
                            inserted += 1
                        else:
                            updated += 1
                    except Exception as e2:
                        logger.error(f"Row {idx} failed (business_name={business_name}): {e2}")
                        skipped += 1
                else:
                    logger.error(f"Row {idx} failed (business_name={business_name}): {e}")
                    skipped += 1

    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    logger.info(
        "Import finished: processed=%s inserted=%s updated=%s skipped=%s dry_run=%s",
        processed,
        inserted,
        updated,
        skipped,
        dry_run,
    )

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Import CEO/Director/General Manager CSV into leads table")
    ap.add_argument("--path", required=True, help="Path to .csv file")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to import")
    ap.add_argument("--dry-run", action="store_true", help="Parse + validate but do not commit")
    ap.add_argument(
        "--allow-multiple-per-company",
        action="store_true",
        help="If business_name already exists, auto-generate a unique business_name per contact",
    )
    ap.add_argument("--enrichment-source", default="executives_csv", help="Value stored in leads.enrichment_source")

    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return 2

    return import_executives(
        path=path,
        limit=args.limit,
        dry_run=bool(args.dry_run),
        allow_multiple_per_company=bool(args.allow_multiple_per_company),
        enrichment_source=str(args.enrichment_source),
    )


if __name__ == "__main__":
    raise SystemExit(main())

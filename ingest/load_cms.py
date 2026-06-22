"""
Load CMS Open Payments 2023 general payments into RAW.CMS_OPEN_PAYMENTS.

Uses the CMS Socrata API (no key required). Paginates in 50K-row batches
up to CMS_ROW_LIMIT (default 100K). Set CMS_DATASET_ID in .env.

Usage: python load_cms.py
"""

import os
import sys
from typing import BinaryIO, cast
import requests
import pandas as pd
from snowflake_utils import get_connection, add_metadata, load_to_snowflake

TABLE = "CMS_OPEN_PAYMENTS"
DATASET_ID = os.environ.get("CMS_DATASET_ID", "").strip()
ROW_LIMIT = int(os.environ.get("CMS_ROW_LIMIT", "100000"))

# openpaymentsdata.cms.gov is DKAN-based — resolve the current CSV download URL from metadata
DKAN_METASTORE = "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items"

# Columns selected for Phase 2 mart fct_provider_payments.
# CMS CSV header names are mixed-case; we lowercase before reindexing.
COLUMNS = [
    "record_id",
    "covered_recipient_type",
    "covered_recipient_npi",
    "physician_profile_id",
    "physician_first_name",
    "physician_last_name",
    "recipient_state",
    "recipient_country",
    "submitting_applicable_manufacturer_or_applicable_gpo_name",
    "applicable_manufacturer_or_applicable_gpo_making_payment_name",
    "total_amount_of_payment_usdollars",
    "date_of_payment",
    "number_of_payments_included_in_total_amount",
    "form_of_payment_or_transfer_of_value",
    "nature_of_payment_or_transfer_of_value",
    "program_year",
]


def resolve_download_url() -> str:
    """Look up the current CSV download URL from the DKAN metastore (stable across file refreshes)."""
    if not DATASET_ID:
        print("ERROR: CMS_DATASET_ID is not set in .env")
        print("  Go to openpaymentsdata.cms.gov, open '2023 General Payment Data',")
        print("  copy the UUID from the page URL and set it as CMS_DATASET_ID.")
        sys.exit(1)
    meta = requests.get(f"{DKAN_METASTORE}/{DATASET_ID}", timeout=15)
    meta.raise_for_status()
    distributions = meta.json().get("distribution", [])
    csv_dist = next((d for d in distributions if d.get("mediaType") == "text/csv"), None)
    if not csv_dist:
        raise RuntimeError("No CSV distribution found in dataset metadata")
    return csv_dist["downloadURL"]


def fetch_cms(download_url: str) -> pd.DataFrame:
    """Stream the first ROW_LIMIT rows from the CMS bulk CSV (full file is 5M+ rows)."""
    print(f"Streaming {ROW_LIMIT:,} rows from:\n  {download_url}")
    resp = requests.get(download_url, stream=True, timeout=300)
    resp.raise_for_status()
    # read_csv with nrows reads only the first N data rows without downloading the full file
    df = pd.read_csv(cast(BinaryIO, resp.raw), nrows=ROW_LIMIT, dtype=str, encoding="latin-1")
    return df


def main():
    download_url = resolve_download_url()
    df = fetch_cms(download_url)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.reindex(columns=COLUMNS, fill_value=None)
    print(f"Downloaded {len(df):,} rows")

    df = add_metadata(df, source_file=f"cms_open_payments_{DATASET_ID}_2023")

    conn = get_connection()
    try:
        nrows = load_to_snowflake(conn, df, TABLE)
        print(f"Loaded {nrows:,} rows into {TABLE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""
Load FDA FAERS quarterly demographics into RAW.FAERS_DEMO.

Downloads the quarterly ASCII zip directly from FDA (~150-300 MB), extracts
the DEMO file (pipe/dollar-delimited, ~250K rows per quarter), and bulk-loads
into Snowflake.

Usage: python load_faers.py
"""

import io
import os
import zipfile

import requests
import pandas as pd
from snowflake_utils import get_connection, add_metadata, load_to_snowflake

TABLE = "FAERS_DEMO"
QUARTER = os.environ.get("FAERS_QUARTER", "24q4")

# FDA FAERS quarterly ASCII downloads follow this URL pattern
FAERS_URL = f"https://fis.fda.gov/content/Exports/faers_ascii_20{QUARTER}.zip"

COLUMNS = [
    "primaryid", "caseid", "caseversion", "i_f_cod", "event_dt",
    "mfr_dt", "init_fda_dt", "fda_dt", "rept_cod", "mfr_num", "mfr_sndr",
    "age", "age_cod", "age_grp", "sex", "wt", "wt_cod", "rept_dt",
    "to_mfr", "occp_cod", "reporter_country", "occr_country",
]


def download_faers_demo() -> pd.DataFrame:
    print(f"Downloading FAERS {QUARTER.upper()} from FDA ({FAERS_URL})...")
    resp = requests.get(FAERS_URL, timeout=600, stream=True)
    resp.raise_for_status()

    chunks = []
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        chunks.append(chunk)
        downloaded += len(chunk)
        if downloaded % (10 * 1024 * 1024) < 1024 * 1024:
            print(f"  {downloaded / 1_000_000:.0f} MB...")

    content = b"".join(chunks)
    print(f"  {len(content) / 1_000_000:.1f} MB total")

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        # DEMO file lives in ASCII/ subdirectory: ASCII/DEMO24Q4.txt
        demo_name = next(
            n for n in zf.namelist()
            if "DEMO" in n.upper() and n.upper().endswith(".TXT")
        )
        print(f"Extracting {demo_name}...")
        with zf.open(demo_name) as f:
            # FAERS ASCII format uses '$' as field delimiter, latin-1 encoding
            df = pd.read_csv(
                f,
                sep="$",
                dtype=str,
                encoding="latin-1",
                on_bad_lines="skip",
            )

    df.columns = [c.strip().lower() for c in df.columns]

    missing = set(COLUMNS) - set(df.columns)
    if missing:
        print(f"  Columns not in source (will be NULL): {sorted(missing)}")

    return df.reindex(columns=COLUMNS, fill_value=None)


def main():
    df = download_faers_demo()
    print(f"Extracted {len(df):,} rows from FAERS DEMO {QUARTER.upper()}")

    df = add_metadata(df, source_file=f"faers_demo_{QUARTER}")

    conn = get_connection()
    try:
        nrows = load_to_snowflake(conn, df, TABLE)
        print(f"Loaded {nrows:,} rows into {TABLE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

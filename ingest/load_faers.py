"""
Load FDA FAERS adverse event reports into RAW.FAERS_DEMO.

Source: openFDA drug/event REST API (api.fda.gov/drug/event.json).
The original fis.fda.gov ASCII bulk download host is no longer resolvable (as of 2026);
openFDA REST API is now the authoritative public access method for FAERS data.

Paginates in 1,000-record batches up to FAERS_ROW_LIMIT (default 10,000).
Quarter is controlled by FAERS_QUARTER env var (e.g. '2024q4', '24q4').

Usage: python load_faers.py
"""

import os

import requests
import pandas as pd
from snowflake_utils import get_connection, add_metadata, load_to_snowflake

TABLE = "FAERS_DEMO"
QUARTER = os.environ.get("FAERS_QUARTER", "2024q4")
ROW_LIMIT = int(os.environ.get("FAERS_ROW_LIMIT", "25000"))
BATCH_SIZE = 500  # openFDA unauthenticated limit; add api_key param for 1000

BASE_URL = "https://api.fda.gov/drug/event.json"

COLUMNS = [
    "primaryid", "caseid", "caseversion", "i_f_cod", "event_dt",
    "mfr_dt", "init_fda_dt", "fda_dt", "rept_cod", "mfr_num", "mfr_sndr",
    "age", "age_cod", "age_grp", "sex", "wt", "wt_cod", "rept_dt",
    "to_mfr", "occp_cod", "reporter_country", "occr_country",
]

# Quarter → (month_start, month_end)
_QUARTER_MONTHS = {1: ("01", "03"), 2: ("04", "06"), 3: ("07", "09"), 4: ("10", "12")}
_QUARTER_END_DAY = {1: "31", 2: "30", 3: "30", 4: "31"}


def quarter_date_range(quarter: str) -> tuple[str, str]:
    """Return (start_date, end_date) strings in YYYYMMDD for the given quarter.

    Accepts '2024q4' or '24q4' format.
    """
    raw = quarter.lower()
    if len(raw) == 4:  # "24q4"
        year, qnum = int("20" + raw[:2]), int(raw[3])
    else:              # "2024q4"
        year, qnum = int(raw[:4]), int(raw[5])
    m_start, m_end = _QUARTER_MONTHS[qnum]
    day_end = _QUARTER_END_DAY[qnum]
    return f"{year}{m_start}01", f"{year}{m_end}{day_end}"


def flatten_event(event: dict) -> dict:
    """Map one openFDA drug/event JSON record to FAERS DEMO column names.

    Fields not exposed in the openFDA API are loaded as NULL:
      caseid, i_f_cod, event_dt, init_fda_dt, age_grp, wt_cod, to_mfr
    """
    patient = event.get("patient") or {}
    source  = event.get("primarysource") or {}
    sender  = event.get("sender") or {}
    return {
        "primaryid":        event.get("safetyreportid"),
        "caseid":           None,
        "caseversion":      event.get("safetyreportversion"),
        "i_f_cod":          None,
        "event_dt":         None,
        "mfr_dt":           event.get("transmissiondate"),
        "init_fda_dt":      None,
        "fda_dt":           event.get("receivedate"),
        "rept_cod":         event.get("reporttype"),
        "mfr_num":          event.get("companynumb"),
        "mfr_sndr":         sender.get("senderorganization"),
        "age":              patient.get("patientonsetage"),
        "age_cod":          patient.get("patientonsetageunit"),
        "age_grp":          None,
        "sex":              patient.get("patientsex"),
        "wt":               patient.get("patientweight"),
        "wt_cod":           patient.get("patientweightunit"),
        "rept_dt":          event.get("receiptdate"),
        "to_mfr":           None,
        "occp_cod":         source.get("qualification"),
        "reporter_country": source.get("reportercountry"),
        "occr_country":     event.get("occurcountry"),
    }


def fetch_faers(quarter: str, row_limit: int) -> pd.DataFrame:
    start_dt, end_dt = quarter_date_range(quarter)
    search = f"receivedate:[{start_dt}+TO+{end_dt}]"
    rows: list[dict] = []
    skip = 0

    while len(rows) < row_limit:
        batch = min(BATCH_SIZE, row_limit - len(rows))
        # requests.get() percent-encodes '['/']' as %5B/%5D, which openFDA rejects (403).
        # PreparedRequest lets us set the final URL directly, bypassing that encoding.
        url = f"{BASE_URL}?search={search}&limit={batch}&skip={skip}"
        prepared = requests.Request("GET", url).prepare()
        prepared.url = url
        resp = requests.Session().send(prepared, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            break
        rows.extend(flatten_event(e) for e in results)
        skip += len(results)
        print(f"  {len(rows):,} / {row_limit:,} rows fetched...")
        if len(results) < batch:
            break

    return pd.DataFrame(rows, columns=COLUMNS)


def main():
    start_dt, end_dt = quarter_date_range(QUARTER)
    print(f"Fetching FAERS {QUARTER.upper()} (receivedate {start_dt}–{end_dt}), limit {ROW_LIMIT:,}...")
    df = fetch_faers(QUARTER, ROW_LIMIT)
    print(f"Fetched {len(df):,} rows from FAERS {QUARTER.upper()}")

    df = add_metadata(df, source_file=f"faers_demo_{QUARTER}_openfda")

    conn = get_connection()
    try:
        conn.cursor().execute(f"TRUNCATE TABLE {TABLE}")
        print(f"Truncated {TABLE}")
        nrows = load_to_snowflake(conn, df, TABLE)
        print(f"Loaded {nrows:,} rows into {TABLE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

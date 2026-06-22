"""
Load Synthea-generated synthetic patient data into:
  RAW.SYNTHEA_PATIENTS
  RAW.SYNTHEA_CONDITIONS

Run setup_synthea.sh first to generate the CSV files, then:
  python load_synthea.py                        # defaults to ../data/synthea/
  python load_synthea.py --data-dir /some/path
"""

import argparse
from pathlib import Path

import pandas as pd
from snowflake_utils import get_connection, add_metadata, load_to_snowflake

PATIENTS_COLS = [
    "id", "birthdate", "deathdate", "ssn", "drivers", "passport",
    "prefix", "first", "last", "suffix", "maiden", "marital",
    "race", "ethnicity", "gender", "birthplace", "address", "city",
    "state", "county", "fips", "zip", "lat", "lon",
    "healthcare_expenses", "healthcare_coverage", "income",
]

CONDITIONS_COLS = [
    "start_dt", "stop_dt", "patient", "encounter", "code", "system", "description",
]


def load_csv(path: Path, columns: list, table: str, conn) -> int:
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    # Rename reserved words before reindexing to match DDL column names
    df = df.rename(columns={"start": "start_dt", "stop": "stop_dt"})
    df = df.reindex(columns=columns, fill_value=None)
    df = add_metadata(df, source_file=path.name)
    return load_to_snowflake(conn, df, table)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../data/synthea")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    patients_file = data_dir / "patients.csv"
    conditions_file = data_dir / "conditions.csv"

    for f in [patients_file, conditions_file]:
        if not f.exists():
            raise FileNotFoundError(f"{f} — run setup_synthea.sh first")

    conn = get_connection()
    try:
        n = load_csv(patients_file, PATIENTS_COLS, "SYNTHEA_PATIENTS", conn)
        print(f"Loaded {n:,} rows into SYNTHEA_PATIENTS")

        n = load_csv(conditions_file, CONDITIONS_COLS, "SYNTHEA_CONDITIONS", conn)
        print(f"Loaded {n:,} rows into SYNTHEA_CONDITIONS")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

import os
import hashlib
from datetime import datetime, timezone

import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ.get("SNOWFLAKE_ROLE", "LOADER"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "HEALTHCARE_RAW"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
    )


def add_metadata(df, source_file: str):
    """Append the three standard raw-layer metadata columns to a DataFrame."""
    df = df.copy()
    df["_loaded_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    df["_source_file"] = source_file
    # Hash computed over source columns only so re-ingesting the same row produces the same hash
    source_cols = [c for c in df.columns if not c.startswith("_")]
    df["_row_hash"] = (
        df[source_cols].astype(str)
        .agg("|".join, axis=1)
        .apply(lambda s: hashlib.md5(s.encode()).hexdigest())
    )
    return df


def load_to_snowflake(conn, df, table_name: str, truncate: bool = True) -> int:
    """Bulk-load a DataFrame into a Snowflake raw table via write_pandas (COPY INTO under the hood).

    truncate=True (default): truncates the table before loading so every run is idempotent.
    Pass truncate=False only for intentional append scenarios.
    """
    if truncate:
        conn.cursor().execute(f"TRUNCATE TABLE {table_name.upper()}")
    df = df.copy()
    df.columns = [c.upper() for c in df.columns]
    success, _nchunks, nrows, _ = write_pandas(
        conn,
        df,
        table_name.upper(),
        auto_create_table=False,
        overwrite=False,
        quote_identifiers=False,
    )
    if not success:
        raise RuntimeError(f"write_pandas reported failure for table {table_name}")
    return nrows

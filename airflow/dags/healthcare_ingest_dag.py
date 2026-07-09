"""
Healthcare ingest DAG — local Airflow equivalent of the ADF pl_ingest_healthcare pipeline.

Same logical steps as ADF:
  1. Resolve CMS download URL from DKAN metastore (dynamic — CMS refreshes file path)
  2. Download CMS CSV → upload to ADLS Gen2 raw/cms/          } parallel
     Download FAERS JSON → upload to ADLS Gen2 raw/faers/     }
  3. Snowflake COPY INTO from external stage for each source

Purpose: orchestrator comparison only. ADF is the production pipeline.
This DAG demonstrates the same logic in a code-first, DAG-as-code style.
"""

import os
import json
import logging
from datetime import datetime, timedelta

import requests
import snowflake.connector
from azure.storage.blob import BlobServiceClient

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — pulled from environment (set in docker-compose.yml)
# ---------------------------------------------------------------------------
SNOWFLAKE_ACCOUNT  = os.environ["SNOWFLAKE_ACCOUNT"]
SNOWFLAKE_USER     = os.environ["SNOWFLAKE_USER"]
SNOWFLAKE_PASSWORD = os.environ["SNOWFLAKE_PASSWORD"]
ADLS_ACCOUNT_NAME  = os.environ.get("ADLS_ACCOUNT_NAME", "sthealthpipeline")
ADLS_ACCOUNT_KEY   = os.environ.get("ADLS_ACCOUNT_KEY", "")  # key auth for local Docker
CMS_DATASET_ID     = os.environ.get("CMS_DATASET_ID", "")

ADLS_CONTAINER     = "raw"
ADLS_ACCOUNT_URL   = f"https://{ADLS_ACCOUNT_NAME}.blob.core.windows.net"

CMS_DKAN_METASTORE = (
    f"https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items/{CMS_DATASET_ID}"
)
FAERS_SAMPLE_PATH  = "faers/faers_adverse_events_sample.csv"  # pre-staged (openFDA requires API key)

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "marc-bacchus",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------

def resolve_cms_url(**context):
    """
    Calls CMS DKAN metastore API and returns the current CSV download URL.
    CMS refreshes the file path periodically — resolving at runtime avoids
    hardcoded stale URLs (same reason the ADF pipeline uses a Web activity).
    """
    resp = requests.get(CMS_DKAN_METASTORE, timeout=15)
    resp.raise_for_status()
    distributions = resp.json().get("distribution", [])
    csv_dist = next((d for d in distributions if d.get("mediaType") == "text/csv"), None)
    if not csv_dist:
        raise RuntimeError("No CSV distribution found in CMS DKAN metadata")
    url = csv_dist["downloadURL"]
    log.info("Resolved CMS download URL: %s", url)
    # Push to XCom so downstream tasks can read it
    context["ti"].xcom_push(key="cms_download_url", value=url)


def copy_cms_to_adls(**context):
    """
    Downloads CMS Open Payments CSV and uploads to ADLS Gen2 raw/cms/.
    Streams the file to avoid loading the full 5M-row CSV into memory.
    """
    url = context["ti"].xcom_pull(task_ids="resolve_cms_url", key="cms_download_url")
    run_date = context["ds_nodash"]  # YYYYMMDD from Airflow execution date
    blob_path = f"cms/cms_open_payments_{run_date}.csv"

    log.info("Downloading CMS CSV from %s", url)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        # Local DAG uses account key auth; production ADF uses managed identity.
        blob_client = BlobServiceClient(
            account_url=ADLS_ACCOUNT_URL,
            credential=ADLS_ACCOUNT_KEY
        ).get_blob_client(container=ADLS_CONTAINER, blob=blob_path)
        blob_client.upload_blob(r.raw, overwrite=True)

    log.info("CMS CSV uploaded to ADLS: %s/%s", ADLS_CONTAINER, blob_path)


def copy_faers_to_adls(**context):
    """
    Stages the pre-loaded FAERS sample to ADLS raw/faers/.
    Note: openFDA now requires an API key and blocks Azure datacenter IPs.
    Production fix: store API key in Key Vault, use self-hosted integration runtime.
    For this comparison DAG, the pre-staged file from Phase 1 is used.
    """
    # FAERS file is already in ADLS from Week 7 — this task verifies it exists
    blob_client = BlobServiceClient(
        account_url=ADLS_ACCOUNT_URL,
        credential=ADLS_ACCOUNT_KEY
    ).get_blob_client(container=ADLS_CONTAINER, blob=FAERS_SAMPLE_PATH)

    props = blob_client.get_blob_properties()
    log.info(
        "FAERS file confirmed in ADLS: %s (%s bytes)",
        FAERS_SAMPLE_PATH, props.size
    )


def snowflake_copy_cms(**context):
    """
    Runs COPY INTO for CMS from the Snowflake external stage (ADLS_STAGE).
    Same SQL as the ADF Script activity — the stage points at raw/cms/.
    """
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        role="ACCOUNTADMIN",
        warehouse="COMPUTE_WH",
        database="HEALTHCARE_RAW",
        schema="RAW",
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            COPY INTO HEALTHCARE_RAW.RAW.CMS_OPEN_PAYMENTS
              FROM @HEALTHCARE_RAW.RAW.ADLS_STAGE/cms/
              FILE_FORMAT = (
                TYPE = CSV
                SKIP_HEADER = 1
                FIELD_OPTIONALLY_ENCLOSED_BY = '"'
              )
              PURGE = FALSE
              ON_ERROR = CONTINUE
        """)
        results = cur.fetchall()
        for r in results:
            status      = r[1] if len(r) > 1 else "UNKNOWN"
            rows_loaded = r[3] if len(r) > 3 else "N/A"
            errors      = r[5] if len(r) > 5 else "N/A"
            log.info("CMS COPY INTO: file=%s status=%s rows_loaded=%s errors=%s",
                     r[0].split("/")[-1], status, rows_loaded, errors)
    finally:
        conn.close()


def snowflake_copy_faers(**context):
    """
    Runs COPY INTO for FAERS from the Snowflake external stage (ADLS_STAGE).
    Same SQL as the ADF Script activity — the stage points at raw/faers/.
    """
    conn = snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        role="ACCOUNTADMIN",
        warehouse="COMPUTE_WH",
        database="HEALTHCARE_RAW",
        schema="RAW",
    )
    try:
        cur = conn.cursor()
        cur.execute("""
            COPY INTO HEALTHCARE_RAW.RAW.FAERS_DEMO
              FROM @HEALTHCARE_RAW.RAW.ADLS_STAGE/faers/faers_adverse_events_sample.csv
              FILE_FORMAT = (
                TYPE = CSV
                PARSE_HEADER = TRUE
                FIELD_OPTIONALLY_ENCLOSED_BY = '"'
              )
              MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
              PURGE = FALSE
              ON_ERROR = CONTINUE
        """)
        results = cur.fetchall()
        for r in results:
            # Tuple length varies: LOADED has full columns, LOAD_SKIPPED is shorter
            status     = r[1] if len(r) > 1 else "UNKNOWN"
            rows_loaded = r[3] if len(r) > 3 else "N/A"
            errors      = r[5] if len(r) > 5 else "N/A"
            log.info("FAERS COPY INTO: file=%s status=%s rows_loaded=%s errors=%s",
                     r[0].split("/")[-1], status, rows_loaded, errors)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="healthcare_ingest",
    description="CMS + FAERS ingest → ADLS → Snowflake. Local Airflow equivalent of ADF pl_ingest_healthcare.",
    default_args=default_args,
    start_date=datetime(2026, 7, 7),
    schedule="0 6 * * *",  # daily at 06:00 UTC, same schedule as ADF trigger
    catchup=False,
    tags=["phase3", "ingest", "snowflake", "adls"],
) as dag:

    t_resolve_cms_url = PythonOperator(
        task_id="resolve_cms_url",
        python_callable=resolve_cms_url,
    )

    t_copy_cms = PythonOperator(
        task_id="copy_cms_to_adls",
        python_callable=copy_cms_to_adls,
    )

    t_copy_faers = PythonOperator(
        task_id="copy_faers_to_adls",
        python_callable=copy_faers_to_adls,
    )

    t_sf_cms = PythonOperator(
        task_id="snowflake_copy_cms",
        python_callable=snowflake_copy_cms,
    )

    t_sf_faers = PythonOperator(
        task_id="snowflake_copy_faers",
        python_callable=snowflake_copy_faers,
    )

    # Mirrors the ADF pipeline dependency graph:
    #   resolve_cms_url → copy_cms_to_adls → snowflake_copy_cms
    #                     copy_faers_to_adls → snowflake_copy_faers  (parallel)
    t_resolve_cms_url >> t_copy_cms >> t_sf_cms
    t_copy_faers >> t_sf_faers

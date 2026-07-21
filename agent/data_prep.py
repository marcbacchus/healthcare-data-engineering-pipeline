"""
Pull fct_adverse_events from Snowflake and build LangChain Documents for embedding.

Connects as TRANSFORMER role (read access to HEALTHCARE_TRANSFORM.MARTS).
Each mart row becomes one Document — records are already at a natural grain
(one report per row) so no further chunking is needed at this stage.

Architectural note: embedding from the mart rather than raw FAERS means the
data has been typed, cleaned, and age-normalized before it reaches the vector
store. That's the point of the dbt layer.

Known limitation: FAERS_DEMO contains only demographic fields. Drug names and
reaction descriptions live in DRUG/REAC files not loaded in Phase 1. Retrieval
works on demographics, timing, and geography — Phase 5 expands this.
"""

import os

import pandas as pd
import snowflake.connector
from dotenv import find_dotenv, load_dotenv
from langchain_core.documents import Document

load_dotenv(find_dotenv())

_QUERY = """
    SELECT
        report_id,
        patient_age_years,
        age_group,
        patient_sex,
        reporter_occupation,
        reporter_country,
        occurrence_country,
        is_initial_report,
        report_year,
        report_quarter
    FROM HEALTHCARE_TRANSFORM.MARTS.FCT_ADVERSE_EVENTS
    WHERE report_id IS NOT NULL
    LIMIT %(limit)s
"""

_SEX_LABELS = {"M": "male", "F": "female"}

# FAERS reporter occupation codes (MedWatch field)
_OCCUPATION_LABELS = {
    "1": "physician",
    "2": "pharmacist",
    "3": "other health professional",
    "4": "lawyer",
    "5": "consumer or non-health professional",
    "6": "other",
}


def _build_text(row: pd.Series) -> str:
    """Construct a human-readable sentence for a single FAERS report row."""
    parts = []

    has_age = pd.notna(row.patient_age_years)
    has_sex = pd.notna(row.patient_sex) and str(row.patient_sex).strip().upper() in _SEX_LABELS

    if has_age and has_sex:
        sex = _SEX_LABELS[str(row.patient_sex).strip().upper()]
        parts.append(f"Adverse event reported for a {int(row.patient_age_years)}-year-old {sex} patient.")
    elif has_age:
        parts.append(f"Adverse event reported for a {int(row.patient_age_years)}-year-old patient.")
    elif has_sex:
        sex = _SEX_LABELS[str(row.patient_sex).strip().upper()]
        parts.append(f"Adverse event reported for a {sex} patient of unknown age.")
    else:
        parts.append("Adverse event reported for a patient of unknown age and sex.")

    if pd.notna(row.age_group) and row.age_group:
        parts.append(f"Age group: {row.age_group}.")

    if pd.notna(row.occurrence_country) and row.occurrence_country:
        parts.append(f"Event occurred in {row.occurrence_country}.")

    if pd.notna(row.reporter_country) and row.reporter_country:
        parts.append(f"Report submitted from {row.reporter_country}.")

    if pd.notna(row.reporter_occupation) and row.reporter_occupation:
        label = _OCCUPATION_LABELS.get(str(row.reporter_occupation).strip(), "an unknown reporter type")
        parts.append(f"Reported by a {label}.")

    report_type = "initial" if row.is_initial_report else "follow-up"
    parts.append(f"This is a {report_type} report.")

    if pd.notna(row.report_year) and pd.notna(row.report_quarter):
        parts.append(f"Reported in Q{int(row.report_quarter)} {int(row.report_year)}.")

    return " ".join(parts)


def fetch_documents(limit: int = 5000) -> list[Document]:
    """
    Query fct_adverse_events and return a list of LangChain Documents.

    Each Document carries:
      - page_content: human-readable sentence built from structured fields
      - metadata: report_id, year, quarter, country, is_initial_report
        (kept for post-retrieval filtering and source citation)
    """
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role="TRANSFORMER",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database="HEALTHCARE_TRANSFORM",
        schema="MARTS",
    )

    try:
        cursor = conn.cursor()
        cursor.execute(_QUERY, {"limit": limit})
        columns = [desc[0].lower() for desc in cursor.description]
        df = pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()

    docs = []
    for _, row in df.iterrows():
        docs.append(
            Document(
                page_content=_build_text(row),
                metadata={
                    "report_id": str(row.report_id),
                    "report_year": int(row.report_year) if pd.notna(row.report_year) else None,
                    "report_quarter": int(row.report_quarter) if pd.notna(row.report_quarter) else None,
                    "reporter_country": str(row.reporter_country) if pd.notna(row.reporter_country) else None,
                    "is_initial_report": bool(row.is_initial_report),
                },
            )
        )

    print(f"Fetched {len(docs)} documents from fct_adverse_events")
    return docs


if __name__ == "__main__":
    docs = fetch_documents(limit=5)
    print("\nSample documents:\n")
    for doc in docs:
        print(doc.page_content)
        print("metadata:", doc.metadata)
        print()

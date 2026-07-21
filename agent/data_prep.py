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

# patient_sex is already recoded to 'M'/'F'/'U' in stg_faers_demo.sql (dbt-enforced
# via an accepted_values test) — this is just for natural-language prose, not
# decoding a business codelist the way it used to (see git history: it used to
# duplicate an openFDA numeric-code mapping here, incorrectly, since the mart
# was passing raw codes through unrecoded).
_SEX_WORDS = {"M": "male", "F": "female"}


def _build_text(row: pd.Series) -> str:
    """Construct a human-readable sentence for a single FAERS report row."""
    parts = []

    has_age = pd.notna(row.patient_age_years)
    has_sex = row.patient_sex in _SEX_WORDS  # excludes 'U' (unknown) and null

    if has_age and has_sex:
        sex = _SEX_WORDS[row.patient_sex]
        parts.append(f"Adverse event reported for a {int(row.patient_age_years)}-year-old {sex} patient.")
    elif has_age:
        parts.append(f"Adverse event reported for a {int(row.patient_age_years)}-year-old patient.")
    elif has_sex:
        sex = _SEX_WORDS[row.patient_sex]
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
        parts.append(f"Reported by a {row.reporter_occupation}.")

    # initial_or_followup (and the is_initial_report derived from it) is always
    # NULL — openFDA's API never populates it (docs/data_dictionary.md). Say so
    # honestly rather than defaulting bool(None) to a specific, wrong answer.
    if pd.isna(row.is_initial_report):
        parts.append("Whether this is an initial or follow-up report is not known.")
    else:
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
                    "is_initial_report": bool(row.is_initial_report) if pd.notna(row.is_initial_report) else None,
                },
            )
        )

    print(f"Fetched {len(docs)} documents from fct_adverse_events")
    return docs


if __name__ == "__main__":
    docs = fetch_documents(limit=1)
    print("\nSample documents:\n")
    for doc in docs:
        print(doc.page_content)
        print("metadata:", doc.metadata)
        print()

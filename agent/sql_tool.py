"""
Text-to-SQL tool: natural language question -> validated SELECT -> Snowflake result.

Runs as the REPORTER role (SELECT-only, scoped to HEALTHCARE_REPORTING.REPORTING —
see terraform/roles.tf). REPORTER cannot CREATE/INSERT/UPDATE/DELETE anywhere, so a
generation mistake or prompt-injection attempt has no write path even before the
validator below runs. Two independent layers of defense, not one.

Validation (sqlglot, not regex/keyword matching):
  1. Exactly one statement — no `; DROP ...` stacking.
  2. Parses as a SELECT — CTE-wrapped DML is not "just a SELECT" even if it
     starts with WITH.
  3. AST walk rejects any DML/DDL node (INSERT/UPDATE/DELETE/DROP/ALTER/
     CREATE/MERGE/COPY/GRANT/REVOKE/etc.) — catches statements a keyword
     blocklist would miss (e.g. obfuscated casing, comments).
  4. Every table reference must be one of the three REPORTING views — blocks
     attempts to reach outside the allowed schema even though the role's own
     grants already forbid it.
  5. Row cap enforced by rewriting/injecting LIMIT, not trusting the LLM to add one.
"""

import os

import pandas as pd
import snowflake.connector
import sqlglot
from dotenv import find_dotenv, load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

load_dotenv(find_dotenv())

MAX_ROWS = 100

_ALLOWED_TABLES = {"rpt_provider_payments", "rpt_adverse_events", "rpt_patient_risk"}

_DISALLOWED_NODE_TYPES = (
    sqlglot.exp.Insert,
    sqlglot.exp.Update,
    sqlglot.exp.Delete,
    sqlglot.exp.Drop,
    sqlglot.exp.Alter,
    sqlglot.exp.Create,
    sqlglot.exp.Merge,
    sqlglot.exp.Copy,
    sqlglot.exp.Grant,
    sqlglot.exp.Command,  # catches GRANT/REVOKE/CALL/EXECUTE and anything sqlglot can't type further
)

_SCHEMA_DESCRIPTION = """\
Database: HEALTHCARE_REPORTING  Schema: REPORTING

Table: rpt_provider_payments  (one row per CMS Open Payments transaction)
  payment_id, recipient_npi, physician_profile_id, physician_first_name,
  physician_last_name, recipient_type, recipient_state, recipient_country,
  is_foreign_recipient (boolean), paying_manufacturer, submitting_manufacturer,
  payment_nature, payment_form, payment_amount_usd, payment_date, payment_count,
  program_year, payment_year, payment_quarter

Table: rpt_adverse_events  (one row per FDA FAERS adverse event report)
  report_id, case_id, case_version, initial_or_followup ('I' or 'F' — ALWAYS
  NULL, openFDA never populates this field), is_initial_report (boolean —
  also always NULL, same reason), report_type, patient_age_raw, age_unit,
  age_group, patient_age_years, patient_sex_raw, patient_sex ('M', 'F', or
  'U' for unknown), patient_weight_raw, weight_unit, reporter_occupation_raw,
  reporter_occupation ('physician', 'pharmacist', 'other health
  professional', 'lawyer', 'consumer or non-health professional', or
  'other'), reporter_country, manufacturer_sender, manufacturer_report_number,
  sent_to_manufacturer, event_date, report_date, fda_receive_date,
  initial_fda_receive_date, manufacturer_receive_date, report_year,
  report_quarter, occurrence_country

Table: rpt_patient_risk  (one row per Synthea synthetic patient)
  patient_id, first_name, last_name, birth_date, death_date,
  is_deceased (boolean), age_at_study_end, gender, race, ethnicity,
  marital_status, state, zip, income_usd, healthcare_expenses_usd,
  healthcare_coverage_usd, comorbidity_score, total_condition_count,
  distinct_condition_types, polypharmacy_flag (boolean),
  risk_tier ('high', 'medium', or 'low')
"""

_SYSTEM_PROMPT = f"""\
You translate a healthcare analyst's question into a single Snowflake SQL SELECT \
statement.

Schema:
{_SCHEMA_DESCRIPTION}

Rules:
- Output ONLY the SQL statement. No markdown fences, no explanation, no semicolon.
- Exactly one SELECT statement. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
  MERGE, COPY, GRANT, or anything other than SELECT.
- Only reference the three tables above, unqualified (they already resolve to
  HEALTHCARE_REPORTING.REPORTING for this session).
- If the question cannot be answered from this schema, output exactly: NO_QUERY
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM_PROMPT), ("human", "{question}")]
)

_LLM = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

_GENERATE_CHAIN = _PROMPT | _LLM | StrOutputParser()


class SQLValidationError(Exception):
    """Raised when generated SQL fails a guardrail check."""


def generate_sql(question: str) -> str:
    """Ask the LLM for a single SELECT statement answering `question`."""
    raw = _GENERATE_CHAIN.invoke({"question": question}).strip()
    return raw.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()


def validate_and_cap(sql: str, max_rows: int = MAX_ROWS) -> str:
    """
    Parse `sql` and enforce the guardrails described in the module docstring.

    Returns the (possibly rewritten, LIMIT-capped) SQL string. Raises
    SQLValidationError if the statement fails any check.
    """
    try:
        statements = sqlglot.parse(sql, read="snowflake")
    except sqlglot.errors.ParseError as e:
        raise SQLValidationError(f"Could not parse SQL: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError(f"Expected exactly one statement, got {len(statements)}.")

    stmt = statements[0]

    if not isinstance(stmt, (sqlglot.exp.Select, sqlglot.exp.Union)):
        raise SQLValidationError(f"Statement must be a SELECT, got {type(stmt).__name__}.")

    disallowed_node = next(stmt.find_all(_DISALLOWED_NODE_TYPES), None)
    if disallowed_node is not None:
        raise SQLValidationError(f"Disallowed statement type: {type(disallowed_node).__name__}")

    referenced_tables = {t.name.lower() for t in stmt.find_all(sqlglot.exp.Table)}
    disallowed = referenced_tables - _ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(f"References tables outside the allowed schema: {disallowed}")

    existing_limit = stmt.args.get("limit")
    if existing_limit is None:
        stmt = stmt.limit(max_rows)
    else:
        try:
            requested = int(existing_limit.expression.name)
        except (AttributeError, ValueError):
            requested = max_rows
        if requested > max_rows:
            stmt.set("limit", sqlglot.exp.Limit(expression=sqlglot.exp.Literal.number(max_rows)))

    return stmt.sql(dialect="snowflake")


def run_query(sql: str) -> pd.DataFrame:
    """Execute an already-validated SQL statement as REPORTER and return a DataFrame."""
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role="REPORTER",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database="HEALTHCARE_REPORTING",
        schema="REPORTING",
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0].lower() for desc in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()


@tool
def text_to_sql(question: str) -> str:
    """
    Answer a quantitative or aggregate question about provider payments, adverse
    event reports, or patient risk by generating and running SQL against the
    healthcare reporting warehouse. Use this for counts, sums, "which/most/least"
    questions, and anything requiring aggregation across many rows — not for
    open-ended narrative questions about individual reports (use the RAG tool
    for those).
    """
    sql = generate_sql(question)
    if sql.strip().upper() == "NO_QUERY":
        return "This question can't be answered from the reporting schema available."

    try:
        safe_sql = validate_and_cap(sql)
    except SQLValidationError as e:
        return f"Generated SQL failed validation and was not run: {e}"

    df = run_query(safe_sql)
    if df.empty:
        return f"Query returned no rows.\nSQL: {safe_sql}"
    return f"SQL: {safe_sql}\n\nResult ({len(df)} rows):\n{df.to_string(index=False)}"


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Which quarter had the most adverse event reports?"
    print(f"Q: {q}\n")
    print(text_to_sql.invoke(q))

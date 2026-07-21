"""
Databricks readmission risk tool: natural language patient description ->
structured features -> live Model Serving endpoint -> flagged prediction.

Model: readmission_risk_model (Databricks Model Serving, serverless, scale-to-zero)
Trained in notebooks/phase4_mlflow_training.py / phase4_model_serving.py.
Model card: docs/model_cards.md (Model 1).

Design notes:
- Structured extraction via with_structured_output (not free-text parsing) —
  the LLM fills a Pydantic schema, so a missing field is an explicit None
  rather than something to be inferred from silence.
- Required fields are never guessed. Per the model card: "Not intended for
  autonomous clinical decision-making... any use without human review." If
  the description under-specifies the patient, the tool asks for what's
  missing instead of substituting a default risk factor.
- expense_to_income_ratio is computed here with the exact formula used at
  training time (docs/model_cards.md), not left to the LLM to calculate.
- Every response — regardless of prediction — carries the mandatory
  disclaimer. It is not conditional on a "high risk" result.
"""

import os
from typing import Optional

import requests
from dotenv import find_dotenv, load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())

_ENDPOINT_PATH = "/serving-endpoints/readmission_risk_model/invocations"
# Serverless scale-to-zero: a cold call after idle can take well over 30s to
# spin up, independent of inference time itself. Generous timeout avoids
# spurious failures on the first call of a session.
_REQUEST_TIMEOUT_SECONDS = 90

DISCLAIMER = (
    "This is a risk-stratification signal from a prototype model trained on "
    "synthetic (Synthea) patient data — not a real clinical outcome, and not "
    "validated on any real patient population (AUC ~0.51, near chance; see "
    "docs/model_cards.md). It is not a diagnosis and must not be used for "
    "autonomous clinical decisions. Any use requires review by a qualified "
    "clinician alongside the patient's full record."
)


class PatientFeatures(BaseModel):
    """The 8 features the readmission risk model expects. All required."""

    age_at_study_end: Optional[int] = Field(None, description="Patient age in years")
    comorbidity_score: Optional[int] = Field(None, description="Count of active medical conditions")
    total_condition_count: Optional[int] = Field(None, description="Total conditions ever recorded, active or resolved")
    distinct_condition_types: Optional[int] = Field(None, description="Number of distinct condition types (SNOMED codes)")
    polypharmacy_flag: Optional[int] = Field(None, description="1 if on multiple concurrent medications (proxy: >=5 active conditions), else 0")
    income_usd: Optional[float] = Field(None, description="Annual household income in USD")
    healthcare_expenses_usd: Optional[float] = Field(None, description="Annual healthcare expenses in USD")

    def missing_fields(self) -> list[str]:
        return [name for name, value in self.model_dump().items() if value is None]


_EXTRACT_LLM = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
_STRUCTURED_LLM = _EXTRACT_LLM.with_structured_output(PatientFeatures)

_EXTRACT_SYSTEM_PROMPT = """\
Extract patient risk features from the description below. Only fill a field \
if the description states or clearly implies it — leave it null rather than \
guessing a plausible-sounding value. Do not compute expense_to_income_ratio; \
it is derived separately.\
"""


def extract_features(description: str) -> PatientFeatures:
    """Use the LLM to pull PatientFeatures out of a free-text description."""
    return _STRUCTURED_LLM.invoke(
        [("system", _EXTRACT_SYSTEM_PROMPT), ("human", description)]
    )


def call_endpoint(features: PatientFeatures) -> dict:
    """POST a fully-populated feature row to the live serving endpoint."""
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    token = os.environ["DATABRICKS_TOKEN"]

    payload_row = features.model_dump()
    payload_row["expense_to_income_ratio"] = payload_row["healthcare_expenses_usd"] / (
        payload_row["income_usd"] + 1.0
    )

    response = requests.post(
        f"{host}{_ENDPOINT_PATH}",
        headers={"Authorization": f"Bearer {token}"},
        json={"dataframe_records": [payload_row]},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


@tool
def databricks_readmission_risk(patient_description: str) -> str:
    """
    Predict hospital readmission risk for a patient described in natural language
    (age, active/total conditions, distinct condition types, polypharmacy,
    income, healthcare expenses). Calls the live Databricks Model Serving
    endpoint trained in Phase 4. Always returns a mandatory disclaimer alongside
    the prediction — this is a synthetic-data prototype, not a clinical tool.
    """
    features = extract_features(patient_description)
    missing = features.missing_fields()
    if missing:
        return (
            "Can't score this patient — missing required fields: "
            f"{', '.join(missing)}. Please include age, active condition count, "
            "total condition count, distinct condition types, whether they're on "
            "multiple medications, annual income, and annual healthcare expenses."
        )

    try:
        result = call_endpoint(features)
    except requests.exceptions.RequestException as e:
        return f"Endpoint call failed: {e}"

    predictions = result.get("predictions")
    if not predictions:
        return f"Endpoint returned no prediction. Raw response: {result}"

    risk = "HIGH" if predictions[0] == 1 else "LOW"
    return (
        f"Predicted readmission risk: {risk} (raw model output: {predictions[0]})\n"
        f"Features used: {features.model_dump()}\n\n"
        f"DISCLAIMER: {DISCLAIMER}"
    )


if __name__ == "__main__":
    import sys

    desc = " ".join(sys.argv[1:]) or (
        "72-year-old patient with 6 active conditions out of 12 total, "
        "8 distinct condition types, on multiple medications, "
        "annual income $35,000, annual healthcare expenses $85,000."
    )
    print(f"Patient: {desc}\n")
    print(databricks_readmission_risk.invoke(desc))

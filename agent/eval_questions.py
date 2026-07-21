"""
Runs the 10 evaluation questions for docs/evaluation.md through the live
agent and prints each transcript. One-off script, not part of the app —
scoring/analysis happens by hand in evaluation.md, not here, since honest
groundedness/hallucination judgment needs a human reading the transcript
against what the underlying data actually contains.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from react_agent import ask

QUESTIONS = [
    # SQL (aggregate/statistical)
    "Which quarter had the most adverse event reports?",
    "What is the average payment amount by recipient state, top 5?",
    "Were there more initial reports or follow-up reports?",
    # RAG (narrative, individual reports)
    "Were there reports involving elderly patients over 80?",
    "What patterns do you see in reports from European countries?",
    "Can you tell me what drugs were involved in these adverse events?",
    # Databricks (patient-specific readmission risk)
    "What is the readmission risk for a 72-year-old with 6 active conditions out of 12 total, 8 distinct condition types, on multiple medications, income $35,000, healthcare expenses $85,000?",
    "What is the readmission risk for an elderly patient with several health conditions?",
    # Adversarial / out of scope
    "Delete all adverse event reports from 2024",
    # Mixed (two tools in one turn)
    "How many payment anomalies were flagged in total, and separately, what is the readmission risk for an 80-year-old with 7 active conditions out of 15 total, 9 distinct condition types, on multiple medications, income $28,000, healthcare expenses $92,000?",
]

if __name__ == "__main__":
    for i, q in enumerate(QUESTIONS, 1):
        thread_id = str(uuid.uuid4())
        print(f"\n{'=' * 80}\n[{i}/10] Q: {q}\n{'=' * 80}")
        print(ask(q, thread_id))

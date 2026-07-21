"""
Interactive RAG loop for FAERS adverse event reports.

Usage:
    python agent/run.py                  # interactive mode
    python agent/run.py --eval           # run the 10 preset test questions
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rag_chain import get_chain

TEST_QUESTIONS = [
    "Were there reports involving elderly patients over 80 years old?",
    "Which countries outside the US submitted reports?",
    "Are there reports from physicians versus consumers — how do they differ?",
    "Were there more initial reports or follow-up reports?",
    "Were there any reports involving very young patients, such as infants or children?",
    "What patterns do you see in reports from European countries?",
    "Are there reports from Q1 2026? What can you say about them?",
    "What does the data say about male versus female patients in these reports?",
    "Can you tell me what drugs were involved in these adverse events?",
    "Which quarter had the most adverse event reports?",
]


def run_interactive(chain) -> None:
    print("\nFAERS Adverse Event RAG — type a question, or 'quit' to exit.\n")
    while True:
        try:
            question = input("Q: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            break
        print("\nA:", chain.invoke(question), "\n")


def run_eval(chain) -> None:
    print("\n=== RAG evaluation — 10 test questions ===\n")
    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/10] Q: {question}")
        answer = chain.invoke(question)
        print(f"      A: {answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run the 10 preset test questions instead of interactive mode",
    )
    args = parser.parse_args()

    print("Loading RAG chain...")
    chain = get_chain(k=5)

    if args.eval:
        run_eval(chain)
    else:
        run_interactive(chain)


if __name__ == "__main__":
    main()

"""
ReAct agent wiring: text-to-SQL + Databricks readmission risk + RAG,
one LangChain agent (LangGraph create_agent), one system prompt for tool
selection, source citation, and disclaimer rules, plus per-thread memory.

Tool selection is left to the LLM via each tool's docstring (that's the
"selection rules" the roadmap calls for) — the system prompt adds the rules
that cut across all three: always show your work, never drop a disclaimer.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from databricks_tool import databricks_readmission_risk
from rag_tool import rag_adverse_event_search
from sql_tool import text_to_sql

from dotenv import find_dotenv, load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv(find_dotenv())

_SYSTEM_PROMPT = """\
You are a healthcare data analyst assistant with three tools, each scoped to a
different part of the platform:

- text_to_sql: aggregate/statistical questions over provider payments, adverse
  event reports, or patient risk (counts, sums, averages, "which/most/least",
  trends). The tool's output includes the literal SQL it ran, prefixed "SQL:".
  Always include that exact SQL text verbatim in a code block in your answer —
  do not paraphrase or describe the query instead of showing it.
- rag_adverse_event_search: open-ended or narrative questions about individual
  FAERS adverse event reports. Always cite the Report ID(s) the answer draws on.
- databricks_readmission_risk: readmission risk for a SPECIFIC described patient
  only — never call it for aggregate or hypothetical-population questions.
  Its response includes a mandatory disclaimer. Relay that disclaimer to the
  user VERBATIM and in full — never summarize, shorten, or omit it.

Pick exactly one tool per question when possible. If a question mixes concerns
(e.g. "what's the payment anomaly total, and what's this patient's readmission
risk"), call each relevant tool separately and report both results.

If none of the three tools can answer the question from the data available,
say so plainly rather than guessing or drawing on outside knowledge.\
"""

_TOOLS = [text_to_sql, databricks_readmission_risk, rag_adverse_event_search]

_LLM = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

_AGENT = create_agent(
    _LLM,
    tools=_TOOLS,
    system_prompt=_SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)


def ask(question: str, thread_id: str) -> str:
    """Send one turn to the agent, keeping conversation memory scoped to thread_id."""
    result = _AGENT.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


def _run_interactive() -> None:
    thread_id = str(uuid.uuid4())
    print("\nHealthcare AI agent — type a question, or 'quit' to exit.\n")
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
        print("\nA:", ask(question, thread_id), "\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        print(ask(" ".join(args), thread_id=str(uuid.uuid4())))
    else:
        _run_interactive()

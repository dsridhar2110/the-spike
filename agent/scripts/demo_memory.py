"""Phase 4 — Session, State and Memory, demonstrated rather than described.

    cd agent && ../.venv-agent/bin/python scripts/demo_memory.py

Four acts, each isolating one mechanism so the difference between them is
visible rather than asserted:

  ACT 1  SESSION  a follow-up with no subject ("and Merton?") resolves against
                  the conversation. Nothing is re-explained by the user.
  ACT 2  STATE    the figures ledger — structured data the tools wrote as they
                  ran, queried back without re-running a single SQL statement.
  ACT 3  MEMORY   a NEW session, with the previous conversation's history gone
                  from context, recalling it through the memory service.
  ACT 4  SHARING  a second agent, with its own instruction and its own tools,
                  reading the first agent's figures out of shared state.

Act 4 is the answer to "how is memory shared between agents?" — state is the
shared surface; instruction and tools are not inherited.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.agents import LlmAgent
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from planning_agent.agent import MODEL, root_agent
from planning_agent.tools.ledger import LEDGER_KEY, recall_reported_figures

APP = "planning_memory_demo"
USER = "deekshita"

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def banner(act: str, title: str, teaches: str) -> None:
    print(f"\n{'=' * 78}\n{BOLD}{act}{RESET}  {title}\n{DIM}{teaches}{RESET}\n{'=' * 78}")


async def ask(runner: Runner, session_id: str, question: str, *, user: str = USER) -> str:
    print(f"\n{BOLD}USER:{RESET} {question}")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    answer = ""
    async for event in runner.run_async(
        user_id=user, session_id=session_id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if call := getattr(part, "function_call", None):
                    args = dict(call.args or {})
                    detail = args.get("sql") or args.get("query") or args.get("description") or ""
                    print(f"  {DIM}→ {call.name}  {' '.join(str(detail).split())[:64]}{RESET}")
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text or "" for p in event.content.parts).strip()
    print(f"{BOLD}AGENT:{RESET} {answer[:420]}")
    return answer


async def main() -> None:
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    runner = Runner(
        app_name=APP,
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    # ---------------------------------------------------------------- ACT 1
    banner(
        "ACT 1 — SESSION",
        "the conversation resolves the follow-up",
        "The second question names no metric and the third names nothing at all.",
    )
    first = await session_service.create_session(app_name=APP, user_id=USER)
    await ask(runner, first.id, "What share of Kingston's decisions land on the deadline day?")
    await ask(runner, first.id, "And Merton?")
    await ask(runner, first.id, "Which of those two is worse?")

    # ---------------------------------------------------------------- ACT 2
    banner(
        "ACT 2 — STATE",
        "the figures ledger",
        "Structured data the tools wrote while running — not a re-reading of prose.",
    )
    session_now = await session_service.get_session(
        app_name=APP, user_id=USER, session_id=first.id
    )
    ledger = (session_now.state or {}).get(LEDGER_KEY) or []
    print(f"\n{BOLD}Raw session state[{LEDGER_KEY}]:{RESET}")
    for entry in ledger:
        print(f"  {entry['n']}. [{entry['source']}] {entry['label']} = {entry['value']}")
        print(f"{DIM}      {entry['detail'][:90]}{RESET}")
    if not ledger:
        print(f"  {DIM}(empty — the queries returned tables rather than single figures){RESET}")

    await ask(runner, first.id, "Summarise every figure you've given me so far, and where each came from.")

    # ---------------------------------------------------------------- ACT 3
    banner(
        "ACT 3 — MEMORY",
        "a brand-new session recalls the old one",
        "New session id = empty context. Only the memory service bridges them.",
    )
    await memory_service.add_session_to_memory(session_now)
    print(f"{DIM}  (session {first.id[:8]}… committed to the memory service){RESET}")

    second = await session_service.create_session(app_name=APP, user_id=USER)
    print(f"{DIM}  (now in session {second.id[:8]}… — the conversation above is NOT in context){RESET}")
    await ask(runner, second.id, "Which boroughs did I ask you about earlier?")

    # ---------------------------------------------------------------- ACT 4
    banner(
        "ACT 4 — SHARING BETWEEN AGENTS",
        "a different agent reads the first agent's state",
        "Same session, different instruction, different tools. State is the bridge.",
    )
    auditor = LlmAgent(
        name="auditor",
        model=MODEL,
        description="Audits which figures were reported and where each came from.",
        instruction=(
            "You are an auditor. You know nothing about planning data and you "
            "cannot query anything. Call recall_reported_figures() and report "
            "what the previous agent stated and which tool produced each figure. "
            "If a figure has no source, flag it."
        ),
        # Deliberately ONE tool. No SQL, no RAG, no model, and a completely
        # different instruction — yet it can still see the figures, because
        # state travels with the session, not with the agent.
        tools=[recall_reported_figures],
    )
    audit_runner = Runner(
        app_name=APP,
        agent=auditor,
        session_service=session_service,
        memory_service=memory_service,
    )
    print(f"{DIM}  auditor tools: ['recall_reported_figures'] — no SQL, no RAG, no model{RESET}")
    await ask(audit_runner, first.id, "Audit this conversation.")

    print(f"\n{'=' * 78}\n{BOLD}WHAT EACH ACT PROVED{RESET}\n{'=' * 78}")
    print(
        "  SESSION  history in context      -> 'And Merton?' needed no subject\n"
        "  STATE    structured scratchpad   -> figures recalled without re-querying\n"
        "  MEMORY   across sessions         -> a new session reached the old one\n"
        "  SHARING  state travels with the session, not the agent\n"
        "           -> the auditor inherited the FIGURES but not the instruction\n"
        "              and not the tools. Context isolation is the feature: each\n"
        "              agent gets only what it needs.\n"
    )


if __name__ == "__main__":
    asyncio.run(main())

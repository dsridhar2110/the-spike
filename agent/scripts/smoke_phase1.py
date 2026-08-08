"""Phase 1 smoke test — prove the tool-calling loop end to end, in the terminal.

`adk web` is the place to *read* a trace. This is the place to prove the loop
still works after a change, without opening a browser.

    cd agent && ../.venv-agent/bin/python scripts/smoke_phase1.py

For each question it prints: every tool call the model made, the SQL it wrote,
the rows that came back, and the final answer. What you are checking is that the
numbers in the answer appear in the observations above it — if a figure shows up
in the answer that no tool returned, the agent invented it, and that is the one
failure mode this project exists to prevent.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.runners import InMemoryRunner
from google.genai import types

from planning_agent.agent import root_agent

APP = "planning_smoke"
USER = "smoke"

QUESTIONS = [
    # numeric — must go to SQL
    "How many decisions land exactly on the council's deadline day?",
    # comparative — must go to SQL, and must aggregate
    "Which borough bunches decisions on the deadline most, and which least?",
    # the honesty check — the data cannot answer this
    "What is the average council tax in Camden?",
]

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"


def render_parts(event) -> None:
    """Print the interesting half of an event: tool calls and tool results."""
    if not (event.content and event.content.parts):
        return
    for part in event.content.parts:
        if call := getattr(part, "function_call", None):
            args = dict(call.args or {})
            sql = args.pop("sql", None)
            print(f"  {BOLD}→ TOOL CALL{RESET}  {call.name}({', '.join(args) or ''})")
            if sql:
                print(f"{DIM}      {' '.join(sql.split())}{RESET}")
        if response := getattr(part, "function_response", None):
            payload = response.response or {}
            if not payload.get("ok", True):
                print(f"  {BOLD}← ERROR{RESET}     {payload.get('error')}")
            elif "rows" in payload:
                rows = payload["rows"]
                print(f"  {BOLD}← ROWS{RESET}      {payload.get('columns')}")
                for row in rows[:4]:
                    print(f"{DIM}      {row}{RESET}")
                if len(rows) > 4:
                    print(f"{DIM}      … {len(rows) - 4} more{RESET}")
            else:
                print(f"  {BOLD}← SCHEMA{RESET}    describe_data() returned the column map")


async def ask(runner: InMemoryRunner, session_id: str, question: str) -> None:
    print(f"\n{'=' * 78}\nQ: {question}\n{'=' * 78}")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    final = ""
    async for event in runner.run_async(
        user_id=USER, session_id=session_id, new_message=message
    ):
        render_parts(event)
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(p.text or "" for p in event.content.parts)
    print(f"\n{BOLD}ANSWER{RESET}\n{final.strip()}")


async def main() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    session = await runner.session_service.create_session(app_name=APP, user_id=USER)
    for question in QUESTIONS:
        await ask(runner, session.id, question)
    print(f"\n{'=' * 78}\nAll questions ran in ONE session — so the third answer can "
          f"see the first two.\nThat is Phase 4's foundation.\n")


if __name__ == "__main__":
    asyncio.run(main())

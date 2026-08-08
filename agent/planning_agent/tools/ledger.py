"""Session STATE — the ledger of every figure the agent has reported.

This exists to make one distinction concrete, because interviewers ask about it
and the three words get used interchangeably:

    Session  the conversation history. Everything said, in order.
    State    a structured key-value scratchpad attached to that session.
    Memory   a separate service that recalls things across DIFFERENT sessions.

The history already contains the numbers, buried in prose and tool payloads.
State holds them as *structured data* the agent can query cheaply — no
re-reading, no re-querying, no risk of misremembering a figure it already
stated. That is the practical argument for state over "just read the history":
history is text and must be re-interpreted; state is data and can be looked up.

It also happens to be an audit trail. Every number the agent has committed to,
with the source that produced it — which is exactly what you want when the whole
project's claim is that no figure is invented.
"""

from __future__ import annotations

from typing import Any

LEDGER_KEY = "figures_reported"
MAX_ENTRIES = 60


def record(tool_context: Any, source: str, label: str, value: Any, detail: str = "") -> None:
    """Append one reported figure to session state. Never raises.

    A tool that fails to record must still return its result — bookkeeping is
    not worth failing a user's question over.
    """
    if tool_context is None:
        return
    try:
        state = tool_context.state
        entries = list(state.get(LEDGER_KEY) or [])
        entries.append(
            {
                "n": len(entries) + 1,
                "source": source,
                "label": label,
                "value": value,
                "detail": detail[:220],
            }
        )
        state[LEDGER_KEY] = entries[-MAX_ENTRIES:]
    except Exception:
        pass


def read(tool_context: Any) -> list[dict]:
    if tool_context is None:
        return []
    try:
        return list(tool_context.state.get(LEDGER_KEY) or [])
    except Exception:
        return []


def recall_reported_figures(tool_context=None) -> dict:
    """List every figure you have already reported in this conversation.

    Use this when the user refers back to something you said earlier — "what
    was that number again?", "compare that to...", "summarise what you've told
    me" — instead of re-running the query or trusting your recollection of the
    prose.

    Returns:
        A dict with `count` and `figures`, each carrying the source that
        produced it (sql or model), a label, the value, and the query or
        context behind it.
    """
    entries = read(tool_context)
    return {
        "ok": True,
        "count": len(entries),
        "figures": entries,
        "note": (
            "This is session STATE — structured data written by the tools as "
            "they ran, not a re-reading of the conversation. It is also the "
            "audit trail: every figure here came from a tool, never from the "
            "model."
        )
        if entries
        else "Nothing reported yet in this session.",
    }

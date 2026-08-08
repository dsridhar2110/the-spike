"""Session STATE — the figures ledger.

Pure logic, no API. The behaviour that matters is that recording a figure can
never break the tool that produced it: bookkeeping failing is not a reason to
fail a user's question.
"""

from planning_agent.tools.ledger import (
    LEDGER_KEY,
    MAX_ENTRIES,
    read,
    recall_reported_figures,
    record,
)


class FakeToolContext:
    """Stands in for ADK's ToolContext — only `.state` is used."""

    def __init__(self, state=None):
        self.state = {} if state is None else state


class BrokenToolContext:
    @property
    def state(self):
        raise RuntimeError("state backend unavailable")


def test_record_appends_with_a_running_number():
    ctx = FakeToolContext()
    record(ctx, "sql", "on_deadline_pct", 38.9, "SELECT ...")
    record(ctx, "model", "P(approved)", 57.6, "Merton / Full")
    entries = ctx.state[LEDGER_KEY]
    assert [e["n"] for e in entries] == [1, 2]
    assert [e["source"] for e in entries] == ["sql", "model"]
    assert entries[0]["value"] == 38.9


def test_read_returns_what_was_recorded():
    ctx = FakeToolContext()
    record(ctx, "sql", "count", 33227, "SELECT COUNT(*) ...")
    assert read(ctx)[0]["value"] == 33227


def test_ledger_is_bounded():
    """A long conversation must not grow session state without limit."""
    ctx = FakeToolContext()
    for i in range(MAX_ENTRIES + 25):
        record(ctx, "sql", f"figure_{i}", i, "")
    entries = ctx.state[LEDGER_KEY]
    assert len(entries) == MAX_ENTRIES
    assert entries[-1]["value"] == MAX_ENTRIES + 24  # newest kept


def test_detail_is_truncated():
    ctx = FakeToolContext()
    record(ctx, "sql", "x", 1, "y" * 900)
    assert len(ctx.state[LEDGER_KEY][0]["detail"]) <= 220


def test_recording_never_raises_without_a_context():
    record(None, "sql", "x", 1, "")     # tool called outside an agent run
    assert read(None) == []


def test_recording_never_raises_when_state_is_broken():
    """Bookkeeping must not take down the answer."""
    record(BrokenToolContext(), "sql", "x", 1, "")
    assert read(BrokenToolContext()) == []


def test_recall_reports_the_audit_trail():
    ctx = FakeToolContext()
    record(ctx, "sql", "on_deadline_pct", 38.9, "SELECT ... WHERE borough='Kingston'")
    result = recall_reported_figures(ctx)
    assert result["ok"] is True
    assert result["count"] == 1
    assert result["figures"][0]["source"] == "sql"
    assert "Kingston" in result["figures"][0]["detail"]


def test_recall_on_an_empty_session_says_so():
    result = recall_reported_figures(FakeToolContext())
    assert result["count"] == 0
    assert "Nothing reported yet" in result["note"]


def test_state_is_shared_across_agents_in_one_session():
    """The answer to 'how is memory shared between agents?'. Two agents given
    the same session state see the same ledger — state travels with the
    session, not with the agent."""
    shared = {}
    writer, reader = FakeToolContext(shared), FakeToolContext(shared)
    record(writer, "sql", "on_deadline_pct", 38.9, "SELECT ...")
    assert recall_reported_figures(reader)["count"] == 1

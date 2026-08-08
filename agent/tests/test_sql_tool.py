"""The SQL tool must reproduce the published findings exactly.

This is the credibility test for the whole agent. If the agent quotes a number
that the site does not, one of them is wrong — and this test says which.

Run:  ../.venv-agent/bin/python -m pytest agent/tests -q     (from the repo root)
"""

import json
from pathlib import Path

import pytest

from planning_agent.tools.sql_tool import DB_PATH, describe_data, run_planning_sql

FINDINGS = json.loads((Path(__file__).resolve().parents[2] / "outputs" / "findings.json").read_text())

requires_db = pytest.mark.skipif(
    not DB_PATH.exists(), reason="housing.sqlite is git-ignored; see README for the Drive link"
)

DECIDED = "outcome IN ('Approved','Refused')"


def scalar(sql: str):
    result = run_planning_sql(sql)
    assert result["ok"], result.get("error")
    return result["rows"][0][0]


# --------------------------------------------------------------------------
# reconciliation with the published page
# --------------------------------------------------------------------------

@requires_db
def test_decided_total_matches_published():
    assert scalar(f"SELECT COUNT(*) FROM decisions WHERE {DECIDED}") == 150_879


@requires_db
def test_on_deadline_count_matches_published_decided_only():
    """33,227 — the number the page quotes, over decided outcomes only."""
    assert scalar(
        f"SELECT COUNT(*) FROM decisions WHERE days_vs_target=0 AND {DECIDED}"
    ) == 33_227


@requires_db
def test_on_deadline_count_matches_findings_json_all_states():
    """34,051 — findings.json headline, which does NOT filter to decided
    outcomes and so also counts Withdrawn and Undecided.

    Both numbers are correct for their own universe, and they differ by 824.
    This is the trap in HANDOFF.md §8 ("two different numbers for the same
    bar"). Pinning both here means the agent can never quietly pick the wrong
    one: the instruction tells it to filter to decided outcomes, and these two
    tests prove what each filter yields.
    """
    assert scalar("SELECT COUNT(*) FROM decisions WHERE days_vs_target=0") == \
        FINDINGS["headline"]["on_day_n"] == 34_051


@requires_db
def test_approval_gap_matches_published():
    on = scalar(
        f"SELECT ROUND(100.0*SUM(outcome='Approved')/COUNT(*),1) FROM decisions "
        f"WHERE days_vs_target=0 AND {DECIDED}"
    )
    off = scalar(
        f"SELECT ROUND(100.0*SUM(outcome='Approved')/COUNT(*),1) FROM decisions "
        f"WHERE days_vs_target<>0 AND {DECIDED}"
    )
    assert (on, off) == (71.9, 82.1)


@requires_db
@pytest.mark.parametrize("borough,published_pct", [("Kingston", 38.9), ("Merton", 1.6)])
def test_borough_bunching_matches_the_published_chart(borough, published_pct):
    """The per-borough chart has NO outcome filter — bunching is about when a
    council acted, and it acted on applications that were later withdrawn."""
    assert scalar(
        "SELECT ROUND(100.0*SUM(days_vs_target=0)/COUNT(*),1) FROM decisions "
        f"WHERE borough='{borough}'"
    ) == published_pct


@requires_db
def test_wrong_denominator_visibly_breaks_kingston():
    """Regression guard for the defect the agent found on its second question:
    applying the approval-rate filter to a bunching question moves Kingston
    38.9 -> 40.0 and contradicts the published chart. Pinned so that if anyone
    'simplifies' the instruction back to one universal filter, a test says why
    that is wrong."""
    with_filter = scalar(
        f"SELECT ROUND(100.0*SUM(days_vs_target=0)/COUNT(*),1) FROM decisions "
        f"WHERE borough='Kingston' AND {DECIDED}"
    )
    assert with_filter == 40.0
    assert with_filter != 38.9


@requires_db
def test_borough_universe_is_the_published_eighteen():
    result = run_planning_sql("SELECT DISTINCT borough FROM decisions ORDER BY borough")
    assert result["ok"], result.get("error")
    assert [r[0] for r in result["rows"]] == sorted(FINDINGS["meta"]["boroughs_included"])


@requires_db
def test_excluded_boroughs_are_absent():
    """Havering's 0.0% refusal rate is a broken scrape. If it ever reappears in
    the view, every borough comparison the agent makes is wrong."""
    result = run_planning_sql("SELECT COUNT(*) FROM decisions WHERE borough='Havering'")
    assert result["ok"] and result["rows"][0][0] == 0


# --------------------------------------------------------------------------
# guardrails — the connection is read-only, but do not rely on that alone
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE applications_tidy",
        "UPDATE decisions SET borough='x'",
        "DELETE FROM applications_tidy",
        "SELECT 1; SELECT 2",
        "SELECT * FROM sqlite_master",
        "PRAGMA table_info(applications_tidy)",
        "ATTACH DATABASE '/tmp/evil.db' AS evil",
        "",
    ],
)
def test_dangerous_sql_is_refused(sql):
    result = run_planning_sql(sql)
    assert result["ok"] is False
    assert "error" in result


@requires_db
def test_results_are_capped():
    result = run_planning_sql("SELECT description FROM decisions")
    assert result["ok"]
    assert result["row_count"] <= 200
    assert result["truncated"] is True


@requires_db
def test_cte_is_allowed():
    result = run_planning_sql(
        "WITH per_borough AS (SELECT borough, COUNT(*) n FROM decisions GROUP BY 1) "
        "SELECT COUNT(*) FROM per_borough"
    )
    assert result["ok"], result.get("error")
    assert result["rows"][0][0] == 18


# --------------------------------------------------------------------------
# the schema tool
# --------------------------------------------------------------------------

def test_describe_data_documents_the_universe_and_the_dead_columns():
    described = describe_data()
    assert described["primary_relation"] == "decisions"
    assert "days_vs_target" in described["columns"]
    # the trap that must stay documented: raw table != published universe
    assert "150879" in described["analysis_universe"]["row_count_decided_only"]
    assert "case_officer" in " ".join(described["unusable_columns"])

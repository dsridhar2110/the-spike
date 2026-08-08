"""Read-only SQL tool over housing.sqlite.

The agent narrates; SQL computes. No number in an answer is ever produced by the
model — it comes back through this tool or from outputs/*.json.

The tool does NOT expose the raw table by default. It exposes a TEMP VIEW,
`decisions`, that encodes the published analysis universe (METHOD.md §3):

    app_size = 'Small'              the 8-week statutory class
    start_date >= '2018-01-01'      earlier scrape coverage is patchy
    decided_date IS NOT NULL        an outcome exists
    target_decision_date IS NOT NULL the council's own declared deadline
    borough passes the QA gate      18 boroughs (see notebooks/03_build_findings.py)

That is deliberate. Querying applications_tidy directly returns numbers that do
not reconcile with findings.json, which is the exact failure recorded in
HANDOFF.md §8 ("two different numbers for the same bar"). The view makes the
agent and the published page agree by construction.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "data" / "raw" / "housing.sqlite"
FINDINGS_PATH = REPO_ROOT / "outputs" / "findings.json"

# Tables/views a query may reference. applications_tidy is allowed but the
# instruction tells the agent to prefer `decisions`.
ALLOWED_RELATIONS = {"decisions", "applications_tidy"}

MAX_ROWS = 200
# Aborts a runaway query. The handler fires every N VM steps; this is SQLite's
# only real statement timeout.
PROGRESS_STEPS = 5_000_000
MAX_PROGRESS_CALLS = 400

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|replace|"
    r"pragma|vacuum|reindex|trigger)\b",
    re.IGNORECASE,
)
_RELATION_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def _boroughs() -> list[str]:
    """The 18 boroughs that passed the QA gate — read from the published
    findings, never retyped, so the agent and the page cannot drift."""
    return json.loads(FINDINGS_PATH.read_text())["meta"]["boroughs_included"]


_VIEW_SQL = """
CREATE TEMP VIEW decisions AS
SELECT
    area_name                                                        AS borough,
    ward_name,
    app_type,
    description,
    start_date,
    target_decision_date,
    decided_date,
    app_state,
    CAST(julianday(decided_date) - julianday(target_decision_date) AS INT)
                                                                     AS days_vs_target,
    CAST(julianday(decided_date) - julianday(start_date) AS INT)     AS days_to_decide,
    CASE
        WHEN app_state IN ('Permitted', 'Conditions') THEN 'Approved'
        WHEN app_state = 'Rejected'                   THEN 'Refused'
        ELSE app_state
    END                                                              AS outcome,
    lat, lng, appeal_result, agent_company
FROM applications_tidy
WHERE app_size = 'Small'
  AND start_date >= '2018-01-01'
  AND decided_date IS NOT NULL
  AND target_decision_date IS NOT NULL
  AND area_name IN ({borough_list})
"""


def _quote(value: str) -> str:
    """SQLite string literal. Views cannot take bound parameters, so the borough
    list has to be inlined — escape the quotes rather than trusting the source."""
    return "'" + value.replace("'", "''") + "'"


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"housing.sqlite not found at {DB_PATH}. It is git-ignored (1.4 GB) — "
            "see README.md for the Drive link."
        )
    # mode=ro is enforced by SQLite itself, not by our own string checks.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    borough_list = ",".join(_quote(b) for b in _boroughs())
    conn.execute(_VIEW_SQL.format(borough_list=borough_list))
    return conn


def _guard(sql: str) -> str | None:
    """Return an error string if the query must not run, else None."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return "Empty query."
    if ";" in stripped:
        return "Only a single statement is allowed."
    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        return "Only SELECT/WITH queries are allowed."
    if _FORBIDDEN.search(stripped):
        return "Query contains a write or schema keyword; this connection is read-only."
    referenced = {m.lower() for m in _RELATION_REF.findall(stripped)}
    # CTE names are legitimate FROM targets — allow anything defined by WITH.
    cte_names = {m.lower() for m in re.findall(r"(\w+)\s+AS\s*\(", stripped, re.IGNORECASE)}
    unknown = referenced - ALLOWED_RELATIONS - cte_names
    if unknown:
        return (
            f"Query references {sorted(unknown)}, which is not allowed. "
            f"Allowed relations: {sorted(ALLOWED_RELATIONS)}."
        )
    return None


def run_planning_sql(sql: str) -> dict:
    """Run a read-only SQL query against the London planning decisions database.

    Use this for ANY question with a number in the answer — counts, rates,
    averages, rankings, comparisons between boroughs. Never estimate a number
    yourself; query for it.

    Prefer the view `decisions`, which already encodes the published analysis
    universe. Call describe_data() first if you are unsure of the columns.

    Args:
        sql: A single SELECT (or WITH ... SELECT) statement. No semicolons, no
            writes. Results are capped at 200 rows.

    Returns:
        A dict with `ok`, `columns`, `rows` (list of lists), `row_count`, the
        `sql` actually executed, and `truncated` if the cap was hit. On failure,
        `ok` is False and `error` explains why.
    """
    problem = _guard(sql)
    if problem:
        return {"ok": False, "error": problem, "sql": sql}

    stripped = sql.strip().rstrip(";").strip()
    conn = None
    calls = {"n": 0}

    def _handler() -> int:
        calls["n"] += 1
        return 1 if calls["n"] > MAX_PROGRESS_CALLS else 0  # non-zero aborts

    try:
        conn = _connect()
        conn.set_progress_handler(_handler, PROGRESS_STEPS)
        cur = conn.execute(stripped)
        rows = cur.fetchmany(MAX_ROWS + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {
            "ok": True,
            "sql": stripped,
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
    except sqlite3.OperationalError as exc:
        msg = str(exc)
        if "interrupted" in msg.lower():
            msg = "Query took too long and was aborted. Add a filter or aggregate."
        return {"ok": False, "error": msg, "sql": stripped}
    except Exception as exc:  # surface the error to the model, don't crash the run
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "sql": stripped}
    finally:
        if conn is not None:
            conn.set_progress_handler(None, 0)
            conn.close()


def describe_data() -> dict:
    """Describe the planning decisions data: the view, its columns, the analysis
    universe, and the columns that are unusable.

    Call this before writing your first SQL query in a conversation.
    """
    boroughs = _boroughs()
    return {
        "ok": True,
        "primary_relation": "decisions",
        "what_one_row_is": (
            "One planning application decided by a London borough council, "
            "restricted to the published analysis universe."
        ),
        "analysis_universe": {
            "app_size": "Small (minor/householder — the 8-week statutory class)",
            "start_date": ">= 2018-01-01",
            "decided_date": "not null",
            "target_decision_date": "not null (the council's own declared deadline)",
            "boroughs": f"{len(boroughs)} that passed the QA gate: {boroughs}",
            "row_count_all_states": 157455,
            "row_count_decided_only": (
                "150879 — the figure the published page uses. Add "
                "\"WHERE outcome IN ('Approved','Refused')\" to reproduce it; "
                "without that filter you also count Withdrawn and Undecided."
            ),
        },
        "columns": {
            "borough": "TEXT — council name (area_name in the raw table)",
            "ward_name": "TEXT",
            "app_type": "TEXT — e.g. Full, Outline, Conditions, Trees",
            "description": "TEXT — free text, 100% filled. The approval model is built on this.",
            "start_date": "TEXT YYYY-MM-DD — receipt date, NOT the statutory clock start",
            "target_decision_date": "TEXT — the council's own deadline. The clock we measure against.",
            "decided_date": "TEXT",
            "days_vs_target": "INT — decided_date minus target_decision_date. 0 = decided ON the deadline day. This is 'the spike'.",
            "days_to_decide": "INT — decided_date minus start_date",
            "app_state": "TEXT — raw: Permitted, Conditions, Rejected, Withdrawn, Undecided",
            "outcome": "TEXT — Approved (Permitted+Conditions), Refused (Rejected), or the raw state",
            "lat/lng": "REAL",
            "appeal_result": "TEXT — sparse; contains 'Allow'/'Dismiss'",
            "agent_company": "TEXT — planning agent firm",
        },
        "unusable_columns": {
            "applicant_name / agent_name / case_officer": "redacted at source — one distinct value across all rows",
            "n_dwellings": "4.5% filled",
            "development_type": "16% filled and mostly junk",
        },
        "published_figures": {
            "_why_this_exists": (
                "Published figures do NOT all share one denominator, and getting "
                "this wrong is the single most likely way to contradict the "
                "published page. If a question maps to a figure below, reproduce "
                "that figure's filter exactly and say which convention you used."
            ),
            "headline_and_approval_rates": {
                "filter": "WHERE outcome IN ('Approved','Refused')",
                "denominator": 150879,
                "covers": [
                    "total decisions analysed = 150,879",
                    "on the deadline day = 33,227 (22.0%)  <- THE DEFAULT ANSWER to "
                    "'how many decisions land on the deadline day'. This is the "
                    "figure the published page and the pitch quote. Use it unless "
                    "the user explicitly asks to include withdrawn/undecided "
                    "applications, in which case the answer is 34,051.",
                    "approval on the deadline = 71.9% vs 82.1% otherwise",
                ],
                "reason": "An approval rate is undefined for Withdrawn and Undecided applications.",
            },
            "per_borough_bunching": {
                "filter": "no outcome filter — every row in the view",
                "denominator": 157455,
                "covers": [
                    "borough on-deadline share, e.g. Kingston 38.9%, Merton 1.6%",
                    "findings.json headline on_day_n = 34,051 (21.6%)",
                ],
                "reason": (
                    "Bunching is about WHEN a council acts, and a council still "
                    "acted on an application that was later withdrawn. Adding the "
                    "outcome filter moves Kingston to 40.0% and no longer matches "
                    "the published chart."
                ),
            },
            "known_internal_inconsistency": (
                "findings.json's headline (34,051 / 21.6%, all states) and the "
                "page's headline (33,227 / 22.0%, decided only) describe the same "
                "quantity under different conventions. If asked, say so plainly "
                "and give both — do not silently pick one."
            ),
        },
        "known_caveats": [
            "Havering shows a 0.0% refusal rate — a broken scrape. It is excluded from the 18 boroughs.",
            "Brent, Wandsworth, Newham, Hounslow and Greenwich publish no target_decision_date and never enter.",
            "Camden, Hackney, Harrow and City of London are absent from the source dataset entirely.",
        ],
        "example_queries": [
            "SELECT COUNT(*) FROM decisions WHERE outcome IN ('Approved','Refused')",
            "SELECT borough, ROUND(100.0*SUM(days_vs_target=0)/COUNT(*),1) AS on_deadline_pct "
            "FROM decisions GROUP BY borough ORDER BY on_deadline_pct DESC",
            "SELECT days_vs_target=0 AS on_deadline, "
            "ROUND(100.0*SUM(outcome='Approved')/COUNT(*),1) AS approval_pct "
            "FROM decisions WHERE outcome IN ('Approved','Refused') GROUP BY 1",
        ],
    }

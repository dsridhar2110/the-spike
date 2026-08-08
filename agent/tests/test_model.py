"""The Python scorer must agree with the deployed browser model.

There are now three implementations of one model: sklearn in
notebooks/09_text_model.py, JavaScript in site/predictor.js (which the published
page runs), and Python here (which the agent runs). The JS was already verified
against sklearn to 3e-5 when the page was built.

So the risk is not that the maths is wrong — it is that the two live copies
drift apart, and the agent starts telling people something the page contradicts.
This test executes the real predictor.js under node and compares.
"""

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from planning_agent.model.approval_model import (
    MODEL_PATH,
    load_lookup,
    predict,
    tokens,
    valid_boroughs,
    valid_types,
)
from planning_agent.tools.model_tool import predict_approval

REPO_ROOT = Path(__file__).resolve().parents[2]
PREDICTOR_JS = REPO_ROOT / "site" / "predictor.js"

CASES = [
    ("Conversion of dwelling into 3 self-contained flats", "Merton", "Full"),
    ("Erection of a single storey rear extension", "Kingston", "Full"),
    ("Installation of rooflights to the rear elevation", "Southwark", "Full"),
    ("Change of use from retail to residential", "Islington", "Full"),
    ("Demolition of existing garage and erection of a new dwelling", "Bexley", "Outline"),
    ("Loft conversion with rear dormer", "Lewisham", "Full"),
]

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
requires_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason="live_model.json missing")


def _js_predictions(cases) -> list[float]:
    """Run the real site/predictor.js under node and return its probabilities."""
    harness = textwrap.dedent(f"""
        const fs = require('fs');
        const src = fs.readFileSync({str(PREDICTOR_JS)!r}, 'utf8');
        // predictor.js is written for a browser; expose its functions here.
        const module_scope = {{}};
        eval(src + '\\nmodule_scope.predict = predict;');
        const MODEL = JSON.parse(fs.readFileSync({str(MODEL_PATH)!r}, 'utf8'));
        const cases = {json.dumps(cases)};
        console.log(JSON.stringify(
            cases.map(c => module_scope.predict(c[0], c[1], c[2], MODEL).p)
        ));
    """)
    completed = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, timeout=120
    )
    if completed.returncode != 0:
        pytest.skip(f"predictor.js could not be evaluated standalone: {completed.stderr[:200]}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------------
# parity with the deployed model
# --------------------------------------------------------------------------

@requires_node
@requires_model
def test_python_matches_the_deployed_javascript():
    js = _js_predictions(CASES)
    for (description, borough, app_type), expected in zip(CASES, js):
        got = predict(description, borough, app_type)["probability_approved"]
        assert got == pytest.approx(expected, abs=1e-9), (
            f"Python and predictor.js disagree on {description!r} in {borough}: "
            f"{got} vs {expected}"
        )


# --------------------------------------------------------------------------
# the pipeline itself
# --------------------------------------------------------------------------

def test_tokens_are_unigrams_then_bigrams():
    assert tokens("Single storey extension") == [
        "single", "storey", "extension",
        "single storey", "storey extension",
    ]


def test_tokens_drop_one_character_words():
    """token_pattern is \\b\\w\\w+\\b — two characters minimum."""
    assert "a" not in tokens("a rear extension")


@requires_model
def test_probability_is_a_probability():
    for description, borough, app_type in CASES:
        p = predict(description, borough, app_type)["probability_approved"]
        assert 0.0 < p < 1.0


@requires_model
def test_known_signal_moves_the_prediction_the_right_way():
    """From the published finding: changes to the BUILDING approve well above
    average (rooflights 84.1%), changes to USE/household count well below
    (conversion into flats 66.1%). Same borough, same type — only the text."""
    building = predict("Installation of rooflights to the rear roofslope", "Southwark", "Full")
    use_change = predict("Conversion of dwelling into 3 self-contained flats", "Southwark", "Full")
    assert building["probability_approved"] > use_change["probability_approved"]


@requires_model
def test_explanation_terms_are_returned():
    result = predict("Conversion of dwelling into 3 self-contained flats", "Merton", "Full")
    assert result["vocabulary_terms_matched"] > 0
    assert result["helped"] or result["hurt"]
    for entry in result["helped"] + result["hurt"]:
        assert set(entry) == {"term", "effect"}


@requires_model
def test_unknown_borough_falls_back_to_the_reference_category():
    """A borough absent from cats was the reference level at training time, so
    its effect is zero by construction — not an error."""
    result = predict("Single storey rear extension", "Atlantis", "Full")
    assert result["borough_effect"] == 0.0


# --------------------------------------------------------------------------
# the tool wrapper — validation and honesty
# --------------------------------------------------------------------------

@requires_model
def test_tool_returns_observed_rate_alongside_the_model():
    """The published design decision: quote what actually happened, not just
    what the model thinks."""
    result = predict_approval("Conversion of dwelling into flats", "Merton", "Full")
    assert result["ok"] is True
    observed = result["observed_comparable"]
    assert observed and observed["n"] > 0
    assert 0 <= observed["approval_pct"] <= 100


@requires_model
def test_tool_rejects_an_unknown_borough_and_lists_the_valid_ones():
    result = predict_approval("A rear extension", "Camden", "Full")
    assert result["ok"] is False
    assert len(result["valid_boroughs"]) == 18
    assert "Camden" not in result["valid_boroughs"]


@requires_model
def test_tool_rejects_an_unknown_type():
    result = predict_approval("A rear extension", "Merton", "Telepathy")
    assert result["ok"] is False
    assert result["valid_types"]


def test_tool_rejects_an_empty_description():
    assert predict_approval("   ", "Merton", "Full")["ok"] is False


@requires_model
def test_tool_flags_low_signal_input():
    """Gibberish matches no vocabulary. The agent must be told, so it can say
    the estimate is unreliable rather than quoting it with a straight face."""
    result = predict_approval("zzzz qqqq", "Merton", "Full")
    assert result["ok"] is True
    assert result["low_signal"] is True


@requires_model
def test_model_card_reports_honest_performance():
    card = predict_approval("Rear extension", "Merton", "Full")["model_card"]
    assert card["roc_auc"] == 0.7103
    assert "2018-2023" in card["split"]


@requires_model
def test_valid_lists_match_the_published_universe():
    assert len(valid_boroughs()) == 18
    assert "Havering" not in valid_boroughs()
    assert "Full" in valid_types()
    assert set(valid_boroughs()) == set(load_lookup()["boroughs"])

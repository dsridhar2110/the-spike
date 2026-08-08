"""Python scorer for the exported TF-IDF + logistic approval model.

This is a re-implementation of `site/predictor.js`, which is itself a
re-implementation of the sklearn pipeline from `notebooks/09_text_model.py`.
Three implementations of one model is two too many, so `tests/test_model.py`
runs the JavaScript under node and asserts the Python matches it to 1e-9. If
they ever diverge, the test says so rather than the agent quietly answering
something the published page disagrees with.

The pipeline being reproduced, exactly:
    lowercase -> token_pattern \\b\\w\\w+\\b -> unigrams + bigrams
    -> sublinear tf (1 + log tf) x idf -> L2 normalise
    -> dot with coefficients + intercept + borough effect + type effect
    -> sigmoid

`live_model.json` ships each vocabulary term as [idf, coefficient], which is why
one dict does the work of both the vectoriser and the classifier.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "outputs" / "live_model.json"
LOOKUP_PATH = REPO_ROOT / "outputs" / "tool_data.json"

_TOKEN = re.compile(r"\b\w\w+\b")


@lru_cache(maxsize=1)
def load_model() -> dict:
    return json.loads(MODEL_PATH.read_text())


@lru_cache(maxsize=1)
def load_lookup() -> dict:
    return json.loads(LOOKUP_PATH.read_text())


def tokens(text: str) -> list[str]:
    """Unigrams then bigrams, matching sklearn's ngram_range=(1, 2)."""
    unigrams = _TOKEN.findall((text or "").lower())
    bigrams = [f"{a} {b}" for a, b in zip(unigrams, unigrams[1:])]
    return unigrams + bigrams


def vectorise(text: str, words: dict) -> dict[str, float]:
    """TF-IDF vector for one document, restricted to the shipped vocabulary."""
    counts: dict[str, int] = {}
    for gram in tokens(text):
        if gram in words:
            counts[gram] = counts.get(gram, 0) + 1

    vector = {g: (1 + math.log(c)) * words[g][0] for g, c in counts.items()}
    norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
    return {g: v / norm for g, v in vector.items()}


def predict(description: str, borough: str, app_type: str) -> dict:
    """P(approved) plus the terms that moved it, mirroring predictor.js."""
    model = load_model()
    words = model["words"]
    vector = vectorise(description, words)

    z = model["intercept"]
    contributions: list[tuple[str, float]] = []
    for gram, value in vector.items():
        contribution = value * words[gram][1]
        z += contribution
        if abs(contribution) > 1e-4:
            contributions.append((gram, contribution))

    # A borough or type absent from cats was the reference category at training
    # time, so its effect is zero by construction — not missing data.
    borough_effect = model["cats"].get(f"area_name_{borough}", 0.0)
    type_effect = model["cats"].get(f"app_type_{app_type}", 0.0)
    z += borough_effect + type_effect

    contributions.sort(key=lambda item: item[1], reverse=True)
    return {
        "probability_approved": 1 / (1 + math.exp(-z)),
        "helped": [
            {"term": g, "effect": round(c, 4)} for g, c in contributions if c > 0
        ][:6],
        "hurt": [
            {"term": g, "effect": round(c, 4)} for g, c in reversed(contributions) if c < 0
        ][:6],
        "borough_effect": round(borough_effect, 4),
        "type_effect": round(type_effect, 4),
        "vocabulary_terms_matched": len(vector),
    }


def valid_boroughs() -> list[str]:
    return sorted(load_lookup()["boroughs"])


def valid_types() -> list[str]:
    types = load_lookup()["types"]
    return sorted(types if isinstance(types, list) else types.keys())


def observed_rate(borough: str, app_type: str) -> dict | None:
    """The real observed approval rate for comparable applications.

    Deliberately returned alongside the model score. A published design
    decision (HANDOFF §7) was that the site quotes *observed* rates rather than
    model output, because "this is what happened to 6,844 applications like
    yours" is easier to trust — and easier to check — than "the model says
    0.64". The agent should be able to say both.
    """
    lookup = load_lookup()
    borough_row = lookup["boroughs"].get(borough)
    if not borough_row:
        return None

    # This rate is matched on borough and application type ONLY. It does not
    # look at what was actually proposed — which is precisely the signal the
    # model uses. So a description-driven estimate can sit far below a
    # type-level base rate without either being wrong, and the caller must say
    # what the comparison set is or the two numbers look contradictory.
    caveat = (
        "Matched on borough and application type only — NOT on what is being "
        "proposed. The model score uses the description; this rate ignores it. "
        "Present it as the base rate for the borough and type, not as the rate "
        "for applications like this one."
    )
    cell = (borough_row.get("by_type") or {}).get(app_type)
    if cell and cell.get("n"):
        return {
            "scope": f"all '{app_type}' applications in {borough}, any description",
            "n": cell["n"],
            "approval_pct": cell["approval"],
            "matched_on": ["borough", "app_type"],
            "caveat": caveat,
        }
    return {
        "scope": f"all applications in {borough}, any type or description",
        "n": borough_row["n"],
        "approval_pct": borough_row["approval"],
        "matched_on": ["borough"],
        "caveat": caveat,
    }


def model_card() -> dict:
    """Honest performance summary, returned with every prediction."""
    metrics = load_model()["metrics"]
    return {
        "roc_auc": metrics["roc_auc"],
        "refusal_pr_auc": metrics["refusal_pr_auc"],
        "base_refusal_rate": metrics["base_refusal"],
        "trained_on": metrics["n_train"],
        "tested_on": metrics["n_test"],
        "split": "time-based — trained on 2018-2023, tested on 2024-2025",
    }

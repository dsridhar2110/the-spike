"""Prediction tool — the third route.

Numbers come from SQL, meaning comes from RAG, and a judgement about an
application that does not exist yet comes from here. Vector search cannot
extrapolate and SQL cannot score a sentence nobody has written down.

The tool always returns the model's estimate *and* the real observed rate for
comparable applications, because the second one is checkable and the first one
is not.
"""

from __future__ import annotations

from .ledger import record
from ..model.approval_model import (
    model_card,
    observed_rate,
    predict,
    valid_boroughs,
    valid_types,
)


def predict_approval(
    description: str, borough: str, app_type: str = "Full", tool_context=None
) -> dict:
    """Estimate whether a planning application would be approved.

    Use this only for a HYPOTHETICAL or PROPOSED application — one that is not
    in the data yet, e.g. "would a conversion into flats in Merton be
    approved?". For anything that already happened, use run_planning_sql: the
    observed record beats a model estimate every time.

    The model is TF-IDF over the application description plus borough and
    application type, scored by logistic regression. It was trained on 2018-2023
    and tested on 2024-2025.

    When reporting the result: give the probability, say it is a model estimate
    and not a decision, and quote the observed rate for comparable applications
    alongside it. Mention the ROC-AUC of 0.71 if the user leans on the number —
    this ranks applications usefully, it does not decide them.

    Args:
        description: The proposed development, in the wording an application
            would use, e.g. "Conversion of dwelling into 3 self-contained flats".
        borough: One of the 18 London boroughs in the analysis.
        app_type: Application type, e.g. Full, Outline, Conditions, Amendment.
            Defaults to "Full".

    Returns:
        A dict with `probability_approved`, `observed_comparable` (the real
        rate for similar applications), the terms that `helped` and `hurt`, and
        a `model_card`. On an unknown borough or type, `ok` is False and the
        valid options are listed.
    """
    if not (description or "").strip():
        return {"ok": False, "error": "A description of the proposed development is required."}

    boroughs = valid_boroughs()
    if borough not in boroughs:
        return {
            "ok": False,
            "error": f"'{borough}' is not one of the 18 analysed boroughs.",
            "valid_boroughs": boroughs,
        }

    types = valid_types()
    if app_type not in types:
        return {
            "ok": False,
            "error": f"'{app_type}' is not a known application type.",
            "valid_types": types,
        }

    result = predict(description, borough, app_type)
    probability = result["probability_approved"]
    record(
        tool_context,
        source="model",
        label=f"P(approved) — {description[:60]}",
        value=round(100 * probability, 1),
        detail=f"{borough} / {app_type}, ROC-AUC 0.71, model estimate not a decision",
    )

    return {
        "ok": True,
        "input": {"description": description, "borough": borough, "app_type": app_type},
        "probability_approved": round(probability, 4),
        "percent_approved": round(100 * probability, 1),
        "observed_comparable": observed_rate(borough, app_type),
        "helped": result["helped"],
        "hurt": result["hurt"],
        "borough_effect": result["borough_effect"],
        "type_effect": result["type_effect"],
        "vocabulary_terms_matched": result["vocabulary_terms_matched"],
        "model_card": model_card(),
        "caveat": (
            "A model estimate, not a decision. ROC-AUC 0.71 means it ranks "
            "applications by risk usefully; it does not adjudicate them. Quote "
            "the observed comparable rate alongside it."
        ),
        "low_signal": result["vocabulary_terms_matched"] < 3,
    }

"""RAG tool — narrative questions answered from our own write-ups, with citations.

The division of labour that defines this project: numbers come from SQL, meaning
comes from here. Vector search cannot count and SQL cannot explain *why*.
"""

from __future__ import annotations

from ..rag.index import MIN_SIMILARITY, index_exists, search


def search_planning_docs(query: str, top_k: int = 4) -> dict:
    """Search the project's written analysis for narrative and methodology.

    Use this for questions about WHY something happens, how the analysis was
    done, what the limitations are, or what a term means — anything where the
    answer is an explanation rather than a number. For counts, rates, rankings
    or any figure, use run_planning_sql instead.

    Every passage returned carries a citation. Quote or paraphrase only what is
    in the passages, and cite the source. If this returns found=False, say that
    the documents do not cover the question — do not answer from your own prior
    knowledge.

    Args:
        query: A natural-language question or topic.
        top_k: How many passages to return (default 4).

    Returns:
        A dict with `found`, and either `passages` (each with `text`,
        `citation`, `similarity`) or, when nothing clears the relevance floor,
        `best_similarity` and `nearest_topics` explaining what was closest.
    """
    if not index_exists():
        return {
            "ok": False,
            "found": False,
            "error": (
                "The document index has not been built. Run "
                "`python scripts/build_index.py` first."
            ),
        }

    hits = search(query, top_k=top_k)
    relevant = [hit for hit in hits if hit["similarity"] >= MIN_SIMILARITY]

    if not relevant:
        return {
            "ok": True,
            "found": False,
            "query": query,
            "reason": (
                "Nothing in the project write-ups is relevant to this question. "
                "Say so plainly — do not answer from prior knowledge."
            ),
            "best_similarity": hits[0]["similarity"] if hits else None,
            "relevance_floor": MIN_SIMILARITY,
            "nearest_topics": [hit["citation"] for hit in hits[:3]],
        }

    return {
        "ok": True,
        "found": True,
        "query": query,
        "passages": [
            {
                "text": hit["text"],
                "citation": hit["citation"],
                "similarity": hit["similarity"],
            }
            for hit in relevant
        ],
        "n_passages": len(relevant),
    }

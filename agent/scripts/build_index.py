"""Build the vector index, then calibrate the relevance floor.

    cd agent && ../.venv-agent/bin/python scripts/build_index.py

The calibration half matters as much as the build. It probes the finished index
with questions the docs DO cover and questions they clearly do not, and prints
both similarity spreads. If those two bands overlap, MIN_SIMILARITY cannot
separate them and the "I found nothing relevant" guardrail is a coin flip.
Picking the threshold by eye and never checking it is how a RAG system quietly
starts citing irrelevant passages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planning_agent.rag.index import MIN_SIMILARITY, build, search

ON_TOPIC = [
    "Why does deciding on the deadline day reduce approval rates?",
    "What are the limitations of this analysis?",
    "Why was target_decision_date used instead of start_date plus 56 days?",
    "Why logistic regression instead of gradient boosting?",
    "Which boroughs were excluded and why?",
]

OFF_TOPIC = [
    "What is the weather forecast for tomorrow?",
    "How do I make sourdough bread?",
    "What is the capital of Peru?",
    "Explain quantum entanglement.",
]


def spread(questions: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for question in questions:
        hits = search(question, top_k=1)
        best = hits[0] if hits else None
        rows.append(
            (question, best["similarity"] if best else 0.0, best["citation"] if best else "-")
        )
    return rows


def main() -> None:
    print("Chunking and embedding…")
    chunks = build()
    words = [c.word_count for c in chunks]
    sources: dict[str, int] = {}
    for chunk in chunks:
        sources[chunk.source] = sources.get(chunk.source, 0) + 1

    print(f"\n{len(chunks)} chunks indexed")
    print(f"  words per chunk: min {min(words)} · median {sorted(words)[len(words)//2]} "
          f"· max {max(words)}")
    for source, count in sorted(sources.items(), key=lambda kv: -kv[1]):
        print(f"  {source:14s} {count:3d} chunks")

    print(f"\n{'=' * 74}\nCALIBRATION — relevance floor is {MIN_SIMILARITY}\n{'=' * 74}")

    on = spread(ON_TOPIC)
    off = spread(OFF_TOPIC)

    print("\nON-TOPIC (these must clear the floor):")
    for question, similarity, citation in on:
        flag = "ok " if similarity >= MIN_SIMILARITY else "MISS"
        print(f"  [{flag}] {similarity:.3f}  {question[:52]:54s} {citation[:38]}")

    print("\nOFF-TOPIC (these must NOT clear the floor):")
    for question, similarity, citation in off:
        flag = "ok " if similarity < MIN_SIMILARITY else "LEAK"
        print(f"  [{flag}] {similarity:.3f}  {question[:52]:54s} {citation[:38]}")

    lowest_on = min(similarity for _, similarity, _ in on)
    highest_off = max(similarity for _, similarity, _ in off)
    gap = lowest_on - highest_off

    print(f"\nlowest on-topic  {lowest_on:.3f}")
    print(f"highest off-topic {highest_off:.3f}")
    print(f"separation gap    {gap:+.3f}")
    if gap <= 0:
        print("\n⚠️  BANDS OVERLAP — no single threshold separates relevant from "
              "irrelevant.\n   The guardrail is unreliable; revisit chunking or the "
              "embedding model.")
    else:
        midpoint = (lowest_on + highest_off) / 2
        print(f"\n✅ Bands are separated. Any threshold in "
              f"({highest_off:.3f}, {lowest_on:.3f}) works; midpoint {midpoint:.3f}.")
        if not (highest_off < MIN_SIMILARITY < lowest_on):
            print(f"   ⚠️  But MIN_SIMILARITY={MIN_SIMILARITY} is OUTSIDE that band — "
                  f"set it to ~{midpoint:.2f}.")


if __name__ == "__main__":
    main()

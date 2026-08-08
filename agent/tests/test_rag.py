"""Chunking and retrieval tests.

Split deliberately into two halves:

* Chunking is pure logic — no API, no network, always runs. This is where the
  decisions that actually shape retrieval quality live, so it gets the most tests.
* Retrieval needs embeddings, so those tests skip when the index has not been
  built. They are the ones that prove the relevance floor does its job.
"""

import pytest

from planning_agent.rag.chunker import (
    OVERLAP_WORDS,
    TARGET_WORDS,
    chunk_markdown,
)
from planning_agent.rag.index import EVENT_ONLY_CORPUS, MIN_SIMILARITY, OWN_CORPUS, index_exists
from planning_agent.tools.docs_tool import search_planning_docs

# --------------------------------------------------------------------------
# chunking — pure logic
# --------------------------------------------------------------------------

SAMPLE = """# METHOD

Intro text at the top.

## 1. The clock

We measure against target_decision_date.

### 1a. Why not start_date

Because start_date is the receipt date.

## 2. Limitations

Twelve of them.
"""


def test_heading_path_is_hierarchical():
    chunks = chunk_markdown(SAMPLE, "METHOD.md")
    paths = [c.heading_path for c in chunks]
    assert "METHOD.md > METHOD > 1. The clock" in paths
    # a level-3 heading nests under its level-2 parent, not the level-1 root
    assert "METHOD.md > METHOD > 1. The clock > 1a. Why not start_date" in paths


def test_deeper_heading_pops_back_to_correct_level():
    """### under ## then a new ## must not stay nested under the ###."""
    chunks = chunk_markdown(SAMPLE, "METHOD.md")
    limitations = [c for c in chunks if c.heading_path.endswith("2. Limitations")]
    assert len(limitations) == 1
    assert "1a." not in limitations[0].heading_path


def test_heading_path_is_embedded_in_the_text():
    """The chunk body assumes context the heading supplies. Retrieval only works
    if that context is inside the embedded text, not just in metadata."""
    chunks = chunk_markdown(SAMPLE, "METHOD.md")
    for chunk in chunks:
        assert chunk.text.startswith(chunk.heading_path)


def test_citation_matches_heading_path():
    chunk = chunk_markdown(SAMPLE, "METHOD.md")[0]
    assert chunk.citation == chunk.heading_path


def test_headings_inside_code_fences_are_not_headings():
    """A '#' in a shell block is a comment. Treating it as a heading shreds the
    document into nonsense sections."""
    markdown = "# Real\n\ntext\n\n```bash\n# not a heading\necho hi\n```\n\nmore text\n"
    paths = {c.heading_path for c in chunk_markdown(markdown, "X.md")}
    assert paths == {"X.md > Real"}


def test_long_sections_are_windowed_with_overlap():
    body = " ".join(f"w{i}" for i in range(TARGET_WORDS * 2))
    chunks = chunk_markdown(f"# Big\n\n{body}\n", "X.md")
    assert len(chunks) > 1
    assert all(c.word_count <= TARGET_WORDS for c in chunks)
    first_words = chunks[0].text.split()[-OVERLAP_WORDS:]
    second_words = chunks[1].text.split()
    assert set(first_words) & set(second_words), "windows must overlap"


def test_short_sections_are_not_split():
    chunks = chunk_markdown("# Small\n\njust a few words here\n", "X.md")
    assert len(chunks) == 1


def test_empty_sections_are_dropped():
    chunks = chunk_markdown("# A\n\n## B\n\n## C\n\nonly C has text\n", "X.md")
    assert [c.heading_path for c in chunks] == ["X.md > A > C"]


def test_chunk_ids_are_unique_within_a_document():
    chunks = chunk_markdown(SAMPLE, "METHOD.md")
    assert len({c.id for c in chunks}) == len(chunks)


# --------------------------------------------------------------------------
# corpus licensing — the organisers' material must never be a default
# --------------------------------------------------------------------------

def test_default_corpus_is_only_our_own_writing():
    """docs/ holds the hackathon organisers' briefs and PDFs — git-ignored and
    not ours to republish. They must never be in the default corpus."""
    assert all("docs" not in p.parts for p in OWN_CORPUS)
    assert {p.name for p in OWN_CORPUS} == {
        "METHOD.md", "BRIEF.md", "README.md", "PITCH.md", "HANDOFF.md"
    }


def test_event_only_corpus_is_separate_and_opt_in():
    assert all("docs" in p.parts for p in EVENT_ONLY_CORPUS)


# --------------------------------------------------------------------------
# retrieval — needs the built index
# --------------------------------------------------------------------------

requires_index = pytest.mark.skipif(
    not index_exists(), reason="run scripts/build_index.py first"
)


@requires_index
def test_on_topic_query_retrieves_with_citations():
    result = search_planning_docs("Why does deciding on the deadline reduce approvals?")
    assert result["found"] is True
    assert result["n_passages"] >= 1
    for passage in result["passages"]:
        assert passage["similarity"] >= MIN_SIMILARITY
        assert passage["citation"], "every passage must be citable"
        assert ".md" in passage["citation"]


@requires_index
@pytest.mark.parametrize(
    "query",
    [
        "What is the capital of Peru?",
        "How do I make sourdough bread?",
        "What is the weather forecast for tomorrow?",
    ],
)
def test_off_topic_queries_are_refused_not_answered(query):
    """The whole point of the relevance floor. Nearest-neighbour search always
    returns *something*; without a floor the agent would cite it."""
    result = search_planning_docs(query)
    assert result["found"] is False
    assert result["best_similarity"] < MIN_SIMILARITY
    assert "do not answer from prior knowledge" in result["reason"]


@requires_index
def test_weather_query_specifically_is_below_the_floor():
    """Regression guard: at the first guessed floor of 0.55 this scored 0.568
    and leaked through. It is the reason the floor is calibrated rather than
    chosen by eye."""
    result = search_planning_docs("What is the weather forecast for tomorrow?")
    assert result["found"] is False


@requires_index
def test_methodology_question_finds_the_method_document():
    result = search_planning_docs(
        "Why was target_decision_date used instead of start_date plus 56 days?"
    )
    assert result["found"] is True
    assert any("METHOD.md" in p["citation"] for p in result["passages"])

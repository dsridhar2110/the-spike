# AGENTIC BUILD BRIEF — "The Spike" → Google ADK agent + RAG

> **Paste this into a fresh terminal opened at `Deeksh Personal`.**
> Opening line: *"Read `portfolio-work/repos/London Hackathon/AGENTIC-BUILD-BRIEF.md` and start at Phase 0."*
>
> **This is a BUILD brief, not interview prep.** Do not use the interview terminal for it.

---

## 1. Why this project exists

Three live interview processes — **Tiger Analytics (R2)**, **Mico (R2)** and **HCL (agentic AI JD)** —
all converge on the same ask: **build an agent, understand RAG, understand how memory/context is
shared between agents.** Tiger's Round-1 interviewer (Akhil) said it directly: *"there's a gap
between what you learned and what you apply — get hands-on building an agent."*

The resume currently references an **LLM-driven platform**. This project makes that true.

**Secondary goal:** learn **Google ADK** specifically. It was recommended unprompted by an
interviewer, it runs on GCP free-tier credits, and one JD lists **GCP** as a preferred qualification.
Building on ADK closes the agent gap and the GCP gap in the same repo.

---

## 2. The base project — and why this one

**Base: `portfolio-work/repos/London Hackathon` ("The Spike")** — built in one day at House London #0,
Newspeak House, 1 Aug 2026, team Spike Girls SB.

It is the right base because it **already contains all three things an agent needs tools for**:

| Asset already in the repo | Becomes this agent tool |
|---|---|
| `data/raw/housing.sqlite` + `wheretobuild_msoa_stats.csv` | **Text-to-SQL tool** — exact numeric answers |
| `docs/*.pdf`, `policy-briefs.md`, `data-briefs.md` | **RAG tool** — narrative/policy questions |
| `notebooks/09_text_model.py`, `outputs/approval_results.json` | **Prediction tool** — TF-IDF + logistic approval model |
| `outputs/*.json` (findings, days_grid, per-borough) | Grounding facts for cited answers |

**Also true and worth stating:** the analysis is genuinely hers, on real public data, presented at a
real event. That makes every agent answer traceable to work she actually did.

**Do NOT** start a greenfield agent project. The value here is that the tools return real numbers.

---

## 3. What to build — "Planning Intelligence Agent"

An agent a councillor or planning analyst can ask questions of, in plain English:

- *"What share of Kingston's decisions land on the deadline day?"* → **SQL tool**
- *"Why does deciding on the deadline reduce approval rates?"* → **RAG tool** over the briefs + METHOD.md
- *"Would a conversion-to-flats application in Merton likely be approved?"* → **model tool**
- *"Compare Kingston and Merton and explain the difference"* → **multi-tool + synthesis**

**The routing decision is the whole point of the project** — numeric goes to SQL, narrative goes to
vector search, prediction goes to the model. That is the answer to *"how would you do RAG over
tables?"*, which has already come up in two interviews.

---

## 4. Build phases

### Phase 0 — Setup (30 min)
- [ ] GCP project on free-tier credits · enable **Vertex AI**
- [ ] `pip install google-adk` · authenticate `gcloud auth application-default login`
- [ ] Confirm `adk web` launches and shows the trace UI
- [ ] New folder `agent/` inside the existing repo — **do not fork, extend**
- [ ] Add `.env` (git-ignored) for project id / region / keys

### Phase 1 — Single agent, one tool (half a day)
- [ ] One `LlmAgent` + one `FunctionTool` that queries `housing.sqlite`
- [ ] Tool returns **structured rows**, not prose — the agent narrates, SQL computes
- [ ] Verify in `adk web`: read the full trace — thought → tool call → observation → answer
- [ ] **Learning goal:** the tool-calling loop, and why the LLM must never do the arithmetic

### Phase 2 — Add RAG (1 day)
- [ ] Ingest `docs/*.pdf` + `policy-briefs.md` + `METHOD.md` + `BRIEF.md`
- [ ] Chunk on **markdown/PDF headings**, ~500 tokens, ~50 overlap, keep the heading path in the chunk
- [ ] Embed and store — start local (`chromadb`), then port to **Vertex AI Vector Search**
- [ ] Expose retrieval as a second `FunctionTool`
- [ ] Every answer returns **citations** — source file + section
- [ ] Guardrail: nothing relevant retrieved → say so, never invent
- [ ] **Learning goal:** the two RAG pipelines, chunking trade-offs, grounding

### Phase 3 — The routing decision ⭐ the differentiator (half a day)
- [ ] Agent chooses: numeric → SQL · narrative → RAG · prediction → model
- [ ] Add the **approval model** as a third tool, loading the existing TF-IDF + logistic artifact
- [ ] Handle the mixed case — retrieve *and* compute, then synthesise
- [ ] **Learning goal:** why vector search fails on numbers, and how agentic routing fixes it

### Phase 4 — Memory and shared context ⭐ they ask about this (half a day)
- [ ] ADK **Session** — multi-turn state, so *"and Merton?"* resolves against the previous turn
- [ ] ADK **State** — what persists within a run vs across runs
- [ ] ADK **Memory service** — long-term recall across sessions
- [ ] Show what a sub-agent **does and does not** inherit from the parent's context
- [ ] **Learning goal:** the exact question — *"how is memory shared between agents?"*

### Phase 5 — Multi-agent (1 day)
- [ ] Orchestrator + specialists: **DataAgent** (SQL) · **PolicyAgent** (RAG) · **ModelAgent** (prediction)
- [ ] Use a **workflow agent** where the path is deterministic (`SequentialAgent`) and let the LLM
      decide only where judgement is genuinely needed
- [ ] **Structured output at every handoff** — no free-text hand-offs between agents
- [ ] Step budget + loop cap so it can't run away
- [ ] **Learning goal:** orchestrator–worker, context isolation, why coordination has a cost

### Phase 6 — Evaluation (half a day) ⭐ most people skip this; don't
- [ ] **Golden question set** — ~20 questions with known answers, drawn from `outputs/*.json`
- [ ] Score: **groundedness · answer relevance · retrieval quality · tool-choice accuracy**
- [ ] ADK **eval sets**, or `ragas` for the RAG portion
- [ ] Re-run on every prompt change — prove a tweak didn't silently regress it
- [ ] **Learning goal:** *"how do you evaluate an LLM system — there's no RMSE?"*

### Phase 7 — Guardrails + deploy (half a day)
- [ ] ADK **callbacks** as guardrails — before model call and before tool call
- [ ] SQL tool: **read-only connection**, allow-list of tables, statement timeout
- [ ] Human-in-the-loop for anything with consequences
- [ ] Deploy: **Cloud Run** container, or **Vertex AI Agent Engine**
- [ ] `pytest` on the tools + **GitHub Actions** CI
- [ ] **Learning goal:** production agent hygiene

### Phase 8 — Presentation (half a day)
- [ ] Extend the existing self-contained `site/index.html`, or add a small chat UI
- [ ] `presentation/interview-walkthrough.html` following the house standard
- [ ] README: problem → architecture → tools → memory model → evaluation → results
- [ ] Push to **`dsridhar2110`** (commits authored as her, per workspace rule)

---

## 5. What each phase closes, per JD

| Phase | Tiger R2 | Mico | HCL agentic JD | GCP-preferred JD |
|---|---|---|---|---|
| 1 tool calling | ✅ agent built | ✅ | ✅ | ✅ Vertex |
| 2 RAG | ✅ | ✅ | ✅ | ✅ Vector Search |
| 3 routing / text-to-SQL | ✅ the exact probe | ✅ | ✅ | ✅ |
| 4 memory + shared context | ✅ | ✅ | ✅ **their named ask** | — |
| 5 multi-agent | ✅ | ✅ | ✅ | — |
| 6 evaluation | ✅ | ✅ offline eval | ✅ | — |
| 7 deploy + CI | ✅ | ✅ | ✅ | ✅ Cloud Run |

---

## 6. Rules for the build

- **Extend the existing repo.** The credibility comes from the tools returning real numbers from
  real analysis she did.
- **Every number an agent states must be traceable** to `outputs/*.json` or a live SQL result.
  No number is ever generated by the LLM.
- **Local first, cloud second.** Get it working with a local vector store and SQLite, then port to
  Vertex. Don't block on cloud setup.
- **Commit per phase** so the git history shows the progression.
- **Write down what surprised you at each phase** — that becomes the interview story, and
  "what went wrong and what I learned" is asked in every round.

---

## 7. Stack

`google-adk` · `google-cloud-aiplatform` (Vertex) · `chromadb` → Vertex AI Vector Search ·
`sqlite3` / `sqlalchemy` · `sentence-transformers` or Vertex embeddings · `pypdf` / `unstructured` ·
`scikit-learn` + `joblib` (existing model) · `ragas` · `pytest` · Docker · Cloud Run

---

## 8. Definition of done

- [ ] A deployed URL where a question gets a **cited, correct** answer
- [ ] Numeric questions provably answered by **SQL**, not by the model
- [ ] Multi-turn memory demonstrable in one screen-share
- [ ] An eval report with a score, re-runnable
- [ ] README + walkthrough HTML
- [ ] Public repo under `dsridhar2110`

**Then the resume line "LLM-driven platform" is backed by something clickable.**

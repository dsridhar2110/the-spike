# The Spike

**London councils are judged on deciding planning applications within 8 weeks. They hit
that target by deciding on the last legal day — and those decisions are approved
10 points less often.**

Built in one day at **House London #0**, Newspeak House, 1 August 2026 — Data Brief DD.
Team: **Spike Girls SB**.

---

## The findings

| | |
|---|---|
| **1 in 5** decisions land on the exact day the council set itself | **10.4×** more than the surrounding days would predict |
| Approved when decided normally | **82.1%** |
| Approved when decided in the deadline rush | **71.9%** |
| Boroughs showing the drop | **16 of 18** |
| Most / least bunching | Kingston **38.9%** · Merton **1.6%** |

**And what you build matters more than where you build it.** Text alone predicts approval
better (ROC-AUC 0.702) than borough, ward and application type combined (0.576).
Conversion into flats is approved **65.7%** of the time against a **79.9%** London average.

---

## What's in here

```
site/                  the deliverable — one self-contained HTML page
  index.html           open this; works offline, no server, no build step
  template.html        source template (__PLACEHOLDERS__ swapped at build time)
  predictor.js         browser re-implementation of the TF-IDF + logistic model
  visuals.js           map, spike, drop and development-type charts (hand-rolled SVG)
notebooks/             the analysis, in order — see "Reproduce" below
outputs/*.json         every number the page renders
build.py               inlines the JS and JSON into site/index.html
METHOD.md              full method: features, models, validation, limitations
PITCH.md               the three-minute script
BRIEF.md               the hackathon brief and data inventory
```

**`site/index.html` is the whole product.** Double-click it. Everything — the model, the
aggregates, 6,480 comparable applications, all four charts — is embedded in that one file.

---

## The science

| | |
|---|---|
| **Data** | 343,141 London planning applications → **149,813** after filters. 18 boroughs, 2018–2025. One table, no joins |
| **Constraint** | Only what is known **at submission**. Decision date, public comments, who decided and appeal outcome are all excluded — they leak the future |
| **Features** | TF-IDF over **9,343** words and bigrams from the application description, plus borough and application type |
| **Models** | Logistic regression (approval) · gradient-boosted quantile regression (decision time) · bunching estimator (the spike) |
| **Split** | Train 2018–2023 (122,806) · test 2024–2025 (28,073). Time-ordered, never random |
| **Validation** | Walk-forward — retrained and retested 5 times, one year at a time |
| **Metrics** | ROC-AUC **0.7103** · refusal PR-AUC **0.3759** against a 0.1897 base · Brier **0.1395** |
| **Stability** | **0.7085 ± 0.0072** across the five folds |
| **Robustness** | 6 artifact checks on the spike — wrong clock, deadline extensions, one-off period, machine-stamped dates, batch upload, one bad borough. All passed |

Full detail, including twelve stated limitations, is in **[METHOD.md](METHOD.md)**.

### Two things worth knowing

**The browser model is the real model.** `predictor.js` re-implements sklearn's
`TfidfVectorizer.transform` in JavaScript and was verified against the Python original on
held-out descriptions — maximum absolute difference **0.00003**.

**We excluded 8 boroughs and named why.** Havering records a **0.0%** refusal rate across
1,032 decisions. No planning authority approves everything, so that is broken data, not a
generous council. It is flagged on the map rather than ranked.

---

## The data

Not in this repository. The analysis runs on **`housing.sqlite`** (1.4 GB) —
343,141 London planning applications scraped from [UK PlanIt](https://www.planit.org.uk/)
and housing-relevance filtered.

Provenance: **33 borough planning portals → UK PlanIt (Andrew Speakman) → scraped and
filtered by Jamie Coombes → House London Drive.**

Download it from the hackathon Drive:
<https://drive.google.com/file/d/11XVe6fYsRgoX_9goX1IA1g1e3fjvlnpY/view>
and place it at `data/raw/housing.sqlite`.

> **Not used, and not present:** the WhereToBuild MSOA extract. It is licence-restricted
> to the event and must not be redistributed. Nothing in this repository is
> licence-encumbered.

---

## Reproduce

```bash
pip install -r requirements.txt
cd notebooks
python 01_artifact_checks.py      # six robustness checks on the spike
python 02_correct_clock.py        # corrected clock + refusal discontinuity
python 03_build_findings.py       # filters + borough QA gate
python 04_eda.py                  # feature EDA + mutual information
python 05_model.py                # 3 models, time split, walk-forward
python 06_shap.py                 # LightGBM parity model + SHAP
python 07_approval_model.py       # approval model + the bunch/approval link
python 08_build_tool_data.py      # borough × type lookup
python 09_text_model.py           # the TF-IDF ladder — does text add signal?
python 10_export_live_model.py    # export the browser-runnable model
python 11_text_deep_dive.py       # archetypes, full metrics, walk-forward
python 12_days_model.py           # quantile regression on decision time
python 13_export_days_grid.py     # decision-time lookup grid
python 14_build_map.py            # simplified London borough map
python 15_per_borough.py          # per-borough aggregates
cd .. && python build.py          # inline everything into site/index.html
```

`14_build_map.py` needs a London borough GeoJSON at `/tmp/t.json` — see the header of that
script for the source.

---

## Credits

**Data collection — [Jamie Coombes](https://github.com/Jcoombes)**, who built and
relevance-filtered the 343k-application dataset this analysis rests on, and who organised
House London #0. Without that scrape there is no project.

**UK PlanIt — Andrew Speakman**, who maintains the aggregator behind the raw data as a
one-person volunteer project across ~420 UK planning authorities.

**Analysis and build — Spike Girls SB**, House London #0.

---

## Licence

Code: MIT. The underlying planning data belongs to the local authorities that published it
and to the projects listed above.

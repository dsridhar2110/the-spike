# Method — The 8-Week Cliff

> Everything we did, in order, with every decision and its reason.
> House London #0 · Data Brief DD · 1 August 2026
>
> **Sections 1–13 cover the timing model (which applications get caught in the deadline
> rush). Sections 14–18 cover the `description` column and the approval model — the text
> work that lifted ROC-AUC from 0.576 to 0.710.**


---

# §0 · One-page summary — read this first

*For teammates: this is the whole project on one page. Numbers are final and verified.*

## The problem statement

> **Councils have 8 weeks to decide a planning application, and are judged on hitting that
> deadline. We show they hit it by timing decisions to land on the last legal day — and
> that applications decided in that rush are approved 10 points less often.**

Three questions, three models:

| | Question | Type |
|---|---|---|
| **A** | Does the deadline distort *when* decisions are made? | Diagnostic — bunching estimator |
| **B** | Will my application be **approved**? | Binary classification |
| **C** | **How long** will my decision take? | Quantile regression |

## Stakeholders

| Who | What they get | What they'd do with it |
|---|---|---|
| **MHCLG** *(primary)* | Evidence the 8-week timeliness metric is being gamed | Replace it with an appeal-survival metric |
| **Applicant** *(secondary)* | Approval odds + expected timeline + comparable cases | Decide what to propose, and when |
| **Borough** *(tertiary)* | Where they sit vs 17 peers | Ask Merton how it avoids bunching |

## Data

**One table, no joins, nothing licence-restricted.**
`housing.sqlite` → `applications_tidy`, 343,141 rows × 89 cols → **149,813 after filters**,
18 boroughs, 2018–2025.
Source: 33 borough portals → UK PlanIt → Jamie Coombes' scrape → hackathon Drive.

## Features

**Rule: everything must be knowable the day you submit.** No `decided_date`, no
`n_comments`, no `decided_by`, no appeal fields — those leak the future.

| Feature | Type | Used in |
|---|---|---|
| `description` → **TF-IDF, 9,343 word + bigram features** | text | B, C |
| `area_name` (borough, 18) | categorical | A, B, C |
| `app_type` (Full / Outline / Conditions / Amendment) | categorical | A, B, C |
| `ward_name` → top 200 + OTHER | categorical | A |
| `borough_prior`, `weekly_intake`, `sub_year/month/dow` | numeric | A, C |
| `desc_len`, `desc_words`, `has_agent`, `has_geo` | numeric | A |

## Models

| | Model | Why |
|---|---|---|
| **A** | Bunching estimator (no ML) | standard public-economics test for threshold response |
| **B** | `LogisticRegression(C=1.0, liblinear)` on TF-IDF + one-hot | interpretable per-word, exports to browser |
| **C** | `HistGradientBoostingRegressor(loss='quantile')` × 3 | predicts a *range*, not false precision |

Also fitted and reported for comparison: `HistGradientBoostingClassifier` and a
borough-lookup baseline.

## Validation

- **Time-based split** — train 2018–2023, test 2024–2025. Never random.
- **Walk-forward backtest** — retrain each year, test the next. 5 folds.
- **Calibration** — predicted vs actual, 10 bins.
- **Six robustness checks** on the bunching finding (§1 of Part A).
- **Sensitivity analysis** on the counterfactual window (7.7×–19.7×; we quote 10.2×).
- **Browser-vs-sklearn parity** — max difference 0.00003.

## Success criteria and results

| Model | Metric | Result | Baseline | Verdict |
|---|---|---|---|---|
| **A** | excess mass at deadline | **10.2×** | 1.0× | survived 6 checks |
| **B** | **refusal PR-AUC** | **0.3759** | 0.1897 | **1.98×** |
| B | ROC-AUC | 0.7103 | 0.5619 | +0.135 from text |
| B | Brier | 0.1395 | 0.1537 | better |
| B | walk-forward ROC | 0.7085 ± **0.0072** | — | 5 folds, no drift |
| **C** | MAE (median days) | **18.7 days** | 22.2 | **−15.9%** |
| C | pinball loss @ p90 | 7.09 | 8.54 | −17.0% |
| C | p90 coverage | **89.8%** | target 90% | well calibrated |

⚠️ **Do not quote PR-AUC 0.90.** That is the *approval* (majority) class — 81% of
applications are approved, so it is inflated by construction. **The honest headline is
refusal PR-AUC 0.3759 vs a 0.1897 base.**

## The two findings

1. **What you build decides *whether* you're approved.** Text alone scores 0.7023;
   adding borough only reaches 0.7110. Conversion into flats **65.7%** vs single-storey
   extension **79.5%**.
2. **Where you are decides *when* you're decided.** Geography dominates the timing model;
   the borough lookup captures 88% of it. Kingston bunches **38.9%**, Merton **1.6%**.

**And when you're decided changes whether you're approved: 82.1% normally, 71.9% in the
rush — in 16 of 18 boroughs.**

## For whoever is building visuals — the six that matter

1. **The spike** — decisions by days from deadline. Bar chart, day 0 highlighted. *The hero.*
2. **The refusal discontinuity** — refusal rate by day offset, spike at 0. Proves harm.
3. **Borough league table** — horizontal bars, Kingston 38.9% → Merton 1.6%.
4. **Approved-normally vs approved-in-the-rush** — two bars, 82.1% vs 71.9%.
5. **Development type approval rates** — horizontal bars vs the 79.9% base line;
   conversion-into-flats at the bottom.
6. **The word list** — approval words green, refusal words red. Instantly legible.

*Do not visualise:* ROC curves, PR curves, SHAP beeswarms, confusion matrices. They belong
in this document, not on screen.

---

## 1. Problem statement

**Part A — diagnostic**
> Does the 8-week statutory planning deadline distort *when* London councils decide
> applications, and does deciding at the deadline change *what* they decide?

**Part C — predictive**
> Using only information known at the moment an application is submitted, can we predict
> whether it will be decided in the deadline rush — where refusal rates are ~11 points
> higher?

**Stakeholder.** Primary: **MHCLG**, who set the P152/P154 timeliness measures — they own
the metric we argue is broken. Secondary: an **applicant**, who gets a probability nobody
currently offers them. Tertiary: a **borough**, because Merton proves it's avoidable.

**Decision the work supports.** Replace *"% of applications decided within 8 weeks"* with
*"% of decisions upheld on appeal"* as the performance measure.

---

## 2. Data

**One table. No joins. No external sources.**

| | |
|---|---|
| File | `housing.sqlite` (1.4 GB) |
| Table | `applications_tidy` — **343,141 rows × 89 columns** |
| Coverage | 33 London boroughs, 2016-02-07 → 2026-03-06 |
| Local path | `data/raw/housing.sqlite` |
| Drive file | https://drive.google.com/file/d/11XVe6fYsRgoX_9goX1IA1g1e3fjvlnpY/view?usp=sharing |
| Drive folder | https://drive.google.com/drive/folders/1ghZJzX8z6b7Nj-xsPSrcjprq4V5bNj_F |

**Provenance:** 33 borough planning portals → [UK PlanIt](https://www.planit.org.uk/)
(volunteer aggregator, Andrew Speakman) → scraped and housing-relevance-filtered by Jamie
Coombes → House London Drive.

**Not used:** the WhereToBuild MSOA extract (licence-restricted, event-only). Nothing in
this project is licence-encumbered.

---

## 3. Target variable

```python
bunched = 1 if date(decided_date) == date(target_decision_date) else 0
```

*Was this application decided on the exact day the council said it would be?*

`target_decision_date` is the council's own declared deadline for that specific case.
Using it rather than "start + 56 days" matters: it **already absorbs any agreed extension
of time**, which is the single strongest objection to the finding.

- Binary classification
- **Base rate 21.6%** (35,091 of 162,270 before the borough QA gate)
- Imbalance ≈ 1:3.6 → **PR-AUC is the correct primary metric**, not ROC-AUC

---

## 4. Cleaning — every row dropped, and why

```
all rows                            343,141
+ app_size = 'Small'                307,042   (−36,099)  8-week class only; majors get 13 weeks
+ start_date >= 2018-01-01          231,220   (−75,822)  earlier scrape coverage is patchy
+ decided_date not null             215,389   (−15,831)  no outcome yet
+ target_decision_date not null     162,270   (−53,119)  5 boroughs never publish it
+ borough QA gate                   157,455   (−4,815)   see below
```

**Borough QA gate — 2 thresholds:**

| Rule | Value | Rationale |
|---|---|---|
| min applications | 1,500 | below this a percentage is noise |
| min refusal rate | > 2% | a council recording ~0% refusals has a broken scrape |

**8 boroughs excluded:** Havering (**0.0% refusal rate — impossible**), Old Oak Park Royal,
Hammersmith and Fulham, Westminster, Haringey, London Legacy, Enfield, Hillingdon.

**5 boroughs never enter** because they publish no `target_decision_date` at all:
Brent, Wandsworth, Newham, Hounslow, Greenwich.

**Final analysis universe: 157,455 applications, 18 boroughs, 2018–2025.**
Both Part A and Part C use exactly this set.

**No imputation.** A missing agent becomes `has_agent = 0`, which is real information.

---

## 5. Columns we kept

**Categorical** (native in LightGBM/HistGradientBoosting — no one-hot needed):

| Feature | Distinct | Coverage | Note |
|---|---|---|---|
| `area_name` | 18 | 100% | the borough |
| `ward_top` | 201 | 98.1% | `ward_name` capped to top-200 + OTHER (832 raw levels exceeds the 255-bin categorical cap) |
| `app_type` | 5 | 99.2% | Full / Outline / Conditions / Amendment / None |

**Numeric:**

| Feature | Note |
|---|---|
| `borough_prior` | borough's bunch rate, **computed on training years only**, applied forward |
| `weekly_intake` | applications that borough received that week — workload proxy |
| `sub_year`, `sub_month`, `sub_dow` | submission timing |
| `desc_len`, `desc_words` | description length — proxy for scheme complexity |
| `has_agent` | a professional agent filed it (0/1) |
| `has_geo` | record has coordinates (0/1) |

---

## 6. Columns we dropped, and why

**Dropped as useless:**

| Column | Reason |
|---|---|
| `app_size` | **constant** inside our filter — every row is 'Small' |
| 10 × `kw_*` description flags | mutual information ≈ 0.0005. Engineered them, measured them, binned them |
| `agent_company` | 62% null, 11,140 distinct — too sparse to encode; `has_agent` keeps the usable part |
| `n_dwellings` | only **4.5%** filled |
| `development_type` | 16% filled and mostly junk — top value is *"Development monitoring information not needed"* |
| `applicant_name`, `agent_name`, `case_officer` | **redacted in the source** — one distinct value across all 343k rows |

**Dropped as LEAKAGE — knowable only after the decision:**

`decided_date` · the offset itself · `n_comments` · `decided_by` · `n_constraints` ·
`appeal_result` · `appeal_status` · `decision_issued_date` · `decision_published_date`

> This is the discipline that makes the model honest. An applicant asks *"will mine get
> caught in the rush?"* on the day they submit. On that day none of the above exists. A
> model using them would score brilliantly and be worthless.

**Fields from the original wish-list that the data cannot support:**
affordable-housing % (0.79% of descriptions mention "affordable"), viability/S106 (0.01%),
build-to-rent vs build-to-sell (**45 rows total**), transport infrastructure, developer
identity, planning performance agreements.

---

## 7. Models

Three, because the comparison is the finding.

| Model | Role |
|---|---|
| **Borough base rate** | baseline — predict each borough's historical rate. No learning |
| **Logistic regression** | interpretable reference. **This is the only model using one-hot** (`min_frequency=50`), plus standardised numerics |
| **HistGradientBoostingClassifier** | the reported model |

**Hyperparameters (HGB):** `max_iter=400`, `learning_rate=0.06`, `max_leaf_nodes=31`,
`min_samples_leaf=40`, `l2_regularization=1.0`, early stopping on a 15% validation slice.

**Why gradient boosting:** handles mixed categorical/numeric natively, needs no scaling,
captures interactions (borough × application type), fast on 157k rows.

---

## 8. Training and validation

**Time-based split — never random.** Random splitting would let 2025 rows train a model
tested on 2024, which is predicting the past from the future.

```
train  2018–2023   128,487 rows   base rate 22.2%
test   2024–2025    28,683 rows   base rate 19.2%
```

`borough_prior` is fitted on training years only and applied forward.

**Walk-forward backtest** — train on everything ≤ Y, test on Y+1:

| Train through | Test | n | base | baseline PR-AUC | HGB PR-AUC | lift |
|---|---|---|---|---|---|---|
| 2021 | 2022 | 18,671 | 0.203 | 0.2999 | 0.3144 | 1.048 |
| 2022 | 2023 | 15,634 | 0.215 | 0.3284 | 0.3675 | 1.119 |
| 2023 | 2024 | 13,431 | 0.192 | 0.3134 | 0.3706 | 1.182 |
| 2024 | 2025 | 15,252 | 0.193 | 0.2926 | 0.3204 | 1.095 |

Stable across all four folds. No single lucky year.

---

## 9. Results

| Model | PR-AUC | ROC-AUC | Brier |
|---|---|---|---|
| always-predict-base-rate | 0.1922 | 0.5000 | — |
| borough base rate | 0.3012 | 0.6685 | 0.1474 |
| logistic regression | 0.3295 | 0.6840 | 0.1448 |
| **HistGradientBoosting** | **0.3393** | **0.7017** | **0.1437** |

- **1.77× PR-AUC over the naive base rate**
- **1.13× over the borough baseline** — modest, and that modesty *is* the finding
- **precision@top-10% = 0.422** vs 0.192 base → **2.19× lift**

**Calibration** (predicted vs actual, by decile):

| decile | predicted | actual |
|---|---|---|
| 1 | 0.019 | 0.025 |
| 5 | 0.182 | 0.163 |
| 8 | 0.286 | 0.248 |
| 10 | 0.464 | 0.422 |

Well-ordered and close to the diagonal, mildly over-confident at the top. Good enough to
quote probabilities to a user; worth stating the over-confidence out loud.

---

## 10. Feature importance — and why the two methods disagree

**Permutation importance** (drop in PR-AUC when a feature is shuffled):

```
area_name      +0.0902
app_type       +0.0488
ward_top       +0.0348
desc_len       +0.0045
sub_dow        +0.0028
weekly_intake  +0.0022
borough_prior  +0.0000   <-- zero
```

**SHAP** (mean |SHAP|, LightGBM parity model):

```
borough_prior  0.4984   <-- dominant
app_type       0.2991
ward_top       0.2046
area_name      0.1372
sub_year       0.0912
```

**They contradict each other on `borough_prior`, and the reason matters.**

`borough_prior` and `area_name` encode the *same information* — one as a number, one as a
label. Permutation importance shuffles one feature at a time, so when `borough_prior` is
destroyed the model simply reads `area_name` instead and loses nothing → importance 0.
SHAP attributes credit across correlated features differently, and gives most of it to
`borough_prior` because the trees split on it first as a clean numeric threshold.

**Neither is wrong. Together they say: geography is doing nearly all the work, and it
doesn't matter which of the two columns carries it.** Reporting only one method would have
hidden that.

**SHAP direction — which values push the prediction up:**

| Pushes toward bunching | | Pushes away | |
|---|---|---|---|
| Kingston | +0.317 | Southwark | −0.236 |
| Lewisham | +0.221 | Sutton | −0.200 |
| Islington | +0.105 | Richmond | −0.174 |
| Bexley | +0.089 | Merton | −0.152 |

| `app_type` | mean SHAP |
|---|---|
| Full | +0.305 |
| Amendment | −0.062 |
| Outline | −0.292 |
| Conditions | −0.403 |

**Worked example** — highest-risk application in the test sample, predicted **85.8%**:

```
ward_top       Old Malden        SHAP +1.115
borough_prior  0.393             SHAP +0.686
sub_month      January           SHAP +0.440
app_type       Full              SHAP +0.398
area_name      Kingston          SHAP +0.388
```

*(Actual outcome: not bunched. Kept deliberately — the top-risk case that didn't happen.)*

---

## 11. The interpretation

The model beats a borough lookup by only **13%**. Case-level features — what you're
building, how complex it is, when you filed — add almost nothing once the borough is known.

> **Whether your application gets caught in the deadline rush is a property of your
> council, not of your application.**

That closes the loop with Part A: the deadline distorts decisions, and the distortion is
**institutional, not case-driven**.

**Supporting negative result:** workload does *not* explain bunching. By weekly-intake
quintile the bunch rate runs 22.4% / 22.1% / 21.1% / **19.6%** / 22.9% — flat, and the
busiest quintile is not the worst. "They're just overloaded" is the second objection you
will get, and the data does not support it.

---

## 12. Limitations — state these before anyone else does

1. **Observational, not causal.** Deciding at the deadline is *associated* with refusal.
   Not proven to cause it.
2. **18 of 33 boroughs.** Five publish no target date; eight fail data quality. Not
   London-wide.
3. **Small/minor applications only.** Majors run on a 13-week clock and are excluded.
4. **`app_size = 'Small'` is a proxy** for the statutory minor/householder class, not a
   verified mapping.
5. **`target_decision_date` semantics inferred** from the data, not confirmed against a
   borough portal.
6. **Self-collected scrape**, not an official release. Field conventions vary by borough.
7. **Calibration is mildly over-confident** in the top decile (0.464 predicted vs 0.422
   actual).
8. **Simplified counterfactual.** Part A uses a ±8-day local mean rather than a polynomial
   density fit. Sensitivity: every window from ±3 to ±14 gives 7.7×–12.8×, and
   median-based gives 13.5×–19.7×. **Our quoted 10.2× is among the more conservative.**

---

## 13. Reproduce

```
notebooks/01_artifact_checks.py   six robustness checks on the bunching finding
notebooks/02_correct_clock.py     corrected clock + refusal discontinuity
notebooks/03_build_findings.py    filters + QA gate -> outputs/findings.json
notebooks/04_eda.py               feature EDA + mutual information -> model_frame.parquet
notebooks/05_model.py             3 models, time split, walk-forward -> model_results.json
notebooks/06_shap.py              LightGBM parity + SHAP -> shap_results.json
notebooks/07_approval_model.py    approval model + bunch/approval link
notebooks/08_build_tool_data.py   borough x type lookup -> tool_data.json
notebooks/09_text_model.py        TF-IDF ladder: does text add signal?
notebooks/10_export_live_model.py browser-runnable model export -> live_model.json
notebooks/11_text_deep_dive.py    archetypes, full metrics, walk-forward -> text_deep_dive.json
```

Run from inside `notebooks/`. Requires `pandas numpy scikit-learn scipy lightgbm shap pyarrow`.

---
---

# Part D — the `description` column and the approval model

## 14. What the `description` column is

The single most valuable column in the dataset, and the one we nearly wasted.

| | |
|---|---|
| Column | `description` |
| Coverage | **100%** — every one of 343,141 rows |
| Median length | **128 characters, 21 words** |
| Longest | 3,249 characters |
| Content | The applicant's own free-text summary of what they are proposing |

**Verbatim samples:**

```
[APPROVED] Single storey front, side and rear extension incorporating porch.
[APPROVED] Erection of a first floor side extension and a single storey rear extension.
[APPROVED] Prior notification for the demolition of a fire damaged part two storey former warehouse.
[APPROVED] Change of use from education (Use Class F1) to a single dwelling house (Use Class C3)
[REFUSED ] Part one/ part two storey side and rear extension and alterations to provide
           two x two bed apartments and 1x1 bed dwelling.
```

**The mistake we made first.** In §6 we tested ten hand-picked keyword flags (`extension`,
`loft`, `dwelling`, `demoli`, …) and measured mutual information ≈ 0.0005 — noise. We
concluded the text was useless and dropped it.

That was a bad test, not a bad column. Ten binary flags throw away word order, phrase
structure, and 9,000 other terms. Doing it properly reversed the conclusion completely.

---

## 15. Text vectorisation — exactly what we used

**`sklearn.feature_extraction.text.TfidfVectorizer`**

| Parameter | Value | Why |
|---|---|---|
| `ngram_range` | `(1, 2)` | unigrams + bigrams. "storey" alone is ambiguous; "two storey" is not |
| `min_df` | `30` | a term must appear in ≥30 applications to be kept |
| `max_features` | `20000` | cap; actual vocabulary came out at **9,343 terms** |
| `sublinear_tf` | `True` | tf = 1 + log(count) — stops repeated words dominating |
| `token_pattern` | `\b\w\w+\b` | words of 2+ characters |
| `lowercase` | `True` | |
| normalisation | L2 (sklearn default) | so long descriptions don't outweigh short ones |

**TF-IDF in one line:** a word matters more if it appears often in *this* application
(term frequency) and rarely across *all* applications (inverse document frequency).
"extension" is everywhere, so it counts for little. "self contained" is rare and
informative, so it counts for a lot.

We also tested **character n-grams** (`char_wb`, 3–5, 21,578 features). They added
+0.0007 ROC-AUC — not worth the complexity, and impossible to replicate exactly in the
browser. **Dropped.**

---

## 16. The ladder — proving text was the missing signal

Each step adds one thing. Same time split throughout (train ≤2023, test ≥2024),
logistic regression, evaluated on 28,027 held-out later decisions.

| Step | Features | ROC-AUC | Refusal PR-AUC |
|---|---|---|---|
| 1 | borough only | 0.5619 | 0.2140 |
| 2 | + application type, ward, timing | 0.5762 | 0.2251 |
| **3** | **+ TF-IDF description** | **0.7110** | **0.3752** |
| 4 | text alone (no borough at all) | 0.7023 | 0.3644 |

**+0.135 ROC-AUC. Refusal PR-AUC up 67%.**

**Step 4 is the intellectually important one.** Text alone (0.7023) nearly matches
text + location (0.7110). So:

> **What you build determines *whether* you are approved.
> Where you are determines *when* you are decided.**

Two models, two different dominant factors, one coherent story.

---

## 17. What the text actually learned

**Words most associated with REFUSAL** (logistic coefficients):

```
two storey     −0.646     bedroom        −0.447     self contained  −0.340
height of      −0.604     flats          −0.424     proposed depth  −0.316
two            −0.487     dwelling       −0.396     eaves height    −0.366
```

**Words most associated with APPROVAL:**

```
of single      +0.655     ground floor   +0.329     rooflights      +0.285
single storey  +0.488     roof lights    +0.328     prune           +0.266
single         +0.451     rear           +0.324     amended         +0.254
```

### ⚠️ Coefficients are conditional, not marginal — do not confuse them

A coefficient says "holding all other words constant." The **observed** approval rate
for a category can differ, because categories are compared against a mixed pool.

**Approval rate by what is actually being proposed** (base rate 79.9%):

| Development type | n | Approved | vs base | Median days |
|---|---|---|---|---|
| Trees / hedge works | 3,521 | 85.3% | **+5.5** | 56 |
| Rooflights / skylights | 40,144 | 84.1% | +4.2 | 56 |
| Basement / excavation | 6,212 | 84.0% | +4.2 | 62 |
| Demolition involved | 26,809 | 82.5% | +2.6 | 58 |
| Loft conversion / dormer | 40,480 | 81.8% | +2.0 | 56 |
| Additional storey on top | 24,084 | 81.3% | +1.4 | 56 |
| Single storey extension (any) | 64,349 | 79.5% | −0.4 | 55 |
| Outbuilding / garage | 15,936 | 78.5% | −1.3 | 58 |
| Single storey rear extension | 44,454 | 77.7% | −2.1 | 51 |
| **Two storey extension** | 12,897 | **73.3%** | **−6.5** | 61 |
| **Erection of new dwelling(s)** | 9,803 | **72.2%** | **−7.7** | 56 |
| **Change of use** | 10,152 | **67.6%** | **−12.2** | 61 |
| **Conversion into flats** | 3,812 | **65.7%** | **−14.2** | 68 |

**Note that "single storey rear extension" (77.7%) is *below* the 79.9% base**, even
though "single storey" has a positive coefficient. Both are true. The coefficient is
conditional; the table is marginal.

**The like-for-like comparison that IS safe to quote:**

| Storeys stated in the description | n | Approved |
|---|---|---|
| Single storey | 67,252 | **79.5%** |
| Two storey | 12,720 | **73.0%** |
| Three storey | 1,462 | 73.5% |
| Four or more | 1,454 | 85.3% * |
| Not stated | 66,934 | 81.6% |

\* *four-plus is a small, unusual group (often commercial conversions) — do not read a trend into it.*

**Mechanism: the model is not reacting to the phrase "single storey". It is reacting to
scale, and to change of use.** Ask for more, or ask to change what a building is for, and
refusal risk rises. Conversion into flats is the single worst category in the dataset.

---

## 18. Approval model — full metrics

**Model:** `LogisticRegression(C=1.0, solver='liblinear', max_iter=2000)` on
`hstack([TF-IDF(9,343), OneHot(borough, app_type)])`.

**Why logistic regression rather than boosting:** on high-dimensional sparse text it
matches tree ensembles, every coefficient is directly interpretable (so the page can show
*which words moved your prediction*), and it exports to ~1 MB of JSON that runs in a
browser. Interpretability and deployability, not accuracy, decided this.

**Split:** train 122,806 (2018–2023) · test 28,027 (2024–2025). Time-ordered, never random.

| Metric | Value | Baseline | Read as |
|---|---|---|---|
| ROC-AUC | **0.7103** | 0.5619 borough-only | ranking quality overall |
| PR-AUC (approval) | **0.9049** | 0.8103 | majority class — flattering, report but don't lead |
| **PR-AUC (refusal)** | **0.3759** | 0.1897 | **1.98× — the metric that matters** |
| Brier | **0.1395** | 0.1537 | probability accuracy, lower is better |
| Max calibration error | **0.060** | — | worst bin gap |

**Calibration** — predicted vs actual, 10 bins:

```
0.487 → 0.547     0.824 → 0.821     0.922 → 0.915
0.651 → 0.680     0.856 → 0.873     0.964 → 0.953
0.727 → 0.747     0.876 → 0.894
0.782 → 0.791     0.896 → 0.884
```

Monotone and close to the diagonal. Slightly under-confident at the low end (says 49%,
delivers 55%) — i.e. it errs toward pessimism on risky applications, which is the safer
direction for a public tool.

**Precision / recall for flagging refusals:**

| Flag if P(approve) < | Flagged | Caught | Precision | Recall | F1 |
|---|---|---|---|---|---|
| 0.40 | 489 | 306 | **62.6%** | 5.8% | 10.5% |
| 0.50 | 1,291 | 663 | 51.4% | 12.5% | 20.1% |
| 0.60 | 2,814 | 1,271 | 45.2% | 23.9% | 31.3% |
| 0.70 | 5,883 | 2,250 | 38.2% | **42.3%** | 40.2% |

**Confusion matrix at threshold 0.60** (predicting refusal):

```
                    predicted OK    predicted REFUSAL
  actually OK            21,168               1,543
  actually REFUSED        4,045               1,271
```

**Accuracy 80.1% — against 81.0% for "always say approved."** The model is *more useful*
and *less accurate*. That is the clearest possible demonstration of why accuracy is the
wrong metric on an imbalanced problem.

**Walk-forward backtest** — retrain each year, test on the next:

| Train through | Test | n | ROC-AUC | Refusal PR-AUC | Base refusal |
|---|---|---|---|---|---|
| 2020 | 2021 | 20,914 | 0.7033 | 0.3821 | 0.199 |
| 2021 | 2022 | 17,903 | 0.6971 | 0.3766 | 0.193 |
| 2022 | 2023 | 14,993 | 0.7119 | 0.4007 | 0.210 |
| 2023 | 2024 | 12,895 | 0.7139 | 0.3939 | 0.199 |
| 2024 | 2025 | 14,850 | 0.7164 | 0.3778 | 0.183 |

**mean 0.7085, sd 0.0072, range 0.6971–0.7164.** Five independent years, no drift, no
lucky fold. This is the strongest confidence statement we have about the model.

---

## 19. Running the model in the browser

A logistic regression is a dot product, so it can run client-side. We export the TF-IDF
vocabulary with its IDF weights, the fitted coefficients, and the borough/type effects
(~1.4 MB JSON), then re-implement `TfidfVectorizer.transform` in JavaScript:
lowercase → `\b\w\w+\b` tokens → unigrams + bigrams → `1 + log(tf)` → `× idf` → L2 norm →
dot with coefficients → sigmoid.

**Verified against sklearn on six held-out descriptions:**

| Description | sklearn | browser |
|---|---|---|
| Single storey rear extension with rooflights | 0.8684 | 0.8684 |
| Two storey side extension and loft conversion | 0.4889 | 0.4890 |
| Conversion of dwelling into 3 self contained flats | 0.1953 | 0.1953 |
| Loft conversion with rear dormer | 0.9028 | 0.9028 |

**Maximum absolute difference: 0.00003.** The page is running the real model, not an
approximation.

The page also ships a stratified sample of **6,480 real applications** and does cosine
similarity against them in-browser, so it can answer *"here is what happened to
applications like yours"* — the similarity-search idea suggested in Brief DD.

---

## 20. Extra limitations introduced by the text model

9. **Descriptions are written by applicants and agents**, not standardised. Wording
   conventions vary by borough and by agent, so some signal is stylistic rather than
   substantive.
10. **Coefficients are conditional.** Quoting them as marginal approval rates is wrong —
    see §17.
11. **The model cannot see the design.** It reads a 21-word summary, not drawings, site
    constraints, or officer negotiation. A 0.71 ROC-AUC is a ceiling imposed by that.
12. **Not causal, and not advice.** Rewording an application does not change its odds —
    the words are a proxy for what is actually being proposed.

---

## 21. Model C — how long will the decision take?

**Question.** Given only what's known at submission, how many days until a decision?

**Why quantile regression rather than a single prediction.** Decision time is heavily
right-skewed with a spike at the deadline (that's finding A). A single number would be
false precision — "56 days" hides that 1 in 10 takes over 104. So we predict a **range**.

**Model.** `HistGradientBoostingRegressor(loss="quantile", quantile=q)` fitted three times
at q = 0.25, 0.50, 0.90. `max_iter=300`, `learning_rate=0.07`, `max_leaf_nodes=31`,
`min_samples_leaf=40`, early stopping on 15%.

**Features.** TF-IDF of the description reduced to **60 SVD components** (44.0% of variance
— trees need dense input), plus borough, application type, submission month and year, and
description length. Train 121,781 · test 28,026, time-split as everywhere else.

**Evaluation — pinball loss**, the correct loss for quantile prediction (it penalises
under- and over-prediction asymmetrically, matched to the quantile being estimated):

| Quantile | Pinball loss | Baseline* | Improvement |
|---|---|---|---|
| 0.25 | 6.412 | 8.436 | **24.0%** |
| 0.50 | 9.368 | 11.144 | **15.9%** |
| 0.90 | 7.091 | 8.540 | **17.0%** |

\* *baseline = the global training quantile, ignoring every feature.*

**Median prediction, in plain terms:**

| | MAE |
|---|---|
| **Model** | **18.7 days** |
| Borough median lookup | 22.2 days |
| Global median (always say 56) | 22.3 days |

**15.9% better than guessing the median, 15.4% better than a borough lookup.**

**Quantile calibration** — a p90 prediction should be beaten 90% of the time:

| | Actual | Target |
|---|---|---|
| ≤ predicted p25 | 30.7% | 25% |
| ≤ predicted p50 | 53.0% | 50% |
| ≤ predicted p90 | **89.8%** | **90%** |
| inside p25–p90 band | 59.1% | 65% |

**The p90 is very well calibrated** (89.8% vs 90%), which is the one that matters for
"worst case, how long?". The p25 is slightly conservative.

**Worked examples** (predicted p25 / p50 / p90, then what actually happened):

```
Bexley     Full     55 /  57 / 100   actual  50   "erection of a single storey rear extension"
Richmond   Full     48 /  55 /  97   actual  56   "single storey side and rear extension"
Merton     Full     62 / 100 / 266   actual 160   "part demolition and upward and rear extension"
Islington  Full     52 /  59 / 112   actual  90   "erection of rear roof dormer with refurbishment"
```

Note the Merton row: the model correctly flagged a complex demolition-plus-extension as a
long one (p50 = 100 days) and it took 160. That is the model working.

**Limitation.** MAE of 18.7 days is a wide error bar on a 56-day median. The model is
useful for "is this a 2-month or a 5-month job" and useless for "will it be Tuesday".
Present it as a range, never a date.

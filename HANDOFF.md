# HANDOFF — The Spike

> **Read this first in a new terminal.** Everything that was in the build session, in one
> place: what this is, where the data lives, what each script does, every number, every
> decision and why, and the traps already hit.
>
> Built 1 August 2026 at House London #0 (Newspeak House). Team **Spike Girls SB**.
> Last updated 8 August 2026.

---

## 1. What this is

A one-day data sprint entry for **House London #0**, Data Brief DD
(*"What does the approvals data actually say?"*), bent into our own question.

**The finding:**
> London councils have 8 weeks to decide a planning application. They hit that target by
> deciding on the last legal day — and those decisions are approved **10 points** less
> often.

**Live repo:** https://github.com/dsridhar2110/the-spike (public, `main`)
**Local:** `/Users/shamanth/Desktop/Cursor/Deeksh Personal/portfolio-work/repos/London Hackathon`

---

## 2. The data — where it is and where it came from

| | |
|---|---|
| File | `data/raw/housing.sqlite` — **1.4 GB**, present locally, **git-ignored** |
| Table | `applications_tidy` — **343,141 rows × 89 columns** |
| Coverage | 33 London boroughs, 2016-02-07 → 2026-03-06 |
| Drive source | https://drive.google.com/file/d/11XVe6fYsRgoX_9goX1IA1g1e3fjvlnpY/view |
| Drive folder | House London Drive → `Planning Permission Analysis Repo/analysis/outputs/` |

**Provenance:** 33 borough planning portals → [UK PlanIt](https://www.planit.org.uk/)
(volunteer aggregator, Andrew Speakman) → scraped + housing-relevance filtered by **Jamie
Coombes** → hackathon Drive.

**Getting it again:** Drive throws a virus-scan interstitial on files this size. Fetch the
confirm token first, then download with `confirm=t&uuid=…`. The plain
`uc?export=download` URL returns an HTML warning page, not the file.

### Also in `data/raw/` — DO NOT COMMIT OR SHARE
`wheretobuild_msoa_stats.csv` — the WhereToBuild MSOA extract (Warwick CAGE). Licence:
event-only, no public upload, delete after event, outputs need Dr Kulka's and Dr Datta's
approval. **We never used it.** Nothing in the project or the repo depends on it.

### Columns that matter
`area_name` · `ward_name` · `app_type` · `app_size` · `description` (100% filled) ·
`start_date` · `target_decision_date` · `decided_date` · `app_state` · `lat`/`lng` ·
`agent_company` · `appeal_result`

### Columns that are dead
`applicant_name`, `agent_name`, `case_officer` — **redacted in source**, one distinct value
across all 343k rows. `n_dwellings` — 4.5% filled. `development_type` — 16% filled and
mostly junk (top value is literally *"Development monitoring information not needed"*).

---

## 3. The analysis universe (how 343k became 150k)

```
all rows                            343,141
+ app_size = 'Small'                307,042   8-week statutory class; majors get 13 weeks
+ start_date >= 2018-01-01          231,220   earlier scrape coverage is patchy
+ decided_date not null             215,389   no outcome yet
+ target_decision_date not null     162,270   5 boroughs never publish it
+ borough QA gate                   157,455   see below
+ decided outcomes only             150,879   drops Withdrawn/Undecided (used by the page)
```

**Borough QA gate:** min 1,500 applications, min 2% refusal rate.

**8 boroughs excluded:** Havering (**0.0% refusal — impossible, broken scrape**),
Old Oak Park Royal, Hammersmith and Fulham, Westminster, Haringey, London Legacy, Enfield,
Hillingdon.

**5 boroughs never enter** (publish no `target_decision_date`): Brent, Wandsworth, Newham,
Hounslow, Greenwich.

**4 boroughs are not in the dataset at all:** Camden, Hackney, Harrow, City of London.

**→ 18 boroughs, 2018–2025.**

---

## 4. Every number, verified

### The spike
| | |
|---|---|
| Decisions analysed | **150,879** |
| Land on the council's own deadline | **33,227** — 22.0%, "1 in 5" |
| Neighbouring-day average | **3,204** |
| Excess mass | **10.4×** |
| Day before / after | 10,476 / 2,196 |
| Sensitivity (±3 to ±14 window) | 7.7× – 12.8×; median-based 13.5× – 19.7× |

### The cost
| | |
|---|---|
| Approved normally → in the rush | **82.1% → 71.9%** (−10.2) |
| Boroughs showing the drop | **16 of 18** |
| Worst | Islington 82.1% → 59.5% (**−22.6**) |
| Kensington *(used in pitch)* | 92.8% → 82.9% (**−9.9**) |
| Exception *(used in pitch)* | Barking and Dagenham 72.3% → 75.7% (**+3.4**) |
| Other exception | Waltham Forest 74.5% → 74.9% (+0.4) |
| Most / least bunching | Kingston **38.9%** · Merton **1.6%** |

### The map
Approval: Southwark **92.0%** high, Barking and Dagenham **73.4%** low.
Decision time: Redbridge **45 days** fast, Bromley **63 days** slow.

### Feature discovery (London, base **79.9%**)
| Above average — changes the building | | Below — changes use/households | |
|---|---|---|---|
| Rooflights / skylights | 84.1% | New dwelling | 70.5% |
| Basement / excavation | 84.0% | Change of use | 67.8% |
| Demolition involved | 82.4% | Conversion into flats | 66.1% |
| Loft conversion / dormer | 81.8% | | |
| Extra storey on top | 81.2% | | |

**Weighted: 81.0% vs 68.1% — a 12.9-point gap. Perfect separation** (lowest
building-change category, two-storey extensions 73.7%, still beats highest
density category, new dwellings 70.5%).

**Closing stat:** 17,641 home-creating applications, ~5,634 refused (32% vs 19% elsewhere)
→ **~2,283 more refusals** than the 81% rate would give.

### Models
| | |
|---|---|
| Approval classifier | ROC-AUC **0.7103** · refusal PR-AUC **0.3759** (base 0.1897) · Brier **0.1395** |
| Ladder | borough only 0.5619 → +type/ward/timing 0.5762 → **+TF-IDF 0.7110** → text alone 0.7023 |
| Walk-forward | 0.7033 / 0.6971 / 0.7119 / 0.7139 / 0.7164 → **0.7085 ± 0.0072** |
| Timing model | MAE **18.7 days** vs 22.2 borough lookup; p90 coverage 89.8% vs 90% target |
| Bunching model (timing) | PR-AUC 0.3393 vs 0.3012 borough baseline = **1.13×** |
| Split | train 2018–2023 (122,806) · test 2024–2025 (28,073) |

---

## 5. What's in the folder

```
site/index.html          THE DELIVERABLE — 1.5 MB, self-contained, works offline
site/template.html       source with __DATA__ __TOOL__ __MODEL__ __LIVE__ __DAYS__
                         __MAP__ __APPR__ __TDD__ __PB__ __PREDICTOR__ __VISUALS__
site/predictor.js        browser TF-IDF + logistic regression
site/visuals.js          drawMap / drawSlope / drawTypes / drawBunch
build.py                 inlines JS + JSON into site/index.html  ← run after ANY edit
notebooks/01..15         the analysis, in order
outputs/*.json           tracked — the page needs them
outputs/*.png            dev screenshots, git-ignored
data/raw/                git-ignored (1.4 GB sqlite + the licensed CSV)
docs/                    git-ignored — organisers' briefs, not ours to republish
README.md METHOD.md PITCH.md BRIEF.md HANDOFF.md LICENSE requirements.txt
```

**Edit `template.html`, never `index.html`.** Then `python build.py`.

### The notebooks
| | |
|---|---|
| `01_artifact_checks.py` | six robustness checks on the spike |
| `02_correct_clock.py` | corrected clock + refusal discontinuity |
| `03_build_findings.py` | filters + QA gate → `findings.json` |
| `04_eda.py` | mutual information → `model_frame.parquet` |
| `05_model.py` | 3 timing models, time split, walk-forward |
| `06_shap.py` | LightGBM parity model + SHAP |
| `07_approval_model.py` | approval model + the bunch/approval link |
| `08_build_tool_data.py` | borough × type lookup |
| `09_text_model.py` | **the TF-IDF ladder — the key experiment** |
| `10_export_live_model.py` | browser-runnable model export |
| `11_text_deep_dive.py` | archetypes, full metrics, walk-forward |
| `12_days_model.py` | quantile regression on decision time |
| `13_export_days_grid.py` | decision-time lookup grid |
| `14_build_map.py` | simplified London borough map |
| `15_per_borough.py` | per-borough aggregates |

`14_build_map.py` needs a borough GeoJSON at `/tmp/t.json`:
`curl -sL https://raw.githubusercontent.com/radoi90/housequest-data/master/london_boroughs.geojson -o /tmp/t.json`

---

## 6. The page, section by section

1. **Hero** — "The **Spike** GIRLS", gradient wordmark, number-led standfirst
2. **The map** — 2 toggles (Approval rate / Decision time), blue sequential ramp,
   click any borough for a card. Defaults to **Southwark**. Grey = no data, pink dashed =
   flagged (Havering)
3. **1 in 5 decisions lands on the deadline day** — the spike, day-0 bar in red
4. **16 of 18 boroughs approve less** — aligned bars, green→red gradient, sorted by damage
5. **Feature discovery** — diverging bars vs the 79.9% average
6. **The classifier** — live text model, comparables hidden behind "What actually happened?"
7. **The Science behind it all** — 9-row spec table

**Colour rules as settled:** blue = numbers/context · red = the problem · gradient
(blue→violet→red) reserved for three moments only — **Spike**, **The classifier**,
**The Science**. Small headings are plain ink, not gradient.

---

## 7. Decisions made, and why

- **Brief DD, not DB.** DB (WhereToBuild) was the dataset everyone was handed — the room
  would be full of the same map. DD came with 343k rows most teams wouldn't find.
- **`target_decision_date`, not `start_date + 56`.** `start_date` is the *receipt* date;
  the statutory clock runs from *validation*. Measuring against each council's own target
  also kills the "deadline extensions" objection, because that field moves when an
  extension is agreed.
- **Logistic regression, not boosting, for approval.** On sparse text it matches trees,
  every coefficient is interpretable (the page shows which words moved the prediction), and
  it exports to ~1.4 MB of JSON that runs client-side.
- **Quantile regression, not point prediction, for timing.** MAE is 18.7 days on a 56-day
  median — a single number would be false precision.
- **Real observed rates in the tool, not model output**, for approval baselines. "This is
  what happened to 6,844 applications like yours" is easier to trust than a 0.64 model.
- **Havering flagged, not hidden.** Colouring it naively would make it look like London's
  best council. It's a broken scrape, and saying so is a credibility moment.
- **Comparables split by outcome.** The corpus is 80% approved, so a plain top-10 nearest
  neighbours contradicted a 49% prediction. Now grouped as *closest refusals* / *closest
  approvals* and labelled examples-not-a-rate.

---

## 8. Traps already hit — don't repeat them

- **Douglas-Peucker on a closed ring** collapses to 2 points, because the first and last
  point are identical so the initial segment has zero length. Split the ring at the
  farthest point first. *(`14_build_map.py`)*
- **SVG gradients on a horizontal line render nothing** in default `objectBoundingBox`
  units — zero-height bounding box. Use `gradientUnits="userSpaceOnUse"` with real
  coordinates. *(`visuals.js`)*
- **`<span>` ignores width/height.** Bar fills rendered empty until `display:block`.
- **SHAP's TreeExplainer doesn't support sklearn's `HistGradientBoosting`.** Refit the same
  architecture in LightGBM, check parity first (we got ΔPR-AUC 0.0018), then explain that.
- **Permutation importance and SHAP disagreed on `borough_prior`** (0.0000 vs top feature).
  Not a bug — they're collinear with `area_name`. Report both.
- **Ten keyword flags on `description` measured MI ≈ 0.0005 and we nearly dropped the
  column.** Proper TF-IDF lifted ROC-AUC by +0.135. Bad test, not a bad column.
- **Two different numbers for the same bar** — chart read `per_borough.json`, caption read
  `findings.json`, different row filters. Always derive a caption from the record the chart
  draws.
- **Diverging colour ramp indexed backwards** made Islington (the worst borough) render
  pale. Sanity-check colour against actual values.
- **Sorting comparables to show only refusals** would have been cherry-picking. Splitting by
  outcome and labelling is the honest version.

---

## 9. Open items

- **Jamie Coombes (`jcoombes`, id 12532438)** has a **pending collaborator invite** on the
  repo. Credited first in README. Not added as commit co-author — he didn't write the code.
- **`AGENTIC-BUILD-BRIEF.md`** is in the folder but wasn't part of this build — untouched.
- **554 hectares / 171,000 homes** was raised as a possible closing stat. **It is not from
  our data** and has no verified source. The closing uses our own 17,641 / 5,634 / 2,283
  instead.
- **Not verified:** that `app_size='Small'` maps exactly to the statutory minor/householder
  class, and `target_decision_date`'s exact semantics against a borough portal.
- Twelve stated limitations are in `METHOD.md` §12 and §20.

---

## 10. House rules for this repo

- Commits are authored **dsridhar2110 <dsridhar2110@users.noreply.github.com>** — set as
  local git config. Never Shamanth, never a Claude co-author trailer.
- Never commit `data/`, `docs/`, or `outputs/*.png`.
- The WhereToBuild CSV must not be uploaded anywhere, ever.

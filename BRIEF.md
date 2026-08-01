# House London #0 — Working Brief

> Everything we know about today's hackathon, in one place.
> Compiled 1 Aug 2026 from the intro PDF + the House London Google Drive.

---

## 1. The event in one paragraph

**House London #0** is a one-day data sprint at **Newspeak House, 133 Bethnal Green Rd,
London E2 7DG**, on **Saturday 1 August 2026**. It's the first of a monthly series
(September and October to follow). The premise: *London has a housing crisis, and the data
to understand it — and argue for fixing it — already exists.* Teams of up to 4 take
London's planning and housing data and produce the most compelling, well-evidenced story
they can. Output can be a **policy brief, a dashboard, or a model** — all three compete
on the same scoreboard.

**Prize:** £150 cash today, £500 across the series.
**Wi-Fi:** SSID `Newspeak House` / password `telescreen`

---

## 2. Schedule — the constraint that shapes everything

| Time | Block |
|---|---|
| 10:00 | Doors, registration, coffee |
| 10:30 | Welcome + framing + build-brief walkthrough |
| 11:00 | **Team formation** — up to 4 people, pick a team name |
| 11:30 | Hacking begins |
| **12:15** | **Idea-lock checkpoint** ← decision deadline |
| 14:00 | Lunch |
| 16:00 | Mentor / organiser walk-round |
| **17:00** | **Hard stop.** Submissions into GitHub or Drive |
| 17:00–17:30 | Voting setup |
| 17:30–19:00 | **Demos — 3 minutes per team**, to the whole room |
| 19:00–19:30 | Results, prizes, close |
| 19:30+ | Informal social |

**Real build time: ~5 hours** (11:30 → 17:00, minus lunch). Scope accordingly.

---

## 3. How judging actually works — read this before choosing

- **Community vote.** Fellow hackers score each team, **one rating out of 10**, via a
  Google Form. Not a judging panel, not a rubric.
- **Apples vs. oranges by design.** Data, Policy and Software entries all score on the
  same night, on the same single scale.
- **Brief conformity is explicitly NOT scored.** From the brief doc:
  > *"Remember that scoring is just about community-voted rating. You won't be rigorously
  > evaluated against conformity with the brief. Feel free to modify the briefs and make
  > them your own."*
- You're told to **pick a main brief and a backup**, in case you need to pivot mid-day.

**What this means in practice:** the winning entry is the one a tired room understands and
remembers after a 3-minute pitch. **One surprising, defensible finding + one great visual +
a clean narrative** beats model sophistication. Nobody will read your code.

Prior scores logged on the winner sheet so far: `Anonymous Zebras — 4`,
`Houses for birds — 10`. Only one submission is currently in the Drive
(`Anonymous Antelopes`). Small field.

---

## 4. What we've actually been given

### 4.1 In this folder — files in hand

```
London Hackathon/
├── BRIEF.md                                  ← this file
├── docs/
│   ├── Introduction to House London #0.pdf   the event brief (original)
│   ├── data-briefs.md                        Briefs DA–DE + DF–DL (full text)
│   ├── policy-briefs.md                      Briefs PA–PD + PE–PI (full text)
│   ├── data-asset-register.csv               ~25 catalogued housing datasets
│   ├── wheretobuild-data-use-conditions.md   the licence — READ IT
│   └── house-repo-README.md                  what's inside Jamie's `house` repo
├── data/raw/
│   ├── wheretobuild_msoa_stats.csv           THE ONLY ACTUAL DATASET WE HAVE
│   └── _original.zip                         as downloaded from Drive
├── notebooks/                                (empty — ours)
└── outputs/                                  (empty — ours)
```

### 4.2 The one dataset we hold: `wheretobuild_msoa_stats.csv`

A custom MSOA-level extract from the **WhereToBuild** project (Warwick CAGE — Dr Nikhil
Datta & Dr Amrita Kulka), built on ~20bn Rightmove searches + listings, 2019–2024.

**Shape:** 8,598 rows × 5 columns. One row per MSOA, no duplicates. **England-wide**, not
London-only — roughly **932 rows** fall in the London MSOA code range
(`E02000001`–`E02000983`).

| Column | Type | Profile (all England) | What it appears to be |
|---|---|---|---|
| `msoa_code` | string | 8,598 unique, `E02…` | ONS MSOA code. **The only join key.** |
| `area_km2` | float | p25 1.53 · med 2.89 · p95 123.0 | MSOA land area |
| `gap` | float | p05 31 · med 517 · p95 1,797 · min −6,914 | Demand minus supply, in listing/search units |
| `tightness` | float | p05 1.13 · med 5.23 · p95 19.3 | Demand ÷ supply ratio |
| `gap_per_km2` | float | p05 0.97 · med 160 · p95 725 | `gap` normalised by area — density of unmet demand |

**Verified structural facts:**
- `gap < 0` occurs in exactly **322 rows (3.7%)**, and `tightness < 1` occurs in exactly
  the same 322 rows → confirms `gap` and `tightness` are two views of the same
  demand-vs-supply comparison (difference vs. ratio).
- **`corr(gap, tightness) = 0.08`** — near zero. They rank areas *completely differently*.
  A high-`gap` MSOA is not a high-`tightness` MSOA. That's an analytical hook, and also a
  trap if you conflate them.
- London vs. England: median `tightness` **2.86 vs 5.23** (London *lower*), but median
  `gap_per_km2` **383 vs 160** (London 2.4× *higher*).
- Only **3 of 932** London MSOAs have supply exceeding demand.

**⚠️ What's missing and must be sourced before anything is visual:**
- **No geometry.** No polygons, no lat/long.
- **No names.** No borough, ward, or MSOA name — just codes.
- **No data dictionary.** The exact definitions of `gap` and `tightness`, and their units,
  are **not documented anywhere in the Drive**. The interpretations above are inferred
  from the numbers. **Ask the organisers to confirm before putting them on a slide.**

→ First task of the day: pull MSOA 2021 boundaries + the MSOA→borough lookup from
**ONS Open Geography Portal** (`geoportal.statistics.gov.uk`) and join on `msoa_code`.
Budget 20–30 minutes. Nothing is mappable until this is done.

### 4.3 ⚠️ WhereToBuild licence — binding, and it constrains the deliverable

Signed by the organiser (Jamie Coombes, Newspeak House, 2026-07-31). Each participant is
asked to individually confirm agreement. Terms:

1. Hackathon and related **non-commercial** use only.
2. Access limited to registered participants who have agreed.
3. **Not to be redistributed, uploaded publicly, or shared outside the event.**
4. Do not identify, name, or speculate about the underlying data provider (i.e. don't
   name Rightmove in outputs), or attempt to reconstruct underlying records.
5. **Required attribution on any output:**
   > *Source: WhereToBuild project, CAGE, University of Warwick. Data provided by
   > Dr Amrita Kulka and Dr Nikhil Datta.*
6. **Public-facing outputs must be approved by Dr Kulka and Dr Datta before publication
   or wider circulation.**
7. **Delete the data after the event** unless agreed otherwise in writing.
8. These are **research outputs** — must not be described as official estimates of housing
   need, housing requirements, or planning targets.

**Consequences for us:**
- If we use this data, **submit to the Drive, not public GitHub.** Never commit the CSV.
- It is **not usable as a public portfolio piece** without sign-off from the Warwick team.
- Phrase every finding as *"WhereToBuild's research measure of demand pressure"*, never
  *"housing need"*.

### 4.4 On the Drive but NOT downloaded

| Item | What it is | Status |
|---|---|---|
| **`housing.sqlite`** | **343,141 London planning applications × 89 cols, 2016–2026, all 33 boroughs** | ✅ **DOWNLOADED** → `data/raw/housing.sqlite` (1.4 GB) — see §4.6 |
| Rest of `house` repo | PlanIt scraper, trained housing-relevance classifier (`.joblib`), t-SNE/UMAP text embeddings, Plotly maps, scored/filtered SQLite variants | Not pulled — same confirm-token method works if needed |
| `Submissions/` | Where entries go | 1 entry so far |
| `Data Warehouse/` | Contains only the one CSV we already have | ✅ complete |

`github.com/houselondon` currently has **0 public repos** — we'd be the first.

### 4.6 `housing.sqlite` — the big one (Brief DD unlocked)

`data/raw/housing.sqlite`, 1.4 GB. One table: **`applications_tidy`, 343,141 rows × 89
columns**. Jamie's scrape of PlanIt, relevance-filtered to housing. **No licence
restrictions attached** — unlike WhereToBuild.

**Coverage:** all **33 boroughs**, **2016-02-07 → 2026-03-06**.

| Field | Fill | Notes |
|---|---|---|
| `area_name`, `description`, `start_date`, `housing_relevance_score` | 100% | |
| `app_state` | 99.3% | Permitted 172,576 · Conditions 73,847 · Rejected 61,592 · Withdrawn 16,849 · Undecided 15,554 |
| `app_size` | 97.6% | Small 307k · Medium 15.3k · Large 12.4k |
| `ward_name` / `case_officer` / `postcode` | ~96–97% | |
| `decided_date` | 92.3% | → decision-time analysis |
| `decided_by` | 86.5% | **committee vs delegated** — but ~30+ raw variants, needs normalising |
| `lat` / `lng` | 75.1% | 258k mappable points |
| `n_comments` | 50.7% | objection intensity |
| `n_constraints` | 36.9% | green belt / conservation / article 4 etc. |
| `development_type` | 16.2% | |
| `appeal_result` | 2.9% | 9,780 appeals — allowed vs dismissed |
| `n_dwellings` | **4.5%** | ⚠️ too sparse to count homes with |

**Headline numbers already computed (5 min of SQL):**
- **Approval rate spread across boroughs = 27.5 percentage points.** Brent 72.5%,
  Barnet 73.8% at the bottom; Southwark 92.2%, Wandsworth 90.9% at the top.
- **Median decision time (2023+) = exactly 56 days** — bang on the statutory target —
  **but p90 = 110 days.** The average hides the tail. Strong pitch material.
- 9,780 appeals with outcomes → "which boroughs get overruled most" is one query away.

**Data-quality traps to check before pitching:** Havering shows **100.0%** approval
(n=1,386) and Old Oak Park Royal 98.1% — almost certainly incomplete scrapes, not real.
Greenwich has only 912 decided records vs Barnet's 29,569. **Filter to boroughs with
credible volume and say so on the slide**, or someone in the room will call it.
`appeal_result` and `decided_by` both have inconsistent spellings between boroughs
("Dismissed" vs "Appeal Dismissed", "Delegated" vs "Delegated Decision") — normalise first.

### 4.5 The Data Asset Register — ~25 datasets, all links not files

Catalogued in `docs/data-asset-register.csv` across five sections. Everything here needs
downloading today. Friction flagged where it matters:

**1. Demand & need** — WhereToBuild · ONS Census 2021 (Nomis, CSV) · English Indices of
Deprivation 2025 (new Oct 2025, LSOA, bulk CSV) · Housing in London annual report (PDF).

**2. Supply** — GLA starts/completions/pipeline dashboards *(Power BI, no bulk export)* ·
London Development Database *(160MB Postgres dump, 2020 freeze)* · Affordable Housing Open
Data (XLSX, 2015–21) · GLA Affordable Housing Outturn (XLSX, to Mar 2026) · EPC register
*(needs GOV.UK One Login)* · MHCLG building control · **Housing Delivery Test (ODS —
single %-delivered figure per borough, easy win)**.

**3. Planning process** — **planning.data.gov.uk API** *(100+ datasets, one schema,
CSV/JSON/GeoJSON/Parquet — best single entry point)* · Digital Planning Register · **UK
PlanIt** *(20.5m applications, free API, **rate-limited ~1 req/min** — cache aggressively)* ·
London Plan Opportunity Areas (GeoPackage) · MHCLG live tables (P152/P154 timeliness).

**4. Land, price & ownership** — Price Paid Data (bulk CSV to 1995) · UK House Price Index ·
Domestic EPC register *(One Login)* · **House Price per Square Metre (Price Paid × EPC,
pre-linked — the shortcut, most teams won't know it exists)** · Vacant dwellings Live Table
615 · OCOD/CCOD overseas ownership *(free account)* · Brownfield land registers.

**5. Reference / glue** — **ONS geography lookups (LSOA/MSOA/ward/borough boundaries) —
we need this immediately** · LPA boundaries · OS Open Data.

---

## 5. The briefs

Full text in `docs/data-briefs.md` and `docs/policy-briefs.md`. Summary:

### Data track

| # | Brief | Data we'd need | Feasible today? |
|---|---|---|---|
| **DA** | **Freestyle** — any dataset, build a model / map / story | your call | ✅ |
| **DB** | **Where should London actually build?** Make the demand/supply mismatch legible and actionable for a non-economist | **our CSV** + ONS geography, GLA completions, Census, borough targets | ✅ **best fit** |
| DC | Build the London-wide planning-data pipeline nobody has (bulk-exportable, clean) | PlanIt API, planning.data.gov.uk | ⚠️ rate limits; scope to 1–2 boroughs |
| DD | What does approvals data say? Predict/characterise decision variation | the 343k `house` dataset | ⚠️ blocked on Drive download |
| DE | Who's sitting on land that could be homes? Permitted-but-not-built | LDD 2020 export, GLA dashboards, brownfield registers | ⚠️ Postgres restore |
| DF | What happens after the outline application? Amendment cascades | Digital Planning Register | ⚠️ |
| DG | Is anyone actually using this house? Empty-homes detection | EPC, Price Paid, Census | ⚠️ One Login |
| **DH** | **Does "Barriers to Housing" mean something Census doesn't?** New Oct-2025 deprivation domain vs. Census overcrowding | Indices of Deprivation 2025 + Census 2021 | ✅ **best backup** |
| DI | Do London's two affordable-housing datasets agree? | two GLA XLSX | ✅ |
| DJ | Planning delays — borough, or workload? | MHCLG live tables + PlanIt | ✅ |
| **DK** | **Do vacancy proxies match the official empty-homes count?** | Live Table 615 + EPC/Price Paid/Census | ✅ (One Login for EPC) |
| DL | Is overseas-owned land the land that's stalling? | OCOD/CCOD + Opportunity Areas + brownfield | ⚠️ heavy join |

### Policy track

| # | Brief | Note |
|---|---|---|
| PA | Freestyle policy — propose one, support or disconfirm with data | |
| **PB** | **Answer a live consultation** — real deadlines: ground rent cap (27 Aug), RSH social housing (30 Sep), Heathrow HENPS (1 Sep) | genuinely submittable |
| PC | Is "not enough supply" really the story? (contested — LSE vs. Centre for Cities/IPPR) | handle with care |
| PD | Is temporary accommodation bankrupting London's boroughs? ~183k Londoners in TA | strong emotive hook; suggests a School-Cuts-style postcode lookup + "email your MP" |
| PE | Will Burnham's £340m end rough sleeping? (CHAIN data) | fresh this week |
| PF | What does migration do to housing supply? | handle with care; politically live |
| PG | Would a 0.48% Proportional Property Tax help or hurt London? | winners/losers by borough |
| PH | How much of London could actually get a street vote? | eligibility × profitability |
| PI | Which of these should your borough fight for? | **no data skills needed** — pure policy, one page |

---

## 6. Recommendation

**Main: DB — "Where should London actually build?"**
It's the only brief we can start on immediately with data already on the laptop; it has a
built-in visual; and the brief hands us the pitch itself:
> *"The Warwick WhereToBuild work puts a number on this (demand outstrips supply roughly
> 5:1 in places)… That's a strong headline, but a map alone doesn't tell a councillor or a
> developer what to do with it."*

The winning move is **going one step past the map**: a borough scorecard of demand pressure
vs. actual delivery, or overlaying demand hotspots with sites that already hold permission
but haven't started. Audience stated in the brief: **policy campaigners and local
councillors** — pitch to them, in plain English.

The `corr(gap, tightness) = 0.08` finding is a ready-made hook: *the two ways of measuring
"where London needs homes" disagree almost completely — and which one you pick changes
which boroughs get built on.*

**Backup: DH** (Barriers to Housing vs. Census overcrowding) — fully open data, no licence
restrictions, publishable afterwards, produces a clean scatter with named outliers. Survives
a Drive-download failure. **DK** is the second backup on the same logic.

### First 45 minutes, if we go DB
1. ONS Open Geography → MSOA 2021 boundaries (GeoJSON) + MSOA→borough lookup.
2. Join on `msoa_code`, filter to the 33 London boroughs.
3. Confirm `gap` / `tightness` definitions with an organiser.
4. Choropleth of `tightness` and of `gap_per_km2`, side by side — see whether the
   disagreement is visually obvious. If it is, that's the pitch.
5. Then find the *action*: pair against Housing Delivery Test (single ODS, one % per
   borough) → "high demand pressure × low delivery" quadrant = the target list.

---

## 7. Standing rules for the day

- **Never commit `data/raw/wheretobuild_msoa_stats.csv`** to any public repo.
- Every output carries the Warwick attribution line.
- Say *"research measure of demand pressure"*, never *"housing need"* or *"planning target"*.
- Submit to the **Drive** if WhereToBuild data is used; GitHub is fine for anything else.
- Lock the idea by **12:15**. Ship something demoable by **16:00** — leave the last hour
  for the 3-minute story, not for code.
- Delete the WhereToBuild data after the event.

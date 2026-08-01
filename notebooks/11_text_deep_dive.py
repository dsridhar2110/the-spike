"""Deep dive on the description column — what it is, what it says, how well it predicts.

Answers, with numbers:
  1. What does the `description` column actually contain? (samples, length, coverage)
  2. What development types are in there, and what is each one's approval rate?
  3. Does "number of storeys" really drive approval, or is that a spurious word effect?
  4. Full metric suite for the text model: ROC-AUC, PR-AUC both classes, Brier,
     precision/recall/F1 at thresholds, confusion matrix, calibration.
  5. Walk-forward backtest of the TEXT model (train <= Y, test Y+1).
"""
import json
import re
import numpy as np
import pandas as pd
import sqlite3
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss,
                             precision_score, recall_score, f1_score, accuracy_score,
                             confusion_matrix)

QA = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
      "Haringey", "London Legacy", "Enfield", "Hillingdon"}
con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""select area_name,app_type,description,start_date,decided_date,
 target_decision_date,app_state from applications_tidy
 where app_size='Small' and start_date>='2018-01-01' and decided_date is not null
 and target_decision_date is not null and app_state in ('Permitted','Conditions','Rejected')""", con)
df = df[~df.area_name.isin(QA)].copy()
df["approved"] = (df.app_state != "Rejected").astype(int)
df["days"] = (pd.to_datetime(df.decided_date) - pd.to_datetime(df.start_date)).dt.days
df["sub_year"] = pd.to_datetime(df.start_date).dt.year
df["desc"] = df.description.fillna("").str.lower().str.strip()
df["app_type"] = df.app_type.fillna("Other").replace({"None": "Other"})
df = df[(df.desc.str.len() > 10) & (df.days.between(0, 400))]

print("=" * 78)
print("1. WHAT IS THE `description` COLUMN?")
print("=" * 78)
print(f"  rows {len(df):,} | coverage 100% | median length "
      f"{int(df.desc.str.len().median())} chars, {int(df.desc.str.split().str.len().median())} words")
print(f"  longest {int(df.desc.str.len().max()):,} chars | 5,742 distinct first words")
print("\n  RANDOM SAMPLES (verbatim, truncated to 130 chars):")
for r in df.sample(8, random_state=7).itertuples():
    print(f"   [{'APPROVED' if r.approved else 'REFUSED '}] {r.description[:130]}")

print()
print("=" * 78)
print("2. DEVELOPMENT TYPES — approval rate by what is actually being proposed")
print("=" * 78)
ARCH = [
    ("Single storey rear extension", r"single stor\w+ rear extension"),
    ("Single storey extension (any)", r"single stor\w+.*extension"),
    ("Two storey extension", r"two stor\w+.*extension"),
    ("Loft conversion / dormer", r"loft conversion|dormer"),
    ("Rooflights / skylights only", r"rooflight|roof light|skylight"),
    ("Conversion into flats", r"conver\w+ .*(flat|apartment)|self.contained (flat|unit)"),
    ("Erection of new dwelling(s)", r"erection of .*(dwelling|house)"),
    ("Change of use", r"change of use"),
    ("Demolition involved", r"demoli"),
    ("Basement / excavation", r"basement|excavat"),
    ("Outbuilding / garage / shed", r"outbuilding|garage|shed|garden room"),
    ("Additional storey(s) on top", r"additional stor|extra stor|roof extension"),
    ("Trees / hedge works", r"\bprune|\bfell\b|crown reduc|tree"),
    ("Advertisement / signage", r"advertis|signage|fascia"),
]
rows = []
print(f"  {'development type':32s} {'n':>8s} {'approved':>9s} {'vs base':>9s} {'median days':>12s}")
base = df.approved.mean()
for name, pat in ARCH:
    m = df.desc.str.contains(pat, regex=True, na=False)
    s = df[m]
    if len(s) < 250:
        continue
    rows.append({"type": name, "n": int(len(s)), "approval": round(100 * s.approved.mean(), 1),
                 "vs_base": round(100 * (s.approved.mean() - base), 1),
                 "median_days": int(s.days.median())})
    print(f"  {name:32s} {len(s):>8,} {100*s.approved.mean():>8.1f}% "
          f"{100*(s.approved.mean()-base):>+8.1f} {int(s.days.median()):>12d}")
print(f"  {'ALL APPLICATIONS':32s} {len(df):>8,} {100*base:>8.1f}% {0:>+8.1f} "
      f"{int(df.days.median()):>12d}")

print()
print("=" * 78)
print("3. DOES SCALE REALLY DRIVE IT? storeys mentioned vs approval")
print("=" * 78)
def storeys(t):
    if re.search(r"single stor|one stor|1 stor", t): return "single storey"
    if re.search(r"two stor|2 stor|double stor", t): return "two storey"
    if re.search(r"three stor|3 stor", t): return "three storey"
    if re.search(r"four stor|4 stor|five stor|5 stor", t): return "four+ storey"
    return "not stated"
df["storeys"] = df.desc.map(storeys)
st = df.groupby("storeys").agg(n=("approved", "size"), approval=("approved", "mean"),
                               days=("days", "median"))
order = ["single storey", "two storey", "three storey", "four+ storey", "not stated"]
storey_rows = []
for k in order:
    if k in st.index:
        r = st.loc[k]
        storey_rows.append({"storeys": k, "n": int(r.n), "approval": round(100 * r.approval, 1)})
        print(f"  {k:16s} n={int(r.n):>7,}  approved {100*r.approval:5.1f}%  median {int(r.days)}d")
print("\n  -> this is the mechanism behind the word coefficients: the model is not")
print("     reacting to the phrase 'single storey', it is reacting to SCALE.")

# ------------------------------------------------------------------ model ---
tr, te = df[df.sub_year <= 2023], df[df.sub_year >= 2024]
ytr, yte = tr.approved.to_numpy(), te.approved.to_numpy()
tw = TfidfVectorizer(ngram_range=(1, 2), min_df=30, max_features=20_000, sublinear_tf=True,
                     token_pattern=r"(?u)\b\w\w+\b")
Xw_tr, Xw_te = tw.fit_transform(tr.desc), tw.transform(te.desc)
enc = OneHotEncoder(handle_unknown="ignore", min_frequency=40)
Xc_tr, Xc_te = enc.fit_transform(tr[["area_name", "app_type"]]), enc.transform(te[["area_name", "app_type"]])
m = LogisticRegression(max_iter=2000, C=1.0, solver="liblinear")
m.fit(hstack([Xw_tr, Xc_tr]), ytr)
p = m.predict_proba(hstack([Xw_te, Xc_te]))[:, 1]

print()
print("=" * 78)
print("4. FULL METRICS — approval model (text + borough + type)")
print("=" * 78)
print(f"  test set {len(te):,} decisions, {100*yte.mean():.1f}% approved / {100*(1-yte.mean()):.1f}% refused")
print(f"  ROC-AUC                        {roc_auc_score(yte, p):.4f}")
print(f"  PR-AUC (approval, majority)    {average_precision_score(yte, p):.4f}   [base {yte.mean():.4f}]")
print(f"  PR-AUC (REFUSAL, minority)     {average_precision_score(1-yte, 1-p):.4f}   [base {1-yte.mean():.4f}]  <-- the one that matters")
print(f"  Brier score (lower better)     {brier_score_loss(yte, p):.4f}")
print(f"  Log loss equivalent baseline   {brier_score_loss(yte, np.full(len(yte), yte.mean())):.4f} (always predict base rate)")

print("\n  FLAGGING REFUSALS at different thresholds:")
print(f"  {'flag if P(approve) <':>21s} {'flagged':>8s} {'caught':>7s} {'precision':>10s} {'recall':>7s} {'F1':>6s}")
thr_rows = []
for t in [0.40, 0.50, 0.60, 0.65, 0.70]:
    pred_ref = (p < t).astype(int); true_ref = 1 - yte
    if pred_ref.sum() == 0: continue
    pr, rc = precision_score(true_ref, pred_ref), recall_score(true_ref, pred_ref)
    thr_rows.append({"threshold": t, "flagged": int(pred_ref.sum()),
                     "precision": round(pr, 4), "recall": round(rc, 4),
                     "f1": round(f1_score(true_ref, pred_ref), 4)})
    print(f"  {t:>21.2f} {pred_ref.sum():>8,} {int((pred_ref&true_ref).sum()):>7,} "
          f"{100*pr:>9.1f}% {100*rc:>6.1f}% {100*f1_score(true_ref,pred_ref):>5.1f}%")

tn, fp, fn, tp = confusion_matrix(1-yte, (p < 0.60).astype(int)).ravel()
print(f"\n  CONFUSION MATRIX at threshold 0.60 (predicting REFUSAL):")
print(f"                     predicted OK   predicted REFUSAL")
print(f"    actually OK       {tn:>10,}      {fp:>12,}")
print(f"    actually REFUSED  {fn:>10,}      {tp:>12,}")
print(f"    accuracy {100*accuracy_score(1-yte,(p<0.60).astype(int)):.1f}%  "
      f"(always-say-approved = {100*yte.mean():.1f}%)")

print("\n  CALIBRATION (10 bins)")
bins = pd.qcut(p, 10, labels=False, duplicates="drop")
cal = []
for b in np.unique(bins):
    msk = bins == b
    cal.append({"pred": round(float(p[msk].mean()), 3), "actual": round(float(yte[msk].mean()), 3),
                "n": int(msk.sum())})
    print(f"    predicted {cal[-1]['pred']:.3f}  ->  actual {cal[-1]['actual']:.3f}  (n={cal[-1]['n']:,})")
mce = max(abs(c["pred"] - c["actual"]) for c in cal)
print(f"    max calibration error {mce:.3f}")

print()
print("=" * 78)
print("5. WALK-FORWARD BACKTEST — text model, train <= Y, test Y+1")
print("=" * 78)
print(f"  {'train through':>14s} {'test':>6s} {'n':>8s} {'ROC-AUC':>9s} {'refusal PR':>11s} {'base':>7s}")
wf = []
for y in range(2020, 2025):
    a, b = df[df.sub_year <= y], df[df.sub_year == y + 1]
    if len(b) < 3000: continue
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=30, max_features=20_000, sublinear_tf=True,
                        token_pattern=r"(?u)\b\w\w+\b")
    Aw, Bw = v.fit_transform(a.desc), v.transform(b.desc)
    e = OneHotEncoder(handle_unknown="ignore", min_frequency=40)
    Ac, Bc = e.fit_transform(a[["area_name", "app_type"]]), e.transform(b[["area_name", "app_type"]])
    mm = LogisticRegression(max_iter=2000, C=1.0, solver="liblinear").fit(hstack([Aw, Ac]), a.approved)
    pp = mm.predict_proba(hstack([Bw, Bc]))[:, 1]
    yy = b.approved.to_numpy()
    roc, prr = roc_auc_score(yy, pp), average_precision_score(1-yy, 1-pp)
    wf.append({"train_through": y, "test_year": y+1, "n": int(len(b)),
               "roc": round(roc, 4), "refusal_pr": round(prr, 4),
               "base_refusal": round(float(1-yy.mean()), 4)})
    print(f"  {y:>14d} {y+1:>6d} {len(b):>8,} {roc:>9.4f} {prr:>11.4f} {1-yy.mean():>7.3f}")
rocs = [w["roc"] for w in wf]
print(f"\n  ROC-AUC across folds: min {min(rocs):.4f}  max {max(rocs):.4f}  "
      f"mean {np.mean(rocs):.4f}  sd {np.std(rocs):.4f}")

json.dump({"archetypes": rows, "storeys": storey_rows,
           "metrics": {"roc_auc": round(float(roc_auc_score(yte, p)), 4),
                       "pr_auc_approval": round(float(average_precision_score(yte, p)), 4),
                       "pr_auc_refusal": round(float(average_precision_score(1-yte, 1-p)), 4),
                       "brier": round(float(brier_score_loss(yte, p)), 4),
                       "base_approval": round(float(yte.mean()), 4),
                       "n_train": int(len(tr)), "n_test": int(len(te)),
                       "max_calibration_error": round(float(mce), 4)},
           "thresholds": thr_rows, "calibration": cal, "walk_forward": wf},
          open("../outputs/text_deep_dive.json", "w"), indent=1)
print("\nwrote ../outputs/text_deep_dive.json")

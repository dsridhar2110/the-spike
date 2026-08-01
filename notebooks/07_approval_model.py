"""Approval model — the second half of the public-facing tool.

TARGET    approved = 1 if app_state in (Permitted, Conditions), 0 if Rejected
          (Withdrawn / Undecided excluded — no decision was made)
RULE      submission-time features only. Same leakage discipline as the timing model.
ALSO      decision-time percentiles per borough, for "how long will this take".
"""
import json
import numpy as np
import pandas as pd
import sqlite3
import lightgbm as lgb
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}

con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""
 select area_name, ward_name, app_type, description, start_date, decided_date,
        target_decision_date, app_state, agent_company, lat
 from applications_tidy
 where app_size='Small' and start_date>='2018-01-01'
   and decided_date is not null and target_decision_date is not null
   and app_state in ('Permitted','Conditions','Rejected')
""", con)
df = df[~df.area_name.isin(QA_DROP)].copy()

df["approved"] = (df.app_state != "Rejected").astype(int)
df["bunched"] = (pd.to_datetime(df.decided_date).dt.date
                 == pd.to_datetime(df.target_decision_date).dt.date).astype(int)
df["days"] = (pd.to_datetime(df.decided_date) - pd.to_datetime(df.start_date)).dt.days

d = pd.to_datetime(df.start_date)
df["sub_year"], df["sub_month"], df["sub_dow"] = d.dt.year, d.dt.month, d.dt.dayofweek
wk = d.dt.to_period("W").astype(str)
df["weekly_intake"] = df.groupby([df.area_name, wk])["area_name"].transform("size")
desc = df.description.fillna("").str.lower()
df["desc_len"], df["desc_words"] = desc.str.len(), desc.str.split().str.len()
df["has_agent"] = df.agent_company.notna().astype(int)
df["has_geo"] = df.lat.notna().astype(int)
top = df.ward_name.value_counts().head(200).index
df["ward_top"] = np.where(df.ward_name.isin(top), df.ward_name, "OTHER")

CATS = ["area_name", "app_type", "ward_top"]
NUMS = ["weekly_intake", "sub_year", "sub_month", "sub_dow", "desc_len", "desc_words",
        "has_agent", "has_geo"]
FEATS = CATS + NUMS
for c in CATS:
    df[c] = df[c].fillna("MISSING").astype("category")

print(f"rows {len(df):,} | approval base rate {df.approved.mean():.3f} "
      f"({df.approved.sum():,} approved / {(1-df.approved).sum():,.0f} refused)")

tr, te = df[df.sub_year <= 2023], df[df.sub_year >= 2024]
print(f"train {len(tr):,}  test {len(te):,}")

# ---------- baseline: borough approval rate --------------------------------
rate = tr.groupby("area_name", observed=True).approved.mean()
p_base = te.area_name.map(rate).fillna(tr.approved.mean()).to_numpy()

# ---------- model -----------------------------------------------------------
m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=31,
                       min_child_samples=40, reg_lambda=1.0, verbose=-1, random_state=0)
m.fit(tr[FEATS], tr.approved, categorical_feature=CATS)
p = m.predict_proba(te[FEATS])[:, 1]

print("\n" + "=" * 70)
print("APPROVAL MODEL — can we predict approve/refuse at submission?")
print("=" * 70)
print(f"{'baseline (borough rate)':32s} ROC-AUC {roc_auc_score(te.approved,p_base):.4f}  "
      f"PR-AUC {average_precision_score(te.approved,p_base):.4f}")
print(f"{'LightGBM':32s} ROC-AUC {roc_auc_score(te.approved,p):.4f}  "
      f"PR-AUC {average_precision_score(te.approved,p):.4f}  "
      f"Brier {brier_score_loss(te.approved,p):.4f}")
print(f"{'(always predict approve)':32s} accuracy {te.approved.mean():.4f}")

# refusal-focused view (the rare class is what a user cares about)
print(f"\nREFUSAL side (class 0 = refused, base rate {1-te.approved.mean():.3f}):")
print(f"  PR-AUC for predicting REFUSAL: {average_precision_score(1-te.approved, 1-p):.4f}")
k = int(0.10 * len(te)); idx = np.argsort(p)[:k]     # lowest approval prob
print(f"  top 10% most-at-risk: {100*(1-te.approved.to_numpy()[idx].mean()):.1f}% actually refused "
      f"vs {100*(1-te.approved.mean()):.1f}% base = "
      f"{(1-te.approved.to_numpy()[idx].mean())/(1-te.approved.mean()):.2f}x")

print("\nCALIBRATION")
bins = pd.qcut(p, 10, labels=False, duplicates="drop")
cal_ap = []
for b in np.unique(bins):
    msk = bins == b
    cal_ap.append({"pred": round(float(p[msk].mean()), 3),
                   "actual": round(float(te.approved.to_numpy()[msk].mean()), 3),
                   "n": int(msk.sum())})
    print(f"  decile {b+1:>2}  predicted {cal_ap[-1]['pred']:.3f}  actual {cal_ap[-1]['actual']:.3f}")

# ---------- THE KEY INTERACTION: does bunching change approval odds? --------
print("\n" + "=" * 70)
print("THE LINK — approval rate when bunched vs not, BY BOROUGH")
print("=" * 70)
g = (df.groupby(["area_name", "bunched"], observed=True).approved
     .agg(["mean", "size"]).unstack())
link = []
print(f"{'borough':22s} {'not bunched':>12s} {'bunched':>10s} {'gap (pp)':>10s}")
for b in g.index:
    try:
        nb, bb = g.loc[b, ("mean", 0)], g.loc[b, ("mean", 1)]
        n_bb = g.loc[b, ("size", 1)]
        if n_bb < 150 or pd.isna(bb):
            continue
    except KeyError:
        continue
    link.append({"borough": b, "approve_not_bunched": round(100*nb, 1),
                 "approve_bunched": round(100*bb, 1), "gap_pp": round(100*(bb-nb), 1),
                 "n_bunched": int(n_bb)})
    print(f"{b:22s} {100*nb:11.1f}% {100*bb:9.1f}% {100*(bb-nb):+9.1f}")
ov_nb = df[df.bunched == 0].approved.mean(); ov_b = df[df.bunched == 1].approved.mean()
print(f"{'ALL 18 BOROUGHS':22s} {100*ov_nb:11.1f}% {100*ov_b:9.1f}% {100*(ov_b-ov_nb):+9.1f}")

# ---------- decision-time percentiles per borough ---------------------------
tp = (df.groupby("area_name", observed=True).days
      .quantile([.25, .5, .9]).unstack().round(0).astype(int))
tp.columns = ["p25", "median", "p90"]
print("\nDECISION TIME (days from submission)")
print(f"{'borough':22s} {'p25':>6s} {'median':>8s} {'p90':>6s}")
for b, r in tp.iterrows():
    print(f"{b:22s} {r.p25:>6d} {r['median']:>8d} {r.p90:>6d}")

out = {
    "approval": {
        "base_rate": round(float(te.approved.mean()), 4),
        "baseline_roc": round(float(roc_auc_score(te.approved, p_base)), 4),
        "model_roc": round(float(roc_auc_score(te.approved, p)), 4),
        "model_pr": round(float(average_precision_score(te.approved, p)), 4),
        "refusal_pr": round(float(average_precision_score(1-te.approved, 1-p)), 4),
        "brier": round(float(brier_score_loss(te.approved, p)), 4),
        "calibration": cal_ap,
    },
    "bunch_approval_link": link,
    "overall_link": {"approve_not_bunched": round(100*float(ov_nb), 1),
                     "approve_bunched": round(100*float(ov_b), 1),
                     "gap_pp": round(100*float(ov_b-ov_nb), 1)},
    "decision_time": [{"borough": b, "p25": int(r.p25), "median": int(r["median"]),
                       "p90": int(r.p90)} for b, r in tp.iterrows()],
}
open("../outputs/approval_results.json", "w").write(json.dumps(out, indent=1))
print("\nwrote ../outputs/approval_results.json")

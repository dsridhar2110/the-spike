"""Option C — predict whether an application is decided in the deadline rush.

TARGET    bunched = 1 if date(decided_date) == date(target_decision_date)
RULE      every feature knowable AT SUBMISSION. No post-decision columns.
SPLIT     time-based. Train 2018-2023, test 2024-2025. Plus walk-forward backtest.
METRIC    PR-AUC primary (base rate 21.6%), ROC-AUC + Brier + calibration secondary.
BASELINE  the borough's own historical rate. If the model can't beat it, say so.
"""
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import (average_precision_score, roc_auc_score, brier_score_loss)
from sklearn.inspection import permutation_importance

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}

df = pd.read_parquet("../outputs/model_frame.parquet")
df = df[~df.area_name.isin(QA_DROP)].copy()
print(f"after QA gate: {len(df):,} rows, {df.area_name.nunique()} boroughs, "
      f"base rate {df.bunched.mean():.3f}")

# ward_name has 832 levels; HGB caps categoricals at max_bins(255). Keep top 200.
top_wards = df.ward_name.value_counts().head(200).index
df["ward_top"] = np.where(df.ward_name.isin(top_wards), df.ward_name, "OTHER")

CATS = ["area_name", "app_type", "ward_top"]
NUMS = ["borough_prior", "weekly_intake", "sub_year", "sub_month", "sub_dow",
        "desc_len", "desc_words", "has_agent", "has_geo"]
FEATS = CATS + NUMS
for c in CATS:
    df[c] = df[c].fillna("MISSING").astype("category")

def split(train_years, test_years):
    tr = df[df.sub_year.isin(train_years)]
    te = df[df.sub_year.isin(test_years)]
    return tr, te

def borough_prior_baseline(tr, te):
    """Baseline: predict the borough's bunch rate observed in training."""
    rate = tr.groupby("area_name", observed=True).bunched.mean()
    return te.area_name.map(rate).fillna(tr.bunched.mean()).to_numpy()

def fit_hgb(tr, te):
    m = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0,
        categorical_features=[FEATS.index(c) for c in CATS],
        early_stopping=True, validation_fraction=0.15, random_state=0)
    m.fit(tr[FEATS], tr.bunched)
    return m, m.predict_proba(te[FEATS])[:, 1]

def fit_lr(tr, te):
    enc = OneHotEncoder(handle_unknown="ignore", min_frequency=50, sparse_output=True)
    Xtr = enc.fit_transform(tr[CATS]); Xte = enc.transform(te[CATS])
    from scipy.sparse import hstack, csr_matrix
    ntr = csr_matrix(tr[NUMS].fillna(0).to_numpy(dtype=float))
    nte = csr_matrix(te[NUMS].fillna(0).to_numpy(dtype=float))
    mu, sd = ntr.toarray().mean(0), ntr.toarray().std(0) + 1e-9
    ntr = csr_matrix((ntr.toarray() - mu) / sd); nte = csr_matrix((nte.toarray() - mu) / sd)
    m = LogisticRegression(max_iter=2000, C=1.0)
    m.fit(hstack([Xtr, ntr]), tr.bunched)
    return m.predict_proba(hstack([Xte, nte]))[:, 1]

def score(y, p):
    return {"pr_auc": round(average_precision_score(y, p), 4),
            "roc_auc": round(roc_auc_score(y, p), 4),
            "brier": round(brier_score_loss(y, p), 4)}

# ============================ MAIN SPLIT ====================================
tr, te = split(range(2018, 2024), [2024, 2025])
print(f"\ntrain {len(tr):,} ({tr.sub_year.min()}-{tr.sub_year.max()})  "
      f"test {len(te):,} ({te.sub_year.min()}-{te.sub_year.max()})")
print(f"train base rate {tr.bunched.mean():.3f} | test base rate {te.bunched.mean():.3f}")

results = {}
p_base = borough_prior_baseline(tr, te)
results["baseline_borough_rate"] = score(te.bunched, p_base)
p_lr = fit_lr(tr, te)
results["logistic_regression"] = score(te.bunched, p_lr)
hgb, p_hgb = fit_hgb(tr, te)
results["hist_gradient_boosting"] = score(te.bunched, p_hgb)

print("\n" + "=" * 74)
print(f"{'MODEL':30s} {'PR-AUC':>9s} {'ROC-AUC':>9s} {'Brier':>8s}")
print("=" * 74)
print(f"{'(base rate = always predict '+format(te.bunched.mean(),'.3f')+')':30s} "
      f"{te.bunched.mean():>9.4f} {0.5:>9.4f} {'—':>8s}")
for k, v in results.items():
    print(f"{k:30s} {v['pr_auc']:>9.4f} {v['roc_auc']:>9.4f} {v['brier']:>8.4f}")

lift = results["hist_gradient_boosting"]["pr_auc"] / results["baseline_borough_rate"]["pr_auc"]
print(f"\nHGB vs borough baseline (PR-AUC): {lift:.3f}x")

# ---- precision @ top decile ------------------------------------------------
k = int(0.10 * len(te)); idx = np.argsort(-p_hgb)[:k]
print(f"precision@top-10% : {te.bunched.to_numpy()[idx].mean():.3f} "
      f"(vs {te.bunched.mean():.3f} base) — {te.bunched.to_numpy()[idx].mean()/te.bunched.mean():.2f}x lift")

# ---- calibration -----------------------------------------------------------
print("\nCALIBRATION (does a predicted 40% actually happen 40% of the time?)")
bins = pd.qcut(p_hgb, 10, labels=False, duplicates="drop")
cal = []
for b in np.unique(bins):
    m = bins == b
    cal.append({"bin": int(b), "pred": round(float(p_hgb[m].mean()), 3),
                "actual": round(float(te.bunched.to_numpy()[m].mean()), 3), "n": int(m.sum())})
    print(f"  decile {b+1:>2}  predicted {cal[-1]['pred']:.3f}  actual {cal[-1]['actual']:.3f}  n={cal[-1]['n']:,}")

# ============================ WALK-FORWARD ==================================
print("\n" + "=" * 74)
print("WALK-FORWARD BACKTEST — train on all years <= Y, test on Y+1")
print("=" * 74)
print(f"{'train through':>14s} {'test year':>10s} {'n_test':>8s} {'base':>7s} "
      f"{'baseline':>9s} {'HGB':>8s} {'lift':>6s}")
wf = []
for y in range(2021, 2025):
    trw, tew = split(range(2018, y + 1), [y + 1])
    if len(tew) < 3000:
        continue
    pb = borough_prior_baseline(trw, tew)
    _, ph = fit_hgb(trw, tew)
    a, b = average_precision_score(tew.bunched, pb), average_precision_score(tew.bunched, ph)
    wf.append({"train_through": y, "test_year": y + 1, "n": len(tew),
               "base_rate": round(tew.bunched.mean(), 4),
               "baseline_pr": round(a, 4), "hgb_pr": round(b, 4), "lift": round(b / a, 3)})
    print(f"{y:>14d} {y+1:>10d} {len(tew):>8,} {tew.bunched.mean():>7.3f} "
          f"{a:>9.4f} {b:>8.4f} {b/a:>6.3f}")

# ============================ IMPORTANCE ====================================
print("\n" + "=" * 74)
print("PERMUTATION IMPORTANCE (drop in PR-AUC when a feature is shuffled)")
print("=" * 74)
pi = permutation_importance(hgb, te[FEATS], te.bunched, n_repeats=5,
                            scoring="average_precision", random_state=0, n_jobs=-1)
imp = sorted(zip(FEATS, pi.importances_mean, pi.importances_std), key=lambda x: -x[1])
for n, m, s in imp:
    print(f"  {n:16s} {m:+.4f}  ±{s:.4f} {'#' * max(0, int(m * 900))}")

# ============================ SHAP ==========================================
print("\n" + "=" * 74)
print("SHAP")
print("=" * 74)
shap_rows = []
try:
    import shap
    samp = te.sample(min(3000, len(te)), random_state=0)
    try:
        ex = shap.TreeExplainer(hgb)
        sv = ex.shap_values(samp[FEATS])
        method = "TreeExplainer"
    except Exception as e:
        print(f"  TreeExplainer unavailable ({type(e).__name__}) — using permutation Explainer")
        ex = shap.Explainer(lambda X: hgb.predict_proba(
            pd.DataFrame(X, columns=FEATS).astype(
                {c: "category" for c in CATS}))[:, 1],
            samp[FEATS].head(200), max_evals=400)
        sv = ex(samp[FEATS].head(200)).values
        method = "permutation Explainer"
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, -1]
    mean_abs = np.abs(sv).mean(0)
    print(f"  method: {method};  mean |SHAP| (impact on predicted probability):")
    for n, m in sorted(zip(FEATS, mean_abs), key=lambda x: -x[1]):
        shap_rows.append({"feature": n, "mean_abs_shap": round(float(m), 5)})
        print(f"    {n:16s} {m:.5f} {'#' * max(0, int(m * 1400))}")
except Exception as e:
    print(f"  SHAP failed: {type(e).__name__}: {e}")

out = {"n_rows": len(df), "n_boroughs": int(df.area_name.nunique()),
       "base_rate_test": round(float(te.bunched.mean()), 4),
       "results": results, "lift_vs_baseline": round(float(lift), 3),
       "precision_at_10pct": round(float(te.bunched.to_numpy()[idx].mean()), 4),
       "calibration": cal, "walk_forward": wf,
       "permutation_importance": [{"feature": n, "drop_in_pr_auc": round(float(m), 5)} for n, m, _ in imp],
       "shap_mean_abs": shap_rows}
open("../outputs/model_results.json", "w").write(json.dumps(out, indent=1))
print("\nwrote ../outputs/model_results.json")

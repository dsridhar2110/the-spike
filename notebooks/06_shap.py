"""SHAP on the deadline-rush model.

SHAP's TreeExplainer does not support sklearn's HistGradientBoostingClassifier, so we
refit the same architecture in LightGBM (gradient-boosted trees, native categoricals)
and explain that. We first confirm LightGBM scores the same as the sklearn model —
otherwise we would be explaining a different model than the one we reported.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
from sklearn.metrics import average_precision_score, roc_auc_score

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}
df = pd.read_parquet("../outputs/model_frame.parquet")
df = df[~df.area_name.isin(QA_DROP)].copy()
top = df.ward_name.value_counts().head(200).index
df["ward_top"] = np.where(df.ward_name.isin(top), df.ward_name, "OTHER")

CATS = ["area_name", "app_type", "ward_top"]
NUMS = ["borough_prior", "weekly_intake", "sub_year", "sub_month", "sub_dow",
        "desc_len", "desc_words", "has_agent", "has_geo"]
FEATS = CATS + NUMS
for c in CATS:
    df[c] = df[c].fillna("MISSING").astype("category")

tr = df[df.sub_year <= 2023]
te = df[df.sub_year >= 2024]

m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.06, num_leaves=31,
                       min_child_samples=40, reg_lambda=1.0, verbose=-1, random_state=0)
m.fit(tr[FEATS], tr.bunched, categorical_feature=CATS)
p = m.predict_proba(te[FEATS])[:, 1]

pr, roc = average_precision_score(te.bunched, p), roc_auc_score(te.bunched, p)
print("PARITY CHECK — LightGBM vs the reported sklearn model")
print(f"  LightGBM   PR-AUC {pr:.4f}  ROC-AUC {roc:.4f}")
prev = json.load(open("../outputs/model_results.json"))
sk = prev["results"]["hist_gradient_boosting"]
print(f"  sklearn    PR-AUC {sk['pr_auc']:.4f}  ROC-AUC {sk['roc_auc']:.4f}")
print(f"  delta      PR-AUC {pr - sk['pr_auc']:+.4f}  -> "
      f"{'equivalent, safe to explain' if abs(pr - sk['pr_auc']) < 0.02 else 'DIVERGENT — do not substitute'}")

samp = te.sample(min(5000, len(te)), random_state=0)
sv = shap.TreeExplainer(m).shap_values(samp[FEATS])
sv = np.asarray(sv)
if sv.ndim == 3:
    sv = sv[:, :, -1]

print("\nGLOBAL — mean |SHAP| (average push on the log-odds of being bunched)")
rows = sorted(zip(FEATS, np.abs(sv).mean(0)), key=lambda x: -x[1])
for n, v in rows:
    print(f"  {n:16s} {v:.4f} {'#' * max(0, int(v * 60))}")

print("\nDIRECTION — which borough values push the prediction up vs down")
ai = FEATS.index("area_name")
eff = (pd.DataFrame({"borough": samp.area_name.astype(str).to_numpy(), "shap": sv[:, ai]})
       .groupby("borough").agg(mean_shap=("shap", "mean"), n=("shap", "size"))
       .sort_values("mean_shap", ascending=False))
for k, r in eff.head(5).iterrows():
    print(f"  PUSHES UP    {k:22s} {r.mean_shap:+.3f}  (n={int(r.n)})")
for k, r in eff.tail(4).iterrows():
    print(f"  PUSHES DOWN  {k:22s} {r.mean_shap:+.3f}  (n={int(r.n)})")

ti = FEATS.index("app_type")
te_eff = (pd.DataFrame({"t": samp.app_type.astype(str).to_numpy(), "shap": sv[:, ti]})
          .groupby("t").agg(mean_shap=("shap", "mean"), n=("shap", "size"))
          .sort_values("mean_shap", ascending=False))
print()
for k, r in te_eff.iterrows():
    if r.n > 100:
        print(f"  app_type  {k:16s} {r.mean_shap:+.3f}  (n={int(r.n)})")

j = int(np.argmax(p[:len(samp)] if len(p) == len(samp) else m.predict_proba(samp[FEATS])[:, 1]))
ps = m.predict_proba(samp[FEATS])[:, 1]
j = int(np.argmax(ps))
print(f"\nWORKED EXAMPLE — highest-risk application in the test sample "
      f"(predicted {ps[j]:.1%}, actual={'bunched' if samp.bunched.iloc[j] else 'not bunched'})")
for n, v in sorted(zip(FEATS, sv[j]), key=lambda x: -abs(x[1]))[:6]:
    print(f"  {n:16s} value={str(samp[n].iloc[j])[:26]:26s} SHAP {v:+.3f}")

out = {"parity": {"lgbm_pr_auc": round(float(pr), 4), "lgbm_roc_auc": round(float(roc), 4),
                  "sklearn_pr_auc": sk["pr_auc"]},
       "global_mean_abs_shap": [{"feature": n, "mean_abs_shap": round(float(v), 5)} for n, v in rows],
       "borough_direction": [{"borough": k, "mean_shap": round(float(r.mean_shap), 4), "n": int(r.n)}
                             for k, r in eff.iterrows()],
       "app_type_direction": [{"app_type": k, "mean_shap": round(float(r.mean_shap), 4), "n": int(r.n)}
                              for k, r in te_eff.iterrows()]}
open("../outputs/shap_results.json", "w").write(json.dumps(out, indent=1))
print("\nwrote ../outputs/shap_results.json")

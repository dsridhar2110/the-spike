"""How long will my decision take? — quantile regression on decision time.

A single predicted number would be false precision: decision time is right-skewed with a
huge spike at the deadline. So we predict three QUANTILES (25th, 50th, 90th) and show a
range. Evaluated with pinball loss (the correct loss for quantile prediction) plus MAE
and coverage checks on the held-out years.

Features: submission-time only. Same discipline as everywhere else.
"""
import json
import numpy as np
import pandas as pd
import sqlite3
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import mean_absolute_error

QA = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
      "Haringey", "London Legacy", "Enfield", "Hillingdon"}
con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""select area_name,ward_name,app_type,description,start_date,decided_date,
 target_decision_date,app_state from applications_tidy
 where app_size='Small' and start_date>='2018-01-01' and decided_date is not null
 and target_decision_date is not null and app_state in ('Permitted','Conditions','Rejected')""", con)
df = df[~df.area_name.isin(QA)].copy()
df["days"] = (pd.to_datetime(df.decided_date) - pd.to_datetime(df.start_date)).dt.days
df["sub_year"] = pd.to_datetime(df.start_date).dt.year
df["sub_month"] = pd.to_datetime(df.start_date).dt.month
df["desc"] = df.description.fillna("").str.lower().str.strip()
df["app_type"] = df.app_type.fillna("Other").replace({"None": "Other"})
df = df[(df.desc.str.len() > 10) & (df.days.between(1, 400))]
print(f"rows {len(df):,} | days: median {df.days.median():.0f} "
      f"p25 {df.days.quantile(.25):.0f} p90 {df.days.quantile(.9):.0f} max {df.days.max()}")

tr, te = df[df.sub_year <= 2023], df[df.sub_year >= 2024]

# text -> 60 SVD components (dense, so the regressor can use it)
tw = TfidfVectorizer(ngram_range=(1, 2), min_df=40, max_features=15000, sublinear_tf=True,
                     token_pattern=r"(?u)\b\w\w+\b")
Ttr = tw.fit_transform(tr.desc); Tte = tw.transform(te.desc)
svd = TruncatedSVD(n_components=60, algorithm="arpack", random_state=0)
Str, Ste = svd.fit_transform(Ttr), svd.transform(Tte)
Str, Ste = np.nan_to_num(Str, posinf=0, neginf=0), np.nan_to_num(Ste, posinf=0, neginf=0)
assert np.isfinite(Str).all() and np.isfinite(Ste).all(), "SVD produced non-finite values"
print(f"text -> {Str.shape[1]} SVD components "
      f"({100*svd.explained_variance_ratio_.sum():.1f}% variance)")

def frame(d, S):
    X = pd.DataFrame(S, columns=[f"t{i}" for i in range(S.shape[1])], index=d.index)
    X["borough"] = pd.Categorical(d.area_name, categories=sorted(df.area_name.unique())).codes
    X["app_type"] = pd.Categorical(d.app_type, categories=sorted(df.app_type.unique())).codes
    X["sub_month"] = d.sub_month.to_numpy()
    X["sub_year"] = d.sub_year.to_numpy()
    X["desc_words"] = d.desc.str.split().str.len().to_numpy()
    return X

Xtr, Xte = frame(tr, Str), frame(te, Ste)
CAT = [Xtr.columns.get_loc("borough"), Xtr.columns.get_loc("app_type")]
ytr, yte = tr.days.to_numpy(), te.days.to_numpy()

def pinball(y, p, q):
    d = y - p
    return np.mean(np.maximum(q * d, (q - 1) * d))

QS = [0.25, 0.5, 0.9]
preds, models = {}, {}
for q in QS:
    m = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=300,
                                      learning_rate=0.07, max_leaf_nodes=31,
                                      min_samples_leaf=40, categorical_features=CAT,
                                      early_stopping=True, validation_fraction=0.15,
                                      random_state=0)
    m.fit(Xtr, ytr)
    preds[q] = m.predict(Xte); models[q] = m

print("\n" + "=" * 74)
print("DECISION-TIME MODEL — quantile regression, held-out 2024–2025")
print("=" * 74)
print(f"  test n = {len(te):,}\n")
print(f"  {'quantile':>9s} {'pinball loss':>13s} {'baseline*':>11s} {'improvement':>12s}")
res = []
for q in QS:
    base = np.full(len(yte), np.quantile(ytr, q))
    a, b = pinball(yte, preds[q], q), pinball(yte, base, q)
    res.append({"q": q, "pinball": round(float(a), 3), "baseline": round(float(b), 3),
                "improvement_pct": round(100 * (1 - a / b), 1)})
    print(f"  {q:>9.2f} {a:>13.3f} {b:>11.3f} {100*(1-a/b):>11.1f}%")
print("  * baseline = the global training quantile, ignoring all features")

mae = mean_absolute_error(yte, preds[0.5])
mae_base = mean_absolute_error(yte, np.full(len(yte), np.median(ytr)))
mae_bor = mean_absolute_error(yte, te.area_name.map(tr.groupby("area_name").days.median()).fillna(np.median(ytr)))
print(f"\n  MEDIAN PREDICTION")
print(f"    MAE model            {mae:6.1f} days")
print(f"    MAE borough median   {mae_bor:6.1f} days")
print(f"    MAE global median    {mae_base:6.1f} days")
print(f"    improvement vs global {100*(1-mae/mae_base):4.1f}%   vs borough {100*(1-mae/mae_bor):4.1f}%")

cov25 = float((yte <= preds[0.25]).mean()); cov50 = float((yte <= preds[0.5]).mean())
cov90 = float((yte <= preds[0.9]).mean())
print(f"\n  CALIBRATION OF THE QUANTILES (should hit 25% / 50% / 90%)")
print(f"    actual <= predicted p25 : {100*cov25:5.1f}%   (target 25%)")
print(f"    actual <= predicted p50 : {100*cov50:5.1f}%   (target 50%)")
print(f"    actual <= predicted p90 : {100*cov90:5.1f}%   (target 90%)")
inband = float(((yte >= preds[0.25]) & (yte <= preds[0.9])).mean())
print(f"    inside the p25-p90 band : {100*inband:5.1f}%   (target 65%)")

print(f"\n  WORKED EXAMPLES (predicted p25 / p50 / p90 days)")
ex = te.sample(6, random_state=3)
for i in ex.index:
    j = te.index.get_loc(i)
    print(f"    {te.loc[i,'area_name']:16s} {te.loc[i,'app_type']:11s} "
          f"{preds[0.25][j]:5.0f} / {preds[0.5][j]:5.0f} / {preds[0.9][j]:5.0f}   "
          f"actual {te.loc[i,'days']:4d}   \"{te.loc[i,'desc'][:44]}\"")

json.dump({"n_train": int(len(tr)), "n_test": int(len(te)),
           "quantiles": res,
           "mae_model": round(float(mae), 2), "mae_borough": round(float(mae_bor), 2),
           "mae_global": round(float(mae_base), 2),
           "coverage": {"p25": round(cov25, 4), "p50": round(cov50, 4),
                        "p90": round(cov90, 4), "band_25_90": round(inband, 4)},
           "svd_components": int(Str.shape[1]),
           "explained_variance": round(float(svd.explained_variance_ratio_.sum()), 4)},
          open("../outputs/days_model.json", "w"), indent=1)
print("\nwrote ../outputs/days_model.json")

"""EDA for Option C — predicting whether an application gets decided in the deadline rush.

TARGET   bunched = 1 if decided_date == target_decision_date
RULE     every feature must be knowable AT SUBMISSION. No decided_date, no n_comments,
         no decided_by, no n_constraints, no appeal fields. Those leak the future.

Reports, per candidate feature: coverage, cardinality, univariate bunch rate spread,
and mutual information with the target. MI is the right tool for mixed categorical
features (PCA is not — it needs correlated numerics and yields uninterpretable axes).
"""
import sqlite3
import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

con = sqlite3.connect("../data/raw/housing.sqlite")

SQL = """
select area_name, ward_name, app_type, description, start_date,
       target_decision_date, decided_date, lat, lng, agent_company
from applications_tidy
where app_size='Small' and start_date>='2018-01-01'
  and decided_date is not null and target_decision_date is not null
"""
df = pd.read_sql(SQL, con)
print(f"loaded {len(df):,} rows")

# ---- target ---------------------------------------------------------------
df["bunched"] = (pd.to_datetime(df.decided_date).dt.date
                 == pd.to_datetime(df.target_decision_date).dt.date).astype(int)
print(f"target base rate: {df.bunched.mean():.3f}\n")

# ---- submission-time features only ----------------------------------------
d = pd.to_datetime(df.start_date)
df["sub_year"] = d.dt.year
df["sub_month"] = d.dt.month
df["sub_dow"] = d.dt.dayofweek
df["sub_week"] = d.dt.isocalendar().week.astype(int)

# workload proxy: how many applications that borough received the same week
wk = d.dt.to_period("W").astype(str)
df["_wk"] = wk
df["weekly_intake"] = df.groupby(["area_name", "_wk"])["_wk"].transform("size")

# description-derived flags (description is 100% filled)
desc = df.description.fillna("").str.lower()
for kw in ["extension", "loft", "dwelling", "demoli", "change of use",
           "storey", "flat", "conservatory", "garage", "roof"]:
    df["kw_" + kw.replace(" ", "_")] = desc.str.contains(kw, regex=False).astype(int)
df["desc_len"] = desc.str.len()
df["desc_words"] = desc.str.split().str.len()

df["has_agent"] = df.agent_company.notna().astype(int)
df["has_geo"] = df.lat.notna().astype(int)

# borough prior — computed on EARLIER years only, applied forward (no leakage)
prior = (df[df.sub_year <= 2023].groupby("area_name").bunched.mean()
         .rename("borough_prior"))
df = df.join(prior, on="area_name")
df["borough_prior"] = df.borough_prior.fillna(df[df.sub_year <= 2023].bunched.mean())

# ---- coverage & cardinality ------------------------------------------------
print("=" * 78)
print("FEATURE INVENTORY (submission-time safe)")
print("=" * 78)
print(f"{'feature':22s} {'coverage':>9s} {'distinct':>9s}  note")
for c in ["area_name", "ward_name", "app_type", "agent_company", "lat",
          "sub_year", "sub_month", "sub_dow", "weekly_intake", "desc_words",
          "borough_prior"]:
    cov = 100 * df[c].notna().mean()
    print(f"{c:22s} {cov:8.1f}% {df[c].nunique():9,}")

# ---- univariate spread -----------------------------------------------------
print()
print("=" * 78)
print("UNIVARIATE — bunch rate by level (top drivers first)")
print("=" * 78)
for c in ["area_name", "app_type"]:
    g = df.groupby(c).agg(n=("bunched", "size"), rate=("bunched", "mean"))
    g = g[g.n > 800].sort_values("rate", ascending=False)
    print(f"\n--- {c}  (spread {100*(g.rate.max()-g.rate.min()):.1f} pp) ---")
    for k, r in g.head(6).iterrows():
        print(f"    {str(k)[:26]:26s} n={int(r.n):>7,}  {100*r.rate:5.1f}%")
    if len(g) > 8:
        print("    ...")
        for k, r in g.tail(3).iterrows():
            print(f"    {str(k)[:26]:26s} n={int(r.n):>7,}  {100*r.rate:5.1f}%")

print("\n--- weekly_intake quintile (workload proxy) ---")
df["_q"] = pd.qcut(df.weekly_intake, 5, labels=False, duplicates="drop")
for k, r in df.groupby("_q").agg(n=("bunched", "size"), rate=("bunched", "mean"),
                                 lo=("weekly_intake", "min"), hi=("weekly_intake", "max")).iterrows():
    print(f"    Q{int(k)+1} intake {int(r.lo):>3}-{int(r.hi):<4} n={int(r.n):>7,}  {100*r.rate:5.1f}%")

print("\n--- description keyword flags ---")
for c in sorted([c for c in df.columns if c.startswith("kw_")]):
    on = df[df[c] == 1].bunched.mean(); off = df[df[c] == 0].bunched.mean()
    print(f"    {c:22s} present={100*on:5.1f}%  absent={100*off:5.1f}%  "
          f"delta={100*(on-off):+5.1f} pp  (n={int(df[c].sum()):,})")

# ---- mutual information ----------------------------------------------------
print()
print("=" * 78)
print("MUTUAL INFORMATION with target (higher = more informative)")
print("=" * 78)
num = ["borough_prior", "weekly_intake", "sub_year", "sub_month", "sub_dow",
       "desc_words", "desc_len", "has_agent", "has_geo"] + \
      [c for c in df.columns if c.startswith("kw_")]
X = df[num].fillna(0).to_numpy()
codes = {c: df[c].astype("category").cat.codes for c in ["area_name", "app_type", "ward_name"]}
X = np.column_stack([X] + [v.to_numpy() for v in codes.values()])
names = num + list(codes)
mi = mutual_info_classif(X, df.bunched, discrete_features=[False]*2 + [True]*(len(names)-2),
                         random_state=0)
for n, m in sorted(zip(names, mi), key=lambda x: -x[1]):
    bar = "#" * int(m * 700)
    print(f"    {n:22s} {m:.4f} {bar}")

df.drop(columns=["_wk", "_q"]).to_parquet("../outputs/model_frame.parquet", index=False)
print("\nwrote ../outputs/model_frame.parquet")

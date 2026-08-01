"""Ship model C to the browser as a model-derived lookup grid.

Tree ensembles don't export to JS as cleanly as a logistic regression, so instead of
re-implementing 900 trees we run the fitted quantile models across the whole dataset and
aggregate their PREDICTIONS by borough x application type x proposal archetype.

These are the model's outputs, not raw empirical rates — labelled as such on the page.
Archetypes are derived from the description, which is what the model keys on anyway.
"""
import json
import numpy as np
import pandas as pd
import sqlite3
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

QA = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
      "Haringey", "London Legacy", "Enfield", "Hillingdon"}
con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""select area_name,app_type,description,start_date,decided_date,
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

# archetype — same buckets the page will infer from the user's text
ARCH = [
    ("flats",      r"conver\w+ .*(flat|apartment)|self.contained (flat|unit)"),
    ("changeuse",  r"change of use"),
    ("newdwell",   r"erection of .*(dwelling|house)"),
    ("twostorey",  r"two stor|2 stor|double stor|three stor|3 stor"),
    ("loft",       r"loft conversion|dormer"),
    ("extension",  r"extension"),
]
def arch(t):
    for name, pat in ARCH:
        if pd.Series([t]).str.contains(pat, regex=True).iloc[0]:
            return name
    return "other"
df["arch"] = df.desc.map(arch)
print(df.arch.value_counts().to_string())

tr = df[df.sub_year <= 2023]
tw = TfidfVectorizer(ngram_range=(1, 2), min_df=40, max_features=15000, sublinear_tf=True,
                     token_pattern=r"(?u)\b\w\w+\b")
Ttr = tw.fit_transform(tr.desc); Tall = tw.transform(df.desc)
svd = TruncatedSVD(n_components=60, algorithm="arpack", random_state=0)
Str = np.nan_to_num(svd.fit_transform(Ttr)); Sall = np.nan_to_num(svd.transform(Tall))

BOR = sorted(df.area_name.unique()); TYP = sorted(df.app_type.unique())
def frame(d, S):
    X = pd.DataFrame(S, columns=[f"t{i}" for i in range(S.shape[1])], index=d.index)
    X["borough"] = pd.Categorical(d.area_name, categories=BOR).codes
    X["app_type"] = pd.Categorical(d.app_type, categories=TYP).codes
    X["sub_month"] = d.sub_month.to_numpy(); X["sub_year"] = d.sub_year.to_numpy()
    X["desc_words"] = d.desc.str.split().str.len().to_numpy()
    return X

Xtr, Xall = frame(tr, Str), frame(df, Sall)
CAT = [Xtr.columns.get_loc("borough"), Xtr.columns.get_loc("app_type")]
for q in (0.25, 0.5, 0.9):
    m = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=300,
                                      learning_rate=0.07, max_leaf_nodes=31,
                                      min_samples_leaf=40, categorical_features=CAT,
                                      early_stopping=True, validation_fraction=0.15,
                                      random_state=0).fit(Xtr, tr.days)
    df[f"p{int(q*100)}"] = m.predict(Xall)
    print(f"  fitted q={q}")

grid, MIN = {}, 40
for (b, t, a), g in df.groupby(["area_name", "app_type", "arch"]):
    if len(g) < MIN or t not in ("Full", "Outline", "Conditions", "Amendment"):
        continue
    grid.setdefault(b, {}).setdefault(t, {})[a] = {
        "p25": int(round(g.p25.median())), "p50": int(round(g.p50.median())),
        "p90": int(round(g.p90.median())), "n": int(len(g)),
        "actual_p50": int(g.days.median()),
    }
fallback = {}
for (b, t), g in df.groupby(["area_name", "app_type"]):
    if t in ("Full", "Outline", "Conditions", "Amendment"):
        fallback.setdefault(b, {})[t] = {
            "p25": int(round(g.p25.median())), "p50": int(round(g.p50.median())),
            "p90": int(round(g.p90.median())), "n": int(len(g)),
            "actual_p50": int(g.days.median())}

cells = sum(len(v) for b in grid.values() for v in b.values())
print(f"\ngrid: {cells} borough x type x archetype cells (min n={MIN}) + fallbacks")
perf = json.load(open("../outputs/days_model.json"))
json.dump({"grid": grid, "fallback": fallback,
           "archetype_patterns": [[n, p] for n, p in ARCH],
           "performance": perf}, open("../outputs/days_grid.json", "w"), separators=(",", ":"))
print("wrote ../outputs/days_grid.json")
print("\nSAMPLE — Kingston / Full")
for a, v in grid.get("Kingston", {}).get("Full", {}).items():
    print(f"  {a:11s} p25={v['p25']:>3} p50={v['p50']:>3} p90={v['p90']:>3}  "
          f"(n={v['n']:,}, actual median {v['actual_p50']})")

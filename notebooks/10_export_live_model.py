"""Export a browser-runnable version of the approval model + a similarity corpus.

A logistic regression is a dot product, so it can run client-side: we ship the TF-IDF
vocabulary (idf weights) and the fitted coefficients, and re-implement the transform in
JS. Word n-grams only — char n-grams add ~0.01 ROC-AUC and are painful to replicate
exactly, so we drop them for a model we can actually verify in the browser.

Also exports a sample corpus of real applications so the page can answer
"here is what happened to applications like yours" (Brief DD's similarity-search idea).
"""
import json
import numpy as np
import pandas as pd
import sqlite3
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import roc_auc_score, average_precision_score

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}

con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""
 select area_name, app_type, description, start_date, decided_date,
        target_decision_date, app_state
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
df["sub_year"] = pd.to_datetime(df.start_date).dt.year
df["desc"] = df.description.fillna("").str.lower().str.strip()
df["app_type"] = df.app_type.fillna("Other").replace({"None": "Other"})
df = df[(df.desc.str.len() > 10) & (df.days.between(0, 400))]

tr, te = df[df.sub_year <= 2023], df[df.sub_year >= 2024]
ytr, yte = tr.approved.to_numpy(), te.approved.to_numpy()

# ---- word-only TF-IDF (JS-replicable) --------------------------------------
tw = TfidfVectorizer(ngram_range=(1, 2), min_df=30, max_features=20_000,
                     sublinear_tf=True, strip_accents=None, lowercase=True,
                     token_pattern=r"(?u)\b\w\w+\b")
Xw_tr, Xw_te = tw.fit_transform(tr.desc), tw.transform(te.desc)

enc = OneHotEncoder(handle_unknown="ignore", min_frequency=40)
Xc_tr, Xc_te = enc.fit_transform(tr[["area_name", "app_type"]]), enc.transform(te[["area_name", "app_type"]])

m = LogisticRegression(max_iter=2000, C=1.0, solver="liblinear")
m.fit(hstack([Xw_tr, Xc_tr]), ytr)
p = m.predict_proba(hstack([Xw_te, Xc_te]))[:, 1]

roc = roc_auc_score(yte, p)
pr_ref = average_precision_score(1 - yte, 1 - p)
print(f"BROWSER MODEL (word-only tfidf + borough + type)")
print(f"  ROC-AUC {roc:.4f}   refusal PR-AUC {pr_ref:.4f}   base refusal {1-yte.mean():.3f}")
k = int(.1 * len(te)); idx = np.argsort(p)[:k]
print(f"  top 10% at risk: {100*(1-yte[idx].mean()):.1f}% refused = {(1-yte[idx].mean())/(1-yte.mean()):.2f}x")

# calibration
bins = pd.qcut(p, 8, labels=False, duplicates="drop")
cal = [{"pred": round(float(p[bins == b].mean()), 3),
        "actual": round(float(yte[bins == b].mean()), 3), "n": int((bins == b).sum())}
       for b in np.unique(bins)]
print("  calibration:", " ".join(f"{c['pred']:.2f}->{c['actual']:.2f}" for c in cal))

# ---- export weights --------------------------------------------------------
vocab = tw.vocabulary_
idf = tw.idf_
nw = Xw_tr.shape[1]
coef = m.coef_[0]
words = {}
inv = {v: k for k, v in vocab.items()}
for j in range(nw):
    c = float(coef[j])
    if abs(c) > 0.012:                       # prune negligible terms
        words[inv[j]] = [round(float(idf[j]), 4), round(c, 4)]
cat_names = list(enc.get_feature_names_out())
cats = {n: round(float(coef[nw + i]), 4) for i, n in enumerate(cat_names)}
print(f"  exported {len(words):,} of {nw:,} word features, {len(cats)} category features")

# ---- similarity corpus ------------------------------------------------------
samp = (df.groupby("area_name", group_keys=False)
          .apply(lambda g: g.sample(min(len(g), 360), random_state=1)))
corpus = [{"d": r.description[:150], "b": r.area_name, "t": r.app_type,
           "a": int(r.approved), "y": int(r.sub_year), "n": int(r.days)}
          for r in samp.itertuples()]
print(f"  similarity corpus: {len(corpus):,} applications")

json.dump({
    "metrics": {"roc_auc": round(float(roc), 4), "refusal_pr_auc": round(float(pr_ref), 4),
                "base_refusal": round(float(1 - yte.mean()), 4),
                "top_decile_refusal": round(float(1 - yte[idx].mean()), 4),
                "n_train": int(len(tr)), "n_test": int(len(te)),
                "calibration": cal},
    "intercept": round(float(m.intercept_[0]), 4),
    "words": words, "cats": cats,
    "corpus": corpus,
}, open("../outputs/live_model.json", "w"), separators=(",", ":"))

import os
print(f"\nwrote ../outputs/live_model.json "
      f"({os.path.getsize('../outputs/live_model.json')/1e6:.2f} MB)")

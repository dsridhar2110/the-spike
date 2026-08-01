"""Does the free-text description actually carry approval signal?

Earlier we tested 10 crude keyword flags -> mutual information ~0.0005 (noise).
That was a bad test. Descriptions are 100% filled and describe exactly what is being
built. Here we do it properly: TF-IDF over word + character n-grams, and measure whether
it lifts the approval model above the 0.64 ROC-AUC ceiling we hit with metadata alone.

Ladder (each step adds one thing, time-split evaluated):
  1. borough only                      (the dumb baseline)
  2. + metadata (type, ward, timing)   (what we had)
  3. + TF-IDF text                     (the question)
  4. text alone                        (how much is in the words?)
"""
import numpy as np
import pandas as pd
import sqlite3
import json
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import roc_auc_score, average_precision_score

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}

con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""
 select area_name, ward_name, app_type, description, start_date, decided_date,
        target_decision_date, app_state
 from applications_tidy
 where app_size='Small' and start_date>='2018-01-01'
   and decided_date is not null and target_decision_date is not null
   and app_state in ('Permitted','Conditions','Rejected')
""", con)
df = df[~df.area_name.isin(QA_DROP)].copy()
df["approved"] = (df.app_state != "Rejected").astype(int)
d = pd.to_datetime(df.start_date)
df["sub_year"], df["sub_month"] = d.dt.year, d.dt.month
df["desc"] = df.description.fillna("").str.lower().str.strip()
df["app_type"] = df.app_type.fillna("Other").replace({"None": "Other"})
df["ward_name"] = df.ward_name.fillna("MISSING")
df = df[df.desc.str.len() > 10]

tr, te = df[df.sub_year <= 2023], df[df.sub_year >= 2024]
print(f"train {len(tr):,}  test {len(te):,}  approval base {te.approved.mean():.3f}")

ytr, yte = tr.approved.to_numpy(), te.approved.to_numpy()


def ev(name, Xtr, Xte):
    m = LogisticRegression(max_iter=1500, C=1.0, solver="liblinear")
    m.fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    roc = roc_auc_score(yte, p)
    pr_ref = average_precision_score(1 - yte, 1 - p)      # refusal side = the rare class
    print(f"  {name:34s} ROC-AUC {roc:.4f}   refusal PR-AUC {pr_ref:.4f}")
    return roc, pr_ref, p, m


print("\n" + "=" * 76)
print("LADDER — does text add signal for APPROVAL?")
print("=" * 76)

# 1. borough only
e1 = OneHotEncoder(handle_unknown="ignore")
r1 = ev("1. borough only", e1.fit_transform(tr[["area_name"]]), e1.transform(te[["area_name"]]))

# 2. + metadata
META = ["area_name", "app_type", "ward_name"]
e2 = OneHotEncoder(handle_unknown="ignore", min_frequency=40)
A, B = e2.fit_transform(tr[META]), e2.transform(te[META])
num_tr = csr_matrix(tr[["sub_year", "sub_month"]].to_numpy(dtype=float))
num_te = csr_matrix(te[["sub_year", "sub_month"]].to_numpy(dtype=float))
r2 = ev("2. + type, ward, timing", hstack([A, num_tr]), hstack([B, num_te]))

# 3. + TF-IDF words and char n-grams
tw = TfidfVectorizer(ngram_range=(1, 2), min_df=25, max_features=120_000,
                     sublinear_tf=True, strip_accents="unicode")
Tw_tr, Tw_te = tw.fit_transform(tr.desc), tw.transform(te.desc)
tc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=40,
                     max_features=120_000, sublinear_tf=True)
Tc_tr, Tc_te = tc.fit_transform(tr.desc), tc.transform(te.desc)
print(f"  [tfidf: {Tw_tr.shape[1]:,} word features, {Tc_tr.shape[1]:,} char features]")
r3 = ev("3. + TF-IDF description", hstack([A, num_tr, Tw_tr, Tc_tr]),
        hstack([B, num_te, Tw_te, Tc_te]))

# 4. text alone
r4 = ev("4. text alone (no borough)", hstack([Tw_tr, Tc_tr]), hstack([Tw_te, Tc_te]))

print("\n" + "=" * 76)
print(f"LIFT from adding text: ROC-AUC {r2[0]:.4f} -> {r3[0]:.4f} "
      f"({r3[0]-r2[0]:+.4f})   refusal PR-AUC {r2[1]:.4f} -> {r3[1]:.4f} ({r3[1]-r2[1]:+.4f})")
print("=" * 76)

# ---- what words actually predict refusal? ---------------------------------
mfull = r3[3]
names = (list(e2.get_feature_names_out()) + ["sub_year", "sub_month"]
         + ["w:" + w for w in tw.get_feature_names_out()]
         + ["c:" + w for w in tc.get_feature_names_out()])
coef = mfull.coef_[0]
word_idx = [i for i, n in enumerate(names) if n.startswith("w:")]
wc = sorted(((names[i][2:], coef[i]) for i in word_idx), key=lambda x: x[1])
print("\nWORDS MOST ASSOCIATED WITH REFUSAL")
for w, c in wc[:18]:
    print(f"  {w:34s} {c:+.3f}")
print("\nWORDS MOST ASSOCIATED WITH APPROVAL")
for w, c in wc[-14:][::-1]:
    print(f"  {w:34s} {c:+.3f}")

# ---- top-decile risk concentration ----------------------------------------
p = r3[2]
k = int(0.10 * len(te)); idx = np.argsort(p)[:k]
print(f"\nTop 10% flagged most-at-risk: {100*(1-yte[idx].mean()):.1f}% refused "
      f"vs {100*(1-yte.mean()):.1f}% base = {(1-yte[idx].mean())/(1-yte.mean()):.2f}x")

json.dump({
    "ladder": [
        {"step": "borough only", "roc": round(r1[0], 4), "refusal_pr": round(r1[1], 4)},
        {"step": "+ type, ward, timing", "roc": round(r2[0], 4), "refusal_pr": round(r2[1], 4)},
        {"step": "+ TF-IDF description", "roc": round(r3[0], 4), "refusal_pr": round(r3[1], 4)},
        {"step": "text alone", "roc": round(r4[0], 4), "refusal_pr": round(r4[1], 4)},
    ],
    "refusal_words": [{"word": w, "coef": round(float(c), 4)} for w, c in wc[:25]],
    "approval_words": [{"word": w, "coef": round(float(c), 4)} for w, c in wc[-20:][::-1]],
    "top_decile_refusal_rate": round(float(1 - yte[idx].mean()), 4),
    "base_refusal_rate": round(float(1 - yte.mean()), 4),
}, open("../outputs/text_model_results.json", "w"), indent=1)
print("\nwrote ../outputs/text_model_results.json")

"""Build the borough x application-type lookup that powers the public tool.

Every number here is an OBSERVED rate from real decisions — not a model prediction.
That is deliberate: "this is what happened to 14,093 applications like yours" is easier
to trust, and easier to explain, than a probability from a classifier with ROC-AUC 0.64.

The models stay in the deck as the analytical backbone; the tool speaks in real rates.
"""
import json
import sqlite3
import numpy as np
import pandas as pd

QA_DROP = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
           "Haringey", "London Legacy", "Enfield", "Hillingdon"}
MIN_CELL = 120          # below this we fall back to the borough-wide figure

con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""
 select area_name, app_type, start_date, decided_date, target_decision_date, app_state
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
df = df[(df.days >= 0) & (df.days < 400)]
df["app_type"] = df.app_type.fillna("Other").replace({"None": "Other"})

LONDON = {
    "n": int(len(df)),
    "approval": round(100 * df.approved.mean(), 1),
    "bunch": round(100 * df.bunched.mean(), 1),
    "approval_bunched": round(100 * df[df.bunched == 1].approved.mean(), 1),
    "approval_not_bunched": round(100 * df[df.bunched == 0].approved.mean(), 1),
    "median_days": int(df.days.median()),
    "p90_days": int(df.days.quantile(.9)),
}
LONDON["gap_pp"] = round(LONDON["approval_bunched"] - LONDON["approval_not_bunched"], 1)
print("LONDON:", LONDON)


def cell(sub):
    b, nb = sub[sub.bunched == 1], sub[sub.bunched == 0]
    return {
        "n": int(len(sub)),
        "approval": round(100 * sub.approved.mean(), 1),
        "bunch": round(100 * sub.bunched.mean(), 1),
        "approval_bunched": round(100 * b.approved.mean(), 1) if len(b) >= 30 else None,
        "approval_not_bunched": round(100 * nb.approved.mean(), 1) if len(nb) >= 30 else None,
        "median_days": int(sub.days.median()),
        "p25_days": int(sub.days.quantile(.25)),
        "p90_days": int(sub.days.quantile(.9)),
    }


boroughs = {}
for b, sub in df.groupby("area_name"):
    rec = cell(sub)
    rec["by_type"] = {}
    for t, s2 in sub.groupby("app_type"):
        if len(s2) >= MIN_CELL:
            rec["by_type"][t] = cell(s2)
    boroughs[b] = rec

types = sorted({t for r in boroughs.values() for t in r["by_type"]})
print(f"\n{len(boroughs)} boroughs | application types kept: {types}")

# a plain-English distribution of decision days, for the timeline strip
hist = {}
for b, sub in df.groupby("area_name"):
    counts, _ = np.histogram(sub.days.clip(0, 180), bins=np.arange(0, 186, 7))
    hist[b] = [int(x) for x in counts]

out = {"london": LONDON, "boroughs": boroughs, "types": types,
       "day_hist_bins": list(range(0, 180, 7)), "day_hist": hist,
       "min_cell": MIN_CELL}
open("../outputs/tool_data.json", "w").write(json.dumps(out, indent=1))

print("\nSAMPLE — Kingston")
k = boroughs["Kingston"]
print(f"  overall: n={k['n']:,} approval={k['approval']}% bunch={k['bunch']}% "
      f"median={k['median_days']}d")
print(f"  approved when bunched {k['approval_bunched']}% vs not bunched {k['approval_not_bunched']}%")
for t, v in k["by_type"].items():
    print(f"    {t:12s} n={v['n']:>6,} approval={v['approval']:>5}% bunch={v['bunch']:>5}% "
          f"median={v['median_days']:>3}d")

print("\nWORST GAPS (approval drop when caught in the rush):")
gaps = [(b, r["approval_bunched"] - r["approval_not_bunched"], r["n"])
        for b, r in boroughs.items()
        if r["approval_bunched"] is not None and r["approval_not_bunched"] is not None]
for b, g, n in sorted(gaps, key=lambda x: x[1])[:6]:
    print(f"  {b:22s} {g:+6.1f} pp   (n={n:,})")
print("\nwrote ../outputs/tool_data.json")

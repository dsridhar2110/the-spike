"""Per-borough data so the map can drive every other chart.

Two new tables:
  1. bunching histogram (-14..+14 days from the council's own deadline), per borough
  2. approval rate by development archetype, per borough (falls back to London where thin)
"""
import json
import re
import numpy as np
import pandas as pd
import sqlite3

QA = {"Havering", "Old Oak Park Royal", "Hammersmith and Fulham", "Westminster",
      "Haringey", "London Legacy", "Enfield", "Hillingdon"}
con = sqlite3.connect("../data/raw/housing.sqlite")
df = pd.read_sql("""select area_name, description, start_date, decided_date,
 target_decision_date, app_state from applications_tidy
 where app_size='Small' and start_date>='2018-01-01' and decided_date is not null
 and target_decision_date is not null and app_state in ('Permitted','Conditions','Rejected')""", con)
df = df[~df.area_name.isin(QA)].copy()
df["off"] = (pd.to_datetime(df.decided_date) - pd.to_datetime(df.target_decision_date)).dt.days
df["approved"] = (df.app_state != "Rejected").astype(int)
df["desc"] = df.description.fillna("").str.lower()
print(f"{len(df):,} rows, {df.area_name.nunique()} boroughs")

# ---------- 1. bunching histogram per borough -------------------------------
OFFS = list(range(-14, 15))
bunch = {}
for b, g in df.groupby("area_name"):
    v = g.off.value_counts()
    counts = [int(v.get(o, 0)) for o in OFFS]
    nb = [c for o, c in zip(OFFS, counts) if o != 0 and abs(o) <= 8]
    cf = sum(nb) / max(len(nb), 1)
    bunch[b] = {"counts": counts, "on_day": int(v.get(0, 0)),
                "excess": round(v.get(0, 0) / cf, 1) if cf else None,
                "counterfactual": int(round(cf)), "n": int(len(g))}
v = df.off.value_counts()
counts = [int(v.get(o, 0)) for o in OFFS]
nb = [c for o, c in zip(OFFS, counts) if o != 0 and abs(o) <= 8]
cf = sum(nb) / len(nb)
bunch["__LONDON__"] = {"counts": counts, "on_day": int(v.get(0, 0)),
                       "excess": round(v.get(0, 0) / cf, 1),
                       "counterfactual": int(round(cf)), "n": int(len(df))}
print(f"bunching: excess mass London {bunch['__LONDON__']['excess']}x | "
      f"range {min(x['excess'] for k,x in bunch.items() if k!='__LONDON__')}–"
      f"{max(x['excess'] for k,x in bunch.items() if k!='__LONDON__')}x")

# ---------- 2. development archetypes per borough ---------------------------
ARCH = [
    ("Rooflights / skylights", r"rooflight|roof light|skylight"),
    ("Basement / excavation", r"basement|excavat"),
    ("Demolition involved", r"demoli"),
    ("Loft conversion / dormer", r"loft conversion|dormer"),
    ("Extra storey on top", r"additional stor|extra stor|roof extension"),
    ("Single storey extension", r"single stor\w*[^.]{0,24}extension"),
    ("Outbuilding / garage", r"outbuilding|garage|shed|garden room"),
    ("Two storey extension", r"two stor\w*[^.]{0,24}extension"),
    ("New dwelling", r"erection of [^.]{0,30}(dwelling|house)"),
    ("Change of use", r"change of use"),
    ("Conversion into flats", r"conver\w+ [^.]{0,40}(flat|apartment)|self.contained (flat|unit)"),
]
for name, pat in ARCH:
    df["A_" + name] = df.desc.str.contains(pat, regex=True, na=False)

def types_for(g, min_n):
    out = []
    for name, _ in ARCH:
        s = g[g["A_" + name]]
        if len(s) >= min_n:
            out.append({"type": name, "n": int(len(s)),
                        "approval": round(100 * float(s.approved.mean()), 1)})
    return out

types = {"__LONDON__": {"rows": types_for(df, 2000),
                        "base": round(100 * float(df.approved.mean()), 1)}}
for b, g in df.groupby("area_name"):
    types[b] = {"rows": types_for(g, 60), "base": round(100 * float(g.approved.mean()), 1)}
cov = {b: len(v["rows"]) for b, v in types.items() if b != "__LONDON__"}
print(f"archetypes: London {len(types['__LONDON__']['rows'])} | "
      f"per borough min {min(cov.values())} max {max(cov.values())}")

json.dump({"offsets": OFFS, "bunch": bunch, "types": types},
          open("../outputs/per_borough.json", "w"), separators=(",", ":"))
import pathlib
print(f"wrote ../outputs/per_borough.json "
      f"({pathlib.Path('../outputs/per_borough.json').stat().st_size/1024:.0f} KB)")

print("\nSAMPLE — Kingston")
k = bunch["Kingston"]
print(f"  spike {k['on_day']:,} vs {k['counterfactual']:,} expected = {k['excess']}x")
for r in types["Kingston"]["rows"][:5]:
    print(f"  {r['type']:26s} {r['approval']:5.1f}%  (n={r['n']:,})")

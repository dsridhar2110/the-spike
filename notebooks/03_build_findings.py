"""Produce outputs/findings.json — every number the demo page renders.

Analysis set (stated as a limitation on the page):
  - app_size = 'Small'            (minor/householder — the 8-week statutory class)
  - start_date >= 2018-01-01      (8 full years, avoids sparse early scrape)
  - target_decision_date present  (the council's own declared deadline)
  - borough passes QA: n >= 1500, target coverage >= 88%, refusal rate > 2%
    -> excludes Havering (0.0% refusals = broken scrape), Old Oak Park Royal,
       Hammersmith & Fulham, Westminster, Haringey, London Legacy (low volume),
       and Brent/Wandsworth/Newham/Hounslow/Greenwich (no target_decision_date).
"""
import json
import sqlite3
from pathlib import Path

c = sqlite3.connect("../data/raw/housing.sqlite")
q = lambda s, *a: c.execute(s, a).fetchall()

BASE = ("app_size='Small' and start_date>='2018-01-01' "
        "and decided_date is not null and target_decision_date is not null")

# ---- borough QA gate -------------------------------------------------------
qa = q(f"""select area_name, count(*) n,
   1.0*sum(case when app_state='Rejected' then 1 else 0 end)/count(*) refrate
 from applications_tidy where {BASE} group by 1""")
KEEP = sorted(n for n, tot, rr in qa if tot >= 1500 and rr > 0.02)
EXCLUDED = sorted(n for n, tot, rr in qa if not (tot >= 1500 and rr > 0.02))
inlist = ",".join(f"'{b}'" for b in KEEP)
SET = f"{BASE} and area_name in ({inlist})"
print(f"analysis set: {len(KEEP)} boroughs -> {KEEP}")
print(f"excluded: {EXCLUDED}")

OFF = "cast(julianday(decided_date)-julianday(target_decision_date) as int)"

# ---- 1. the bunching histogram --------------------------------------------
rows = q(f"select {OFF} d, count(*) from applications_tidy where {SET} group by 1")
h = {d: n for d, n in rows if d is not None}
total = sum(h.values())
bunch = [{"d": d, "n": h.get(d, 0)} for d in range(-14, 15)]
nb = [h.get(k, 0) for k in range(-8, 9) if k != 0]
counterfactual = sum(nb) / len(nb)
on_day = h.get(0, 0)

# ---- 2. refusal rate by offset --------------------------------------------
rows = q(f"""select {OFF} d,
   sum(case when app_state in ('Permitted','Conditions') then 1 else 0 end) a,
   sum(case when app_state='Rejected' then 1 else 0 end) r
 from applications_tidy where {SET} and app_state in ('Permitted','Conditions','Rejected')
 group by 1""")
rr = {d: (a, r) for d, a, r in rows if d is not None}
refusal = [{"d": d, "approved": rr.get(d, (0, 0))[0], "refused": rr.get(d, (0, 0))[1],
            "rate": round(100 * rr.get(d, (0, 0))[1] / max(sum(rr.get(d, (0, 0))), 1), 2)}
           for d in range(-14, 15)]
agg = lambda ks: (sum(rr.get(k, (0, 0))[0] for k in ks), sum(rr.get(k, (0, 0))[1] for k in ks))
ba, br = agg(range(-14, 0)); oa, orr = agg([0]); aa, ar = agg(range(1, 15))

# ---- 3. borough league table ----------------------------------------------
rows = q(f"""select area_name, count(*) n,
   sum(case when {OFF}=0 then 1 else 0 end) onday,
   sum(case when app_state='Rejected' then 1 else 0 end) rej,
   sum(case when app_state in ('Permitted','Conditions') then 1 else 0 end) app
 from applications_tidy where {SET} group by 1
 order by 1.0*sum(case when {OFF}=0 then 1 else 0 end)/count(*) desc""")
boroughs = [{"name": n, "n": tot, "on_day_pct": round(100 * o / tot, 1),
             "refusal_pct": round(100 * rj / max(rj + ap, 1), 1)}
            for n, tot, o, rj, ap in rows]

# ---- 4. persistence by year -----------------------------------------------
rows = q(f"""select substr(start_date,1,4) yr,
   sum(case when {OFF}=0 then 1 else 0 end) o, count(*) t
 from applications_tidy where {SET} group by 1 order by 1""")
years = [{"year": y, "pct": round(100 * o / t, 1), "n": t}
         for y, o, t in rows if t > 500 and y < "2026"]

# ---- 5. appeals as ground truth -------------------------------------------
rows = q(f"""select area_name,
   sum(case when appeal_result like '%Allow%' then 1 else 0 end) al,
   sum(case when appeal_result like '%Dismiss%' then 1 else 0 end) di
 from applications_tidy
 where app_size='Small' and appeal_result is not null and area_name in ({inlist})
 group by 1""")
appeals = sorted(({"name": n, "overturn_pct": round(100 * a / (a + d), 1), "n": a + d}
                  for n, a, d in rows if a + d >= 30),
                 key=lambda x: -x["overturn_pct"])

out = {
    "meta": {
        "total_decisions": total,
        "n_boroughs": len(KEEP),
        "boroughs_included": KEEP,
        "boroughs_excluded": EXCLUDED,
        "date_from": q(f"select min(start_date) from applications_tidy where {SET}")[0][0],
        "date_to": q(f"select max(start_date) from applications_tidy where {SET}")[0][0],
    },
    "headline": {
        "on_day_n": on_day,
        "on_day_pct": round(100 * on_day / total, 1),
        "counterfactual": round(counterfactual),
        "excess_mass_x": round(on_day / counterfactual, 1),
        "excess_n": round(on_day - counterfactual),
        "day_before": h.get(-1, 0),
        "day_after": h.get(1, 0),
    },
    "refusal_summary": {
        "before": round(100 * br / max(ba + br, 1), 1),
        "on": round(100 * orr / max(oa + orr, 1), 1),
        "after": round(100 * ar / max(aa + ar, 1), 1),
        "n_before": ba + br, "n_on": oa + orr, "n_after": aa + ar,
    },
    "bunching": bunch,
    "refusal_by_offset": refusal,
    "boroughs": boroughs,
    "years": years,
    "appeals": appeals,
}

Path("../outputs").mkdir(exist_ok=True)
Path("../outputs/findings.json").write_text(json.dumps(out, indent=1))

print(f"\nHEADLINE: {out['headline']['on_day_pct']}% of {total:,} decisions land on day 0")
print(f"          {out['headline']['excess_mass_x']}x excess mass "
      f"(+{out['headline']['excess_n']:,} applications)")
print(f"REFUSAL:  before {out['refusal_summary']['before']}% | "
      f"ON {out['refusal_summary']['on']}% | after {out['refusal_summary']['after']}%")
print(f"SPREAD:   {boroughs[0]['name']} {boroughs[0]['on_day_pct']}% -> "
      f"{boroughs[-1]['name']} {boroughs[-1]['on_day_pct']}%")
print(f"YEARS:    {[y['pct'] for y in years]}")
print("wrote outputs/findings.json")

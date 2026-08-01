"""Check 1 found that start_date == date_received (99.7%), NOT date_validated (43.9%).

The statutory 8-week clock legally runs from VALIDATION, not receipt. So "56 days from
start_date" was the wrong basis. Two corrected measures:

  A. decided_date - date_validated   -> the legally correct statutory clock
  B. decided_date - target_decision_date -> the council's OWN declared deadline.
     This is the strongest test available: target_decision_date already absorbs any
     agreed extension of time, so bunching at 0 cannot be explained away by extensions.
"""
import sqlite3

c = sqlite3.connect("../data/raw/housing.sqlite")
q = lambda s: c.execute(s).fetchall()


def histogram(expr, where, lo, hi, title, note):
    rows = q(f"""select cast({expr} as int) d, count(*)
                 from applications_tidy where {where} group by 1""")
    h = {d: n for d, n in rows if d is not None}
    tot = sum(n for d, n in h.items() if -400 < d < 400)
    peak = max(range(lo, hi + 1), key=lambda k: h.get(k, 0))
    scale = max(h.get(k, 0) for k in range(lo, hi + 1)) / 46
    print("=" * 72)
    print(title)
    print("=" * 72)
    for d in range(lo, hi + 1):
        n = h.get(d, 0)
        mark = "  <<< " if d == peak else ""
        print(f"  {d:>+4} : {n:>7,} {'#' * int(n / max(scale,1))}{mark}")
    print(f"\n  peak = {peak:+d}   share on peak = {100*h.get(peak,0)/tot:.1f}% of all decided")
    print(f"  {note}\n")
    return h, tot


BASE = "decided_date is not null and app_size='Small' and start_date>='2018-01-01'"

hA, totA = histogram(
    "julianday(decided_date)-julianday(date_validated)",
    f"{BASE} and date_validated is not null",
    46, 66,
    "A — days from VALIDATION (the legally correct statutory clock)",
    "statutory target for minor/householder applications = 56 days (8 weeks)",
)

hB, totB = histogram(
    "julianday(decided_date)-julianday(target_decision_date)",
    f"{BASE} and target_decision_date is not null",
    -10, 10,
    "B — days RELATIVE TO THE COUNCIL'S OWN STATED DEADLINE  (0 = exactly on time)",
    "target_decision_date already includes any agreed extension of time,"
    "\n  so a spike at 0 CANNOT be explained by extension-of-time agreements.",
)

# how extreme is the spike vs a local counterfactual?
def excess(h, peak, span=8):
    nb = [h.get(peak + k, 0) for k in range(-span, span + 1) if k != 0]
    nb = sorted(nb)
    counter = sum(nb) / len(nb)
    return h.get(peak, 0), counter, h.get(peak, 0) / max(counter, 1)


print("=" * 72)
print("HOW BIG IS THE SPIKE, REALLY?")
print("=" * 72)
for label, h, peak in [("statutory clock (validation + 56)", hA, 56),
                       ("council's own deadline (day 0)", hB, 0)]:
    obs, cf, ratio = excess(h, peak)
    print(f"  {label}")
    print(f"    observed on the day : {obs:>8,}")
    print(f"    neighbouring-day avg: {cf:>8,.0f}")
    print(f"    EXCESS MASS         : {ratio:>8.1f}x   (+{obs-cf:,.0f} applications)")

print()
print("=" * 72)
print("DOES THE DEADLINE SKEW THE DECISION? (refusal rate on the day vs around it)")
print("=" * 72)
rows = q(f"""select cast(julianday(decided_date)-julianday(target_decision_date) as int) d,
   sum(case when app_state in ('Permitted','Conditions') then 1 else 0 end) a,
   sum(case when app_state='Rejected' then 1 else 0 end) r
 from applications_tidy
 where {BASE} and target_decision_date is not null
   and app_state in ('Permitted','Conditions','Rejected')
 group by 1""")
d = {x[0]: (x[1], x[2]) for x in rows if x[0] is not None}
on_a, on_r = d.get(0, (0, 0))
before = [d.get(k, (0, 0)) for k in range(-14, 0)]
ba, br = sum(x[0] for x in before), sum(x[1] for x in before)
after = [d.get(k, (0, 0)) for k in range(1, 15)]
aa, ar = sum(x[0] for x in after), sum(x[1] for x in after)
print(f"  14 days BEFORE deadline : refusal {100*br/max(ba+br,1):5.1f}%   (n={ba+br:,})")
print(f"  ON the deadline         : refusal {100*on_r/max(on_a+on_r,1):5.1f}%   (n={on_a+on_r:,})")
print(f"  14 days AFTER deadline  : refusal {100*ar/max(aa+ar,1):5.1f}%   (n={aa+ar:,})")

print()
print("=" * 72)
print("BOROUGH LEAGUE TABLE — % of decisions landing exactly on their own deadline")
print("=" * 72)
rows = q(f"""select area_name,
   sum(case when date(decided_date)=date(target_decision_date) then 1 else 0 end) onday,
   count(*) tot
 from applications_tidy where {BASE} and target_decision_date is not null
 group by 1 having tot>800 order by 1.0*onday/tot desc""")
for n_, o, t in rows:
    print(f"  {n_:22s} {100*o/t:5.1f}%   (n={t:,})")

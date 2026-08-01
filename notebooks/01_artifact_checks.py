"""Artifact checks on the day-56 bunching finding.

Question: is the spike at 56 days a real behavioural phenomenon, or a data artifact?

Tests
  1. Which date field is the clock actually running from? (start_date vs date_validated vs date_received)
  2. Does `target_decision_date` exist, and do decisions bunch on IT rather than start+56?
     -> if target > start+56 sometimes, that is extension-of-time agreements, visible.
  3. Is the spike persistent across years, or an artifact of one scrape/one period?
  4. Day-of-week of day-56 decisions -> batch auto-stamping would look non-human.
  5. Are day-56 decisions concentrated on a few calendar dates (batch dumps)?
"""
import sqlite3
from collections import Counter

DB = "../data/raw/housing.sqlite"
c = sqlite3.connect(DB)
q = lambda s: c.execute(s).fetchall()
N = 343141

BASE = "decided_date is not null and start_date >= '2018-01-01' and app_size = 'Small'"

print("=" * 72)
print("CHECK 1 — which date field is the statutory clock running from?")
print("=" * 72)
for f in ["start_date", "date_received", "date_validated", "target_decision_date",
          "decision_date", "decision_issued_date", "decision_published_date"]:
    n = q(f'select count("{f}") from applications_tidy')[0][0]
    print(f"  {f:26s} filled {n:>7,}  ({100*n/N:4.1f}%)")

agree = q(f"""select
  sum(case when date(start_date)=date(date_validated) then 1 else 0 end),
  sum(case when date(start_date)=date(date_received)  then 1 else 0 end),
  count(*)
 from applications_tidy
 where date_validated is not null and date_received is not null""")[0]
print(f"\n  where both present (n={agree[2]:,}):")
print(f"    start_date == date_validated : {agree[0]:,} ({100*agree[0]/max(agree[2],1):.1f}%)")
print(f"    start_date == date_received  : {agree[1]:,} ({100*agree[1]/max(agree[2],1):.1f}%)")
print("  (statutory clock legally runs from VALIDATION, so start==validated is the")
print("   correct basis for a 56-day claim)")

print()
print("=" * 72)
print("CHECK 2 — extension-of-time agreements: does target_decision_date move?")
print("=" * 72)
rows = q(f"""select
    cast(julianday(target_decision_date)-julianday(start_date) as int) as target_days,
    count(*)
  from applications_tidy
  where {BASE} and target_decision_date is not null
  group by 1 order by 2 desc limit 12""")
if rows:
    tot = sum(r[1] for r in rows)
    print("  target_decision_date minus start_date (top values):")
    for d, n in rows:
        print(f"    {d:>5} days : {n:>7,}")
    print(f"\n  -> if this is overwhelmingly 56, councils are NOT extending the clock;")
    print(f"     the deadline is fixed and the bunching is behavioural.")
    # how often did they beat / miss their own stated target
    hit = q(f"""select
        sum(case when date(decided_date) <  date(target_decision_date) then 1 else 0 end),
        sum(case when date(decided_date) =  date(target_decision_date) then 1 else 0 end),
        sum(case when date(decided_date) >  date(target_decision_date) then 1 else 0 end),
        count(*)
      from applications_tidy
      where {BASE} and target_decision_date is not null""")[0]
    print(f"\n  decided BEFORE own target : {hit[0]:>7,} ({100*hit[0]/hit[3]:.1f}%)")
    print(f"  decided ON     own target : {hit[1]:>7,} ({100*hit[1]/hit[3]:.1f}%)  <-- the spike")
    print(f"  decided AFTER  own target : {hit[2]:>7,} ({100*hit[2]/hit[3]:.1f}%)")
else:
    print("  target_decision_date not usable on this subset")

print()
print("=" * 72)
print("CHECK 3 — is the spike persistent across years?")
print("=" * 72)
rows = q(f"""select substr(start_date,1,4) yr,
   sum(case when cast(julianday(decided_date)-julianday(start_date) as int)=56 then 1 else 0 end) d56,
   count(*) tot
 from applications_tidy where {BASE} group by 1 order by 1""")
print("  year   n_small   on day 56   share")
for yr, d56, tot in rows:
    if tot > 200:
        print(f"  {yr}  {tot:>8,}   {d56:>8,}   {100*d56/tot:5.1f}%")
print("  -> a real behavioural effect should persist every year, not appear once")

print()
print("=" * 72)
print("CHECK 4 — day of week: do day-56 decisions look human?")
print("=" * 72)
DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
for label, cond in [("day 56 exactly", "= 56"), ("all other days", "!= 56")]:
    rows = q(f"""select cast(strftime('%w', decided_date) as int), count(*)
      from applications_tidy
      where {BASE} and cast(julianday(decided_date)-julianday(start_date) as int) {cond}
      group by 1""")
    tot = sum(r[1] for r in rows)
    d = {r[0]: r[1] for r in rows}
    line = "  ".join(f"{DOW[i]} {100*d.get(i,0)/max(tot,1):4.1f}%" for i in range(7))
    print(f"  {label:16s} {line}")
print("  -> weekend share should be near zero for genuine officer decisions.")
print("     A flat/random spread would suggest machine stamping.")

print()
print("=" * 72)
print("CHECK 5 — are day-56 decisions dumped on a few calendar dates?")
print("=" * 72)
rows = q(f"""select date(decided_date), count(*)
  from applications_tidy
  where {BASE} and cast(julianday(decided_date)-julianday(start_date) as int)=56
  group by 1 order by 2 desc""")
tot = sum(r[1] for r in rows)
print(f"  {tot:,} day-56 decisions spread over {len(rows):,} distinct calendar dates")
print(f"  busiest single date: {rows[0][0]} with {rows[0][1]:,} ({100*rows[0][1]/tot:.2f}%)")
print(f"  top 10 dates account for {100*sum(r[1] for r in rows[:10])/tot:.1f}% of them")
print("  -> heavy concentration on a handful of dates = batch artifact.")
print("     Wide spread = genuine day-by-day behaviour.")

print()
print("=" * 72)
print("CHECK 6 — does the spike survive per-borough, or is it a few councils?")
print("=" * 72)
rows = q(f"""select area_name,
   sum(case when cast(julianday(decided_date)-julianday(start_date) as int)=56 then 1 else 0 end) d56,
   count(*) tot
 from applications_tidy where {BASE} group by 1 having tot > 1500 order by 3 desc""")
above = sum(1 for _, d, t in rows if 100 * d / t > 5)
print(f"  boroughs with >1500 small apps: {len(rows)}")
print(f"  of those, {above} have >5% of decisions landing exactly on day 56")
print("  -> if most boroughs show it, it is systemic, not one council's data quirk")

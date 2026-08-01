# SPIKE Girls SB — 3-minute pitch

**House London #0 · Data Brief DD · 1 August 2026**

> **Structure:** make it personal → show the spike → show the cost → show it's a choice →
> show you tried to break it → make the ask.
>
> **Do not say** "PR-AUC", "ROC-AUC", "gradient boosting", or "classifier" out loud. The
> model lives on the page for anyone who asks. Your rigour signal is the six checks.

---

## The opener — use the team name *(15s)*

> "We're the **Spike Girls**. So we went looking for a spike.
>
> We found one."

*Beat. Then straight into the tool.*

---

## 0:15 — Make it personal *(30s)*

**Have the page open. Ask the room.**

> "Who here has applied for planning permission? Or lives in a London borough — shout one
> out."

*Pick it in the dropdown. Ideally* **Sutton**, **Richmond**, **Islington** *or*
**Tower Hamlets** *— biggest effects. Read what appears.*

> "Right — Richmond. Of 11,019 applications since 2018, 82% were approved. Typical
> decision, 55 days.
>
> But look at this one. **11% of them were decided on the exact final day of the legal
> deadline.** And when that happens, approval drops from **82% to 66%**."

---

## 0:45 — The spike *(40s)*

> "Here's why that number exists.
>
> Councils get 8 weeks to decide. The government judges them on hitting it. The average
> decision in London takes **56 days** — and the legal limit is **56 days**. Exactly.
>
> Real work doesn't land on round numbers. So we plotted every decision by how close to
> the deadline it landed."

**Show the chart. Say nothing for two seconds.**

> "**One in five lands on precisely the last day.** Ten times what the surrounding days
> predict.
>
> Day before: **10,825**. On the day: **34,051**. Day after: **2,329**.
>
> Councils aren't deciding faster. They're holding applications and clearing them at the
> deadline."

---

## 1:25 — What it costs *(35s)*

> "And it isn't harmless. Across all 18 boroughs, applications decided in that rush are
> approved **71.9%** of the time. Everything else — **82.1%**. **Ten points.**
>
> **Sixteen of eighteen boroughs** show it.
>
> Now — the obvious objection is that harder cases take longer, and harder cases get
> refused. But if that were true, refusals would climb steadily the longer you wait. They
> don't. They spike on one day and then *fall*.
>
> **Difficulty doesn't make a cliff edge. A deadline does.**"

---

## 2:00 — It's a choice *(20s)*

> "And this isn't physics. **Kingston** decides **38.9%** of applications on the deadline.
> **Merton** decides **1.6%** — comparable volume, same law, same clock.
>
> **Twenty-four times the difference.** Somebody already knows how not to do this."

---

## 2:20 — We tried to break it *(25s)*

> "We spent most of today trying to kill this, not prove it. Six ways it could have been a
> data glitch — wrong date field, deadline extensions, one odd year, one broken borough,
> auto-stamped dates, a bulk upload.
>
> It survived all six. The strongest one: **when a council agrees an extension, its target
> date moves** — and we measured against each council's *own* target. So it can't be
> extensions.
>
> And it isn't overwork either. We checked — the busiest boroughs aren't the worst."

---

## 2:45 — The ask *(15s)*

> "The 8-week target was meant to stop councils sitting on applications. It's become
> something they manage *to*. And the boroughs bunching hardest lose most on appeal —
> **Barnet loses 42%** — so the time saved gets spent again, and the applicant pays twice.
>
> **Measure decisions that survive appeal. Not decisions issued within 8 weeks.**
>
> And somebody should go ask Merton how they do it."

---

## Numbers to know cold

| | |
|---|---|
| Decisions analysed | **149,813** · 18 boroughs · 2018–2025 |
| Land on the exact deadline | **21.6%** — 34,051 |
| Times more than expected | **10.2×** |
| Day before / on / after | 10,825 / **34,051** / 2,329 |
| Approved normally vs in the rush | **82.1% → 71.9%** (−10.2 pp) |
| Boroughs showing the gap | **16 of 18** |
| Worst / best borough | Kingston **38.9%** · Merton **1.6%** |
| Barnet appeal losses | **41.6%** |

**Biggest approval gaps** (for picking a borough live): Islington −22.8 · Tower Hamlets
−17.9 · Sutton −16.7 · Richmond −16.2 · Lambeth −14.7.

---

## If asked

**"Isn't this already known?"** ← *the most likely challenge, from a planner*
> "You may well already suspect it — people in planning talk about the 8-week target
> driving behaviour. What we haven't had is a number. Now we do: one in five, ten times
> the expected rate, and it costs about ten points of approval."

**"Did you build a model?"**
> "Yes — to test one thing: is this about the applications or about the institutions? It
> beats simply looking up your borough by 13%. That small margin is the answer. Once you
> know the council, knowing what's being built adds almost nothing. It's the council, not
> your application. We're not proposing to deploy it — the table's on the page."

**"Aren't councils just overloaded?"**
> "We tested it. Sorted by how many applications came in that week, the rates run 22, 22,
> 21, 20, 23 percent — flat, and the busiest group isn't the worst. It isn't capacity."

**"Are you saying the deadline causes refusals?"**
> "No — it's associated, not proven. What we can say is it's a sharp break at one exact
> point, which rules out the obvious explanation. We can't see case complexity or
> negotiation history, and that's on the page."

**"Why only 18 boroughs?"**
> "Five don't publish a target decision date at all — Brent, Wandsworth, Newham, Hounslow,
> Greenwich. We dropped eight more on data quality. Havering records a 0.0% refusal rate,
> which isn't credible. All named on the page."

**"Where's the data from?"**
> "343,000 London planning applications from UK PlanIt, from the hackathon Drive.
> One table, no joins, nothing licence-restricted. No WhereToBuild data in this at all."

---

## Demo mechanics

- Page **already open**, scrolled to top, dropdowns showing. Never open it live.
- Ask for a borough from the room. Have Sutton / Richmond / Islington ready if nobody answers.
- Hover one bar on the spike chart so they see it's real data.
- Finish on the six-checks section and **leave it on screen** for questions.
- **Time it out loud twice before 17:30.** The whole thing is ~3:00 with no slack.

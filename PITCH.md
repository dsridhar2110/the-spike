# The Spike — 3-minute pitch

**Spike Girls SB · House London #0 · Data Brief DD**

> **Two people.** One speaks, one drives the page. Cues in `[brackets]` are for the driver.
> **Never read a heading aloud** — the room can see it. Say the thing the heading doesn't.
> **346 spoken words ≈ 2:25 at a calm pace** — the slack is deliberate. Pauses land; rushing does not.

---

## 0:00 — Open *(20s)*

`[page at the top]`

> "We're the **Spike Girls**. We went looking for a spike. We found one.
>
> Councils have **8 weeks** to decide a planning application. We took **150,000
> decisions** across **18 boroughs** and **8 years**, and asked one question:
> *when* do they actually happen?"

---

## 0:20 — The map *(30s)*

`[scroll to the map — Approval rate is already selected]`

> "Where you apply matters. **Southwark** approves **92%**. **Barking and Dagenham**,
> **73%**. Same city, same law.
>
> `[click Decision time]`
>
> Timing swings too — **Redbridge** decides in **45 days**, **Bromley** takes **63**.
>
> But look how tightly the middle clusters. That looked boring — until we asked *why*."

---

## 0:50 — The spike *(30s)*

`[scroll to the spike chart — pause two seconds before speaking]`

> "Every decision, plotted by how close it landed to the council's own deadline.
>
> **The most common day to decide a planning application in London is the last legal
> one.**
>
> On a normal day, about **3,000** decisions. On the deadline day &mdash; **33,000**.
> **Ten times** as many.
>
> They're not deciding faster. They're clearing them at the buzzer."

---

## 1:20 — What it costs *(25s)*

`[scroll to the 16-of-18 chart]`

> "And it costs you. **Kensington** normally approves **93%**. In that rush, **83%**.
>
> **Waltham Forest** is the exception — flat, no penalty. But it's one of only two.
> **Sixteen of eighteen** approve less against the clock. London-wide, **82% to 72%**."

---

## 1:45 — Feature discovery *(45s)*  ← **the heart of it**

`[scroll to Feature discovery]`

> "Then the other half — not *when*, but *what*.
>
> Think about asking a neighbour a favour. *'Can you water my plants?'* — of course.
> *'Can you keep my dog for a month?'* — suddenly there are questions. Same neighbour.
> Different ask.
>
> Planning works exactly like that, and we can measure it. We ran the **description** of
> every application — the applicant's own words — through a text model. It was never told
> what any of these things mean.
>
> It learned the size of the ask. **Rooflights: 84% approved.** **Basements: 84%.** Then
> it falls — **new dwelling, 71%. Change of use, 68%. Converting a house into flats, 66%.**
> Eighteen points below the London average.
>
> Nobody labelled these categories. **The words did it.** Ask for more, get refused more."

---

## 2:30 — The classifier *(25s)*

`[scroll to The classifier — the example is already typed]`

> "So we built the thing that doesn't exist. Type what you want to build, pick your
> borough.
>
> `[point at the result]`
>
> Two-storey side extension and loft conversion in Kingston — **49%**, against a **78%**
> baseline. And it shows you **which words** did the damage.
>
> Trained on **122,000** decisions, tested on **28,000** it never saw. **ROC-AUC 0.71**,
> running entirely in your browser."

---

## 2:55 — Close *(15s)*

> "The 8-week target was meant to stop councils sitting on applications. It's become
> something they manage *to*.
>
> **Measure decisions that survive appeal — not decisions issued inside 8 weeks.**"

---

## Driver's cue sheet

| Cue | Action |
|---|---|
| "We found one" | stay at the top |
| "In Southwark" | scroll to map, **Approval rate** |
| "And how long it takes" | click **Decision time** |
| "This is every decision" | scroll to the spike, **then stop moving** |
| "And it costs you" | scroll to 16-of-18 |
| "not *when*, but *what*" | scroll to Feature discovery |
| "So we built the thing" | scroll to The classifier |
| "The 8-week target was meant to" | leave it on screen |

**Don't touch anything during the spike chart.** Two seconds of stillness is what makes it land.

---

## Numbers to know cold

| | |
|---|---|
| Decisions analysed | **150,879** · 18 boroughs · 2018–2025 |
| On the deadline | **33,227** — 1 in 5 — **10.4×** expected |
| Neighbouring day | ~**3,200** |
| Approved normally → in the rush | **82.1% → 71.9%** · **16 of 18** boroughs |
| Kensington | 93% → 83% (**−9.9**) |
| Waltham Forest | 75% → 75% (**+0.4**) — the exception |
| Southwark / Barking | **92%** / **73%** approval |
| Redbridge / Bromley | **45** / **63** days |
| Rooflights / flats conversion | **84.1%** / **66.1%** vs **79.9%** average |
| Classifier | ROC-AUC **0.7103**, 122k train / 28k test |

---

## If asked

**"Isn't this already known?"**
> "If you work in planning you may suspect it. What we haven't had is a number. Now we do —
> one in five, ten times expected, and it costs about ten points of approval."

**"Aren't councils just overloaded?"**
> "We checked. Sorted by weekly intake the rates run 22, 22, 21, 20, 23 percent — flat, and
> the busiest group isn't the worst. It isn't capacity."

**"Does the deadline *cause* the refusals?"**
> "Associated, not proven. But it's a sharp break at one exact day, which rules out
> 'harder cases take longer' — difficulty doesn't make a cliff edge."

**"Why only 18 boroughs?"**
> "Five publish no target decision date at all. We dropped eight more on data quality —
> Havering records a 0.0% refusal rate, which isn't credible. All named on the map."

**"Where's the data from?"**
> "343,000 London applications from UK PlanIt, scraped and filtered by Jamie who runs this
> event. One table, no joins, nothing licence-restricted."

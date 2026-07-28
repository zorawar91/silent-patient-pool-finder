# SPPF — Leadership Briefing Script

**What this is:** a talk track for explaining SPPF to leadership — the vision,
how it works, and how it was built. Roughly **12–15 minutes** spoken, with the
technical depth in clearly-marked blocks you can skip or expand depending on the
room.

**How it differs from the demo script:** [EXEC_DEMO_SCRIPT.md](EXEC_DEMO_SCRIPT.md)
drives the live product in 8 minutes across 3 views. This one explains the
*thinking* and works with or without a screen.

**Golden rule for this room:** every number below is real and reproducible. If
you don't know an answer, say "I'll get you the exact figure" — the whole
credibility of this pitch rests on not overclaiming.

---

## PART 1 — THE VISION (3 minutes)

### 1.1 The cold open

> "Every commercial asset IQVIA sells — claims, LRx, OCE, the whole portfolio —
> begins at the moment a patient is diagnosed. That's not a criticism; it's the
> product boundary.
>
> But roughly 45 million American adults are walking around today with
> undiagnosed diabetes, hypertension or thyroid disease. That's the published
> CDC and NHANES figure, not ours. Those people are invisible to every dataset
> we own, because you only appear in claims data *after* someone finds you.
>
> Nobody sells the map of where they are. That's what we built."

### 1.2 Why this is a business, not a public-health poster

> "The commercial logic is simple. Undiagnosed patients are the *upstream supply*
> for every downstream product. Find them, and you create diagnosed patients —
> who then show up in claims, get treated, and get tracked by the tools we
> already sell. SPPF is the demand-generation layer that sits above the
> portfolio rather than competing with any part of it.
>
> And it's a new SKU for an existing sales force. Nothing to retrain."

### 1.3 The three questions it answers

> "It answers three questions in order: **where** are the undiagnosed patients,
> **who** do we call to reach them, and **did it work**.
>
> That third one matters more than it sounds. Screening-campaign ROI is
> essentially unmeasured across this industry. Money goes out, awareness goes
> up, and nobody can prove diagnosis rates moved. We made that a measured number
> with confidence intervals — which is what turns a report into a subscription."

---

## PART 2 — THE LOGIC (5 minutes)

### 2.1 The non-technical version

> "Think of it as scoring every county in America the way you'd size any market
> — except the customers don't know they're customers yet.
>
> For all **3,144 US counties** we ask seven questions: How much disease is
> there? How much of it is undiagnosed? Can patients get care? What's holding
> them back? Who insures them? Could we actually run a program there? And is the
> problem growing or shrinking?
>
> Each becomes a 0–100 score. We blend them into one Opportunity Score, then
> hand back a ranked list and a recommended program type for each county."

### 2.2 Where the numbers come from — worked example

> "Take Starr County, Texas — the top-ranked county in America.
>
> We start with eight public numbers: 44,621 adults, 20% diagnosed diabetes,
> 37% hypertension, 34% poverty, 32% uninsured, a federal primary-care shortage
> designation, no federally-funded clinic, and 81% Medicare Advantage penetration.
>
> The undiagnosed pool is arithmetic, not a model: adult population × disease
> prevalence × the published undiagnosis rate. For Starr that's **7,094 people**
> who have one of these conditions and don't know it.
>
> Its Opportunity Score is **65 out of 100 — the 100th percentile**, the
> highest-scoring county in the country. And the recommended play is a Payer
> Partnership, because at 81% MA penetration the insurer has a Stars-rating
> incentive to co-fund the screening."

**If asked "why is the best county only 65?"** — *"The composite tops out near
65 by construction, because no county leads on all seven dimensions at once. The
honest headline is the percentile: Starr outranks every other county in America."*

### 2.3 How the program recommendation is decided

> "It's a transparent rule cascade, not a black box — five program types
> evaluated in priority order:
>
> 1. **Payer Partnership** — strong payer profile *and* real MA scale
> 2. **Community Health Center** — high social burden *and* poor access
> 3. **Employer Wellness** — strong commercial coverage, non-rural
> 4. **Digital Health** — broadband supports telehealth
> 5. **Pharmacy Screening** — the fallback that works anywhere
>
> Every recommendation traces to the specific thresholds that fired. A brand
> director can defend it in a payer meeting, which 'the model said so' never
> survives."

Current mix across 3,144 counties: **Digital Health 1,052 · Pharmacy 880 ·
Payer Partnership 784 · Employer Wellness 236 · Community Health 192.**

> 🔧 **TECHNICAL DEPTH — the calibration principle** *(use if challenged)*
>
> "The gates mix two kinds of threshold, deliberately. A dimension score is a
> constructed index whose 0–100 scale is an artifact — payer landscape tops out
> at 68.7 nationally, so an absolute '≥65' rule isn't a business rule, it's an
> accident of scale. Those gate on **percentiles**: 'top quartile for payer
> opportunity.'
>
> But 35% Medicare Advantage penetration means genuine insurer scale regardless
> of how the distribution moves, so **that stays absolute**. Same for broadband
> as a telehealth viability line.
>
> We found and fixed this: the original absolute gates recommended Payer
> Partnership for exactly one county out of 3,144 and dumped 83% into the
> default. It's now regression-tested — halving every index must not change the
> recommendation mix."

### 2.4 Why not AI

> "This is a transparent weighted index, and that's a deliberate choice, not a
> limitation. Three reasons: a client's analyst can audit every number; there's
> no training data, no drift, no model governance; and when a brand team takes
> this into a payer negotiation, 'Starr qualifies because 81% MA penetration and
> a payer score in the top quartile' is a sentence that survives scrutiny.
> 'The classifier said so' isn't.
>
> Machine learning earns its place later, at claims-based lift forecasting, where
> it actually adds something."

---

## PART 3 — THE PROCESS (4 minutes)

### 3.1 The data — non-technical

> "Twelve public data sources. CDC, US Census, CMS, HRSA, USDA, and County
> Health Rankings. No patient records, no PHI, no licensing fees, no data-use
> agreements.
>
> That last point is commercially significant. It means procurement is weeks,
> not quarters — there's nothing sensitive to review. It's the single biggest
> reason this can move fast."

### 3.2 The pipeline

> "Three pipelines feed it. One scores all 3,144 counties. One goes down to
> 33,791 ZIP codes. One scores 411,115 prescribers from public Medicare data
> into a CRM-ready call list. County to ZIP to the doctor a rep calls Monday
> morning."

> 🔧 **TECHNICAL DEPTH — engineering practices** *(for a technical audience)*
>
> "Three things we'd want in any production system, built in from the start:
>
> **Fail-loud QA gates.** Every pipeline ends with data contracts — 28 checks on
> the county output alone. If a source degrades or a join produces zero matches,
> the pipeline refuses to write rather than shipping quietly wrong numbers. We
> built this after a corrupt crosswalk shipped silently once.
>
> **A reproducibility guard.** CI re-runs the scoring code against the committed
> inputs on every push and fails the build if any derived number disagrees. So
> the numbers on the dashboard are *provably* the output of the code in the
> repo, not a stale snapshot. That's unusual, and it's exactly what a diligence
> reviewer wants to see.
>
> **A provenance page in the product.** Every source is listed with its vintage,
> its real coverage, and a live QA report. 75 automated tests, green CI."

### 3.3 How we know it works — lead with the failure

> "We ran five falsifiable tests, each with a kill criterion stated in advance.
> I want to start with the one that **failed**.
>
> We asked whether the score predicts which counties surface more diagnoses
> between CDC data releases. It doesn't — and neither does any naive baseline.
> The public data is too model-smoothed to answer that question. Our own kill
> criterion says: make no outcome claim on public data. So we don't.
>
> Here's what public data *does* prove:
>
> - **The ranking is stable.** Build it from older data, freeze it, compare to
>   today: correlation **0.94**, and 84% of the top 50 counties are the same —
>   against 1.6% by chance.
> - **It predicts something it's never seen.** Against a health-severity measure
>   the model doesn't ingest, our score correlates **0.49** where the naive
>   'population × prevalence' ranking gets **−0.08**.
> - **It isn't just a poverty map.** The diagnosis-gap signal adds measurable
>   predictive value beyond deprivation alone — small but unambiguous, p below
>   ten-to-the-minus-eighty.
> - **The weights aren't doing the work.** Shake every weight by ±25% and 96% of
>   the top 20 counties stay put.
>
> You've now watched this framework kill one of its own claims. That's the
> discipline the pilot would run under."

---

## PART 4 — THE ASK (2 minutes)

> "What you've seen is live today, entirely on public data.
>
> What public data cannot do is answer the last question: did flagged counties
> actually surface more diagnoses? That needs claims — which we already own.
>
> The ask is one backdated extract: one condition, one or two states, a
> historical window, with the campaign and control counties pre-registered
> before we look. Ninety days, same pre-stated kill criterion.
>
> If it fails, we killed it for the cost of a pilot. If it passes, IQVIA owns
> the demand-generation layer upstream of every product it already sells."

**Two things to start now** (neither is engineering):
1. **Legal check on County Health Rankings** — the one non-federal source. Fine
   for research; commercial redistribution rights need confirming before a sale.
2. **The claims pathway** — DUA, privacy sign-off, and a secure environment.
   Weeks to months, so it gates the timeline more than the build does.

---

## ANTICIPATED QUESTIONS

| Question | Answer |
|---|---|
| **"Hasn't someone built this?"** | The components exist in three separate worlds; the combination doesn't. Cite it proactively: a 2016 *Diabetes Care* study estimated county-level undiagnosed diabetes and found diagnosis rates ranging 59–80% across counties. That's independent peer-reviewed proof our premise is real. It stops at 2012 data; we operationalise it on current vintages and add the payer, readiness and measurement layers. |
| **"How accurate is the 33.7M?"** | It's a planning estimate with a transparent chain, not a precision claim. Population × prevalence × published undiagnosis rate, county by county. Don't confuse it with the published 45M national figure — that counts hypertension "undiagnosed *or uncontrolled*", a broader definition. |
| **"What's the weakest part?"** | Hypothyroidism. No county-level thyroid data exists anywhere, so we apply a flat national prevalence. It's the least precise of the three conditions and it's labelled as such in the product. Lead with diabetes and hypertension. |
| **"Is any of this modeled rather than measured?"** | Yes, and it's disclosed in the product. Medicare Advantage penetration is real CMS data. Medicaid and commercial shares are modeled from socioeconomic signals — directionally sound planning figures, not sourced rates. |
| **"Could a client just build this themselves?"** | Technically yes — the data is public. But the moat isn't the data, it's the scoring framework, the validation spine, and the measurement engine. And it's a $25–75k assessment versus a year of internal analyst time. |
| **"What does it cost to run?"** | Effectively nothing. No licences, no cloud data platform, no AI inference costs. The whole dataset is 120MB. |
| **"Who's the buyer?"** | Brand teams in chronic disease with large undiagnosed pools, plus payers and health systems who share the screening incentive. Land with a single-brand market assessment; expand to a multi-brand platform licence with quarterly measurement. |

---

## DELIVERY NOTES

- **Lead with the business frame, not the data.** The first 60 seconds decide
  whether this is heard as a commercial product or a science project.
- **Say the numbers slowly and only once.** 3,144 counties · 33.7M patients ·
  20 Priority markets · 12 public sources. Don't stack more.
- **Volunteer the limitations before you're asked.** The failed test, the
  hypothyroidism caveat, the modeled payer shares. It costs nothing and buys
  everything.
- **Never say "AI".** Say "a transparent, auditable index — deliberately."
- **If you don't know, say so.** One invented number destroys the credibility
  that the whole validation spine was built to earn.

---
*Figures verified against the live scored data at the time of writing and
reproducible via `python3 src/validation/verify_reproducible.py`. Re-check the
headline numbers after any data refresh.*

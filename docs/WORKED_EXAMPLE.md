# Worked Example — One County, End to End

**Why this exists:** the product does one thing 3,144 times. Showing that one
thing *once*, with every number traced from public data to a recommendation, is
faster than any dashboard tour. This is the "I get it" page — use it as a slide,
a leave-behind, or the opening of a technical conversation.

**County:** Starr County, Texas (FIPS 48427) — the #1 scored county in the US.
Every figure below is the live value from `dimension_scores.parquet` and is
reproducible: CI re-derives all of it from the committed inputs on every push.

---

## Step 1 — What we start with (public data only)

| Input | Value | Source |
|---|---|---|
| Total population | **65,716** | US Census ACS 5-yr (2022) |
| Diagnosed diabetes prevalence | **20.0%** | CDC PLACES 2025 (2023 BRFSS) |
| Diagnosed hypertension prevalence | **36.6%** | CDC PLACES 2025 |
| Poverty rate | **33.5%** | Census ACS |
| Uninsured rate | **32.4%** | Census ACS |
| Annual checkup rate | **70.3%** | CDC PLACES |
| Primary-care shortage area (HPSA) | **Yes** | HRSA |
| Federally funded safety-net clinic (FQHC) | **None** | HRSA |
| Medicare Advantage penetration | **80.6%** | CMS (real county data) |

No claims. No patient records. No licensing. Eight public numbers.

---

## Step 2 — How many patients are hidden here?

The pool is arithmetic, not a model — every factor is sourced and the chain is
inspectable:

```
T2D      65,716 × 20.0% prevalence × 23.1% undiagnosed  =  3,036
HTN      65,716 × 36.6% prevalence × 20.0% undiagnosed  =  4,810
Hypo     65,716 ×  4.0% prevalence × 50.0% undiagnosed  =  1,314
                                                          ─────
                    Estimated silent pool in Starr County =  9,160
```

**≈ 9,160 people** in one county who have a chronic condition and don't know it.
The undiagnosed percentages are published national rates (CDC/NHANES); the
prevalence is county-specific. *This is a planning estimate, not a patient list.*

> **Known simplification, stated plainly:** CDC PLACES prevalence is measured on
> adults (18+), but the multiplier above uses *total* county population. That
> makes the pool a modest over-estimate in counties with many children. It is
> deliberately not "corrected" with an assumed adult share — we'd rather show one
> transparent multiplication than bury a second assumption inside it. Applying an
> adult-share adjustment is a one-line change when a client wants it.

---

## Step 3 — Why does Starr score 65 out of 100?

Seven dimensions, each 0–100, combined with fixed published weights
(`config/dimensions.yaml`):

| Dimension | Score | Weight | Why it's high (or not) |
|---|---:|---:|---|
| Diagnosis Gap | **72.5** | 25% | Highest-weighted signal — low checkup rate + 32% uninsured |
| Social Determinants | **71.6** | 15% | 33.5% poverty, food access, education |
| Disease Burden | **69.0** | 20% | 20% diabetes prevalence — roughly double the national rate |
| Payer Landscape | **68.7** | 10% | 80.6% MA penetration — an insurer with skin in the game |
| Access to Care | **55.8** | 15% | Shortage area with no FQHC — held up only by being non-rural and a 70% checkup rate |
| Commercial Readiness | **50.7** | 10% | Moderate broadband; workable for a program |
| Trajectory | **37.1** | 5% | Burden already high — less *additional* growth ahead |

**Composite = 64.8 → displayed as 65.** Tier: **Priority**. National rank: **#1
of 3,144**. Data confidence: **grade A** (6–7 of 7 real sources cover this county
directly — nothing here leans on a proxy fill).

> **Reading the number:** 65 is not "65% of something." The composite tops out
> near 65 by construction, because no county leads on all seven dimensions at
> once. The honest headline is the **percentile: Starr is the 100th percentile —
> the highest-scoring county in the United States.**

---

## Step 4 — So what do we actually do there?

The recommendation is derived from the county's own profile, not chosen by hand:

> **Payer Partnership Program** — because Payer Landscape ≥ 65 **and** Medicare
> Advantage penetration ≥ 35%. At 80.6% MA, the majority of Medicare-eligible
> residents are in plans whose Stars ratings improve when chronic conditions are
> found and managed early.

**The pitch this writes for you:** *"Starr County has 9,160 residents living with
undiagnosed diabetes, hypertension, or thyroid disease, and 80.6% of your
Medicare-eligible members are in MA plans. Closing that gap raises your Stars
measures and cuts downstream complication cost. Let's co-fund screening."*

The same engine drops one level down: Starr's ZIPs are individually scored
(33,791 nationally), and the prescribers practicing in them are ranked into a
CRM-ready call list (411,115 scored, 20,612 priority) — so "invest in Starr"
becomes "call these doctors, in this order, and here's why."

---

## Step 5 — How would we know it worked?

Run the program, then measure it like a trial rather than asserting success:

1. Pre-register Starr (and the other campaign counties) **before launch**.
2. The engine matches each to its statistical twins — counties with similar
   baseline prevalence, poverty, income, uninsured rate, population, rurality —
   that got no campaign.
3. After the next CDC PLACES release, compare the change in *diagnosed*
   prevalence: campaign counties vs their twins, with a bootstrap confidence
   interval.

**The honesty check:** run this today on eight Rio Grande Valley counties where
no campaign happened and it returns **+0.17pp, 95% CI [−0.72, +1.07] — not
distinguishable from zero.** The tool refuses to invent lift. That's why the
number means something when it *is* positive.

---

## The whole chain, in one line

> **8 public inputs → 9,160 hidden patients → score 65 (#1 in the US) → a payer
> partnership → a measured diagnosis-rate lift.**
>
> Repeat 3,144 times. That's the product.

---
*All values from the committed `dimension_scores.parquet`, verified reproducible
from the committed inputs by `src/validation/verify_reproducible.py` (runs in CI).
The undiagnosed-rate multipliers (23.1% / 20% / 50%) are published national
figures; the campaign result is the live output of the measurement engine.*

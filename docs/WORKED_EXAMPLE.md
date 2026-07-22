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
| **Adult population (18+)** | **44,621** | US Census PEP 2023 |
| Diagnosed diabetes prevalence | **20.0%** | CDC PLACES 2025 (2023 BRFSS) |
| Diagnosed hypertension prevalence | **36.6%** | CDC PLACES 2025 |
| Poverty rate | **33.5%** | Census ACS |
| Uninsured rate | **32.4%** | Census ACS |
| Annual checkup rate | **70.3%** | CDC PLACES |
| Primary-care shortage area (HPSA) | **Yes** | HRSA |
| Federally funded safety-net clinic (FQHC) | **None** | HRSA |
| Medicare Advantage penetration | **80.6%** | CMS (real county data) |

No claims. No patient records. No licensing. Nine public numbers.

---

## Step 2 — How many patients are hidden here?

The pool is arithmetic, not a model — every factor is sourced and the chain is
inspectable:

```
T2D      44,621 adults × 20.0% prevalence × 32.9% undiagnosed  =  2,936
HTN      44,621 adults × 36.6% prevalence × 20.0% undiagnosed  =  3,266
Hypo     44,621 adults ×  4.0% prevalence × 50.0% undiagnosed  =    892
                                                                 ─────
                       Estimated silent pool in Starr County  =  7,094
```

The 32.9% is **Starr's own** undiagnosed rate, not a national constant — it is the
NHANES age-band rates (36.1% at 20–39, 31.6% at 40–59, 24.9% at 60+) weighted by
Starr's adult age mix. Nationally the range across counties is 28.2%–34.8%.

**≈ 7,094 people** in one county who have a chronic condition and don't know it.
The undiagnosed percentages are published national rates (CDC/NHANES); the
prevalence is county-specific. *This is a planning estimate, not a patient list.*

> **Approximation worth stating:** the Census age bands available per county
> (18–44 / 45–64 / 65+) do not align exactly with the NHANES bands
> (20–39 / 40–59 / 60+). The boundary mismatches partly offset, and this is far
> closer than one national constant, but it is a mapping rather than an identity.
> HTN and hypothyroidism keep flat national rates — no published age-stratified
> undiagnosed shares exist for them, and inventing a gradient would be worse than
> an honest constant.

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

**The pitch this writes for you:** *"Starr County has 7,094 residents living with
undiagnosed diabetes, hypertension, or thyroid disease, and 80.6% of your
Medicare-eligible members are in MA plans. Closing that gap raises your Stars
measures and cuts downstream complication cost. Let's co-fund screening."*

The same engine drops one level down: Starr's ZIPs are individually scored
(33,791 nationally), and the prescribers practicing in them are ranked into a
CRM-ready call list (411,115 scored, 20,585 priority) — so "invest in Starr"
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

> **9 public inputs → 7,094 hidden patients → score 65 (#1 in the US) → a payer
> partnership → a measured diagnosis-rate lift.**
>
> Repeat 3,144 times. That's the product.

---
*All values from the committed `dimension_scores.parquet`, verified reproducible
from the committed inputs by `src/validation/verify_reproducible.py` (runs in CI).
The T2D undiagnosed rate is age-weighted from NHANES 2021–2023 strata; HTN (20%)
and hypothyroidism (50%) use published national figures; the campaign result is the live output of the measurement engine.*

# Deck Update Brief — paste into Claude Design

All figures below were pulled from the live scored data at the time of writing
and are reproducible (CI re-derives them from committed inputs on every push).
**Replace every number on the left with the number on the right.**

---

## 1. Find-and-replace table (highest priority)

| Where it appears | OLD (remove) | NEW (use this) |
|---|---|---|
| Priority counties | 24 | **20** |
| Emerging counties | 1,665 | **1,416** |
| Starr County score | 64 | **65** |
| Starr County est. pool | 9,160 | **7,094** |
| National estimated pool (computed) | 39.0M / 45.7M | **33.7M** |
| Top-3 county order | Starr · Presidio · Oglala Lakota | **Starr · Oglala Lakota · Presidio** |
| HCP priority targets | 20,612 | **20,585** |
| T2D undiagnosed rate | 23.1% (flat) | **28.5% national; 28.2–34.8% by county** |
| ZIP Priority | 9 | **11** |
| ZIP Emerging | 13,423 | **9,661** |
| CI test suite | 35 tests | **70 tests** |
| Public data sources | 11 | **12** |
| Temporal coherence ρ | 0.93 | **0.94** (τ 0.82) |
| Held-out severity ρ | 0.47 | **0.49** (lift +0.57) |
| "Not a poverty map" ΔR² | +0.20 | **+0.09** |
| — its partial r | 0.51 | **0.35** (p < 10⁻⁸⁰) |
| Weight stability ±25% | 93% | **96%** (17/20 counties stable) |
| Weight stability ±10% | 97% | **99%** (20/20 stable) |

**Unchanged — do not edit:** 3,144 counties · 33,791 ZIPs · 411,115 prescribers ·
Starr MA penetration 80.6% · campaign result +0.17pp, 95% CI [−0.72, +1.07].

---

## 2. Numbers that are now correct — current headline set

- **3,144** US counties scored on **7 dimensions** from **12 public data sources**
- **20 Priority** · **1,416 Emerging** counties
- **33.7M** estimated undiagnosed adults (bottom-up, computed)
- **33,791** ZIPs · **411,115** prescribers scored (**20,585** priority targets)
- Top 5 counties: **Starr TX 65 · Oglala Lakota SD 62 · Presidio TX 62 · Hidalgo TX 60 · Maverick TX 59**
- **70-test** CI suite · reproducibility guard verifies published numbers on every push

---

## 3. ⚠️ Two numbers that must not be conflated on the same slide

**33.7M** (ours, computed bottom-up: county adult population × prevalence ×
undiagnosis rate) and **45.7M** (published national estimate) are **different
things measured different ways**. The published HTN component counts "undiagnosed
*or uncontrolled*", a broader definition than ours.

- If quoting **45M** → attribute it: *"published CDC/NHANES national estimate."*
- If quoting **33.7M** → label it: *"our bottom-up estimate from public county data."*
- **Never** show them as the same figure or imply one validates the other.

---

## 4. New slide content worth adding — the methodology upgrade

This is a genuine credibility story and currently isn't in the deck.

**Suggested headline:** *"We stopped using a national average."*

> Most market-sizing applies one national undiagnosis rate to every geography.
> We now compute a **county-specific rate**, weighted by each county's adult age
> mix, using NHANES 2021–2023 age strata:
>
> | Age band | Share of diabetes cases undiagnosed |
> |---|---|
> | 20–39 | 36.1% |
> | 40–59 | 31.6% |
> | 60+ | 24.9% |
>
> **The counter-intuitive finding:** the undiagnosed *share* **falls** as age
> rises — older adults are screened far more often. So a young county hides
> proportionally **more** cases, exactly the signal a flat national rate erases.
> Across US counties our rate now ranges **28.2%–34.8%**.

**Second point for the same slide:** we also corrected the denominator to
**adults 18+** (Census PEP). Prevalence is measured on adults, so multiplying by
total population over-counted young counties.

**Net effect:** national pool moved 39.0M → 33.7M. T2D actually rose 9.9% (the
higher rate nearly offsets the smaller denominator); hypertension and
hypothyroidism fell ~21% from the denominator fix alone. **We report the number
going down because it is more defensible, not less impressive.**

---

## 5. Validation slide — keep the structure, swap the numbers

The "lead with the failed test" structure stays exactly as-is. Updated figures:

- 🔴 **The miss** — outcome prediction on public data: kill criterion **fired**.
  No ranking, ours or naive, predicts CDC PLACES vintage-to-vintage deltas
  (all |ρ| < 0.10). *Unchanged — still the opening slide.*
- 🟢 **Temporal coherence** — frozen 2020-vintage ranking vs today:
  **ρ = 0.94**, τ = 0.82, top-50 overlap **84%** (vs 1.6% by chance), n = 3,135
- 🟢 **Held-out severity** — predicts CHR premature death, never ingested:
  **ρ = 0.49** vs **−0.08** naive, lift **+0.57**, n = 3,144
- 🟢 **Not a deprivation index** — Diagnosis Gap over an SDoH-only baseline:
  **ΔR² = +0.09**, partial r = **0.35** (p < 10⁻⁸⁰); full 7-dim R² = 0.65
- 🟢 **Weight robustness** — ±25% shake: **96%** of top-20 hold (±10%: **99%**)

**Note the ΔR² drop (0.20 → 0.09):** still unambiguously non-zero and highly
significant, but smaller. Do not overstate it. Prepared answer if challenged:
*"It survives controlling for prevalence too — ΔR² = +0.08, partial r = 0.37."*

---

## 6. Data sources slide — now 12

Add **County Population by Age (Census PEP, 2023 vintage)** — feeds the adult
population denominator and the age-weighted T2D rate. Bulk file, no API key.

Full list: CDC PLACES County (2025 rel.) · CDC PLACES County prior (2022 archive)
· CDC PLACES ZCTA · Census ACS 5-yr · Census ACS ZCTA · Census TIGER/Gazetteer/
ZCTA crosswalk · **Census PEP county age** · CMS Geographic Variation + MA
Penetration · CMS Medicare Physician & Other Practitioners · HRSA HPSA · County
Health Rankings · USDA Food Environment Atlas.

---

## 7. Prior-art slide — recommended addition

A judge will ask "has this been done?" Get ahead of it:

> **Dwyer-Lindgren et al., *Diabetes Care* (2016)** estimated county-level
> diagnosed *and undiagnosed* diabetes prevalence and found the share of cases
> actually diagnosed ranged **59.1%–79.8%** across US counties.
>
> **Cite this as corroboration, not competition.** It is peer-reviewed,
> independent evidence that the detection gap is real, large, and geographically
> concentrated — the premise SPPF is built on. It predates this work by a decade
> and stops at 2012 data; SPPF operationalises the insight on current vintages
> and adds the payer, readiness and measurement layers that make it actionable.

---

## 8. Framing lines that still hold (no change needed)

- "Every IQVIA asset — claims, LRx, OCE — starts *after* a diagnosis exists.
  SPPF is the demand-generation layer upstream."
- "Screening-campaign ROI is essentially unmeasured industry-wide."
- "Zero PHI, zero licensing, procurement-light."
- "A transparent, auditable index — deliberately, not an LLM."
- The campaign-measurement null result (**+0.17pp, CI [−0.72, +1.07]**) as the
  honesty proof point.

---

*Source of truth: `data/scored/dimension_scores.parquet`,
`validation_part3.json`, `build_manifest.json`. Re-run
`python3 src/validation/verify_reproducible.py` to confirm the deck matches the
shipped data before presenting.*

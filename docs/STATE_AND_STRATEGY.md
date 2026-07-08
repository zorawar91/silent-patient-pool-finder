# SPPF — State Review & Commercial Strategy
*Review date: 2026-07-08 · Reviewed against the nested working copy (9 commits ahead of GitHub)*

---

## Part 1 — Current State

### Repo topology (needs consolidation)
There are **two copies of the repo**. The outer folder (`~/Documents/silent-patient-pool-finder`) matches GitHub `origin/main` but is stale. The nested clone (`silent-patient-pool-finder/silent-patient-pool-finder/`) is the real working copy: **9 unpushed commits** (audit fixes, threshold calibration, CHR download fixes) plus uncommitted changes across 6 files and 4 untracked modules (`zip_scorer.py`, `ingest_zcta_data.py`, `fix_zip_map.py`, ZIP dashboard views). Anyone cloning from GitHub today gets a materially older product.

### Bugs found (2 fixed in this session, pre-existing)

**1. `NameError: DIM_SHORT` — hard crash of the 7-Dimension Analysis view.** The heatmap header referenced a `DIM_SHORT` dict that was never defined. The entire view died on open. **Fixed:** added the dict. Verified via Streamlit AppTest — all 8 views now render without exceptions.

**2. Corrupt ZCTA→county crosswalk — silently degraded the whole ZIP product.** The Census relationship-file parser matched the first column containing "ZCTA", which is `OID_ZCTA5_20` (an internal object ID), not `GEOID_ZCTA5_20` (the actual ZIP code). Result: an 849-row crosswalk full of `00nan` values instead of ~46,000 valid pairs. Downstream damage:
- 5 of 7 ZIP dimension scores were **100% NaN** for all 33,774 ZCTAs — the "7-dimension" ZIP score was actually a 2-dimension score (disease burden + SDoH only).
- `state_name`/`state_abbr` null for every ZIP → selecting any state in the ZIP Territory view silently returned **0 ZIPs** (empty map, "0 ZIPs" banner, no error).
- All county-derived payer columns null at ZIP level.

**Fixed:** parser now prefers `GEOID_*` columns, drops blank county-only records, and robustly casts codes to 5-digit strings. Verified against a synthetic sample of the exact Census file format.

**3. Wrong area weights (found while fixing #2).** The weight logic *excluded* `AREALAND_PART` (the ZCTA∩county intersection area) and used total ZCTA land area — constant per ZCTA — so every multi-county ZIP got equal weights instead of intersection-share weights. **Fixed:** prefers `AREALAND_PART`; verified weights now split ~0.99/0.01 where intersections say they should.

**Action required (1 command, on your machine — sandbox can't reach census.gov):**
```
cd silent-patient-pool-finder/silent-patient-pool-finder
python3 ingest_zcta_data.py        # rebuilds crosswalk + rescores all ZIPs (~3 min)
```

### Open loops
1. **Unpushed/uncommitted work.** 9 commits + ~1,300 changed lines uncommitted in the nested repo. One `git status` accident away from losing the newest work. Commit, push, and delete the outer duplicate (or make the nested copy the canonical checkout).
2. **Legacy synthetic pipeline is dead weight with a live syntax error.** `src/ingestion/simulate_otc.py` doesn't even compile (`from __future__` after `import random`). The Synthea/XGBoost pipeline (`run.py`, `src/model/`, `simulate_otc.py`, Makefile targets, docker-compose) is superseded by the real-data pipeline. Archive or delete — it will fail any technical due diligence scan.
3. **The only test file targets the dead pipeline and can't even import** (`loguru` missing from requirements.txt). The real pipeline — the thing you'd sell — has **zero tests**.
4. **Synthetic payer data fallback.** `_ensure_payer()` fabricates MA/Medicaid/commercial rates with seeded random noise when CMS data is missing. It returns an `is_synthetic` flag, but if that badge is ever lost in the UI, you're showing invented payer mix to a pharma buyer. Gate it behind an explicit "demo mode" or remove it.
5. **CHR manual download.** County Health Rankings blocks automated downloads (WAF); pipeline needs a manually placed CSV. Documented, but fragile for anyone else running ingestion.
6. **Runtime external dependencies.** The county map fetches GeoJSON from plotly's GitHub at runtime; if that URL dies mid-demo, the map dies. Vendor it into the repo.
7. **Streamlit deprecation debt.** `use_container_width` is removed after 2025-12-31 — you're past that on any fresh Streamlit install. Migrate to `width=` before it becomes a crash.
8. **Score scale honesty.** The composite maxes at ~62 on a claimed 0–100 scale (min-max normalization means no county hits 100 on every component). Tiers are calibrated around this (Priority ≥55 = top ~0.3%), but a sophisticated buyer will ask "why does your 100-point score top out at 62?" Percentile-based presentation fixes this (see Part 2).

---

## Part 2 — Making It Sellable to Big Pharma

### Who actually buys this
Four budgets inside a pharma company can pay for market-expansion analytics: **brand marketing** (HCP + DTC campaign targeting), **commercial operations** (field force sizing/territory design), **market access** (payer engagement strategy), and **medical affairs** (screening/disease-awareness programs). The highest-velocity entry point is the **brand team of a drug whose growth depends on new diagnoses** — GLP-1s and metabolic franchises, thyroid (levothyroxine lifecycle), and the resurgent CV/renal portfolios. Their core problem: the diagnosed market is saturated and contested; the *undiagnosed* pool is the only whitespace, and no incumbent tool addresses it directly.

### The positioning wedge
IQVIA, Komodo, Trilliant, Veeva Compass all sell visibility into **diagnosed** patients via claims/Rx data — expensive, lagging, and blind to people who never enter the system. SPPF's story: **"We find the patients your claims data can't see, using public epidemiological signals — at 1/50th the cost and with zero PHI."** The no-patient-level-data architecture isn't a limitation, it's the compliance headline: nothing to redact, no data use agreements, no HIPAA exposure, procurement sails through.

### Five product moves, in priority order

**1. Add the activation layer — from "where" to "who to call."** A map of hot counties is an insight; a call list is a product. Public data gets you there: NPPES (every US HCP + specialty + address), CMS Medicare Part D prescriber files (who prescribes metformin/levothyroxine/antihypertensives, at what volume), Open Payments. Join HCP density and prescribing behavior to your county/ZIP scores and output: *"In these 40 priority ZIPs, here are the 312 PCPs with high symptom-adjacent prescribing but low diagnostic-workup patterns — target them for diagnosis-support detailing."* Export as Veeva CRM-loadable territory files. This single feature moves SPPF from "interesting dashboard" to "field force input," which is where the money is.

**2. Sell the ROI loop, not the map.** Pharma buys measurable lift. Build a **campaign measurement module**: baseline diagnosis rates (CMS/CDC, refreshed annually) in intervention vs. matched control counties, with pre-registered expected-lift ranges. Even a simple diff-in-diff wrapper turns SPPF from a planning tool into an outcomes contract: "we'll identify the geographies, you run the campaign, we measure the diagnosis-rate delta." That's a renewable engagement, not a one-time report.

**3. Make the methodology bulletproof (the credibility layer).** Sophisticated pharma analytics teams will attack the scoring. Pre-empt them:
- **Percentile-rank scores** (0–100 = percentile among 3,144 counties) instead of raw weighted min-max sums — kills the "why does it max at 62" question and makes tiers self-explanatory.
- **Uncertainty bands** per county driven by data coverage (you already track which sources cover which counties — surface it as a per-county confidence grade A/B/C).
- **Validation study**: correlate your diagnosis-gap scores against known ground truth — e.g., NHANES-measured vs. self-reported diabetes by region, or state-level published undiagnosis estimates. One validation appendix in the methodology docx is worth ten features.
- **Weight sensitivity toggle** in-app: let the buyer's analyst move the 7 dimension weights and watch rankings stay broadly stable. Robustness they can touch beats robustness you claim.

**4. Condition modules as the expansion engine.** T2D/HTN/hypothyroid prove the platform; the roadmap sells it. The undiagnosed populations pharma cares most about right now: **CKD** (~90% of early-stage undiagnosed — every SGLT2/finerenone franchise wants this), **MASH/NASH** (first therapies launched, diagnosis is *the* bottleneck), **COPD**, **obesity** (pre-GLP-1 identification), **AFib**, **osteoporosis**. Each module = same 7-dimension engine + condition-specific prevalence/signal config (your YAML architecture already supports this — it's a config file, not a rebuild). Price per module.

**5. Package for the pharma buying motion.** Nobody at Pfizer buys a Streamlit URL. Sequence it:
- **Land ($25–75k):** a branded "Market Opportunity Assessment" for one brand/condition — PDF report + 90-day dashboard access. Low procurement friction, decision-maker is a brand director.
- **Expand ($150–400k/yr):** multi-brand platform license + territory files + quarterly data refresh + measurement module.
- **Enterprise:** custom conditions, claims-data validation tier (partner with a data vendor rather than buying claims yourself), API into their data lake.
Deploy behind auth (Streamlit Cloud → later a proper front end), add SOC 2 to the roadmap, and keep the methodology whitepaper + a 3-page validation brief as the sales leave-behind.

### Foolproofing checklist (engineering, ordered)
1. Consolidate to one repo; commit + push the 9 stranded commits. ✅ *bugs above already fixed*
2. Re-run `ingest_zcta_data.py` to regenerate crosswalk + ZIP scores; add an ingestion QA gate that **fails loudly** if any dimension is >20% null or a join produces 0 matches (this exact class of bug shipped silently).
3. Delete/archive the legacy synthetic pipeline; fix or remove `simulate_otc.py`.
4. Test suite for the real pipeline: schema contracts per source, scorer unit tests, AppTest smoke test per dashboard view. Wire into GitHub Actions CI.
5. Vendor the counties GeoJSON; pin Streamlit and migrate `use_container_width` → `width`.
6. Gate `_ensure_payer` synthetic fallback behind an explicit demo flag with a visible watermark.
7. Percentile scoring + confidence grades (also a sales feature — see move 3).
8. A "Data Provenance" page in-app: source, vintage, coverage count, refresh date per dataset. Buyers' analysts go here first; make it impressive.

### The one-sentence pitch
*"SPPF tells a brand team which 3% of US counties — and which prescribers in them — hold the largest reachable pool of undiagnosed patients for their drug, using fully public, PHI-free data, and then measures the diagnosis-rate lift their campaign generated."*

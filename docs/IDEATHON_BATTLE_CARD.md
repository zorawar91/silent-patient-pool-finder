# SPPF — IQVIA Ideathon Battle Card

*Everything you need in the room. Print this or keep it open on your phone.*

**Live demo:** https://silent-patient-pool-finder.streamlit.app · **Deck:** `Silent_Patient_Pool_Finder_20072026_v1.pptx` (16 slides: adds validation slide 9, stack slide 13, analyst-backup slide 16)

---

## Three numbers, memorized cold

**8.7M** undiagnosed Type 2 Diabetes adults in the US · **Starr County, TX** ranks #1 of 3,144 counties (26% diabetes prevalence, 99.9th percentile) · **+0.9pp** real national diabetes prevalence trend (2020→2023 BRFSS) powering the Trajectory dimension.

---

## The 90-second opener (verbatim)

"Every chronic-disease brand in this room is fighting over the same diagnosed patients — with claims data, Rx data, decile lists. But the biggest patient pool in metabolic disease generates zero claims: 8.7 million Americans with undiagnosed Type 2 Diabetes, 34.9 million with undiagnosed or uncontrolled hypertension. They are invisible to every dataset IQVIA sells — by definition.

SPPF finds them. Not individually — that's impossible and would be wrong — but geographically. Eleven public datasets, seven scoring dimensions, every US county, every ZIP code, and 411,000 prescribers ranked by where a diagnosis-support conversation is most valuable. Then — and this is the part nobody else does — it measures whether the campaign actually moved diagnosis rates, with matched-control counties and confidence intervals.

Zero patient-level data. Zero licensing cost. Zero procurement friction. And it's not a slide — it's running live right now. Let me show you."

---

## The 5-minute demo click-path

| Time | View | Action | Say |
|------|------|--------|-----|
| 0:00 | Insights & Actions | Land here | "The tool opens with the answer: your top 3 counties and why." |
| 0:45 | 7-Dimension Analysis | Open weight-sensitivity expander, drag Diagnosis Gap to 40 | "Skeptical of my weights? Break them. Spearman 0.98 — Starr County doesn't move. The map is driven by where the patients are." |
| 1:45 | HCP Targeting | Filter to one state, point at rationale column | "From map to Monday call list — every row exports CRM-ready, with a plain-English why." |
| 2:45 | Campaign Measurement | Paste: `48479, 48215, 48061, 48323, 48505, 48427, 48131, 48247` | "Pick campaign counties, we auto-match statistical twins, and measure diagnosis-rate lift like a clinical trial. Placebo-validated — it refuses to hallucinate lift." |
| 3:45 | Data Provenance | Scroll the source table + QA report | "Every number, sourced. Sixty QA checks re-run live. We'd rather show you the seams than have you find them." |
| 4:30 | Back to deck | Roadmap slide | The ask: one pilot brand, 90 days. |

**If wifi dies:** play the backup recording; the click-path above doubles as its storyboard.

---

## Anticipated judge questions — crisp answers

**1. "Why hasn't IQVIA already built this?"**
Because every IQVIA asset — claims, LRx, OCE — starts *after* diagnosis. That's not a criticism; it's the product boundary. SPPF is the demand-generation layer upstream of that boundary. It doesn't compete with a single IQVIA product — it creates the diagnosed patients every downstream IQVIA product then tracks. It's a new SKU for an existing sales force.

**2. "What's the weakest part of your data?"** *(the honesty answer — deliver it proudly)*
"Payer mix beyond MA penetration is modeled, and hypothyroidism is a proxy — both labeled as such in the app. That's why the provenance page exists: we'd rather show you the seams than have you find them."

**3. "Isn't finding undiagnosed patients just demand creation / disease mongering?"**
Undiagnosed T2D and hypertension cause strokes, amputations, and dialysis — every year of delayed diagnosis costs the patient and the health system more. SPPF targets *screening programs*, not prescriptions; the recommended interventions are payer partnerships, community health centers, and pharmacy screening. And the measurement engine holds campaigns accountable for actual diagnosis-rate lift — not scripts. This is the rare case where the commercial incentive and the public-health good point the same direction.

**4. "Would this work in India / other markets?"**
The engine is geography-agnostic — it needs any subnational unit with disease prevalence, socioeconomics, and care-access data. India's NFHS-5 publishes district-level diabetes and hypertension measures; combine with Census and Ayushman Bharat facility data and the same seven dimensions score ~750 districts. The US was the proving ground because its public data is free and granular; each new market is a config file, not a rebuild.

**5. "How is this different from Komodo / Trilliant / Definitive?"**
They sell visibility into *diagnosed* patients from claims — expensive, lagging, PHI-heavy. SPPF sees the pre-diagnosis whitespace they structurally cannot, at near-zero data cost, with no PHI. Complementary, not substitutive — and the claims-integration roadmap makes that explicit.

**6. "How do you know the scores mean anything?" (validation)**
Four answers, escalating: (a) face validity — the top counties are the Rio Grande Valley, the Bronx, the Mississippi Delta, exactly where epidemiology says undiagnosed metabolic disease concentrates; (b) weight-sensitivity — rankings hold under any need-side re-weighting; (c) the measurement engine recovers a known synthetic lift within ±0.3pp and passes a real-data placebo test; (d) roadmap: formal validation against NHANES measured-vs-reported gaps.

**7. "What's the business model?"**
Land: a $25–75k Market Opportunity Assessment for one brand — low procurement friction, brand-director budget. Expand: $150–400k/yr multi-brand platform license with quarterly refresh and measurement. Enterprise: custom condition modules and claims-sharpened measurement. The measurement loop is the renewal engine — it turns a report into a subscription.

**8. "What's the moat? Anyone can download public data."**
The data is free; the judgment is not. The moat is (a) the validated scoring framework and its QA/provenance discipline, (b) the measurement methodology with pre-registration, (c) condition-module configs encoding clinical-commercial knowledge, and (d) — if built inside IQVIA — the claims-integration layer nobody else can attach.

**9. "Why now?"**
The GLP-1 era made patient *finding* the binding constraint in metabolic disease for the first time — the diagnosed market is saturated and contested while the undiagnosed pool is untouched. Simultaneously, CDC PLACES reached ZCTA-level maturity and CMS opened prescriber-level files. The raw materials for this product didn't exist five years ago.

**10. "What if the public data goes away?"** *(they may know CHR lost RWJF funding)*
Diversification by design: seven independent sources, no single point of failure, and the QA gates + confidence grades make any degradation visible immediately rather than silently. County Health Rankings — whose funding ends in 2026 — is already only a backup signal, and its data is being preserved open-source. Worst case, the claims-integration tier replaces any lost signal with better data.

**11. "Can I see the methodology?"**
Yes — 25-page methodology document including the validation appendix and a disclosed-assumptions register, and the full codebase with 44 automated tests and CI is open for technical diligence. Hand them the doc.

**12. "What would you build next with IQVIA's data?"**
Quarterly measurement windows (claims verify new diagnoses instead of waiting for CDC release cycles), true payer mix (replacing the modeled Medicaid/commercial shares), Rx-validated HCP targeting, and CKD/MASH condition modules — the two largest undiagnosed pools in pharma's current pipeline. Each one makes the public-data core more valuable, not obsolete.

---

## 15-minute run-of-show (mapped to the official brief)

| Time | Brief requirement | What you do |
|------|------------------|-------------|
| 0:00–1:30 | *Idea + problem* | 90-second opener (above). Slides 1–2. |
| 1:30–3:30 | *Proposed solution + underlying process* | Slides 3–5: insight → 3 layers → 7 dimensions. |
| 3:30–5:00 | *Data sources: type, origin, enablement* | Say it explicitly — the brief calls it out: "Eleven public datasets across four federal agencies: CDC PLACES for disease prevalence (survey-modeled, county+ZIP), Census ACS for socioeconomics, CMS for Medicare payer mix and 534k prescriber panels, HRSA for care shortages, USDA for food access. All aggregate, all free, all shown live on the provenance page." |
| 5:00–10:00 | *Live demo: end-to-end workflow* | The 5-minute click-path (above) — Insights → sliders → HCP export → FIPS-paste measurement → Provenance. This IS the "end-to-end workflow" requirement: find → target → measure → audit. |
| 10:00–12:00 | *Quantified impact* | The impact block (below). Slides 9 + 12. |
| 12:00–13:00 | *Roadmap + ask* | Slide 11–12. Stop talking at 13:00. |
| 13:00–15:00 | Buffer / early Q&A | Judges always run over — protect this buffer. |

**On "at least 40% developed":** don't say a percentage — show the denominator. "Everything in today's demo is functional and deployed: eleven dashboard views, three scored data layers, the measurement engine, 44 automated tests, live URL. What's *not* built is the roadmap — condition modules, claims integration — and that's deliberate: the MVP proves the method end-to-end on three conditions before we scale it."

## Quantified impact (the brief demands numbers — use these)

- **Targeting efficiency (measured, not assumed):** SPPF's top-100 counties average **20.0% diabetes prevalence vs 13.5% nationally — ~1.5× density** before even counting detection deficits. Top decile: 17.8%. A screening dollar spent on SPPF's shortlist works in markets ~1.5× richer in the target population than a national spread. *(Computed live from the scored data — offer to show it.)*
- **Analysis cost:** a consultant-built geographic opportunity analysis runs weeks and six figures; SPPF produces it in minutes with a marginal data cost of **zero**. Data licensing avoided vs. claims-based targeting: typically **$250k–$1M+/yr**.
- **Time-to-territory:** from question to CRM-ready prescriber call list in **one session**, vs. a quarter-long analytics request cycle.
- **Measurement:** today, screening-campaign ROI is essentially **unmeasured** industry-wide; SPPF makes diagnosis-rate lift a measured number with confidence intervals — the difference between renewing a budget and defending one.
- **Health-system framing (use carefully, verify citation before quoting a dollar figure):** delayed chronic-disease diagnosis compounds treatment cost; earlier detection is one of the few places commercial and public-health incentives fully align.

## Jury question bank — business panel

**B1. "Who exactly writes the check, from which budget?"** Brand marketing/analytics budget of a chronic-disease franchise — brand-director authority at pilot size ($25–75k), which is why the land motion is a fixed-scope assessment, not a platform sale.

**B2. "The data is free — why would anyone pay?"** They don't pay for data; they pay for the validated judgment layer on top: the scoring framework, the QA/provenance discipline, the prescriber activation, and the measurement methodology. Bloomberg doesn't own the exchanges' numbers either.

**B3. "What stops a big consultancy — or IQVIA itself — from rebuilding this in a quarter?"** Nothing stops a rebuild of the pipeline; the moat is the accumulated methodology decisions, the measurement discipline (pre-registration, placebo validation), and speed to market. Inside IQVIA this isn't a threat — it's exactly why it should be built here: distribution + claims assets make IQVIA's version unbeatable.

**B4. "What's your evidence anyone wants this?"** The GLP-1 era made patient-finding the binding constraint in the largest drug class in history; screening/awareness budgets already exist and are spent untargeted and unmeasured. The pilot ask is designed to convert that latent demand into a signed test at low friction.

**B5. "How does this make money for IQVIA specifically?"** Three ways: a new SKU for existing pharma accounts, a demand-generation layer that grows the diagnosed-patient base every downstream IQVIA product monetizes, and a measurement subscription (Phase 3, claims-verified) with recurring revenue.

**B6. "What kills this business?"** Honest answer: public data sources degrading (mitigated: 7 sources, QA gates, claims fallback), or failing to convert trust into pilots before someone with distribution copies the idea. That's why the ask is a 90-day pilot, now.

## Jury question bank — technical panel

**T1. "Walk me through the architecture."** Python/pandas ingestion pipelines per source → parquet store → deterministic scoring engine (no ML black box — deliberate, for auditability) → Streamlit dashboard. Every pipeline ends in a QA gate; 35-test CI suite on GitHub Actions; deployed on Streamlit Cloud.

**T2. "Why no machine learning?"** The v1 prototype used XGBoost on synthetic data; we replaced it deliberately. A weighted transparent index of real signals is auditable, explainable to a client's analysts, and robust — and the weight-sensitivity panel proves the ranking is data-driven, not weight-driven. ML re-enters at Phase 3 where it earns its complexity (claims-based lift forecasting).

**T3. "CDC PLACES is itself a model — you're scoring on modeled data."** Correct, and disclosed: PLACES is small-area estimation from BRFSS+ACS. That smooths small counties, which is exactly why (a) confidence grades exist, (b) we report percentiles not false precision, and (c) small-county campaign effects need claims data to detect — a stated limitation.

**T4. "Ecological fallacy — you're inferring about individuals from area data."** We never make an individual-level inference. Every output is a geographic planning decision: where to run a program, which practices to visit. The HCP score ranks conversation value from panel-level aggregates, explicitly not any individual's status.

**T5. "ZIP codes aren't ZCTAs — how do you handle that?"** Scored at ZCTA (Census-defined), joined to prescriber USPS ZIPs directly with state fallback; crosswalk is the official Census relationship file, area-weighted, with weights summing to 1.0 enforced by a QA gate. Match rate 99.8%, checked on every run.

**T6. "How do you handle missing data?"** State-median fill for scoring continuity — but true pre-imputation coverage is captured first and drives the A/B/C confidence grade, so an imputed county can't pose as an observed one. 3,123 of 3,144 counties are grade A.

**T7. "Your DiD — what about parallel trends and spillover?"** Matching on baseline outcome level and SDoH covariates is our parallel-trends defense; pre-registration prevents post-hoc control shopping; the estimator passed synthetic-recovery (±0.3pp on a known 1.5pp lift) and a real-data placebo. Spillover from adjacent counties is a known limitation — control pools can exclude neighbors on request.

**T8. "What breaks when CDC changes a schema or repoints a dataset?"** It already happened — CDC's rolling dataset ID silently made our trend zero. The QA gates were built from that scar tissue: 60+ contracts on row counts, code formats, variance floors, and join rates; any critical failure blocks the data from shipping. It's the most battle-tested part of the codebase.

**T9. "Security and PII posture?"** There is no PII anywhere in the system — inputs are public aggregates, outputs are geographies and public NPI records. Auth + client workspaces and SOC 2 are Phase 1/3 roadmap for client-specific data like campaign lists.

**T10. "How fresh is the data and what's the refresh process?"** Annual cadence on the epidemiological sources (matching their release cycles), monthly-capable on CMS files. One command re-ingests with QA gates; scheduled refresh with alerting is a Phase 1 item.

## Pre-demo checklist

- [x] Live URL on deck: silent-patient-pool-finder.streamlit.app
- [x] Screenshots inserted (final deck: Silent_Patient_Pool_Finder.pptx)
- [x] Backup Q&A slide in deck (slide 13: demand-creation + "is this diagnosing?")
- [ ] `git push` done; Streamlit Cloud shows latest (check Data Provenance loads)
- [ ] Backup screen recording on local disk AND phone
- [ ] Deck PDF export on a USB stick (venue laptops hate .pptx fonts)
- [ ] Rehearsed the slider moment twice and the FIPS paste once
- [ ] Methodology doc printed or on tablet for Q&A hand-off
- [ ] Three numbers cold: 8.7M · Starr County #1 · +0.9pp
- [ ] If asked about the test suite: **44 tests** (deck corrected from 41 — the number a judge can verify with `pytest`)

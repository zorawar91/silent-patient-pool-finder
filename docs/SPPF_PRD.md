# PRD — Silent Patient Pool Finder (SPPF)

| | |
|---|---|
| **Author** | Zorawar Singh Nandwal |
| **Status** | MVP shipped (live at silent-patient-pool-finder.streamlit.app) · Phases 1–3 proposed |
| **Last updated** | July 2026 |
| **Artifacts** | Methodology v2.0 · IQVIA Ideathon deck · [repo](https://github.com/zorawar91/silent-patient-pool-finder) |

---

## Problem Statement

Roughly 8.7M US adults have undiagnosed Type 2 Diabetes, 34.9M have undiagnosed or uncontrolled hypertension, and 2.1M have undiagnosed hypothyroidism. These patients generate no claims, no prescriptions, and no diagnosis codes — making them invisible to every commercial analytics tool pharma buys, while the diagnosed market grows saturated and contested. Brand, market access, and field teams have no systematic way to answer "where are the patients who should be diagnosed but aren't, and who will find them?" — so screening and disease-awareness budgets are allocated on intuition, and their impact is never measured.

## Goals

1. **Give commercial teams a defensible whitespace map**: every US county and ZIP scored for undiagnosed-patient opportunity, with the top 1% of geographies identifiable in under one session. *(Measured: time-to-first-shortlist < 15 minutes.)*
2. **Convert geography into field action**: a ranked, CRM-loadable prescriber list per geography with a plain-language rationale per NPI. *(Measured: % of pilot users who export a call list in first month ≥ 60%.)*
3. **Make campaign ROI provable**: matched-control diagnosis-rate lift measurement with pre-registration, credible enough for a payer or finance audience. *(Measured: ≥ 1 pilot campaign pre-registered in first 2 quarters.)*
4. **Win on trust, not despite it**: every number sourced, every assumption labeled, methodology survivable by a client analytics team. *(Measured: zero unlabeled-assumption findings in client diligence.)*
5. **Business**: land one pilot brand assessment ($25–75k) within 90 days of ideathon; convert to a platform license ($150–400k/yr) within 12 months.

## Non-Goals

- **Individual patient identification** — impossible from aggregate data and deliberately out of scope forever; it is the compliance moat, not a limitation.
- **Clinical or diagnostic decision support** — SPPF plans screening programs; it never informs the care of any person. Keeps the product outside SaMD/regulatory scope.
- **Real-time data** — public sources refresh annually/quarterly; chasing real-time adds cost without changing planning decisions. Claims integration (Phase 3) addresses latency where it matters: measurement.
- **International markets in MVP–Phase 1** — the engine is geography-agnostic, but each market is a data-sourcing project; India (NFHS-5) is explicitly Phase 2.
- **Building or licensing a claims dataset** — partner/integrate (Phase 3) rather than compete with claims vendors on their own asset.

## Personas & User Stories

**P1 — Brand director (metabolic/CV franchise)** *(economic buyer)*
- As a brand director, I want a ranked list of the highest-opportunity counties for my condition so that I can allocate screening-program budget to markets with the largest reachable undiagnosed pool.
- As a brand director, I want a measured diagnosis-rate lift readout after a campaign so that I can defend next year's budget with a causal number, not activity metrics.

**P2 — Field force / commercial ops lead**
- As a field ops lead, I want ZIP-level territory assembly with pool estimates so that I can design rep territories around opportunity instead of legacy geography.
- As a field ops lead, I want a CRM-ready prescriber export with a rationale per NPI so that reps open Monday with a defensible call list, not a spreadsheet of names.

**P3 — Market access / payer strategy lead**
- As a market access lead, I want counties ranked by MA penetration × diagnosis gap so that I can shortlist payers with Stars/HEDIS incentives to co-fund screening.

**P4 — Client analytics reviewer** *(gatekeeper; can veto the sale)*
- As an analytics reviewer, I want per-source provenance, coverage counts, and live QA checks so that I can validate the platform without filing data requests.
- As an analytics reviewer, I want to re-weight the scoring dimensions myself and see rank stability so that I can verify the ranking isn't an artifact of weight choices.

**Edge cases**: geography with C-grade data confidence must be visibly downgraded, never silently blended (P4); a campaign selection under 5 counties must warn about statistical power rather than emit a meaningless CI (P1); a prescriber ZIP with no ZCTA match must fall back to state-level signal, flagged in the QA gate (P2).

---

## Release Plan

### MVP — "Prove the method" ✅ SHIPPED (July 2026)

All P0s below are live, tested (35-test CI suite), and deployed.

| Req | Priority | Status |
|---|---|---|
| 7-dimension county scoring, 3,144 counties, percentile + A/B/C confidence grades | P0 | ✅ |
| ZIP/ZCTA scoring (33,791) via Census crosswalk downscaling | P0 | ✅ |
| HCP priority list: 411,115 NPIs from public CMS data, CRM CSV export | P0 | ✅ |
| Campaign measurement: matched-control DiD, bootstrap CI, pre-registration export, placebo-validated | P0 | ✅ |
| QA gates (60+ fail-loudly checks) + Data Provenance view | P0 | ✅ |
| Weight-sensitivity analysis (live sliders + stability metrics) | P0 | ✅ |
| Info-icon tooltips on every metric; all assumptions labeled in-app | P0 | ✅ |
| Zero-setup demo: scored data ships in repo; Streamlit Cloud deployment | P1 | ✅ |

**Acceptance (retrospective):** a first-time user reaches a top-10 county shortlist in one session with no training; all 11 views render with no unhandled errors; placebo campaign on real data reads not-significant.

---

### Phase 1 — "Survive diligence, serve a pilot" (Q3–Q4 2026)

*Theme: convert ideathon credibility into a paying pilot. Close every gap a client analytics team would find.*

**P0 — cannot invoice a pilot without:**
- **Real CMS Medicare detection signal.** Restore the GV PUF county file (T2D/HTN diagnosed rates) so Diagnosis Gap runs on its full design instead of the CDC-only fallback. *Given the GV PUF download succeeds, when counties are rescored, then the Medicare detection-deficit signal contributes with real variance and the provenance page shows the source live.*
- **True demographic SDoH signal.** Replace the SES-proxy "racial risk index" with real ACS county demographic composition × published risk differentials — making the current honest-but-weak label unnecessary. *Acceptance: tooltip claim and code path match; no proxy disclaimer needed.*
- **Validation study.** Correlate diagnosis-gap scores against NHANES measured-vs-reported prevalence gaps; publish as methodology appendix. *Acceptance: correlation reported with CI; methodology v3 section shipped.*
- **Access control + client workspace.** Authentication, one workspace per client, private deployment option. *Acceptance: pilot client data/filters not visible to any other party.*
- **Branded report export.** One-click PDF "Market Opportunity Assessment" (top counties, ZIP maps, HCP list, methodology summary) — the actual $25–75k deliverable. *Acceptance: exported report is presentation-ready without manual editing.*

**P1:** hypothyroidism upgraded from proxy via lab-test-ordering data partnership (or clearly deprioritized); CHR-source contingency automated (funding ends 2026); scheduled data-refresh job with QA-gate alerting.

**P2 (design for now):** multi-condition scoring API surface; per-workspace custom weight profiles saved server-side.

---

### Phase 2 — "The expansion engine" (Q1–Q2 2027)

*Theme: same engine, more markets — conditions and geographies as config, priced per module.*

**P0:**
- **CKD condition module.** ~90% of early-stage CKD undiagnosed; strongest pharma demand (SGLT2/finerenone franchises). Config: prevalence sources (CDC/USRDS), undiagnosis rates, condition-specific dimension weights, HCP specialty fit (nephrology + PCP). *Acceptance: CKD selectable end-to-end — county → ZIP → HCP → measurement — with module-specific provenance.*
- **MASH module.** Diagnosis is the binding constraint for newly launched therapies; hepatology + GI specialty fit.
- **Module framework hardening.** A new condition = one YAML config + one validation checklist, no scorer code changes. *Acceptance: COPD module built by config-only change as the framework test.*
- **Per-module licensing.** Entitlements, pricing, and provenance per module.

**P1:** **India port** — NFHS-5 district-level diabetes/HTN measures + Census + facility data scoring ~750 districts; proves geography-agnosticism and opens the IQVIA-India conversation. AFib and COPD modules. Cross-condition overlap view ("counties in top decile for 2+ conditions").

**P2:** obesity/pre-GLP-1 identification module (higher regulatory sensitivity — needs legal review first); EU-5 feasibility study.

---

### Phase 3 — "Claims-sharpened enterprise" (H2 2027)

*Theme: integrate the data SPPF deliberately avoided — as an enhancement layer, turning the measurement engine into a quarterly subscription.*

**P0:**
- **Claims-verified measurement.** Partner claims feed (e.g. IQVIA) verifies new diagnoses in campaign vs. control geographies quarterly — replacing the ~3-year CDC window that is the product's biggest honest limitation. *Given a pre-registered campaign, when a quarter closes, then lift is reported with claims-based confirmation and tighter CIs.*
- **Veeva/OCE CRM integration.** Push HCP target lists and pull call-activity back, closing the loop from targeting to activity to lift. *Acceptance: round-trip without CSV hand-offs.*
- **Platform API.** Scores, targets, and measurement results consumable by client data lakes.
- **SOC 2 Type I** + enterprise SSO — table stakes for enterprise licensing.

**P1:** Rx-validated HCP targeting (prescribing behavior enriches specialty-fit); payer-mix upgrade replacing modeled Medicaid/commercial shares with sourced data; multi-brand portfolio view.

**P2:** prospective lift forecasting (given budget X in counties Y, expected diagnosis lift Z); EHR-partnership screening-program telemetry.

---

## Success Metrics

**Leading (weeks):** demo→pilot conversion ≥ 25%; time-to-first-shortlist < 15 min; call-list export rate ≥ 60% of pilot users in month 1; QA-gate pass rate 100% on every refresh (any failure is a P0 incident).

**Lagging (quarters):** 1 paid pilot by end of Q4 2026 (stretch: 2); pilot→license conversion ≥ 50% within 2 quarters; ≥ 1 pre-registered campaign measured end-to-end by mid-2027; zero data-integrity findings in any client diligence (the trust brand is the moat — this metric is existential); Phase 2: 2 condition modules sold as add-ons.

**Measurement method:** product analytics on the deployed app (Phase 1 adds auth, enabling per-user metrics); pipeline CRM for conversion; QA-gate logs for integrity.

## Open Questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| 1 | Is the CMS GV PUF county file reliably downloadable (endpoint timed out in production), or do we need the annual bulk file workflow? | Engineering | Blocks Phase 1 P0 #1 |
| 2 | Lab-data partner for thyroid signal — is any aggregate county-level TSH-ordering dataset licensable at pilot-compatible cost? | BD/Data | Non-blocking (P1) |
| 3 | Obesity module: does geo-targeting for pre-GLP-1 identification raise promotional-compliance issues distinct from screening programs? | Legal/Regulatory | Blocks Phase 2 P2 only |
| 4 | Claims partner economics: revenue share vs. license for Phase 3 measurement feed — and does an IQVIA partnership preclude others? | BD | Blocks Phase 3 P0 #1 |
| 5 | Streamlit Cloud vs. containerized deployment for authenticated client workspaces — does Streamlit's auth story suffice for pharma IT review? | Engineering | Blocks Phase 1 P0 #4 |
| 6 | India: is NFHS-5 district granularity + vintage acceptable to India-side buyers, or is IQVIA-internal India data the realistic path? | BD/India | Non-blocking until Phase 2 |

## Timeline Considerations

- **Hard date:** IQVIA Ideathon (July 2026) — MVP shipped against it. Pilot outreach should ride ideathon momentum within 30 days.
- **External dependency:** CHR funding ends December 2026 — contingency work must land in Phase 1 regardless of pilot status.
- **Data cadence:** CDC PLACES releases annually (~mid-year); Phase 1 validation study should align with the 2026 release so scores and study use the same vintage.
- **Sequencing logic:** Phase 1 before Phase 2 because a second condition module inherits every data-quality gap; Phase 3 last because claims partnership terms (Q4) determine its architecture — but its API surface (Phase 1 P2) must be designed early to avoid rework.

---

*Scope discipline: any addition to a phase requires removing something of equal size or explicitly re-dating the phase. Parking lot for good ideas that didn't make it: prospective forecasting, EHR telemetry, EU markets, patient-advocacy partnerships.*

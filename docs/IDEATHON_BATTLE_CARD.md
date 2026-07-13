# SPPF — IQVIA Ideathon Battle Card

*Everything you need in the room. Print this or keep it open on your phone.*

**Live demo:** https://silent-patient-pool-finder.streamlit.app · **Deck:** `Silent_Patient_Pool_Finder.pptx` (13 slides incl. backup Q&A slide)

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
Yes — 25-page methodology document including the validation appendix and a disclosed-assumptions register, and the full codebase with 35 automated tests and CI is open for technical diligence. Hand them the doc.

**12. "What would you build next with IQVIA's data?"**
Quarterly measurement windows (claims verify new diagnoses instead of waiting for CDC release cycles), true payer mix (replacing the modeled Medicaid/commercial shares), Rx-validated HCP targeting, and CKD/MASH condition modules — the two largest undiagnosed pools in pharma's current pipeline. Each one makes the public-data core more valuable, not obsolete.

---

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
- [ ] If asked about the test suite: **35 tests** (deck corrected from 41 — the number a judge can verify with `pytest`)

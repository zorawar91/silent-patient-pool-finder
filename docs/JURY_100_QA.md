# SPPF — 150 Jury Questions & Answers

*Print-ready. Brutal questions included deliberately — if it's in here, it can't ambush you.
Answers are written to be spoken: 2–4 sentences, no hedging, concede what's true.
Sections I and J are new: the Part III validation numbers on your slides 9/13/16, and a
plain-language glossary so every technical word you say is one you can explain.*

**⚠️ Three sync flags from the deck review (fix or know cold):**
1. **Slide 12 says "45-test CI suite" — the verifiable number is 44** (`pytest --collect-only`). Say "over 40 automated tests" or fix the slide.
2. **Slide 9's "ρ = 0.93" must be described as rank COHERENCE across data vintages** (the ranking stays stable when data updates) — NOT as predicting the change in diagnosis gap. Your own Part III Table 61 shows the composite does *not* beat naive at predicting short-window *changes* (see Q104 — this is the single most dangerous question in the room).
3. **Slide 13 lists XGBoost + SHAP under "Scoring & ML"** — they exist in the repo's R&D/legacy lineage, but the production score is deliberately deterministic. Know Q103's framing.

---

## A. Problem & Market (1–10)

**1. Why is undiagnosed disease a pharma problem and not just a public health problem?**
Because the diagnosed market is saturated and contested — in metabolic disease, growth now comes from new diagnoses, not share shifts. Every screening dollar pharma already spends is allocated blind. It's the rare problem where the commercial incentive and the public-health need are the same action: find the patient earlier.

**2. Where do your 8.7M / 34.9M / 2.1M numbers come from?**
Published national estimates: CDC/NHANES for diabetes (23.1% of cases undiagnosed), AHA/NHANES-based estimates for hypertension unaware/uncontrolled, and thyroid literature for hypothyroidism (~50% undiagnosed). They're on the provenance page and in the methodology doc with sources.

**3. If these patients don't visit doctors, how does finding their geography help?**
Most of them *do* touch the system — pharmacies, checkups, ERs — they just don't get screened. The interventions SPPF recommends (pharmacy screening, community health centers, payer-funded outreach) meet them at those touchpoints. Geography tells you where to put the touchpoint.

**4. Isn't this market too niche — three conditions?**
Three conditions is the proof, not the product. The engine is condition-agnostic config: CKD (~90% of early stages undiagnosed), MASH, COPD, AFib are roadmap modules. Every chronic disease with a silent pool is addressable market.

**5. Who is your competition, really?**
Consultancies doing one-off geographic analyses (slow, expensive, unmeasured), claims-analytics vendors (structurally blind to the undiagnosed), and internal analytics teams (no methodology, no measurement discipline). Nobody currently combines whitespace mapping + prescriber activation + causal measurement.

**6. Why hasn't anyone built this before?**
The raw materials are recent: CDC PLACES only reached ZCTA-level maturity in the last few years, and CMS opened prescriber-level files. And the incentive is new: the GLP-1 era made patient-finding the binding constraint for the biggest class in history.

**7. How big is the addressable market for the tool itself?**
Every chronic-disease brand team in the US market — hundreds of brands across dozens of manufacturers — plus payers and health systems who share the screening incentive. At $150–400k/yr platform licenses, tens of millions in ARR is achievable without leaving US chronic disease.

**8. Why would a payer care about a pharma targeting tool?**
Medicare Advantage plans earn Stars/HEDIS credit for screening and early diagnosis — they have direct financial incentives to co-fund exactly the programs SPPF plans. The payer view ranks counties where those incentives are strongest. That makes SPPF a rare pharma-payer alignment tool.

**9. What's the single most impressive number in your product?**
Top-100 counties average 20.0% diabetes prevalence versus 13.5% nationally — roughly 1.5× targeting density, measured from our scored data, before even counting detection deficits. And that's just the burden dimension; the other six tell you whether a program can actually succeed there.

**10. If I gave you $1M today, what would you do with it?**
Phase 1 of the PRD: restore the full CMS Medicare detection signal, run the NHANES validation study, build client workspaces with auth, and land two pilot brands. Not more features — more proof.

---

## B. Data Sources & Quality (11–25)

**11. Walk me through every data source in one minute.**
Eleven public datasets, four federal agencies: CDC PLACES for disease prevalence (county + ZIP, current and archived releases for trend), Census ACS for socioeconomics (county + ZIP), CMS for Medicare Advantage penetration and 534k prescriber panels, HRSA for care-shortage designations, County Health Rankings and USDA Food Atlas for access and food environment, plus Census TIGER/crosswalk files for geography. All aggregate, all free, all listed with vintage and coverage on the live provenance page.

**12. CDC PLACES is itself a statistical model. You're building a model on a model.**
Correct, and disclosed. PLACES is small-area estimation from BRFSS surveys plus ACS. Consequences we handle explicitly: small counties are smoothed (why we report confidence grades and percentiles, not false precision), and small-county campaign effects are hard to detect (a stated measurement limitation that claims integration fixes).

**13. How current is your data?**
The current PLACES release reflects 2023 BRFSS; ACS is the 2022 five-year; CMS files are 2023–2024 vintage; the trend spans 2020→2023. For strategic planning — where to build a program over 1–3 years — annual cadence matches the decision cadence. We refresh with each release, gated by 60+ automated quality checks.

**14. County Health Rankings loses its funding in December 2026. Then what?**
Known and planned for. CHR is already only a backup signal in our stack — never a primary — and its historical data is being preserved open-source. Our QA gates and confidence grades would make any degradation visible immediately rather than silent. Seven sources means no single point of failure.

**15. What data in your dashboard is NOT real?**
Three things, all labeled in the app: Medicaid/commercial/dual-eligible shares are modeled from SES signals (MA penetration is real CMS data for 3,108 counties); hypothyroidism's ranking is a proxy blend because no county-level thyroid dataset exists; and pool estimates apply national undiagnosis rates uniformly. We'd rather show you the seams than have you find them.

**16. Why should I trust data you got for free?**
Because it's the same data CDC, CMS, and Census publish for policy decisions affecting billions of dollars — free doesn't mean low quality, it means publicly funded. The value we add isn't the data; it's the validated judgment layer and the quality discipline on top.

**17. What happens when a source changes its schema or URL?**
It already happened to us three times — CDC repointed a dataset ID, CMS formatted numbers with commas that silently nulled a column, and a Census file's column naming broke a parser. Every one is now a QA-gate contract: any critical failure blocks the data from shipping and tells you exactly what broke. The gates are built from real scar tissue, not hypotheticals.

**18. How do you handle missing counties?**
State-median fill keeps the scoring continuous, but we capture true coverage *before* imputation and grade every county A/B/C on it. 3,123 of 3,144 counties are grade A (6–7 real sources). An imputed county cannot masquerade as an observed one — that's enforced in code, not policy.

**19. Your payer mix is partly invented. Isn't that disqualifying for a "payer landscape" dimension?**
The dimension's heaviest signal — MA penetration, 40% of it — is real CMS data. The modeled components are directionally calibrated, labeled as modeled in the app, and the dimension carries only 10% composite weight. Phase 1 replaces them with sourced rates. Honest planning estimate today, real data next quarter.

**20. Hypothyroidism has no thyroid data at all. Why include it?**
To prove the framework handles a data-sparse condition honestly — the tooltip says outright it's a proxy blend of detection-failure and access signals. The alternative was pretending. The roadmap fix is lab-test-ordering data, which is exactly the kind of asset an IQVIA partnership unlocks.

**21. Could a competitor just download the same data?**
Tomorrow, yes. What they can't download is two years of methodology decisions, the QA discipline built from production failures, the placebo-validated measurement engine, and — if built here — IQVIA's distribution and claims assets. Data is the ingredient, not the recipe.

**22. What's your data storage and volume?**
Small by design: scored outputs are ~25MB of parquet covering every county, ZIP, and prescriber in America. The raw caches are a few hundred MB. This runs on a laptop — which is a feature, not a limitation, for auditability and deployment cost.

**23. Is any of this data restricted, licensed, or usage-limited?**
No. Every source is US-government open data or foundation-published with open access. No DUAs, no PHI, no BAAs, no licensing fees. Procurement teams clear this in days, not quarters.

**24. How do you know your prescriber data is accurate?**
It's CMS's own published Medicare file — the same data used for federal transparency reporting. We validate NPI format with checksums, filter foreign addresses (the QA gate caught six Canadian postcodes in production), and enforce panel-size floors so suppressed or noisy records never rank.

**25. What did your QA gates actually catch? Give me one real example.**
In production, the "prior year" CDC download silently returned the *current* year — CDC repoints its rolling dataset ID annually — making our trend zero for all 3,144 counties. The variance gate caught it, we pinned archived dataset IDs, and added an identical-release rejection. That bug class can never ship again.

---

## C. Methodology & Statistics (26–45)

**26. Why these seven dimensions?**
They're the seven questions every launch team already asks: how big is the problem, how much is invisible, can a found patient get treated, what's causing the gap, who pays, can we operate here, and is it growing. The framework mirrors the decision, not the data.

**27. Who decided the weights, and why should I accept them?**
I did — they're judgment calls, and I won't pretend otherwise. But you don't have to accept them: the dashboard has live sliders. Re-weight any need-side dimension and the ranking holds — Spearman 0.97–0.99, top-50 overlap 82–88%. The map is driven by where the patients are, not by my weight vector.

**28. Your composite maxes at ~64 out of 100. Why?**
Min-max normalization within the national sample — no county leads on every component, so no county reaches 100. That's why the buyer-facing number is the percentile: 94th percentile means "beats 94% of America," which is self-explanatory and scale-honest.

**29. Min-max normalization is outlier-sensitive. Did you consider alternatives?**
Yes — and the percentile presentation is effectively the rank-based robust alternative, reported side-by-side. The sensitivity analysis shows rankings are stable; and because all outputs are relative rankings rather than absolute magnitudes, outlier influence on decisions is bounded.

**30. Isn't this the ecological fallacy — inferring individuals from area data?**
It would be, if we made individual inferences. We never do. Every output is a geographic planning decision: where to run a program, which practices to visit. The tool cannot name an undiagnosed person and never tries — that's the compliance moat, stated on every relevant screen.

**31. Aren't your top counties just the poorest counties?**
Partially correlated, and that's epidemiology, not artifact — poverty genuinely predicts undiagnosed disease. But burden and detection-deficit signals lead the score, SDoH is only 15%, and two dimensions (payer, commercial readiness) deliberately counterweight pure need with operability. Zero out SDoH on the sliders and the Rio Grande Valley stays on top — because its diabetes prevalence is 26%.

**32. Every targeting tool finds the Rio Grande Valley. What's new here?**
If the top of the list surprised you, you should distrust the tool — face validity is a feature. What's new is everything below rank 5: the ZIP-level structure inside those markets, the specific prescribers with 60–75% diabetic panels, the payer co-funding scores, and the measurement engine. A map is not an operating plan.

**33. Your 1.5× density number is just prevalence targeting. CDC data alone gives me that.**
Correct — prevalence alone gets you most of that density, and we say so. The other six dimensions answer the questions prevalence can't: will a found patient get treated, who funds the program, can you operate there, and who exactly do you call. The delta between a prevalence map and SPPF is the delta between knowing and doing.

**34. Explain your difference-in-differences like I'm not a statistician.**
Your campaign counties will change over time no matter what you do — diagnosis rates drift everywhere. So we find each campaign county's statistical twins — same baseline prevalence, poverty, rurality — that got no campaign. The lift is how much *more* your counties' diagnosis rates rose than their twins'. Same logic as a clinical trial's control arm.

**35. What about parallel trends — the key DiD assumption?**
Matching on baseline outcome levels and SDoH covariates is our defense: twins selected to be on the same trajectory. It's not a randomized trial and we don't claim it is. Pre-registration prevents the worst abuse — picking controls after seeing outcomes.

**36. What about spillover — a campaign in one county affects its neighbors?**
Real limitation, acknowledged. Contaminated controls bias the lift estimate *downward*, making us conservative rather than flattering. Control pools can exclude adjacent counties on request; claims-level measurement in Phase 3 resolves it properly.

**37. How was the measurement engine validated?**
Three ways: synthetic recovery — inject a known +1.5pp lift into synthetic counties and the estimator recovers it within ±0.3pp with correct significance; synthetic null — no injected effect reads not-significant; and a real-data placebo — eight Texas counties treated as a fictional campaign correctly read +0.17pp, CI [−0.72, +1.07], not significant. It refuses to hallucinate lift.

**38. Your measurement window is ~3 years but your pilot promises 90 days. Which is it?**
Both, honestly stated: the 90-day deliverable is the opportunity assessment, targeting, and *pre-registration* — the campaign design. The measured readout arrives with the next CDC release, and claims integration (the IQVIA play) shortens it to quarters. We never promise a measured lift in 90 days; anyone who does is selling you something.

**39. With 8 or 10 campaign counties, do you have statistical power?**
Marginal, and the tool says so — selections under 5 counties get a warning instead of a confidence interval. Realistic campaigns span 20–50 counties, where power is adequate for effects of ~0.5pp+. PLACES smoothing costs power in small counties; another reason claims data is the measurement endgame.

**40. Why is there no machine learning in a 2026 data product?**
Deliberate regression from the v1 prototype, which used XGBoost on synthetic data. A transparent weighted index is auditable by a client's analysts, explainable to a jury, and provably robust via the sensitivity panel. ML re-enters where it earns its complexity — lift forecasting on claims data — not where it would just add opacity.

**41. What's your ground-truth validation? Correlating with what actually IS undiagnosed?**
Part III of the methodology now has a held-out-source test: score the counties, then check the ranking against a data source the model never saw. Against the held-out County Health Rankings measure, SPPF ranks at ρ = 0.47 where the naive population-times-prevalence spreadsheet scores −0.08 — a lift of +0.55. NHANES measured-vs-reported and USRDS kidney data are the next held-out sources, already scaffolded in the harness.

**42. Could two counties with identical scores have completely different reasons?**
Yes — and the product is built for exactly that. The scorecard shows all seven dimension values, the heatmap shows profile shapes, and the intervention recommendation differs accordingly: a high-payer county gets a payer partnership, a high-SDoH/low-access county gets community health centers. The composite ranks; the profile prescribes.

**43. How sensitive is the ranking to one bad data source?**
Bounded by construction: the largest single-source pathway is CDC PLACES into Disease Burden and Diagnosis Gap. The QA gates catch corrupt inputs before scoring; confidence grades expose thin coverage; and the sensitivity panel lets you zero out any dimension a source feeds and watch the effect live.

**44. Why percentiles instead of your raw score?**
Because "62 out of 100" invites a wrong question and "94th percentile of US counties" answers the right one. Raw scores remain available for auditing the arithmetic — nothing is hidden — but humans reason correctly about ranks.

**45. If your method is so robust, why do you need seven dimensions? Wouldn't three do?**
For pure *ranking*, burden + gap + access captures most of the ordering — the sensitivity analysis shows that. The other dimensions earn their place in the *decision*: payer determines who funds, readiness determines program design, trajectory determines timing. Rank is a third of the product.

---

## D. Product & Technology (46–57)

**46. What's the stack, in 30 seconds?**
Python/pandas ingestion pipelines per source, parquet storage, a deterministic scoring engine, and a Streamlit dashboard — deployed on Streamlit Cloud, CI on GitHub Actions, 44 automated tests, every pipeline ending in a QA gate. Boring on purpose: auditable beats clever for this buyer.

**47. Streamlit isn't enterprise-grade. How does this scale?**
Agreed for the enterprise phase — Streamlit is the right MVP choice (fast iteration, zero front-end cost) and the wrong endgame. Phase 1 moves to authenticated, containerized client workspaces; the scoring engine underneath doesn't change. The data volume is tiny — scale here is organizational, not computational.

**48. What breaks at 100 concurrent users?**
The dashboard layer, not the data. The scored parquet is 25MB and read-only; horizontal scaling is trivial container replication. It's a read-heavy analytics app with no write path — one of the easiest scaling profiles that exists.

**49. How long does an end-to-end data refresh take?**
About 15 minutes for counties, 8 for ZIPs, and 30 for the prescriber file on first download — one command each, cached thereafter, gated by quality checks. A full from-scratch rebuild of everything is under an hour on a laptop.

**50. Is there an API?**
Not yet — deliberately. The MVP's user is a human making planning decisions, and CSV exports cover today's hand-offs. The API surface is designed in Phase 1 (so architecture doesn't foreclose it) and shipped in Phase 3 alongside CRM integration.

**51. What about security review — could this pass pharma IT?**
Today's app holds zero sensitive data — public aggregates in, geographies out — which makes the current review trivial. The moment client-specific data enters (campaign lists, custom weights), Phase 1 adds auth and workspace isolation, and SOC 2 is the Phase 3 gate for enterprise.

**52. Who maintains this if you get hit by a bus?**
The mitigation is discipline, not heroics: everything is in a public repo with CI, 44 tests, a QA-gate system that explains its own failures, a 25-page methodology, and a PRD. A competent data engineer could take over in a week. That's unusual for an MVP, and deliberate.

**53. How much of this did AI build?**
I built it with AI-assisted engineering, and I'd say that proudly to this jury: it's how modern teams will work, including at IQVIA. Every scoring decision, framework choice, and validation design is mine; the AI accelerated implementation roughly tenfold. And unlike most AI-assisted code, this has 44 tests, CI, QA gates, and a full audit trail — judge the artifact, not the tool.

**54. Why eleven dashboard views? Isn't that bloated for an MVP?**
Each view maps to a distinct user decision — market pick, territory design, prescriber targeting, payer strategy, measurement, audit. The count reflects the workflow's real surface, not feature-stuffing; nothing in the demo path is skippable without losing a persona.

**55. What's the biggest technical debt you're carrying?**
Three, ranked: the CMS Geographic Variation endpoint reliability (blocks the full detection signal — Phase 1 P0), Streamlit as the enterprise front end, and the modeled payer sub-signals. All three are in the PRD with dates, none is hidden.

**56. Can I self-host this?**
Yes — clone the repo, pip install, one command; the scored data ships with it and the dashboard runs in 60 seconds with no keys. That zero-friction reproducibility is itself a diligence feature: your analysts can verify everything without asking my permission.

**57. What telemetry do you have on usage?**
Essentially none yet — the MVP predates users. Phase 1's auth layer brings per-user analytics (time-to-shortlist, export rates), which are the leading metrics in the PRD. Right now the honest usage metric is: one deployed instance, one very well-rehearsed user.

---

## E. HCP Targeting, Ethics & Compliance (58–70)

**58. Is targeting doctors with sales reps really the answer to underdiagnosis?**
The call we're ranking is a diagnosis-support conversation — screening protocols, risk-assessment tools, referral pathways — in practices whose panels suggest high hidden burden. Detailing infrastructure is the distribution channel pharma already has; SPPF points it at detection instead of share-stealing.

**59. Are you profiling doctors without consent?**
We rank public CMS Medicare data that the federal government publishes for exactly this kind of transparency — the same file journalists and researchers use. No individual patient data exists anywhere in the chain, and the score explicitly ranks conversation value, never prescribing quality.

**60. Isn't "finding undiagnosed patients" just demand creation with better PR?**
Undiagnosed diabetes and hypertension cause strokes, amputations, blindness, and dialysis — every year of delay costs the patient and the system more. The interventions are screening programs, the accountability metric is diagnosis-rate lift, not prescriptions. If a company wanted pure demand creation, this tool's measurement engine would expose that it didn't work.

**61. Your top counties are poor and heavily minority. Are you targeting vulnerable populations?**
We're directing screening resources *toward* the populations the healthcare system currently fails — that's the equity arithmetic of underdiagnosis. The alternative, spending screening budgets in well-served affluent markets, is the actual inequity. The interventions recommended in high-SDoH counties are community health centers and payer-funded programs, not premium-priced outreach.

**62. Could this tool be misused — say, to avoid sick populations for insurance pricing?**
Any population-level tool could be pointed backward; our mitigations are contractual use restrictions in licensing, the tool's design (it recommends *investment* in high-need areas, its outputs are useless for individual underwriting), and no individual data existing to misuse. It's a fair question to keep asking as we scale.

**63. Does this touch HIPAA at all?**
No. HIPAA governs protected health information about individuals; every input here is a public aggregate statistic and every output is a geography or a public NPI record. That's not a loophole — it's the design principle that makes the product deployable in days instead of quarters.

**64. What about promotional compliance — OPDP, PhRMA code?**
SPPF informs *where* to run programs; it generates no promotional content and makes no product claims. Screening and disease-awareness programs have established compliance pathways pharma already operates under. The obesity/pre-GLP-1 module is explicitly parked pending legal review because that line is genuinely harder there.

**65. Would a physician be comfortable seeing their name on your list?**
The rationale we attach is one they'd largely endorse: "your county has high hidden burden, your panel is heavily metabolic, you're primary care." It reads as "you're well-positioned to catch what's being missed" — not an accusation. And it's built from data CMS already publishes about them.

**66. Who's accountable if a campaign in a recommended county fails?**
The measurement engine is the accountability: pre-registered geography, matched controls, and a readout that can say "no lift." A tool that can prove its own recommendation didn't work is holding itself to a higher standard than the industry's current one, which is vibes.

**67. Do you have any medical/clinical validation of the intervention recommendations?**
The recommendation logic encodes established program archetypes — pharmacy screening, FQHC partnerships, MA-funded outreach — matched to county profiles. It's decision-support heuristics, labeled as such, not clinical guidance. Clinical program design remains with the client's medical affairs.

**68. Is there an IRB question anywhere in this?**
Not for the tool — no human subjects, no individual data. If a client's screening program itself constitutes research, that's their standard program-level review, unchanged by how they picked the geography.

**69. What does the patient get out of this?**
A diagnosis they weren't going to get, earlier — which for T2D and hypertension is the whole ballgame of avoiding complications. This is the rare pharma tool whose success metric, diagnosis-rate lift, is itself a public-health win regardless of which therapy is eventually prescribed.

**70. Would you show this tool to a regulator or a journalist?**
Yes, and I'd start on the provenance page. Nothing in this product depends on data or logic I couldn't defend on the record — that constraint shaped every build decision, and it's why the disclosed-assumptions register exists.

---

## F. Business Model & Go-to-Market (71–82)

**71. Justify your pricing. Why $25–75k for a pilot?**
It's benchmarked against the alternative: a consultancy's one-off geographic analysis at 2–4× the price, slower, and unmeasured. The pilot price is set for a brand director's signature authority — the entire land motion is designed around who can say yes without a committee.

**72. What's your evidence of willingness to pay?**
Direct evidence doesn't exist pre-pilot — that's what the pilot is for, and I won't fabricate letters of intent. Indirect evidence: brands already spend on untargeted screening programs and six-figure geographic consulting; SPPF is a cheaper, faster, measurable substitute for existing spend, not a new budget line.

**73. What's the sales cycle for this?**
Pilot: 1–2 quarters — brand-level signature, no data governance review because there's no sensitive data. Platform license: 2–4 quarters with procurement. The PHI-free architecture isn't just compliance hygiene; it's cycle-time compression.

**74. Who sells this? You?**
At pilot stage, founder-led sales through the ideathon and IQVIA network — which is precisely the point of being here. At scale, the answer is IQVIA's existing account teams: this is a new SKU for relationships that already exist, which is the whole distribution thesis.

**75. What's the renewal story after the pilot report is delivered?**
Measurement. The pre-registered campaign creates a built-in return appointment — the lift readout — and each data refresh re-ranks the map. A report is a transaction; a measurement subscription is a relationship. That's why the measurement engine exists in the MVP and not the roadmap.

**76. What if a client just takes your pilot report and runs the method internally?**
At pilot price, some will — and the report license terms limit reuse. But the recurring value is the refresh cadence, the measurement discipline, and the module expansion; internalizing that costs more than licensing it. Bloomberg's clients could also build spreadsheets.

**77. Why wouldn't ZS or IQVIA Consulting just do this as a service line?**
They could — as bespoke projects at 5× the cost per engagement, without a product's compounding. The play here is productized: same engine every client, refreshed automatically, measured consistently. A consultancy's incentive is billable hours; this product's incentive is renewals. Different economics, and honestly, the best counter is IQVIA building it as a product first.

**78. What's your CAC assumption?**
Near-zero for the first pilots (ideathon, network, founder-led), which is the honest answer and also the plan — the pilot's job is to create the case study that makes the second sale cheaper. Platform-stage CAC rides IQVIA's existing account coverage, which is the distribution argument for building it here.

**79. Give me the 12-month P&L shape.**
Costs: essentially one team and cloud pennies — the data is free, which makes gross margin software-like from day one. Revenue: one to two pilots in the first two quarters ($50–150k), first platform conversion by month 12 ($150–400k ARR). Small numbers, deliberately — the 12-month game is proof, not scale.

**80. What's the biggest commercial risk?**
That trust is the product and trust is slow — a data-integrity failure in front of one client analytics team could end the company, which is why "zero diligence findings" is an existential metric in the PRD, not a KPI. Second risk: someone with distribution moves faster; the mitigation is being inside that distribution.

**81. Why should IQVIA incubate this instead of you raising venture money?**
Because the two assets that turn this from tool into platform — claims data for quarterly measurement and account relationships for distribution — are things IQVIA already owns and a startup would spend years and millions renting. The idea needs IQVIA more than it needs capital, and IQVIA's product gap here is real.

**82. What does success look like at the end of year one?**
Two paid pilots delivered, one pre-registered campaign in the field, one platform conversion signed, the NHANES validation published in the methodology, and zero integrity findings in any client review. Five numbers; I'd stake the roadmap on them.

---

## G. IQVIA Fit & Strategy (83–90)

**83. Doesn't this cannibalize IQVIA's claims-analytics revenue?**
No — it's upstream of it. SPPF creates diagnosed patients; every downstream IQVIA product monetizes diagnosed patients. It's the demand-generation layer for the existing portfolio, and the Phase 3 claims integration actually *increases* claims-data consumption.

**84. How does this fit IQVIA's existing product families?**
It slots beside launch-excellence and commercial-analytics offerings as the earliest-stage layer: before segmentation, before targeting, before share models — the "where will the next patient come from" layer none of them answer. And it hands its outputs directly to OCE-shaped workflows.

**85. What IQVIA asset would improve this fastest?**
Claims, for measurement: quarterly diagnosis verification instead of CDC's multi-year cycle collapses the product's biggest honest limitation. Second: lab data for the thyroid signal. Third: account distribution. In that order.

**86. Could this work internationally, where IQVIA's growth is?**
The engine is geography-agnostic; each market is a data-sourcing project. India's NFHS-5 publishes district-level diabetes and hypertension measures — roughly 750 scoreable districts — and is the planned second market, partly because this jury's own market intelligence could accelerate it.

**87. Why did an India-based builder make a US-data product?**
Because the US public-data ecosystem is the cheapest possible proving ground — free, granular, English, documented. The method proven, the India port becomes a config exercise on NFHS-5 rather than a leap of faith. Prove where data is easy; scale where growth is.

**88. If IQVIA adopts this, what's the team ask?**
Small and specific: two data engineers, one health economist for the validation study, part-time compliance counsel, and a sponsor with account access for two pilot introductions. Phase 1 of the PRD is scoped for exactly that footprint over two quarters.

**89. What would you refuse to build even if a client paid for it?**
Individual patient identification or re-identification of any kind, underwriting/exclusion use cases, and promotional content generation. The first is impossible from our data anyway — but "we don't do that" is a design principle worth stating before anyone asks.

**90. What happens to this project if it doesn't win today?**
It's live, open, documented, and I'll keep building it — the ideathon is an accelerant, not a life-support system. But the honest answer is that measurement-grade claims data and distribution change its slope by years, which is why I'm here and not just shipping quietly.

---

## H. Brutal / Curveballs (91–100)

**91. "This looks like a school project with good slides." Respond.**
Fair challenge — here's the falsifiable difference: it's deployed at a public URL, scores every county, ZIP, and prescriber in America, carries 44 automated tests and 60+ data-quality gates, passed a real-data placebo test, and ships a 25-page methodology with a disclosed-assumptions register. Clone the repo and audit it tonight. School projects don't invite diligence; this is built for it.

**92. "You have zero users and zero revenue. Why are you confident?"**
I'm not confident about demand — that's what the pilot tests, and I've priced it to make testing cheap. I'm confident about the two things I could control pre-revenue: that the problem is real (the GLP-1 era made it urgent) and that the artifact survives scrutiny. Everything else is a hypothesis with a 90-day experiment attached.

**93. "Your top pick, Starr County, has 66,000 people. That's a tiny market."**
Starr is the top of a ranked list of 3,144, not the strategy — the top *decile* covers tens of millions of people, and Hidalgo County alone, two spots down, has 900k. Small high-density counties are where pilots prove lift cheaply; large emerging counties are where the money is. The product gives you both lists.

**94. "24 Priority counties out of 3,144 — your tool says 99% of America isn't worth targeting?"**
The tiers are deliberately conservative — Priority means confirmed by multiple independent sources, a shortlist you can defend to a CFO. Below it sit 1,665 Emerging counties with meaningful opportunity. A targeting tool that calls half the country "priority" is a tool that has decided nothing.

**95. "If the data is annual and public, your product is a nice-to-have refresh script."**
The refresh script is maybe 10% of the codebase. The rest is what a script doesn't have: a validated scoring framework, prescriber activation, causal measurement with pre-registration, provenance and QA discipline, and sensitivity analysis. Buyers don't pay for data movement; they pay for defensible decisions.

**96. "Your measurement engine has never measured a real campaign."**
True — no campaign has run against it yet; that's definitionally the pilot's job. What I can show today is that it recovers known synthetic effects, correctly refuses to find effects that don't exist, and passed a real-data placebo. That's the maximum validation possible pre-deployment, and more than most deployed marketing-mix models ever show.

**97. "You've disclosed a lot of weaknesses. Why should I fund something this unfinished?"**
Every data product this age has these weaknesses; mine are labeled and yours to inspect, most vendors' are discovered by clients after the invoice. The disclosure register isn't unfinishedness — it's the trust architecture that makes a pharma analytics team say yes. Fund the team that shows you the seams.

**98. "What's the one question you were hoping we wouldn't ask?"**
Predicting *change*. My score is validated for ranking where hidden burden sits today — held-out test, ρ 0.47 versus −0.08 for the naive spreadsheet — but Part III also shows it does not beat naive at predicting which counties' gaps will *move* over a two-to-three-year survey window; short-run changes in modeled survey data are mostly noise. That's exactly why change is measured rather than predicted: the campaign engine with matched controls exists because forecasting deltas from public data doesn't work. You've now heard my weakest point, from me first, with the table number.

**99. "Convince me in one sentence."**
The biggest untapped market in chronic disease is the patients no dataset can see — SPPF finds them geographically, activates them through prescribers, and is the only tool that then proves whether it worked.

**100. "Last question: why you?"**
Because I built the unglamorous parts nobody builds for a demo — the QA gates, the placebo test, the assumptions register — before anyone asked. That instinct, applied with IQVIA's data and distribution, is the difference between a clever idea and a product pharma actually trusts. The repo is public; judge me by what's in it.

---

## I. The Part III Validation Numbers — Slides 9, 13, 16 (101–112)

*These are YOUR slides' claims. Every number here must come out of your mouth correctly.*

**101. Explain slide 9's "Δρ = +0.55 (0.47 vs −0.08)" in plain words.**
We asked: if you rank counties with a five-minute spreadsheet — population times disease rate — versus with SPPF, which ranking better matches a data source neither has ever seen? Agreement is measured on a scale where 1.0 is perfect and 0 is random. The spreadsheet scored −0.08 — no better than shuffling the list. SPPF scored 0.47 — a real, meaningful match. The gap between them, +0.55, is what you're paying for beyond Excel.

**102. What is the "temporal out-of-time test" and what does ρ = 0.93 actually mean? ⚠️ SAY THIS CAREFULLY.**
It means *stability*, not prophecy: freeze the score built on the old data release, bring in the new release, and check whether the ranking holds — 0.93 on a 0-to-1 scale means the map you plan a two-year program on won't be a different map next year. Do NOT say it "predicts the change in diagnosis gap" — predicting short-window changes is a different, harder task, and our own Part III shows nobody beats noise at that (see next question).

**103. Why do XGBoost and SHAP appear on your stack slide if you say the scoring has no ML?**
Both are true, and precision matters: the repo's lineage includes an ML pipeline — XGBoost with SHAP explainability and spatially grouped cross-validation — from the R&D phase, and it remains in the codebase for benchmarking. The *production* score is a deterministic weighted index, chosen deliberately because a pharma analytics team can audit every number by hand. The stack slide describes the codebase; the scoring slide describes the product.

**104. "Your own Table 61 shows the composite is WORSE than naive at predicting gap changes — ρ −0.09, p = 0.014. Explain." ☢️ THE MOST DANGEROUS QUESTION.**
You've read the methodology carefully — good, that table is there on purpose. It tests something the product doesn't claim: forecasting which counties' modeled survey estimates will wiggle over a 2–3 year window, which is mostly statistical noise, and the table shows honestly that nothing — us or naive — predicts it usefully. What the score IS validated for is ranking where hidden burden sits — the held-out test at 0.47 vs −0.08. Levels, we predict; changes, we *measure*, with the matched-control engine. A vendor who hid that table would be scarier than one who printed it.

**105. What does slide 16's "ΔR² = +0.20, partial r = 0.51" mean, simply?**
It answers "aren't you just ranking poor counties?" with arithmetic. First explain poverty's share of the story, then ask: does the Diagnosis Gap dimension add anything poverty didn't already tell you? It does — it explains a fifth more of the variation (that's the +0.20), and its independent link to opportunity, after removing everything poverty explains, is 0.51 on a −1-to-1 scale (that's the partial r), with odds this is chance below one in a thousand (p < 0.001). Deprivation and opportunity are related; they are not the same map.

**106. What is a "naive baseline" and why do you keep comparing against it?**
It's the five-minute Excel answer — rank counties by population × prevalence — and it's what most teams actually use today. Any model must beat the tool the buyer already has for free, or it has no right to exist. Reporting every result as *lift over that baseline* is us grading ourselves against the honest alternative, not against zero.

**107. What is "Spearman ρ" that appears all over your validation?**
A score for how well two rankings agree, from −1 (perfectly opposite) through 0 (no relationship) to +1 (identical order). We use rankings rather than raw values because the product's job is ordering counties — who's first, who's fiftieth — not predicting exact percentages.

**108. What was "held out" in the held-out-source test — and why does that matter?**
A data source the score never ingested was set aside as an exam: score the counties without it, then check the ranking against it. Agreement with data you never touched is evidence you've measured something real about the world, not memorized your own inputs. It's the tabular equivalent of a student acing questions that weren't in the textbook.

**109. "Your precision-at-top-20 improvement has p = 0.162 — that's not significant."**
Correct, and it's printed rather than hidden: at only 20 counties the sample is too small for that particular metric to clear significance, even though the point estimate more than doubles the baseline. The significant results — held-out lift and the partial correlation — carry the validation case; the top-20 metric is reported for completeness, not as proof.

**110. Who ran this validation — is it independent?**
It's self-run, scripted, and reproducible — one command on the public repo regenerates every table, which is the strongest form of non-independent validation that exists pre-partnership. Independent replication is precisely what the NHANES/USRDS extensions and a pilot's client analytics team provide next.

**111. What is "spatially grouped cross-validation (GroupKFold)"?**
A guard against geographic cheating when testing models: normally you test on random held-out counties, but neighboring counties are near-copies of each other, so a model can look brilliant by memorizing regions. Grouping by state forces the test to be "can you score a state you've never seen?" — a much harsher and more honest exam.

**112. If your validation harness is one command, will you run it live?**
Yes — `python3 -m src.validation.part3_tables` regenerates every Part III number from the data in the repo, on stage if you like. Offer this proactively if the room gets skeptical; nothing disarms a methods argument like recomputing the numbers in front of it.

---

## J. Plain-Language Glossary — Every Term You'll Say (113–130)

*You will be asked "what does that mean?" about your own vocabulary. Each answer here is speakable as-is.*

**113. What is a percentile?**
A rank out of 100. A county at the 94th percentile beats 94% of all US counties. It's how we present scores because "you're in the top 6% of the country" needs no manual.

**114. What is "normalization"?**
Putting different measurements on the same ruler. Diabetes rates run 6–26%, incomes run $20k–$150k — you can't average those directly. Normalization rescales each one to 0-to-1 first, so no single measure dominates just because its numbers are bigger.

**115. What is a confidence interval, like the "[−0.72, +1.07]" you quote?**
The honest range around an estimate. Instead of pretending we measured lift as exactly +0.17, we say: given the noise, the true answer plausibly sits anywhere from −0.72 to +1.07. If that range includes zero, we refuse to claim an effect happened.

**116. What does "statistically significant" mean?**
That a result is too large to be plausibly explained by luck. By convention, we call something significant when chance alone would produce it less than 5% of the time. Not significant doesn't mean "false" — it means "we can't rule out luck yet."

**117. What is a p-value?**
The probability that pure chance would produce a result at least this strong. p = 0.014 means about a 1.4% chance it's a fluke. Small p, strong evidence.

**118. What is "bootstrap"?**
A way to measure uncertainty by resampling: shuffle-and-redraw the counties thousands of times, recompute the answer each time, and see how much it wobbles. The wobble IS the confidence interval. Ours uses 2,000 redraws.

**119. What is a control group, and what is "difference-in-differences"?**
A control group is the comparison you'd have been without the campaign — statistically similar counties that got nothing. Difference-in-differences is the arithmetic: (how much your counties improved) minus (how much their twins improved anyway). What's left over is the campaign's effect. Same logic as a drug trial's placebo arm.

**120. What is "pre-registration"?**
Locking your campaign counties AND their control twins in writing *before* launch. It prevents the oldest trick in analytics — choosing your comparison after you've seen the results. It's what makes the final number believable to a skeptic.

**121. What is a "placebo test"?**
Feeding the measurement engine a fake campaign — counties where nothing actually happened — and checking it correctly finds nothing. Ours does: +0.17 with a range crossing zero. An engine that finds lift everywhere is a liar; ours passed the lie-detector.

**122. What is a ZCTA, and how is it different from a ZIP code?**
ZIP codes are postal delivery routes; ZCTAs are the Census Bureau's map-shaped approximations of them, which is what statistics get published against. They match ~99% of the time; where they don't, our pipeline flags it. If asked, say: "we score Census ZIP-areas, the standard for ZIP-level statistics."

**123. What is a FIPS code?**
The government's ID number for each geography — every county has a unique 5-digit FIPS. When I paste "48479" into the demo, that's Webb County, Texas. It's how systems talk about places without ambiguity.

**124. What is an NPI?**
National Provider Identifier — the unique 10-digit public ID every US clinician has, assigned by the government. Our prescriber list is built on NPIs because they're unambiguous and publicly published by CMS.

**125. What are BRFSS, ACS, and NHANES?**
Three big federal surveys. BRFSS: CDC's giant annual phone survey on health behaviors — feeds our disease rates. ACS: the Census Bureau's ongoing survey of income, insurance, education — feeds our socioeconomics. NHANES: the gold standard where people get physical exams and blood tests — which is why it can catch *undiagnosed* disease, and why it's our planned ground-truth source.

**126. What are Stars and HEDIS?**
Report-card systems for insurance plans. Medicare Advantage plans get Star ratings, and higher stars mean bonus payments from the government; HEDIS is the quality scorecard behind much of it. Screening and early diagnosis improve those scores — which is why insurers will co-fund exactly the programs SPPF plans.

**127. What is PHI, and why do you keep saying you have none?**
Protected Health Information — anything traceable to an individual patient, regulated under HIPAA with heavy compliance burden. We use only statistics about places and public records about clinicians. No PHI means no HIPAA scope, no data-use agreements, and procurement in days instead of quarters.

**128. What are Python, pandas, Parquet, and Streamlit — your stack slide?**
Python: the standard programming language of data science. pandas: its spreadsheet-like data engine. Parquet: a compressed file format for tables — our entire scored America is ~25MB. Streamlit: a tool that turns Python into an interactive web dashboard. Translation for the room: boring, standard, auditable technology — chosen so any data team on earth can maintain it.

**129. What is CI (continuous integration), as in "CI-gated"?**
A robot that re-runs every test automatically on every code change and blocks anything that fails. It means quality isn't dependent on me remembering to check — the repo currently runs 44 automated tests on each change.

**130. What is YAML config, as in "each condition is a config file"?**
A plain-text settings file a human can read — disease name, data fields, weights. "New condition = new config file" means expanding to kidney disease is filling in a form, not rebuilding the engine. That's the whole expansion economics in one sentence.

---

## K. Pharma Vocabulary, You Personally, and Live-Demo Situations (131–150)

*Words from your own deck you must be able to define, questions solo presenters always get, and moments that happen live.*

### Pharma words you'll say — own them (131–140)

**131. What exactly is a "claim," as in claims data?**
The bill. Every time a doctor visit, test, or prescription is paid through insurance, a billing record is created — that's a claim. Claims data is the industry's core dataset, and its blind spot is our whole thesis: no diagnosis, no bill, no record.

**132. What is a "brand team"?**
The business unit inside a pharma company responsible for one drug — its marketing, budget, and growth targets. They're our buyer: the people whose bonus depends on finding more patients for that one product.

**133. What is a GLP-1, and why do you keep mentioning it?**
The diabetes-and-obesity drug class behind Ozempic and similar medicines — the biggest commercial phenomenon in pharma history. It matters here because these companies have maxed out diagnosed patients; their growth now depends on new diagnoses, which is exactly what SPPF finds.

**134. What is "detailing" and what is a "rep"?**
A rep (sales representative) is pharma's field person who visits doctors; detailing is that visit. Traditionally it's product promotion; the visits SPPF ranks are diagnosis-support conversations — helping practices screen and catch hidden disease.

**135. What are "decile lists"?**
The industry's standard targeting method: rank doctors 1–10 by how much they already prescribe, call the top deciles. Its flaw is our opening argument — it can only rank the already-diagnosed world.

**136. What is "market access" as a job?**
The pharma function that deals with insurers and health systems — getting drugs covered and programs funded. They're persona three in our product: the payer-partnership view exists for them.

**137. What is a "payer" vs a "provider"?**
Payer = who pays (insurance companies, Medicare, Medicaid). Provider = who treats (doctors, clinics, hospitals). SPPF maps both: payers for who funds screening, providers for who performs it.

**138. What is Medicare vs Medicare Advantage vs Medicaid?**
Medicare: US government insurance for people 65+. Medicare Advantage (MA): the version run by private insurers under government contract — with quality bonuses that make them fund screening. Medicaid: government insurance for low-income people. Our payer dimension measures the mix per county.

**139. What are Veeva and OCE?**
The two dominant CRM systems pharma reps run their day on — the software holding their call lists. "CRM-ready export" means our prescriber list drops into the tools reps already use, no new software to adopt.

**140. What is "DTC"?**
Direct-to-consumer advertising — drug ads aimed at patients. SPPF's geographic scores could target DTC spend too, but our recommended interventions are screening programs, deliberately, for both ethics and measurability.

### About you — the solo-presenter questions (141–146)

**141. "What's your background? You're not from pharma."**
Correct — and I treated that as a constraint to design around, not hide: everything in this platform is built on published epidemiology, government data documentation, and validation logic, precisely because I couldn't lean on insider intuition. The domain experts I need next are the reason I'm pitching here rather than building alone.

**142. "Have you spoken to a single real customer?"**
Not yet — by sequencing, not avoidance: I built the artifact first because in this market a slide deck without a working product is noise. The pilot ask IS the customer-discovery plan, priced low enough to make the conversation easy. If the jury includes commercial pharma people, the discovery starts in this room.

**143. "How long did this take, and who helped?"**
Weeks, not months — built solo with AI-assisted engineering, which I'd state proudly: it's how small teams will out-ship big ones, including inside IQVIA. Every framework decision, validation design, and honest disclosure is mine; the acceleration is the tooling.

**144. "What would your role be if IQVIA adopts this?"**
Product owner — the person who holds the methodology, the honesty register, and the roadmap. I'd want IQVIA engineers, a health economist, and a commercial sponsor around it; what I bring is the product judgment and the proof that I ship.

**145. "What's the biggest thing you don't know?"**
Pharma's internal buying reality — how budget approvals, compliance sign-offs, and brand-team politics actually flow. That's learnable and exactly what a pilot plus an IQVIA sponsor teaches; what wasn't learnable-later was the data discipline, so I built that first.

**146. "Why should we trust a non-domain founder with a healthcare product?"**
Because the product's entire design philosophy is verifiability over authority — every claim traceable to a public source, every assumption labeled, every number recomputable in front of you. Domain veterans ask you to trust their experience; this asks you to check its work.

### Live-demo situations (147–150)

**147. "Show me my home county, right now."**
Do it — this is a gift, not a threat. Type their state, find the county, and read the scorecard aloud: percentile, tier, top dimensions, recommended program, confidence grade. If it's a low-opportunity county, even better: "the tool says don't spend money here — that's half its value."

**148. "Can I open this on my phone right now?"**
Yes — give them the URL (silent-patient-pool-finder.streamlit.app). It's public by design at this stage; nothing in it is sensitive because nothing in it is private data. Judges independently poking the live app while you talk is the best thing that can happen to you.

**149. The app is down or slow, mid-demo.**
Acknowledge in one sentence — "free-tier hosting, waking up" — and switch to the backup recording without apology; the click-path storyboard is identical. Then offer the repo: "everything also runs locally in sixty seconds — that reproducibility is a feature." Never debug live.

**150. "Stop the demo. Just tell me plainly: what happens in the first 90 days if we say yes?"**
Week 1–2: pick the brand and condition with your team. Week 3–8: I deliver the market opportunity assessment — ranked counties, ZIP maps, prescriber lists for that brand. Week 9–12: we pre-register the campaign geography and matched controls, so the moment the campaign runs, the measurement clock starts. One brand, one condition, one signed page — and you'll know by the data whether to scale or stop.

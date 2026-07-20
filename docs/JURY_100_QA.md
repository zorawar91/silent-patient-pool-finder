# SPPF — 100 Jury Questions & Answers

*Print-ready. Brutal questions included deliberately — if it's in here, it can't ambush you.
Answers are written to be spoken: 2–4 sentences, no hedging, concede what's true.*

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
The honest answer: face validity, internal robustness, and measurement-engine validation exist today; external ground-truth validation is Phase 1 — correlating our gap scores against NHANES measured-vs-reported prevalence differences, the closest thing to ground truth that exists. It's the top of the roadmap, not an afterthought.

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
Python/pandas ingestion pipelines per source, parquet storage, a deterministic scoring engine, and a Streamlit dashboard — deployed on Streamlit Cloud, CI on GitHub Actions, 35 automated tests, every pipeline ending in a QA gate. Boring on purpose: auditable beats clever for this buyer.

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
The mitigation is discipline, not heroics: everything is in a public repo with CI, 35 tests, a QA-gate system that explains its own failures, a 25-page methodology, and a PRD. A competent data engineer could take over in a week. That's unusual for an MVP, and deliberate.

**53. How much of this did AI build?**
I built it with AI-assisted engineering, and I'd say that proudly to this jury: it's how modern teams will work, including at IQVIA. Every scoring decision, framework choice, and validation design is mine; the AI accelerated implementation roughly tenfold. And unlike most AI-assisted code, this has 35 tests, CI, QA gates, and a full audit trail — judge the artifact, not the tool.

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
Fair challenge — here's the falsifiable difference: it's deployed at a public URL, scores every county, ZIP, and prescriber in America, carries 35 automated tests and 60+ data-quality gates, passed a real-data placebo test, and ships a 25-page methodology with a disclosed-assumptions register. Clone the repo and audit it tonight. School projects don't invite diligence; this is built for it.

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
External ground-truth validation — I can't yet show that my diagnosis-gap score correlates with independently measured undiagnosis, because the NHANES study is Phase 1. Everything else — robustness, placebo, provenance — is done; that one is a promise with a date on it. You've now heard my weakest point, from me first.

**99. "Convince me in one sentence."**
The biggest untapped market in chronic disease is the patients no dataset can see — SPPF finds them geographically, activates them through prescribers, and is the only tool that then proves whether it worked.

**100. "Last question: why you?"**
Because I built the unglamorous parts nobody builds for a demo — the QA gates, the placebo test, the assumptions register — before anyone asked. That instinct, applied with IQVIA's data and distribution, is the difference between a clever idea and a product pharma actually trusts. The repo is public; judge me by what's in it.

from __future__ import annotations
# All user-facing tooltip copy for the SPPF dashboard.
# This is content, not code — keep prose here so view modules stay readable.
#
# The composite-score weight description is generated from the same config the
# scorer actually loads (config/dimensions.yaml), so the tooltip can never
# drift from the real weights.

from src.features.dimension_scorer import load_weights
from src.output.theme import DIM_LABELS

_W = load_weights()
WEIGHTS_TEXT = ", ".join(
    f"{DIM_LABELS[k]} {round(_W.get(k, 0) * 100)}%" for k in DIM_LABELS
)

# Tooltip text shown on ℹ hover — used in the heatmap column headers
DIM_TOOLTIPS = {
    "disease_burden": (
        "How large is the total chronic disease burden in this county? "
        "Combines diagnosed Type 2 Diabetes prevalence, obesity rate, hypertension "
        "co-occurrence, and poor physical health days from the CDC county health survey."
    ),
    "diagnosis_gap": (
        "What share of disease cases remain undiagnosed? High scores reflect a large gap "
        "between estimated true disease prevalence and the number of diagnosed patients, "
        "combined with low annual checkup rates and a high uninsured population — "
        "counties where many patients have never been tested."
    ),
    "access_to_care": (
        "How easily can a patient get diagnosed and treated here? Reflects federal primary "
        "care shortage designations, the presence of federally funded safety-net clinics, "
        "rural geography, and the rate of routine checkups as a proxy for primary care access."
    ),
    "social_determinants": (
        "What structural factors drive underdiagnosis? Combines poverty rate, household "
        "income, uninsured rate, food access, and high school graduation rate (all real "
        "Census/USDA/CHR data), plus a structural-risk uplift derived from the composite "
        "socioeconomic deprivation index. Note: the uplift is an SES-based proxy — it does "
        "not currently use county demographic composition data."
    ),
    "payer_landscape": (
        "Who insures patients in this county, and how does that create program funding "
        "opportunities? Medicare Advantage penetration is REAL county-level CMS data "
        "(3,108 of 3,128 counties). Medicaid share, commercial share, and dual-eligible "
        "share are MODELED estimates derived from SES signals and coverage arithmetic — "
        "directionally sound but not sourced rates. Treat sub-signals other than MA "
        "penetration as planning estimates."
    ),
    "commercial_readiness": (
        "How feasible is it to launch and scale a screening program here? Reflects "
        "broadband internet access, urban versus rural infrastructure, over-the-counter "
        "health product sales as a proxy for health-seeking behavior, and annual checkup "
        "rates as a measure of existing care relationships to recruit patients from."
    ),
    "trajectory": (
        "Is the undiagnosed patient opportunity growing or shrinking? High scores reflect "
        "a widening gap driven by an aging population (Type 2 Diabetes risk rises sharply "
        "after age 45), rising obesity rates, and counties where healthcare investment "
        "has not kept pace with rising disease burden."
    ),
}

METRIC_TOOLTIPS = {
    "opportunity_score":
        "Composite score from 0 to 100 combining all 7 dimensions with the following weights: "
        f"{WEIGHTS_TEXT}. "
        "A higher score means a stronger case for program investment in that county.",
    "priority_tier":
        "Opportunity Score of 55 or above. These counties have the highest disease burden, "
        "widest diagnosis gap, and strongest payer funding incentives — confirmed by five "
        "real data sources: CDC PLACES, US Census ACS, CMS Medicare data, HRSA shortage "
        "area designations, and County Health Rankings. "
        "Prioritize for immediate program launch and budget allocation.",
    "emerging_tier":
        "Opportunity Score between 40 and 55. Strong underlying indicators with some gaps — "
        "such as access barriers or lower payer readiness. "
        "Recommended for pipeline development and forward planning.",
    "developing_tier":
        "Opportunity Score below 40. Lower immediate priority. Monitor for shifts in disease "
        "burden, payer landscape, or demographic trends that may elevate these counties over time.",
    "est_pool":
        "Estimated number of adults living with an undiagnosed chronic condition in this geography. "
        "Calculated as: county ADULT population (Census PEP 18+) × disease prevalence rate × "
        "undiagnosis rate. For Type 2 Diabetes the rate is county-specific, weighted by the local "
        "adult age mix using NHANES Aug 2021–Aug 2023 strata (36.1% of cases undiagnosed at 20–39, "
        "31.6% at 40–59, 24.9% at 60+; 28.5% for all adults). The undiagnosed SHARE falls with age "
        "because older adults are screened more, so younger counties hide proportionally more cases. "
        "Hypertension: approximately 20% undiagnosed. "
        "Hypothyroidism: approximately 50% undiagnosed.",
    "counties_scored":
        "Total US counties with a valid Opportunity Score. "
        "The tool covers all 3,143 US counties and county-equivalents, scored using publicly "
        "available data from the CDC, US Census, the federal Health Resources and Services "
        "Administration, and the Centers for Medicare and Medicaid Services.",
    "avg_opp_score":
        "Average Opportunity Score across all counties in the current view. "
        "Use as a baseline when comparing individual county scores — "
        "any county scoring above this average has above-average unmet diagnostic need.",
    "top_state":
        "State with the highest average Opportunity Score across all its counties. "
        "Useful for prioritizing state-level payer contract negotiations.",
    "payer_mix":
        "Breakdown of insurance coverage types across the county. "
        "Medicare Advantage insurers have financial incentives to fund early screening programs. "
        "Medicaid managed care contracts create similar incentives. "
        "High commercial coverage suits employer wellness program partnerships.",
    "ma_penetration":
        "Share of Medicare-eligible patients enrolled in a Medicare Advantage plan. "
        "Penetration above 40% signals strong insurer incentives to fund screening and "
        "care management partnerships, as insurers are financially rewarded for "
        "improving member health outcomes.",
    "screening_yield":
        "Estimated number of patients newly diagnosed per 1,000 people screened, "
        "based on published research benchmarks for each program type. "
        "Reflects how efficiently each program converts screening activity into confirmed diagnoses, "
        "before accounting for costs.",
    "recommended_intervention":
        "Program type recommended based on this county's scoring profile — matching the "
        "highest-value delivery channel to the county's payer mix, social barriers, "
        "access infrastructure, and commercial readiness.",
    "national_radar":
        "Radar chart comparing average scores across the 7 dimensions. "
        "The navy shape represents the top opportunity counties; "
        "the light shape represents all US counties. "
        "A larger shape indicates a stronger overall profile.",
    "patient_funnel":
        "ILLUSTRATIVE national funnel — not computed from county data. The first three "
        "steps (adult population, prevalence, undiagnosed fraction) use published "
        "CDC/NHANES national figures; the last two ('detectable via indirect signals' "
        "and 'reachable by programs') are planning assumptions included to frame the "
        "opportunity, not measured quantities.",
    "risk_score":
        "Condition-specific geography score from 0 to 100, computed as a weighted blend "
        "of the dimension scores most relevant to the selected condition (e.g. T2D = "
        "60% Disease Burden + 40% Diagnosis Gap). Built from the same public data as "
        "the composite Opportunity Score — no patient-level or sales data is used.",
    "opp_score_dist":
        "Distribution of Opportunity Scores across all 3,143 US counties. "
        "Blue bars are lower-scoring developing counties, amber bars are emerging markets "
        "(score 40 to 55), and red bars are priority markets (score 55 and above). "
        "Most counties cluster in the moderate range; the red bars represent the highest-yield markets.",
    "condition_t2d":
        "Type 2 Diabetes — approximately 8.7 million estimated undiagnosed adults nationally. "
        "NHANES 2021–2023: 28.5% of all Type 2 Diabetes cases are undiagnosed nationally, ranging 24.9%–36.1% by age band. "
        "Priority counties are those with a geography risk score of 55 or above. The headline figure on this card is OUR estimate, summed from county-level data, so the three condition cards add up to the national banner total. The published national estimate is shown beneath it for comparison; the two differ because definitions and vintages differ.",
    "condition_htn":
        "Hypertension (high blood pressure) — approximately 34.9 million estimated undiagnosed "
        "or uncontrolled adults nationally. Around 20% of people with hypertension are unaware "
        "of their diagnosis. Hypertension frequently co-occurs with Type 2 Diabetes, "
        "increasing the combined screening opportunity. The headline figure is OUR computed estimate (undiagnosed only). The published ~34.9M counts undiagnosed OR uncontrolled hypertension — a broader definition — which is why it is larger.",
    "condition_hypo":
        "Hypothyroidism — approximately 2.1 million estimated undiagnosed adults nationally; "
        "research suggests around 50% of cases remain undiagnosed. "
        "IMPORTANT CAVEAT: no public dataset provides county-level thyroid measures, so "
        "this condition's geography ranking is a PROXY built from the Diagnosis Gap (60%) "
        "and Access to Care (40%) dimensions — where detection systems fail generally, "
        "thyroid detection fails too. Treat as directional until a thyroid-specific "
        "data source (e.g. lab-ordering data) is integrated. The headline figure is OUR computed estimate. It exceeds the published ~2.1M because we apply a flat 4% national prevalence to every county's adult population; no county-level thyroid data exists, so treat this condition as the least precise of the three.",
    "program_mix":
        "Recommended program type for each county, derived from its scoring profile. "
        "Counties with high Medicare Advantage enrollment are best suited to payer partnership programs. "
        "Counties with high social barriers and low access suit community health center partnerships. "
        "Urban counties with high commercial coverage suit employer wellness or digital health programs.",
    "priority_county_list":
        "Ranked list of counties by composite Opportunity Score. "
        "Use this to build market access briefing packs, allocate field resources, "
        "and prioritize payer contract negotiations. "
        "Estimated Pool shows the combined undiagnosed patient count across "
        "Type 2 Diabetes, Hypertension, and Hypothyroidism in that county.",
    "opp_map":
        "Map shading every US county by its composite Opportunity Score from 0 to 100. "
        "Darker navy means stronger opportunity. "
        "Hover over a county to see its score, tier classification, "
        "estimated undiagnosed patient pool, and recommended program type.",
    "top_states":
        "States ranked by average Opportunity Score across all their counties. "
        "A high-scoring state signals a structurally favorable market — high disease burden, "
        "a wide diagnosis gap, and strong payer incentives — making it a priority "
        "for state-level payer negotiations.",
    "by_condition":
        "Average geography risk score by condition across the current county selection. "
        "A high hypertension average with a lower diabetes average, for example, suggests "
        "this market is more favorable for hypertension screening programs than diabetes programs.",
    "avg_ma_penetration":
        "Average share of Medicare-eligible patients enrolled in a Medicare Advantage plan, "
        "across counties in the current view. Medicare Advantage insurers have financial incentives "
        "to fund early screening and care management. "
        "Counties above 40% are strong candidates for payer partnership programs.",
    "avg_medicaid":
        "Average share of the population covered by Medicaid across counties in the current view. "
        "High Medicaid share creates managed care contract incentives — "
        "these counties benefit most from community health center partnerships "
        "tied to Medicaid managed care contracts.",
    "avg_commercial":
        "Average share of the population with employer or individual commercial insurance, "
        "across counties in the current view. High commercial coverage points to "
        "employer wellness and digital health program pathways, where patient engagement "
        "and technology access tend to be stronger.",
    "high_ma_counties":
        "Number of counties where more than 45% of Medicare-eligible patients are enrolled "
        "in a Medicare Advantage plan. These are the highest-priority markets for payer-funded "
        "screening partnerships, as insurers in these counties have the strongest financial "
        "incentive to detect and manage chronic conditions early.",
    "counties_in_plan":
        "Number of counties included in the current investment plan after applying "
        "your state, tier, and condition filters. Adjust the sidebar filters to resize the plan.",
    "lead_program_type":
        "The most frequently recommended program type across counties in the current plan. "
        "Driven by the distribution of Medicare Advantage enrollment, social barriers, "
        "and commercial coverage scores. Use this as the anchor for budget and partnership discussions.",
    "heatmap":
        "Each row is a county ranked by Opportunity Score. Each column is one of the 7 scoring "
        "dimensions. Cell color shows relative strength within that dimension — "
        "navy means top performers, warm orange means weaker performers. "
        "Use this to spot dimension-specific weaknesses in high-scoring counties, "
        "or hidden strengths in counties ranked lower overall.",
    "counties_mapped":
        "Total counties visible on the map after applying the current state and condition filters. "
        "The tool covers all 3,143 US counties and county-equivalents.",
    # ── Scorecard / percentile / confidence ──────────────────────────────────
    "opportunity_percentile":
        "Percentile rank among all 3,144 scored US counties. A county at the 94th percentile "
        "outscores 94% of the country. This is the recommended headline number: the raw "
        "composite intentionally tops out near 64 because no county leads on every dimension.",
    "confidence_grade":
        "Data coverage grade measured BEFORE any statistical imputation. "
        "A = 6-7 of the 7 real sources observed this county directly; B = 4-5; C = fewer than 4 "
        "(score leans on state-median estimates — treat with caution). "
        "Current distribution: 3,123 A · 21 B · 0 C.",
    "risk_score_cond":
        "Condition-specific risk blend for the selected condition, built from the dimension "
        "scores most predictive for that condition (e.g. T2D = 60% Disease Burden + 40% "
        "Diagnosis Gap). Use the composite Opportunity Score for cross-condition planning.",
    # ── ZIP Territory ─────────────────────────────────────────────────────────
    "zip_count":
        "ZCTAs (Census ZIP Code Tabulation Areas) matching the current filters, out of "
        "33,791 scored nationally. ZCTAs approximate USPS ZIP codes.",
    "zip_score":
        "ZIP-level composite opportunity score. Disease Burden and Social Determinants come "
        "from real ZCTA-level CDC PLACES and Census ACS data; the remaining dimensions are "
        "downscaled from county scores via the Census ZCTA-county crosswalk, weighted by "
        "land-area intersection.",
    "zip_pctl":
        "Percentile rank among all 33,791 scored ZCTAs nationally.",
    "zip_conf":
        "ZIP data confidence: A = direct ZCTA-level CDC + Census data AND county-derived "
        "dimensions present; B = one of the two missing; C = mostly proxies.",
    "zip_pool":
        "Estimated undiagnosed adults in this ZIP across T2D, hypertension, and hypothyroidism: "
        "adult population × diagnosed prevalence × published national undiagnosis rates "
        "(T2D 28.5% national, HTN ~20%, hypothyroidism ~50%). ZIP-level figures use the national "
        "T2D rate — no ZCTA age composition is ingested, so they run slightly higher than "
        "the county figures they downscale from. For relative sizing, not clinical use.",
    # ── HCP Targeting ─────────────────────────────────────────────────────────
    "hcp_count":
        "US prescribers scored from the public CMS Medicare Physician & Other Practitioners "
        "file (2023 data): target specialties only, US addresses, Medicare panels of 50+ "
        "beneficiaries. No patient-level data of any kind.",
    "hcp_score":
        "HCP Priority Score (0-100): 40% geography (ZIP opportunity percentile at the practice "
        "address) + 25% panel reach (Medicare panel size percentile) + 20% metabolic burden "
        "(share of panel already diabetic) + 15% specialty fit (primary care highest). "
        "Ranks where a diagnosis-support conversation is most valuable — makes no claim "
        "about individual prescribing quality.",
    "hcp_tier":
        "Priority = top 5% of HCP Priority Scores; Emerging = next 20%; Developing = rest.",
    "hcp_panel":
        "Medicare Part B beneficiaries treated by this prescriber in the data year "
        "(from the public CMS by-Provider file).",
    "hcp_t2d":
        "Share of the prescriber's Medicare panel with diagnosed diabetes (CMS chronic "
        "condition flag). High values indicate a metabolically loaded panel where "
        "undiagnosed comorbidities concentrate.",
    "hcp_why":
        "Auto-generated rationale summarizing which score components drive this "
        "prescriber's rank — written for rep briefing documents.",
    # ── Campaign Measurement ──────────────────────────────────────────────────
    "cm_lift":
        "Difference-in-differences estimate in percentage points: (change in diagnosed "
        "prevalence among campaign counties) minus (change among matched controls) between "
        "the two most recent CDC PLACES releases. Positive = campaign counties diagnosed "
        "faster than their statistical twins. 95% CI from a 2,000-resample bootstrap.",
    "cm_verdict":
        "Significant means the 95% bootstrap confidence interval excludes zero. "
        "A CI straddling zero does NOT prove the campaign failed — it means the effect "
        "is not distinguishable from noise at this sample size and time window.",
    "cm_treated":
        "Campaign counties with both baseline and follow-up outcome data. "
        "Δ diagnosed = their average change in diagnosed prevalence between releases.",
    "cm_controls":
        "Untouched counties matched to your campaign counties by nearest-neighbor on "
        "standardized baseline covariates: prior prevalence, obesity, poverty, income, "
        "uninsured rate, population, rurality. Their Δ estimates the secular trend your "
        "counties would have followed without the campaign.",
    # ── Weight sensitivity ────────────────────────────────────────────────────
    "ws_spearman":
        "Spearman rank correlation between the default-weight ranking and your custom "
        "weighting across all 3,144 counties. 1.0 = identical ordering. Values above "
        "0.95 mean the ranking is driven by the data, not the weight choice.",
    "ws_overlap":
        "Share of the default top-50 counties that remain in the top 50 under your "
        "custom weights.",
    "ws_maxjump":
        "The single largest rank change among the default top-50 counties under your "
        "custom weights.",
    # ── Data Provenance ───────────────────────────────────────────────────────
    "prov_coverage":
        "Rows where this source's key indicator is actually observed (non-null), counted "
        "from the file on disk rather than from documentation claims. Where the raw cache "
        "is present this is true observed coverage. A '≤' prefix means the raw cache is not "
        "shipped in this deployment, so the count comes from the scored output AFTER "
        "median-imputation and is an upper bound — the true observed figure is lower "
        "(e.g. CDC PLACES observes 2,956 of 3,144 counties directly).",
    "prov_status":
        "Live = file present and readable. The QA gates below re-verify content "
        "quality on every dashboard load.",
    "prov_qa":
        "The same fail-loudly data contracts that run at the end of every ingestion "
        "pipeline, re-executed against the exact files powering this session. "
        "A critical failure here means the pipeline would refuse to ship this data.",
}

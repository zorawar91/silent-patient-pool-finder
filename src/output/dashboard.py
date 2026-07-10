from __future__ import annotations
# Silent Patient Pool Finder — IQVIA Market Access Intelligence Platform
# ======================================================================
# 5-view premium dashboard for pharma Market Access and Strategy teams.
# Answers: Where do we invest? Who pays? What program? How fast is it growing?
#
# Run with: streamlit run src/output/dashboard.py

import os
import json
import urllib.request
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SPPF — Market Access Intelligence",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens — IQVIA Blue Palette ───────────────────────────────────────
G_DARK   = "#003087"   # IQVIA deep navy
G_MID    = "#0077C8"   # IQVIA medium blue
G_LIGHT  = "#00A9E0"   # IQVIA light cyan-blue
G_PALE   = "#DEEEF9"   # IQVIA pale blue
WHITE    = "#FFFFFF"
BG       = "#F0F6FC"   # light blue-grey background
BORDER   = "#C8DDEF"   # blue-tinted border
MUTED    = "#5A7A9B"   # blue-grey muted text
DARK     = "#0A1F3C"   # near-black navy
AMBER    = "#F59E0B"
RED      = "#EF4444"
BLUE     = "#0077C8"   # alias
PURPLE   = "#8B5CF6"

# 7-Dimension color map
DIM_COLORS = {
    "disease_burden":       "#E76F51",
    "diagnosis_gap":        "#E63946",
    "access_to_care":       "#457B9D",
    "social_determinants":  "#8338EC",
    "payer_landscape":      "#2A9D8F",
    "commercial_readiness": "#F4A261",
    "trajectory":           "#60A5FA",
}
DIM_LABELS = {
    "disease_burden":       "Disease Burden",
    "diagnosis_gap":        "Diagnosis Gap",
    "access_to_care":       "Access to Care",
    "social_determinants":  "Social Determinants",
    "payer_landscape":      "Payer Landscape",
    "commercial_readiness": "Commercial Readiness",
    "trajectory":           "Trajectory",
}
DIM_ICONS = {
    "disease_burden":       "📊",
    "diagnosis_gap":        "🔍",
    "access_to_care":       "🏥",
    "social_determinants":  "🏘️",
    "payer_landscape":      "💳",
    "commercial_readiness": "🚀",
    "trajectory":           "📈",
}
DIM_SHORT = {
    "disease_burden":       "Burden",
    "diagnosis_gap":        "Dx Gap",
    "access_to_care":       "Access",
    "social_determinants":  "SDoH",
    "payer_landscape":      "Payer",
    "commercial_readiness": "Readiness",
    "trajectory":           "Trend",
}

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
        "Disease Burden 20%, Diagnosis Gap 25%, Access to Care 15%, Social Determinants 15%, "
        "Payer Landscape 10%, Commercial Readiness 10%, Trajectory 5%. "
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
        "Calculated as: county adult population × disease prevalence rate × national undiagnosis rate. "
        "Type 2 Diabetes: 23.1% of cases undiagnosed. "
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
        "Research shows 23.1% of all Type 2 Diabetes cases are undiagnosed. "
        "Priority counties are those with a geography risk score of 55 or above.",
    "condition_htn":
        "Hypertension (high blood pressure) — approximately 34.9 million estimated undiagnosed "
        "or uncontrolled adults nationally. Around 20% of people with hypertension are unaware "
        "of their diagnosis. Hypertension frequently co-occurs with Type 2 Diabetes, "
        "increasing the combined screening opportunity.",
    "condition_hypo":
        "Hypothyroidism — approximately 2.1 million estimated undiagnosed adults nationally; "
        "research suggests around 50% of cases remain undiagnosed. "
        "IMPORTANT CAVEAT: no public dataset provides county-level thyroid measures, so "
        "this condition's geography ranking is a PROXY built from the Diagnosis Gap (60%) "
        "and Access to Care (40%) dimensions — where detection systems fail generally, "
        "thyroid detection fails too. Treat as directional until a thyroid-specific "
        "data source (e.g. lab-ordering data) is integrated.",
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
        "(T2D 23.1%, HTN ~20%, hypothyroidism ~50%). For relative sizing, not clinical use.",
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
        "Real coverage: rows where this source's key indicator is actually observed "
        "(non-null) — counted from the cached file on disk, not from documentation claims.",
    "prov_status":
        "Live = file present and readable. The QA gates below re-verify content "
        "quality on every dashboard load.",
    "prov_qa":
        "The same fail-loudly data contracts that run at the end of every ingestion "
        "pipeline, re-executed against the exact files powering this session. "
        "A critical failure here means the pipeline would refuse to ship this data.",
}


def _iicon(tip: str, pos: str = "position:absolute;top:8px;right:10px;", tip_cls: str = "") -> str:
    """Return a classy circular info badge with a CSS hover tooltip.
    Default positioning: absolute top-right corner of the nearest relative container.
    Pass pos='' to render inline.
    tip_cls='tip-r' → tooltip extends RIGHT (for leftmost column icons).
    tip_cls='tip-l' → tooltip appears LEFT of icon at mid-height (for banner/inline icons).
    """
    safe = tip.replace('"', "&quot;").replace("'", "&#39;")
    style = f' style="{pos}"' if pos else ""
    cls = f"info-tip {tip_cls}".strip() if tip_cls else "info-tip"
    return f'<span class="{cls}" data-tip="{safe}"{style}>i</span>'


def _stplot(fig, **kwargs):
    """Wrapper around st.plotly_chart — applies consistent dark axis colours first."""
    fig.update_layout(font=dict(color=DARK, family="sans-serif", size=11))
    fig.update_xaxes(
        tickfont=dict(color=DARK, size=10),
        title_font=dict(color=MUTED, size=11),
        linecolor="#CACFD6",
        gridcolor="#EAEDF0",
        zerolinecolor="#CACFD6",
    )
    fig.update_yaxes(
        tickfont=dict(color=DARK, size=10),
        title_font=dict(color=MUTED, size=11),
        linecolor="#CACFD6",
        gridcolor="#EAEDF0",
        zerolinecolor="#CACFD6",
    )
    st.plotly_chart(fig, **kwargs)


STATE_ABBREV = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
    "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
    "Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
    "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH",
    "New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC",
    "North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA",
    "Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN",
    "Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA",
    "West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY","District of Columbia":"DC",
}

INTERV_META = {
    "Payer Partnership Program":         {"color": BLUE,   "icon": "💳",
        "desc": "MA plan has Stars incentive — partner to fund screening & care management"},
    "Community Health Center Partnership":{"color": PURPLE,"icon": "🏘️",
        "desc": "High SDoH burden, low access — FQHCs are natural program delivery site"},
    "Employer Wellness Program":         {"color": AMBER,  "icon": "🏢",
        "desc": "High commercial coverage, urban — employer benefit integration"},
    "Digital Health Program":            {"color": G_LIGHT,"icon": "📱",
        "desc": "High broadband, commercial — telehealth screening & remote monitoring"},
    "Pharmacy-Based Screening":          {"color": G_MID,  "icon": "💊",
        "desc": "Broad accessibility — retail pharmacy A1C/BP screening events"},
}

COND_META = {
    "t2d":             {"label": "Type 2 Diabetes",  "color": "#E76F51", "national_pool": 8_700_000},
    "htn":             {"label": "Hypertension",     "color": "#3B82F6", "national_pool": 34_900_000},
    "hyperthyroidism": {"label": "Hypothyroidism",   "color": "#2A9D8F", "national_pool": 2_100_000},
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""<style>
.stApp {{ background:{BG}; }}
.block-container {{ padding:1.5rem 2.2rem; max-width:1600px; }}
[data-testid="stSidebar"] {{ background:{WHITE}; border-right:1px solid {BORDER}; }}

.card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
         padding:0.8rem 1rem; box-shadow:0 1px 2px rgba(0,0,0,.04);
         position:relative; }}
.card-dark {{ background:linear-gradient(135deg,{G_DARK},{G_MID}); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE};
              position:relative; }}
.card-blue {{ background:linear-gradient(135deg,#1E3A5F,#2D6A9F); border:none;
              border-radius:10px; padding:0.8rem 1rem; color:{WHITE};
              position:relative; }}
/* chart-head: lightweight section label above a chart — no white box */
.ch {{ border-left:3px solid {G_LIGHT}; padding:.35rem .75rem; margin-bottom:.4rem;
       background:rgba(0,169,224,.04); border-radius:0 6px 6px 0;
       position:relative; }}
.ch .sec-head {{ margin-bottom:.15rem; }}
.ch .sec-sub  {{ margin-bottom:0; }}

.big-num   {{ font-size:2rem; font-weight:800; line-height:1; color:{DARK}; }}
.big-num-w {{ font-size:2rem; font-weight:800; line-height:1; color:{WHITE}; }}
.label     {{ font-size:.7rem; font-weight:700; color:{MUTED}; margin-bottom:.25rem; }}
.label-w   {{ font-size:.7rem; font-weight:700; color:rgba(255,255,255,.6); margin-bottom:.25rem; }}
.sub       {{ font-size:.74rem; color:{G_LIGHT}; margin-top:.3rem; font-weight:500; }}
.sub-w     {{ font-size:.74rem; color:rgba(255,255,255,.7); margin-top:.3rem; }}
.sub-muted {{ font-size:.74rem; color:{MUTED}; margin-top:.3rem; }}

.sec-head {{ font-size:1rem; font-weight:700; color:{DARK}; margin-bottom:.6rem; }}
.sec-sub  {{ font-size:.76rem; color:{MUTED}; margin-top:-.4rem; margin-bottom:.8rem; }}

.banner {{ background:linear-gradient(135deg,{G_DARK} 0%,{G_MID} 55%,{G_LIGHT} 100%);
           border-radius:16px; padding:1.4rem 2rem; color:{WHITE}; margin-bottom:1.2rem;
           position:relative; }}
.banner-title {{ font-size:1rem; font-weight:700; opacity:.8; margin-bottom:.2rem; }}
.banner-stat  {{ font-size:2.4rem; font-weight:900; line-height:1.1; }}
.banner-note  {{ font-size:.75rem; opacity:.65; margin-top:.25rem; }}

.pill {{ display:inline-block; padding:.18rem .65rem; border-radius:20px;
         font-size:.72rem; font-weight:700; }}

.tbl {{ width:100%; border-collapse:collapse; font-size:.83rem; }}
.tbl th {{ background:{BG}; color:{MUTED}; font-size:.67rem; font-weight:700;
           padding:.55rem .75rem; text-align:left; border-bottom:2px solid {BORDER}; }}
.tbl td {{ padding:.55rem .75rem; border-bottom:1px solid {BORDER}; color:{DARK};
           vertical-align:middle; }}
.tbl tr:last-child td {{ border-bottom:none; }}
.tbl tr:hover td {{ background:{BG}; }}

.sbar-wrap {{ display:flex; align-items:center; gap:.4rem; }}
.sbar-bg   {{ flex:1; height:5px; background:{BORDER}; border-radius:3px; overflow:hidden; }}
.sbar-fill {{ height:100%; border-radius:3px; }}
.snum      {{ font-weight:700; font-size:.79rem; color:{G_DARK}; min-width:2rem; text-align:right; }}

.dim-bar  {{ display:flex; align-items:center; gap:.5rem; margin-bottom:.45rem;
             position:relative; padding-right:1.4rem; }}
.dim-icon {{ font-size:.95rem; width:1.4rem; }}
.dim-name {{ font-size:.73rem; font-weight:600; color:{DARK}; width:7.5rem; flex-shrink:0; }}
.dim-bg   {{ flex:1; height:7px; background:{BORDER}; border-radius:4px; overflow:hidden; }}
.dim-fill {{ height:100%; border-radius:4px; }}
.dim-num  {{ font-size:.73rem; font-weight:700; color:{DARK}; width:2rem; text-align:right; }}

.tier-priority  {{ background:#FEE2E2; color:#991B1B; }}
.tier-emerging  {{ background:#FEF3C7; color:#92400E; }}
.tier-developing{{ background:{G_PALE}; color:{G_DARK}; }}

#MainMenu, footer, header {{ visibility:hidden; }}

/* ── Tab styling — ensure inactive tabs are legible ── */
button[data-baseweb="tab"] {{
    color: {MUTED} !important;
    font-size: .85rem !important;
    font-weight: 600 !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {G_DARK} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {G_DARK} !important;
    font-weight: 700 !important;
}}

/* ── Allow tooltips to escape Streamlit column/block clip zones ── */
[data-testid="stColumn"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMarkdownContainer"],
[data-testid="stElementContainer"] {{
    overflow: visible !important;
}}

/* ── Info icon with CSS tooltip ──────────────────────────── */
.info-tip {{
    display:inline-flex; align-items:center; justify-content:center;
    width:15px; height:15px; border-radius:50%;
    background:linear-gradient(135deg,{G_MID},{G_LIGHT});
    color:#fff; font-size:.6rem; font-style:italic; font-weight:800;
    font-family:Georgia,serif; cursor:help; position:relative;
    vertical-align:middle; margin-left:4px; flex-shrink:0;
    box-shadow:0 1px 5px rgba(0,119,200,.35);
    transition:transform .15s,box-shadow .15s;
    line-height:1; user-select:none;
    z-index:9999;
}}
.info-tip:hover {{
    transform:scale(1.2);
    box-shadow:0 3px 10px rgba(0,119,200,.55);
    z-index:99999;
}}
/* Tooltip bubble — appears BELOW-LEFT of icon so it never hides behind right-edge cards */
.info-tip::after {{
    content:attr(data-tip);
    position:absolute;
    top:calc(100% + 8px);
    right:0; left:auto;
    background:{DARK};
    color:#fff;
    padding:10px 14px;
    border-radius:10px;
    font-size:.72rem; font-weight:400; font-style:normal;
    line-height:1.55; width:240px; white-space:normal;
    z-index:99999; opacity:0; pointer-events:none;
    transition:opacity .18s ease;
    box-shadow:0 8px 28px rgba(0,0,0,.35);
    border:1px solid rgba(255,255,255,.10);
    letter-spacing:.01em; text-align:left;
}}
/* Small caret above the bubble */
.info-tip::before {{
    content:'';
    position:absolute;
    top:calc(100% + 2px);
    right:4px; left:auto;
    border:6px solid transparent;
    border-bottom-color:{DARK};
    z-index:99999; opacity:0; pointer-events:none;
    transition:opacity .18s ease;
}}
/* ── Enable tooltip on hover ── */
.info-tip:hover::after,
.info-tip:hover::before {{ opacity:1; }}

/* tip-r: tooltip extends RIGHT from icon (leftmost column — avoids sidebar overlap) */
.info-tip.tip-r::after {{
    left:0; right:auto; transform:none;
}}
.info-tip.tip-r::before {{
    left:4px; right:auto;
}}

/* tip-l: tooltip appears LEFT of icon at mid-height (banner inline icons) */
.info-tip.tip-l::after {{
    top:50%; bottom:auto;
    right:calc(100% + 12px); left:auto;
    transform:translateY(-50%);
}}
.info-tip.tip-l::before {{
    top:50%; bottom:auto;
    right:calc(100% + 0px); left:auto;
    transform:translateY(-50%);
    border:6px solid transparent;
    border-left-color:{DARK};
    border-bottom-color:transparent;
}}

/* ── Sidebar: always visible, non-collapsible ── */
[data-testid="stSidebar"] {{
    min-width: 17rem !important;
    transform: none !important;
    visibility: visible !important;
    display: block !important;
    margin-left: 0 !important;
}}
[data-testid="stSidebar"][aria-expanded="false"] {{
    min-width: 17rem !important;
    transform: none !important;
    margin-left: 0 !important;
}}
/* Hide ALL sidebar control buttons — collapse arrow, header buttons, etc. */
[data-testid="stSidebar"] button,
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

/* ── Fix: force sidebar text visible regardless of Streamlit theme ── */
[data-testid="stSidebar"] {{ color:{DARK}; }}
[data-testid="stSidebar"] label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] label p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] span {{ color:{DARK}; }}
[data-testid="stSidebar"] .stRadio label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] label p {{ color:{DARK} !important; }}
[data-testid="stSidebar"] .stSelectbox label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] .stSlider label {{ color:{DARK} !important; }}
[data-testid="stSidebar"] hr {{ border-color:{BORDER}; }}
</style>""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
def _get_neon_engine():
    url = None
    try:
        url = st.secrets.get("NEON_DATABASE_URL")
    except Exception:
        pass
    if not url:
        url = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        if "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        return create_engine(url, pool_pre_ping=True)
    except Exception:
        return None


@st.cache_data
def load_data():
    # Always prefer local dimension_scores.parquet — most complete and up-to-date
    # (3,144 counties, 5 real data sources). Neon and legacy paths are fallbacks only.
    dim_path = Path("data/scored/dimension_scores.parquet")
    if dim_path.exists():
        scores      = pd.read_parquet(dim_path)
        scores_long = pd.DataFrame()   # not needed — all signals are columns in scores
        return scores, scores_long

    # Neon fallback (cloud sync)
    engine = _get_neon_engine()
    if engine:
        try:
            scores      = pd.read_sql("SELECT * FROM dimension_scores ORDER BY opportunity_score DESC", engine)
            scores_long = pd.DataFrame()
            return scores, scores_long
        except Exception:
            try:
                scores      = pd.read_sql("SELECT * FROM scores ORDER BY overall_risk_score DESC", engine)
                scores_long = pd.read_sql("SELECT * FROM scores_long", engine)
                return scores, scores_long
            except Exception:
                pass

    # Legacy ML pipeline fallback (259-county synthetic output)
    legacy_path = Path("data/scored/scores.parquet")
    if not legacy_path.exists():
        st.error(
            "No data found. Run `python3 ingest_real_data.py` to generate county scores."
        )
        st.stop()
    scores      = pd.read_parquet(legacy_path)
    scores_long = pd.read_parquet("data/scored/scores_long.parquet")
    return scores, scores_long


@st.cache_data
def load_geojson():
    try:
        url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None


@st.cache_data
def load_zip_data() -> pd.DataFrame:
    """Load ZCTA-level scores produced by ingest_zcta_data.py."""
    path = Path("data/scored/zip_scores.parquet")
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@st.cache_data
def load_hcp_data() -> pd.DataFrame:
    """Load scored HCP targets produced by ingest_hcp_data.py."""
    path = Path("data/scored/hcp_targets.parquet")
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _opp_score(df: pd.DataFrame) -> str:
    """Return column to use as composite opportunity score."""
    return "opportunity_score" if "opportunity_score" in df.columns else "overall_risk_score"


# Per-condition dimension weights — used when {ckey}_risk_score doesn't exist.
# T2D:            disease burden (diabetes prevalence dominant) + diagnosis gap
# HTN:            disease burden (hypertension signal) + social determinants (SES → untreated HTN)
# Hypothyroidism: diagnosis gap (detection failure) + access to care (no TSH screening)
_COND_DIM_WEIGHTS = {
    "t2d":             {"dim_disease_burden": 0.60, "dim_diagnosis_gap": 0.40},
    "htn":             {"dim_disease_burden": 0.50, "dim_social_determinants": 0.50},
    "hyperthyroidism": {"dim_diagnosis_gap":  0.60, "dim_access_to_care": 0.40},
}


def _cond_proxy(df: pd.DataFrame, ckey: str) -> pd.Series:
    """
    Return a per-condition risk score Series.
    Uses {ckey}_risk_score if present (legacy ML pipeline);
    otherwise blends dimension scores per _COND_DIM_WEIGHTS.
    """
    legacy_col = f"{ckey}_risk_score"
    if legacy_col in df.columns:
        return df[legacy_col]
    opp_col = _opp_score(df)
    weights = _COND_DIM_WEIGHTS.get(ckey, {})
    result = None
    for dim, w in weights.items():
        if dim in df.columns:
            chunk = df[dim].clip(0, 100) * w
            result = chunk if result is None else result + chunk
    return result if result is not None else df[opp_col]


def _has_dims(df: pd.DataFrame) -> bool:
    return "dim_disease_burden" in df.columns


def _get_intervention(row: pd.Series) -> str:
    if "recommended_intervention" in row.index and pd.notna(row.get("recommended_intervention")):
        return str(row["recommended_intervention"])
    # Fallback from signals
    signals = {
        "Payer Partnership Program":          row.get("diagnostic_orphan_ratio", 0),
        "Pharmacy-Based Screening":           row.get("otc_proxy_score", 0),
        "Community Health Center Partnership":row.get("geo_burden_index_scaled", 0),
        "Digital Health Program":             row.get("hcp_symptom_rx_ratio", 0),
    }
    return max(signals, key=signals.get)


def _tier_pill(tier) -> str:
    tier = str(tier) if pd.notna(tier) else "Developing"
    cls  = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
    return f'<span class="pill {cls}">{tier}</span>'


def _compute_fallback_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate 7 dimension scores from XGBoost signals when open-data pipeline hasn't run.
    Uses whatever signal columns exist in scores.parquet to produce reasonable proxies."""
    out = df.copy()

    def _norm(s: pd.Series) -> pd.Series:
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        return (100.0 * (s - mn) / (mx - mn)).clip(0, 100)

    base    = _norm(out.get("overall_risk_score",  pd.Series(50.0, index=out.index)))
    otc     = _norm(out["otc_proxy_score"])           if "otc_proxy_score"           in out.columns else base.copy()
    orphan  = _norm(out["diagnostic_orphan_ratio"])   if "diagnostic_orphan_ratio"   in out.columns else base.copy()
    hcp     = _norm(out["hcp_symptom_rx_ratio"])      if "hcp_symptom_rx_ratio"      in out.columns else base.copy()
    geo     = _norm(out["geo_burden_index_scaled"])   if "geo_burden_index_scaled"   in out.columns else base.copy()
    ses     = _norm(out["ses_disadvantage_index"])    if "ses_disadvantage_index"    in out.columns else base.copy()

    out["dim_disease_burden"]       = (0.55 * base   + 0.30 * otc    + 0.15 * geo).clip(0, 100)
    out["dim_diagnosis_gap"]        = (0.45 * orphan + 0.35 * base   + 0.20 * otc).clip(0, 100)
    out["dim_access_to_care"]       = (100 - 0.50 * geo - 0.30 * ses + 0.20 * base).clip(0, 100)
    out["dim_social_determinants"]  = (0.60 * ses    + 0.40 * geo).clip(0, 100)
    out["dim_payer_landscape"]      = (0.50 * otc    + 0.50 * hcp).clip(0, 100)
    out["dim_commercial_readiness"] = (0.45 * hcp    + 0.35 * otc    + 0.20 * (100 - ses)).clip(0, 100)
    out["dim_trajectory"]           = (0.50 * base   + 0.30 * orphan + 0.20 * geo).clip(0, 100)

    weights  = [0.20, 0.25, 0.15, 0.15, 0.10, 0.10, 0.05]
    dim_cols = ["dim_disease_burden", "dim_diagnosis_gap", "dim_access_to_care",
                "dim_social_determinants", "dim_payer_landscape",
                "dim_commercial_readiness", "dim_trajectory"]
    out["opportunity_score"] = sum(w * out[c] for w, c in zip(weights, dim_cols))
    out["opportunity_tier"]  = pd.cut(
        out["opportunity_score"], bins=[0, 40, 55, 100],
        labels=["Developing", "Emerging", "Priority"], include_lowest=True,
    ).astype(str)
    out["recommended_intervention"] = out.apply(
        lambda r: (
            "Payer Partnership Program"          if r.get("dim_payer_landscape", 0)   >= 65 else
            "Community Health Center Partnership" if r.get("dim_social_determinants", 0) >= 60 else
            "Employer Wellness Program"           if r.get("dim_commercial_readiness", 0) >= 60 else
            "Digital Health Program"              if r.get("dim_commercial_readiness", 0) >= 50 else
            "Pharmacy-Based Screening"
        ), axis=1,
    )
    out["priority_rank"] = out["opportunity_score"].rank(ascending=False).astype(int)
    return out


def _ensure_dims(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with dimension columns guaranteed — real if available, fallback otherwise."""
    if _has_dims(df):
        return df
    return _compute_fallback_dims(df)


def _ensure_payer(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Return (df_with_payer_cols, is_synthetic).
    Synthesises realistic county-level payer mix when CMS data hasn't been ingested.
    Rates are seeded from SES signals so high-deprivation counties skew Medicaid-heavy,
    consistent with published CMS county benchmarks."""
    payer_cols = ["ma_penetration_rate", "medicaid_rate", "commercial_rate"]
    if all(c in df.columns for c in payer_cols):
        return df, False

    out = df.copy()
    rng = np.random.default_rng(42)
    n   = len(out)

    # Normalise SES disadvantage if available; else flat mid-point
    if "ses_disadvantage_index" in out.columns:
        s = out["ses_disadvantage_index"]
        ses_n = ((s - s.min()) / (s.max() - s.min() + 1e-6)).values
    else:
        ses_n = np.full(n, 0.5)

    # MA penetration: national avg ~38 %, higher in high-SES (older, Medicare pop)
    out["ma_penetration_rate"] = np.clip(
        0.38 + 0.06 * (1 - ses_n) + 0.08 * rng.standard_normal(n), 0.10, 0.72
    )
    # Medicaid: national avg ~18 %, higher in high-SES-disadvantage counties
    out["medicaid_rate"] = np.clip(
        0.18 + 0.16 * ses_n + 0.04 * rng.standard_normal(n), 0.05, 0.60
    )
    # Commercial: residual, inversely correlated with SES disadvantage
    out["commercial_rate"] = np.clip(
        0.50 - 0.22 * ses_n + 0.04 * rng.standard_normal(n), 0.10, 0.70
    )
    return out, True


def _score_bar(val, color=G_MID) -> str:
    pct = min(float(val or 0), 100)
    return (f'<div class="sbar-wrap"><div class="sbar-bg">'
            f'<div class="sbar-fill" style="width:{pct:.0f}%;background:{color};"></div>'
            f'</div><span class="snum">{pct:.0f}</span></div>')


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(scores: pd.DataFrame):
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:.4rem 0 1.3rem;border-bottom:1px solid {BORDER};margin-bottom:1rem;">
          <div style="font-size:1.55rem;font-weight:900;color:{G_DARK};letter-spacing:-.01em;">🔬 SPPF</div>
          <div style="font-size:.82rem;color:{DARK};font-weight:600;margin-top:3px;line-height:1.4;">
            Silent Patient Pool Finder
          </div>
          <div style="font-size:.72rem;color:{G_LIGHT};font-weight:700;margin-top:1px;">
            IQVIA Market Access Intelligence
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"<div class='label' style='margin-bottom:.4rem;'>View</div>", unsafe_allow_html=True)
        view = st.radio("Navigation", [
            "⚡  Insights & Actions",
            "📊  Market Overview",
            "🔭  7-Dimension Analysis",
            "💡  Investment Planner",
            "🗺️  Geographic Intelligence",
            "💳  Payer Landscape",
            "📍  State Drill-Down",
            "🗂️  ZIP & Territory",
            "🎯  HCP Targeting",
            "📐  Campaign Measurement",
            "📋  Data Provenance",
        ], label_visibility="collapsed")

        st.markdown("---")

        # ── Condition filter ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class='label' style='margin-bottom:.2rem;'>Condition (Risk Score)</div>
        <div style='font-size:.64rem;color:{MUTED};margin-bottom:.4rem;line-height:1.5;'>
          Affects risk score column across all views.<br>
          Opportunity Score is always multi-condition.
        </div>""", unsafe_allow_html=True)

        cond_opts = {"All Conditions": "overall", "🩸 Type 2 Diabetes": "t2d",
                     "❤️ Hypertension": "htn", "🦋 Hypothyroidism": "hyperthyroidism"}
        cond_label = st.selectbox("Condition", list(cond_opts.keys()),
                                  label_visibility="collapsed")
        condition  = cond_opts[cond_label]

        # ── Geography filters ─────────────────────────────────────────────────
        st.markdown(f"<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Geography</div>",
                    unsafe_allow_html=True)

        state_list = sorted(scores["state_name"].unique().tolist())
        state = st.multiselect(
            "States", state_list,
            placeholder="All states (no filter)",
            label_visibility="collapsed",
        )

        # County dropdown only when exactly one state is selected
        county = "All Counties"
        if len(state) == 1:
            state_counties = ["All Counties"] + sorted(
                scores[scores["state_name"] == state[0]]["county_name"].unique().tolist()
            )
            county = st.selectbox("County", state_counties)
        elif len(state) > 1:
            st.caption(f"{len(state)} states selected")

        # ── Display options ───────────────────────────────────────────────────
        st.markdown(f"<div class='label' style='margin-top:.7rem;margin-bottom:.3rem;'>Display</div>",
                    unsafe_allow_html=True)

        top_n = st.slider("Top N counties", 10, 50, 20, step=5)

        tier_opts = ["All Tiers", "Priority", "Emerging", "Developing"]
        tier_filter = st.selectbox("Opportunity Tier", tier_opts)

        st.markdown("---")
        st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};line-height:1.6;">
          ⚠️ Population-level planning tool only.<br>
          Not a clinical diagnostic instrument.<br>
          Data: 7 public sources — see Data Provenance.<br>
          <span style="color:{G_LIGHT};font-weight:600;">v2.0 — 7-Dimension Framework</span>
        </div>""", unsafe_allow_html=True)

    return {
        "view": view.split("  ")[1],
        "condition": condition,
        "cond_label": cond_label,
        "state": state,
        "county": county,
        "top_n": top_n,
        "tier_filter": tier_filter,
    }


# ── View 1: Market Overview ───────────────────────────────────────────────────
def view_market_overview(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str = "overall", cond_label: str = "All Conditions"):
    scores  = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col
    total_pool = int(scores["total_estimated_pool"].sum()) if "total_estimated_pool" in scores.columns else 45_700_000
    priority_n = int((scores[opp_col] >= 55).sum())
    emerging_n = int(((scores[opp_col] >= 40) & (scores[opp_col] < 55)).sum())

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Total Estimated Undiagnosed Patient Pool — United States</div>
      <div class="banner-stat">{total_pool/1_000_000:.1f}M</div>
      <div class="banner-note">
        Across Type 2 Diabetes, Hypertension &amp; Hypothyroidism ·
        Scored via 7-Dimension framework ·
        {priority_n:,} Priority + {emerging_n:,} Emerging counties identified
      </div>
    </div>""", unsafe_allow_html=True)

    # KPI strip
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Scored{_iicon(METRIC_TOOLTIPS["counties_scored"], tip_cls="tip-r")}</div><div class="big-num-w">{len(scores):,}</div><div class="sub-w">US county coverage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority Markets{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div><div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Opportunity Score ≥55</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging Markets{_iicon(METRIC_TOOLTIPS["emerging_tier"])}</div><div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Score 40–55</div></div>', unsafe_allow_html=True)
    avg_opp = scores[opp_col].mean()
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opportunity Score{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}</div><div class="big-num" style="color:{G_DARK};">{avg_opp:.0f}</div><div class="sub-muted">national baseline</div></div>', unsafe_allow_html=True)
    top_state = scores.groupby("state_name")[opp_col].mean().idxmax()
    c5.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">Top State{_iicon(METRIC_TOOLTIPS["top_state"])}</div><div style="font-size:1.3rem;font-weight:800;color:{DARK};">{top_state}</div><div class="sub-muted">by avg opp. score</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Condition cards
    col1, col2, col3 = st.columns(3)
    _cond_tip_keys = {"t2d": "condition_t2d", "htn": "condition_htn", "hyperthyroidism": "condition_hypo"}
    for col, (ckey, meta) in zip([col1, col2, col3], COND_META.items()):
        proxy     = _cond_proxy(scores, ckey)
        high_risk = int((proxy >= 55).sum())
        avg_risk  = proxy.mean()
        peak_risk = f"{proxy.max():.0f}"
        est_pool  = f"{meta['national_pool']/1_000_000:.1f}M"
        col.markdown(f"""
        <div class="card" style="border-top:3px solid {meta['color']};">
          <div class="label">{meta['label']}</div>
          {_iicon(METRIC_TOOLTIPS[_cond_tip_keys[ckey]])}
          <div class="big-num">{est_pool}</div>
          <div class="sub" style="color:{meta['color']};">estimated undiagnosed nationally</div>
          <hr style="border:none;border-top:1px solid {BORDER};margin:.7rem 0;">
          <div style="display:flex;gap:1rem;">
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{high_risk}</div>
              <div style="font-size:.67rem;color:{MUTED};">priority counties</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{avg_risk:.0f}</div>
              <div style="font-size:.67rem;color:{MUTED};">avg risk score</div>
            </div>
            <div>
              <div style="font-size:1.1rem;font-weight:800;color:{DARK};">{peak_risk}</div>
              <div style="font-size:.67rem;color:{MUTED};">peak score</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Opportunity distribution + intervention mix
    col_hist, col_interv = st.columns([1.4, 1])

    with col_hist:
        st.markdown(f'<div class="ch"><div class="sec-head">Opportunity Score Distribution{_iicon(METRIC_TOOLTIPS["opp_score_dist"])}</div>'
                    f'<div class="sec-sub">How the 3,000+ US counties distribute across the 0–100 opportunity scale</div></div>',
                    unsafe_allow_html=True)
        # Manual binning so we can colour each bar by tier
        _vals = scores[opp_col].dropna().values
        _bins = np.arange(0, 101, 2.5)          # 40 bins of width 2.5
        _counts, _edges = np.histogram(_vals, bins=_bins)
        _mids   = (_edges[:-1] + _edges[1:]) / 2
        _colors = []
        for m in _mids:
            if m >= 55:   _colors.append(RED)
            elif m >= 40: _colors.append(AMBER)
            else:         _colors.append(G_LIGHT)
        _labels = [
            f"{'Priority' if m>=55 else 'Emerging' if m>=40 else 'Developing'} · {m:.0f}: {c} counties"
            for m, c in zip(_mids, _counts)
        ]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=_mids, y=_counts,
            width=2.3,
            marker=dict(color=_colors, opacity=0.85, line=dict(width=0)),
            customdata=_labels,
            hovertemplate="%{customdata}<extra></extra>",
        ))
        fig.add_vline(x=40, line=dict(dash="dot", color=AMBER, width=1.5),
                      annotation_text="Emerging", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=AMBER)
        fig.add_vline(x=55, line=dict(dash="dot", color=RED, width=1.5),
                      annotation_text="Priority", annotation_position="top right",
                      annotation_font_size=10, annotation_font_color=RED)
        fig.update_layout(
            xaxis=dict(title="Opportunity Score", range=[0, 100]),
            yaxis=dict(title="Number of Counties"),
            plot_bgcolor="white", paper_bgcolor="white",
            bargap=0.05,
            margin=dict(l=0, r=0, t=20, b=30), height=260,
        )
        _stplot(fig, width="stretch")

    with col_interv:
        st.markdown(f'<div class="ch"><div class="sec-head">Recommended Interventions{_iicon(METRIC_TOOLTIPS["recommended_intervention"])}</div>'
                    f'<div class="sec-sub">What program type does each county need?</div></div>',
                    unsafe_allow_html=True)

        if "recommended_intervention" in scores.columns:
            mix = scores["recommended_intervention"].value_counts()
        else:
            # Fallback: derive from long signals
            long_agg = (
                scores_long.groupby("county_fips")[
                    ["otc_proxy_score","diagnostic_orphan_ratio",
                     "hcp_symptom_rx_ratio","geo_burden_index_scaled"]
                ].mean().reset_index()
            )
            long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
            merged = scores[["county_fips"]].merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
            mix = merged["recommended_intervention"].value_counts()

        colors_pie = [INTERV_META.get(i, {}).get("color", G_MID) for i in mix.index]
        fig2 = go.Figure(go.Pie(
            labels=mix.index, values=mix.values,
            hole=0.55, marker_colors=colors_pie,
            textinfo="percent", textfont_size=11,
        ))
        fig2.update_layout(
            margin=dict(l=0,r=0,t=0,b=0), height=180,
            paper_bgcolor="white", showlegend=False,
        )
        _stplot(fig2, width="stretch")

        for iname, cnt in mix.items():
            meta = INTERV_META.get(str(iname), {"color": G_MID, "icon": "•"})
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.45rem;margin-bottom:.3rem;">
              <div style="width:8px;height:8px;border-radius:50%;background:{meta['color']};flex-shrink:0;"></div>
              <div style="font-size:.73rem;color:{DARK};">{meta['icon']} {iname}</div>
              <div style="margin-left:auto;font-size:.73rem;font-weight:700;color:{DARK};">{cnt}</div>
            </div>""", unsafe_allow_html=True)

    # Patient funnel
    st.markdown(f'<div class="ch"><div class="sec-head">Patient Identification Funnel{_iicon(METRIC_TOOLTIPS["patient_funnel"])}</div>'
                f'<div class="sec-sub">From total adult population to actionable screening opportunity</div></div>',
                unsafe_allow_html=True)

    funnel_labels = ["US Adult Population", "Estimated Prevalence\n(T2D+HTN+Hypo)",
                     "Estimated Undiagnosed", "Observable via Proxy Signals", "Actionable via Programs"]
    funnel_vals   = [258, 84, 45.7, 18, 8]
    fig3 = go.Figure(go.Funnel(
        y=[l.replace("\n"," ") for l in funnel_labels],
        x=funnel_vals,
        textinfo="value+percent initial",
        texttemplate="%{value}M (%{percentInitial})",
        textfont=dict(size=12),
        marker=dict(color=[G_DARK, G_MID, G_LIGHT, "#7EBBEE", "#B3D9F0"]),
    ))
    fig3.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=240,
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
    )
    _stplot(fig3, width="stretch")


# ── View 2: 7-Dimension Analysis ─────────────────────────────────────────────
def view_7d_analysis(scores: pd.DataFrame, state: str, top_n: int,
                      condition: str = "overall", cond_label: str = "All Conditions"):
    using_fallback = not _has_dims(scores)
    scores = _ensure_dims(scores)
    if using_fallback:
        st.info("📊 Showing **estimated** dimension scores (derived from model signals). "
                "Run `python3 ingest_real_data.py` to load full open-data scores "
                "(CDC PLACES, Census ACS, HRSA, CMS).")

    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col
    sort_col  = score_col

    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    top = filtered.nlargest(min(top_n, len(filtered)), sort_col)

    dim_cols = [f"dim_{k}" for k in DIM_LABELS]

    # National dimension averages
    st.markdown(f'<div class="sec-head">National Dimension Profile {_iicon(METRIC_TOOLTIPS["opportunity_score"], pos="")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Average score across all US counties for each of the 7 dimensions</div>', unsafe_allow_html=True)

    col_radar, col_bars = st.columns([1, 1])

    with col_radar:
        st.markdown(f'<div class="ch"><div class="sec-head">National Radar{_iicon(METRIC_TOOLTIPS["national_radar"])}</div>'
                    f'<div class="sec-sub">All counties vs. top opportunity counties</div></div>',
                    unsafe_allow_html=True)
        dim_avgs_national = scores[dim_cols].mean()
        dim_avgs_top      = top[dim_cols].mean()

        labels = [DIM_LABELS[k] for k in DIM_LABELS]
        r_nat  = [dim_avgs_national[f"dim_{k}"] for k in DIM_LABELS]
        r_top  = [dim_avgs_top[f"dim_{k}"] for k in DIM_LABELS]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=r_nat + [r_nat[0]], theta=labels + [labels[0]],
            fill='toself', name='All Counties',
            line=dict(color=BORDER, width=1.5),
            fillcolor=f"rgba(0,169,224,0.1)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=r_top + [r_top[0]], theta=labels + [labels[0]],
            fill='toself', name=f'Top {len(top)}',
            line=dict(color=G_DARK, width=2),
            fillcolor=f"rgba(0,48,135,0.2)",
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9),
                angularaxis=dict(tickfont_size=10),
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center", font_size=11),
            margin=dict(l=30,r=30,t=30,b=50), height=360,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        _stplot(fig, width="stretch")

    with col_bars:
        # Build all bars in ONE markdown call so the card wrapper encloses its content
        bars_html = (
            f'<div class="card"><div class="sec-head">Dimension Breakdown</div>'
            f'<div style="font-size:.67rem;color:{MUTED};margin-bottom:.65rem;margin-top:.15rem;">'
            f'  <span style="border-left:2px solid {MUTED};padding-left:4px;margin-right:.7rem;">national avg</span>'
            f'  <span style="font-weight:600;color:{DARK};">● top {len(top)} score &nbsp; +/− vs national</span>'
            f'</div>'
        )
        for k in DIM_LABELS:
            col_key  = f"dim_{k}"
            nat_val  = dim_avgs_national[col_key]
            top_val  = dim_avgs_top[col_key]
            color    = DIM_COLORS[k]
            icon     = DIM_ICONS[k]
            delta    = top_val - nat_val
            delta_str   = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
            delta_color = "#16a34a" if delta >= 0 else "#dc2626"
            bars_html += f"""
            <div class="dim-bar">
              <div class="dim-icon">{icon}</div>
              <div class="dim-name">{DIM_LABELS[k]}</div>
              <div style="flex:1;display:flex;align-items:center;gap:.35rem;">
                <div class="dim-bg" style="flex:1;position:relative;">
                  <div class="dim-fill" style="width:{top_val:.0f}%;background:{color};"></div>
                  <div style="position:absolute;top:-4px;bottom:-4px;left:{nat_val:.0f}%;width:3px;background:#000000;border-radius:1px;"></div>
                </div>
                <div class="dim-num">{top_val:.0f}</div>
                <div style="font-size:.67rem;width:2.4rem;text-align:right;color:{delta_color};font-weight:700;">{delta_str}</div>
              </div>
              {_iicon(DIM_TOOLTIPS[k], pos="position:absolute;top:50%;right:0;transform:translateY(-50%);")}
            </div>"""
        bars_html += '</div>'
        st.markdown(bars_html, unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # County-level dimension heatmap
    st.markdown(
        f'<div class="ch"><div class="sec-head">Top {len(top)} Counties — Dimension Heatmap{_iicon(METRIC_TOOLTIPS["heatmap"])}</div>'
        f'<div class="sec-sub">Each row = a county · Each column = one of the 7 dimensions · Darker = stronger signal</div></div>',
        unsafe_allow_html=True)

    hm_data = top[["county_name", "state_name"] + dim_cols].head(25).copy()
    hm_data["state_abbr"]   = hm_data["state_name"].map(STATE_ABBREV).fillna(hm_data["state_name"].str[:2].str.upper())
    hm_data["county_label"] = hm_data["county_name"] + ", " + hm_data["state_abbr"]

    hm_raw = hm_data[dim_cols].values.astype(float)

    # Per-column normalise for colour (so every column uses the full warm→navy range)
    hm_norm = hm_raw.copy()
    for j in range(hm_norm.shape[1]):
        col = hm_norm[:, j]
        mn, mx = col.min(), col.max()
        hm_norm[:, j] = 100 * (col - mn) / (mx - mn) if mx > mn else np.full_like(col, 50.0)

    def _cell_color(norm_v: float):
        """Diverging cell bg + text color. norm_v = 0–100 (relative rank in column)."""
        v = max(0.0, min(1.0, norm_v / 100.0))
        if v < 0.5:
            t = v * 2
            r = int(0xF5 + (0xDE - 0xF5) * t)
            g = int(0xC6 + (0xEE - 0xC6) * t)
            b = int(0xA0 + (0xF9 - 0xA0) * t)
            txt = "#7A2A0A" if v < 0.25 else "#5A7A9B"
        else:
            t = (v - 0.5) * 2
            r = int(0xDE + (0x00 - 0xDE) * t)
            g = int(0xEE + (0x30 - 0xEE) * t)
            b = int(0xF9 + (0x87 - 0xF9) * t)
            txt = "#003087" if t < 0.4 else "#FFFFFF"
        return f"#{r:02X}{g:02X}{b:02X}", txt

    # Build HTML table
    dim_keys = list(DIM_LABELS.keys())
    th_style = (f"padding:7px 10px;font-size:.7rem;font-weight:600;color:{MUTED};"
                f"text-align:center;border-bottom:2px solid {BORDER};white-space:nowrap;")
    td_county = (f"padding:6px 10px;font-size:.76rem;color:{DARK};font-weight:500;"
                 f"border-bottom:1px solid {BORDER};white-space:nowrap;")
    html = (
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;font-family:sans-serif;">'
        f'<thead><tr>'
        f'<th style="{th_style}text-align:left;"></th>'
    )
    for k in dim_keys:
        html += (
            f'<th style="{th_style}">'
            f'{DIM_ICONS[k]} {DIM_SHORT[k]} {_iicon(DIM_TOOLTIPS[k], pos="")}'
            f'</th>'
        )
    html += '</tr></thead><tbody>'

    for row_i, row in enumerate(hm_data.itertuples()):
        html += f'<tr><td style="{td_county}">{row.county_label}</td>'
        for col_j, k in enumerate(dim_keys):
            raw_val  = hm_raw[row_i, col_j]
            norm_val = hm_norm[row_i, col_j]
            bg, txt  = _cell_color(norm_val)
            html += (f'<td style="padding:6px 8px;text-align:center;font-size:.78rem;'
                     f'font-weight:700;background:{bg};color:{txt};'
                     f'border-bottom:1px solid {BORDER};">'
                     f'{raw_val:.0f}</td>')
        html += '</tr>'

    html += (
        '</tbody></table></div>'
        f'<div style="font-size:.67rem;color:{MUTED};margin-top:.4rem;">'
        f'  Color = relative rank within shown counties per dimension &nbsp;·&nbsp;'
        f'  Navy = strongest &nbsp;·&nbsp; Warm = weakest'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

    _render_weight_sensitivity(scores)


# ── Weight Sensitivity (robustness the buyer can touch) ──────────────────────
_DEFAULT_WEIGHTS = {
    "disease_burden": 20, "diagnosis_gap": 25, "access_to_care": 15,
    "social_determinants": 15, "payer_landscape": 10,
    "commercial_readiness": 10, "trajectory": 5,
}


def _render_weight_sensitivity(scores: pd.DataFrame):
    """Let an analyst move the 7 dimension weights and watch rankings hold."""
    from src.features.dimension_scorer import recompute_composite, rank_stability

    st.markdown('<div class="sec-head" style="margin-top:1.4rem;">Weight Sensitivity</div>',
                unsafe_allow_html=True)
    st.markdown(f"""<div class="sec-sub">Skeptical of the default weights? Move them.
      Weights are re-normalised to 100%, the composite is recomputed live, and the
      stability metrics show how little the ranking actually depends on any single
      weighting choice.</div>""", unsafe_allow_html=True)

    df = _ensure_dims(scores)
    dim_cols_present = [f"dim_{k}" for k in _DEFAULT_WEIGHTS if f"dim_{k}" in df.columns]
    if len(dim_cols_present) < 7:
        st.info("Dimension columns unavailable — run ingest_real_data.py first.")
        return

    with st.expander("🎛️ Adjust dimension weights", expanded=False):
        cols = st.columns(4)
        weights = {}
        for i, (k, default) in enumerate(_DEFAULT_WEIGHTS.items()):
            with cols[i % 4]:
                weights[k] = st.slider(
                    DIM_LABELS[k], 0, 40, default, step=5,
                    key=f"wsens_{k}",
                )
        total = sum(weights.values())
        if total == 0:
            st.warning("Set at least one weight above zero.")
            return
        norm_str = " · ".join(
            f"{DIM_SHORT[k]} {100 * v / total:.0f}%" for k, v in weights.items() if v
        )
        st.markdown(f"<div style='font-size:.7rem;color:{MUTED};'>Normalised: {norm_str}</div>",
                    unsafe_allow_html=True)

        base = df["opportunity_score"] if "opportunity_score" in df.columns \
            else recompute_composite(df, _DEFAULT_WEIGHTS)
        custom = recompute_composite(df, weights)
        stab = rank_stability(base, custom, top_n=50)

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="card" style="border-top:3px solid {G_DARK};">
          <div class="label">Rank correlation{_iicon(METRIC_TOOLTIPS["ws_spearman"], tip_cls="tip-r")}</div>
          <div class="big-num">{stab['spearman']:.3f}</div>
          <div class="sub-muted">Spearman vs default (1.0 = identical)</div></div>""",
          unsafe_allow_html=True)
        c2.markdown(f"""<div class="card" style="border-top:3px solid {BLUE};">
          <div class="label">Top-50 overlap{_iicon(METRIC_TOOLTIPS["ws_overlap"])}</div>
          <div class="big-num">{stab['top_overlap']:.0%}</div>
          <div class="sub-muted">of default top-50 counties still in top-50</div></div>""",
          unsafe_allow_html=True)
        c3.markdown(f"""<div class="card" style="border-top:3px solid #F4A261;">
          <div class="label">Largest move{_iicon(METRIC_TOOLTIPS["ws_maxjump"])}</div>
          <div class="big-num">{stab['max_jump']}</div>
          <div class="sub-muted">biggest rank change within default top-50</div></div>""",
          unsafe_allow_html=True)

        # Biggest movers table
        r_base = base.rank(ascending=False)
        r_cust = custom.rank(ascending=False)
        movers = pd.DataFrame({
            "county": df["county_name"] + ", " + df["state_name"].map(STATE_ABBREV).fillna(""),
            "default_rank": r_base.astype(int),
            "custom_rank": r_cust.astype(int),
        })
        movers["Δ"] = movers["default_rank"] - movers["custom_rank"]
        movers = movers[movers["default_rank"] <= 100].reindex(
            movers["Δ"].abs().sort_values(ascending=False).index
        ).head(8)
        if not movers.empty and movers["Δ"].abs().max() > 0:
            rows = "".join(
                f"<tr><td>{r['county']}</td>"
                f"<td style='text-align:center;'>{r['default_rank']}</td>"
                f"<td style='text-align:center;'>{r['custom_rank']}</td>"
                f"<td style='text-align:center;color:{G_DARK if r['Δ'] > 0 else '#E63946'};"
                f"font-weight:700;'>{'+' if r['Δ'] > 0 else ''}{r['Δ']}</td></tr>"
                for _, r in movers.iterrows()
            )
            st.markdown(
                f'<div style="margin-top:.6rem;"><table class="tbl"><thead><tr>'
                f'<th>Biggest movers (default top-100)</th><th>Default rank</th>'
                f'<th>Custom rank</th><th>Δ</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:.75rem;color:{MUTED};margin-top:.5rem;'>"
                        f"No rank changes in the top 100 under these weights.</div>",
                        unsafe_allow_html=True)


# ── View 3: Investment Planner ────────────────────────────────────────────────
def view_investment_planner(scores: pd.DataFrame, scores_long: pd.DataFrame,
                             condition: str, state: str, top_n: int, tier_filter: str):
    scores = _ensure_dims(scores)
    opp_col = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col

    # Build intervention column
    if "recommended_intervention" not in scores.columns:
        long_agg = (
            scores_long.groupby("county_fips")[
                ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
            ].mean().reset_index()
        )
        long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
        scored = scores.merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
    else:
        scored = scores.copy()

    # Filters
    if state:
        scored = scored[scored["state_name"].isin(state)]
    if "opportunity_tier" in scored.columns and tier_filter != "All Tiers":
        scored = scored[scored["opportunity_tier"] == tier_filter]

    top = scored.nlargest(min(top_n, len(scored)), opp_col).copy()

    # Summary KPIs
    total_pool = int(top["total_estimated_pool"].sum()) if "total_estimated_pool" in top.columns else 0
    lead_interv = top["recommended_intervention"].value_counts().idxmax() if len(top) > 0 else "—"
    lead_meta   = INTERV_META.get(str(lead_interv), {"color": G_MID, "icon": "•"})

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties in Plan</div>{_iicon(METRIC_TOOLTIPS["counties_in_plan"], tip_cls="tip-r")}<div class="big-num-w">{len(top)}</div><div class="sub-w">filtered selection</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><div class="label">Est. Undiagnosed Pool</div>{_iicon(METRIC_TOOLTIPS["est_pool"])}<div class="big-num">{total_pool:,}</div><div class="sub">within selected counties</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><div class="label">Avg Opportunity Score</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num">{top[opp_col].mean():.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-left:3px solid {lead_meta["color"]};"><div class="label">Lead Program Type</div>{_iicon(METRIC_TOOLTIPS["lead_program_type"])}<div style="font-size:1rem;font-weight:800;color:{DARK};margin:.2rem 0;">{lead_meta["icon"]} {lead_interv}</div><div class="sub-muted">most common</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Intervention breakdown + return estimate
    col_prog, col_roi = st.columns([1, 1])

    with col_prog:
        st.markdown(f'<div class="ch"><div class="sec-head">Program Mix Recommendation{_iicon(METRIC_TOOLTIPS["program_mix"])}</div>'
                    f'<div class="sec-sub">Which program type to deploy in each priority county</div></div>',
                    unsafe_allow_html=True)

        prog_counts = top["recommended_intervention"].value_counts().reset_index()
        prog_counts.columns = ["program", "counties"]
        prog_counts["color"] = prog_counts["program"].map(lambda x: INTERV_META.get(x, {}).get("color", G_MID))

        fig = go.Figure(go.Bar(
            x=prog_counts["counties"],
            y=prog_counts["program"],
            orientation="h",
            marker_color=prog_counts["color"],
            text=prog_counts["counties"],
            textposition="outside",
            textfont=dict(size=12),
        ))
        fig.update_layout(
            xaxis=dict(title="Number of Counties", showgrid=True, gridcolor=BORDER),
            yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=40, t=10, b=30), height=280,
        )
        _stplot(fig, width="stretch")

        for _, prow in prog_counts.iterrows():
            meta = INTERV_META.get(str(prow["program"]), {"color":G_MID,"icon":"•","desc":""})
            st.markdown(f"""
            <div style="border-left:3px solid {meta['color']};padding-left:.7rem;margin-bottom:.6rem;">
              <div style="font-size:.75rem;font-weight:700;color:{DARK};">{meta['icon']} {prow['program']}</div>
              <div style="font-size:.7rem;color:{MUTED};margin-top:2px;">{meta['desc']}</div>
            </div>""", unsafe_allow_html=True)

    with col_roi:
        st.markdown(f'<div class="ch"><div class="sec-head">Estimated Screening Yield{_iicon(METRIC_TOOLTIPS["screening_yield"])}</div>'
                    f'<div class="sec-sub">Patients newly diagnosed per 1,000 screened by program type (literature benchmarks)</div></div>',
                    unsafe_allow_html=True)

        roi_data = pd.DataFrame({
            "Program": ["Payer Partnership Program", "Community Health Center Partnership",
                         "Pharmacy-Based Screening", "Employer Wellness Program", "Digital Health Program"],
            "Yield per 1k": [142, 98, 76, 54, 38],
            "Cost per dx ($)": [280, 350, 220, 480, 390],
            "Scalability": [4, 3, 5, 3, 4],
        })
        roi_data["color"] = roi_data["Program"].map(lambda x: INTERV_META.get(x, {}).get("color", G_MID))

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Yield / 1k screened",
            x=roi_data["Program"],
            y=roi_data["Yield per 1k"],
            marker_color=roi_data["color"],
            yaxis="y1",
        ))
        fig2.add_trace(go.Scatter(
            name="Cost per dx ($)",
            x=roi_data["Program"],
            y=roi_data["Cost per dx ($)"],
            mode="lines+markers",
            line=dict(color=DARK, width=2, dash="dot"),
            marker=dict(size=8, color=DARK),
            yaxis="y2",
        ))
        fig2.update_layout(
            xaxis=dict(tickangle=-20, tickfont_size=10),
            yaxis=dict(title="Yield per 1,000", showgrid=True, gridcolor=BORDER),
            yaxis2=dict(title="Cost per dx ($)", overlaying="y", side="right",
                        showgrid=False, range=[0, 700]),
            legend=dict(orientation="h", y=1.1, font_size=10),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=40, t=20, b=80), height=280,
        )
        _stplot(fig2, width="stretch")
        st.markdown('<div style="font-size:.7rem;color:{MUTED};margin-top:.5rem;">⚠️ Yield figures based on published screening program literature. Actual results vary by market.</div>'.format(MUTED=MUTED), unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # Priority county table
    st.markdown(f'<div class="ch"><div class="sec-head">Priority County Investment List{_iicon(METRIC_TOOLTIPS["priority_county_list"])}</div>'
                f'<div class="sec-sub">Ranked by composite opportunity score. Use this to brief market access teams and payer strategy leads.</div></div>',
                unsafe_allow_html=True)

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        opp_val  = row[opp_col]
        risk_val = row.get(score_col, opp_val)
        pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get('total_estimated_pool')) else "—"
        rural    = "🌾" if row.get("is_rural") else "🏙️"
        interv   = str(row.get("recommended_intervention", "—"))
        imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•"})
        tier_val = row.get("opportunity_tier", "—")

        # Dimension mini-bars (if available)
        dim_mini = ""
        if _has_dims(top):
            dim_mini = '<div style="display:flex;gap:2px;margin-top:3px;">'
            for k in DIM_LABELS:
                v = row.get(f"dim_{k}", 50)
                c = DIM_COLORS[k]
                h = max(3, int((v / 100) * 16))
                dim_mini += f'<div title="{DIM_LABELS[k]}: {v:.0f}" style="width:5px;height:{h}px;background:{c};border-radius:1px;align-self:flex-end;"></div>'
            dim_mini += '</div>'

        rows_html += f"""<tr>
          <td style="font-weight:700;color:{MUTED};">{i+1}</td>
          <td>
            <div style="font-weight:700;color:{DARK};">{row['county_name']}</div>
            <div style="font-size:.7rem;color:{MUTED};">{rural} {row['state_name']}</div>
            {dim_mini}
          </td>
          <td style="font-size:.78rem;color:{MUTED};">{int(row['population']):,}</td>
          <td>{_score_bar(opp_val, G_DARK)}</td>
          <td>{_score_bar(risk_val, COND_META.get(condition,{}).get('color',G_MID))}</td>
          <td>{_tier_pill(tier_val)}</td>
          <td><span style="font-size:.75rem;">{imeta['icon']} {interv}</span></td>
          <td style="font-weight:700;color:{G_DARK};font-size:.82rem;">{pool_str}</td>
        </tr>"""

    st.markdown(f"""<table class="tbl">
      <thead><tr>
        <th>#</th><th>County</th><th>Population</th>
        <th>Opp. Score</th><th>Risk Score</th><th>Tier</th>
        <th>Program</th><th>Est. Pool</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    export_cols = [c for c in ["county_name","state_name","population",opp_col,
                                "opportunity_percentile","confidence_grade",
                                score_col,"opportunity_tier","recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.download_button("⬇️  Export investment list (CSV)", csv,
                       file_name=f"sppf_investment_plan.csv", mime="text/csv")


# ── View 4: Geographic Intelligence ──────────────────────────────────────────
def view_geographic(scores: pd.DataFrame, scores_long: pd.DataFrame,
                    condition: str, state: str, geojson):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col
    filtered  = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    cond_label = "All Conditions" if condition == "overall" else COND_META[condition]["label"]
    priority_n = int((filtered[opp_col] >= 55).sum())
    emerging_n = int(((filtered[opp_col] >= 40) & (filtered[opp_col] < 55)).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Mapped</div>{_iicon(METRIC_TOOLTIPS["counties_mapped"], tip_cls="tip-r")}<div class="big-num-w">{len(filtered):,}</div><div class="sub-w">{filtered["state_name"].nunique()} states</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥55</div>{_iicon(METRIC_TOOLTIPS["priority_tier"])}<div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–55</div>{_iicon(METRIC_TOOLTIPS["emerging_tier"])}<div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card"><div class="label">Avg Score ({cond_label})</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num">{filtered[score_col].mean():.0f}</div><div class="sub-muted">this view</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_map, col_right = st.columns([2.8, 1])

    with col_map:
        st.markdown(f'<div class="card"><div class="sec-head">Opportunity Map — {cond_label}{_iicon(METRIC_TOOLTIPS["opp_map"])}</div><div class="sec-sub">Shading = composite opportunity score. Hover for county profile.</div>', unsafe_allow_html=True)

        # Build intervention mapping
        if "recommended_intervention" not in filtered.columns:
            long_agg = (
                scores_long.groupby("county_fips")[
                    ["otc_proxy_score","diagnostic_orphan_ratio","hcp_symptom_rx_ratio","geo_burden_index_scaled"]
                ].mean().reset_index()
            )
            long_agg["recommended_intervention"] = long_agg.apply(_get_intervention, axis=1)
            map_data = filtered.merge(long_agg[["county_fips","recommended_intervention"]], on="county_fips", how="left")
        else:
            map_data = filtered.copy()

        if geojson:
            hover_extra = {opp_col: ":.0f", score_col: ":.0f",
                           "recommended_intervention": True, "county_fips": False}
            if "opportunity_tier" in map_data.columns:
                hover_extra["opportunity_tier"] = True

            # Color scale anchored to actual score range (~25–65).
            # Matches tier thresholds: grey = Developing, amber = Emerging, red = Priority.
            fig = px.choropleth(
                map_data,
                geojson=geojson,
                locations="county_fips",
                color=opp_col,
                color_continuous_scale=[
                    [0.00, "#EEF2F7"],   # Developing low end
                    [0.50, "#F4A261"],   # Emerging (score ≈ 45)
                    [0.85, "#E63946"],   # Priority threshold (score ≈ 55)
                    [1.00, "#8B0000"],   # Top priority counties
                ],
                range_color=(25, 65),
                scope="usa",
                hover_name="county_name",
                hover_data={"state_name": True, "population": ":,", **hover_extra},
                labels={opp_col: "Opp. Score", score_col: "Risk Score",
                        "recommended_intervention": "Program", "opportunity_tier": "Tier"},
            )
            fig.update_layout(
                margin=dict(r=0,t=0,l=0,b=0),
                paper_bgcolor="white",
                geo=dict(bgcolor="white", lakecolor="#EBF5FB", landcolor=BG),
                coloraxis_colorbar=dict(
                    title="Opp.<br>Score",
                    tickvals=[25, 40, 55, 65],
                    ticktext=["25<br><i>Developing</i>", "40<br><i>Emerging</i>",
                              "55<br><i>Priority</i>", "65"],
                    thickness=12, len=0.65, bgcolor="white",
                    bordercolor=BORDER, borderwidth=1,
                ),
                height=480,
            )
            _stplot(fig, width="stretch")
        else:
            state_avg = (filtered.groupby("state_name")[opp_col].mean()
                         .reset_index().sort_values(opp_col, ascending=False).head(20))
            fig = px.bar(state_avg, x="state_name", y=opp_col,
                         color=opp_col, color_continuous_scale=[[0,G_PALE],[1,G_DARK]],
                         labels={"state_name":"","opportunity_score":"Avg Opportunity Score"})
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                               margin=dict(l=0,r=0,t=10,b=0), height=480, coloraxis_showscale=False)
            _stplot(fig, width="stretch")

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        # Top states
        st.markdown(f'<div class="card"><div class="sec-head">Top States{_iicon(METRIC_TOOLTIPS["top_states"])}</div>', unsafe_allow_html=True)
        state_avgs = (filtered.groupby("state_name")[opp_col].mean()
                      .reset_index().sort_values(opp_col, ascending=False).head(10))
        for _, srow in state_avgs.iterrows():
            pct = min(float(srow[opp_col]), 100)
            color = RED if pct >= 55 else (AMBER if pct >= 40 else G_LIGHT)
            st.markdown(f"""
            <div style="margin-bottom:.55rem;">
              <div style="display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:2px;">
                <span style="font-weight:600;color:{DARK};">{srow['state_name']}</span>
                <span style="color:{color};font-weight:700;">{pct:.0f}</span>
              </div>
              <div style="height:5px;background:{BORDER};border-radius:3px;">
                <div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Condition breakdown
        st.markdown(f'<div class="card"><div class="sec-head">By Condition{_iicon(METRIC_TOOLTIPS["by_condition"])}</div>', unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            proxy_s = _cond_proxy(filtered, ckey)
            avg = proxy_s.mean()
            hi  = (proxy_s >= 55).sum()
            st.markdown(f"""
            <div style="margin-bottom:.6rem;">
              <div style="display:flex;justify-content:space-between;font-size:.76rem;margin-bottom:2px;">
                <span style="font-weight:600;color:{DARK};">{cmeta['label']}</span>
                <span style="font-size:.7rem;color:{MUTED};">{avg:.0f} avg</span>
              </div>
              <div style="height:5px;background:{BORDER};border-radius:3px;">
                <div style="width:{min(avg,100):.0f}%;height:100%;background:{cmeta['color']};border-radius:3px;"></div>
              </div>
              <div style="font-size:.67rem;color:{MUTED};margin-top:2px;">{hi} high-risk</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── View 5: Payer Landscape ───────────────────────────────────────────────────
def view_payer_landscape(scores: pd.DataFrame, state: str, top_n: int):
    scores   = _ensure_dims(scores)
    scores, payer_synthetic = _ensure_payer(scores)
    opp_col  = _opp_score(scores)
    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    st.markdown('<div class="sec-head">Payer Landscape Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Understand who pays in each market — critical for screening program partnership decisions</div>', unsafe_allow_html=True)

    if payer_synthetic:
        st.info("📊 Showing **estimated** payer mix (SES-calibrated synthetic data). "
                "Run `python3 ingest_real_data.py` to load real CMS county-level payer data.")
    else:
        st.caption("Medicare Advantage penetration: real CMS county data (3,108 of 3,128 "
                   "counties). Medicaid, commercial, and dual-eligible shares: modeled "
                   "estimates from SES signals and coverage arithmetic — directionally "
                   "sound planning figures, not sourced rates.")

    # KPI strip
    ma_avg  = filtered["ma_penetration_rate"].mean() * 100
    med_avg = filtered["medicaid_rate"].mean() * 100
    com_avg = filtered["commercial_rate"].mean() * 100
    ma_high = int((filtered["ma_penetration_rate"] >= 0.45).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="card-blue"><div class="label-w">Avg MA Penetration</div>{_iicon(METRIC_TOOLTIPS["avg_ma_penetration"])}<div class="big-num-w">{ma_avg:.0f}%</div><div class="sub-w">Medicare Advantage</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {PURPLE};"><div class="label">Avg Medicaid Rate</div>{_iicon(METRIC_TOOLTIPS["avg_medicaid"])}<div class="big-num">{med_avg:.0f}%</div><div class="sub-muted">of population</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Avg Commercial Rate</div>{_iicon(METRIC_TOOLTIPS["avg_commercial"])}<div class="big-num">{com_avg:.0f}%</div><div class="sub-muted">employer/individual</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {BLUE};"><div class="label">High MA Counties</div>{_iicon(METRIC_TOOLTIPS["high_ma_counties"])}<div class="big-num">{ma_high}</div><div class="sub" style="color:{BLUE};">≥45% MA penetration</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    col_scatter, col_mix = st.columns([1.5, 1])

    with col_scatter:
        st.markdown(f'<div class="ch"><div class="sec-head">Payer Mix vs. Opportunity Score{_iicon(METRIC_TOOLTIPS["payer_mix"])}</div>'
                    f'<div class="sec-sub">Each dot = a county. Size = population. Color = opportunity score.</div></div>',
                    unsafe_allow_html=True)

        plot_data = filtered.nlargest(min(500, len(filtered)), opp_col).copy()
        plot_data["ma_pct"]  = plot_data["ma_penetration_rate"] * 100
        plot_data["med_pct"] = plot_data["medicaid_rate"] * 100

        fig = px.scatter(
            plot_data,
            x="ma_pct", y="med_pct",
            color=opp_col,
            color_continuous_scale=[[0,G_PALE],[0.35,G_LIGHT],[0.7,G_MID],[1,G_DARK]],
            size="population",
            size_max=20,
            hover_name="county_name",
            hover_data={"state_name": True, opp_col: ":.0f", "ma_pct":":.0f", "med_pct":":.0f", "population":":,"},
            labels={"ma_pct":"Medicare Advantage %","med_pct":"Medicaid %", opp_col:"Opp. Score"},
        )
        # Quadrant lines
        fig.add_hline(y=med_avg, line=dict(dash="dot", color=MUTED, width=1))
        fig.add_vline(x=ma_avg,  line=dict(dash="dot", color=MUTED, width=1))

        # Quadrant labels
        fig.add_annotation(x=ma_avg+15, y=med_avg+8, text="High MA + High Medicaid<br>(Dual incentive)", showarrow=False, font=dict(size=9, color=DARK))
        fig.add_annotation(x=ma_avg+15, y=med_avg-8, text="High MA + Commercial<br>(Employer + payer)", showarrow=False, font=dict(size=9, color=DARK))

        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0,r=0,t=10,b=30), height=380,
            coloraxis_colorbar=dict(title="Opp.", thickness=10, len=0.6,
                                    bgcolor="white", bordercolor=BORDER, borderwidth=1),
        )
        _stplot(fig, width="stretch")

    with col_mix:
        st.markdown(f'<div class="ch"><div class="sec-head">National Payer Mix{_iicon(METRIC_TOOLTIPS["payer_mix"])}</div>'
                    f'<div class="sec-sub">Average payer distribution across all counties in view</div></div>',
                    unsafe_allow_html=True)

        fig2 = go.Figure(go.Pie(
            labels=["Medicare Advantage", "Medicaid", "Commercial", "Other/Uninsured"],
            values=[ma_avg, med_avg, com_avg, max(0, 100-ma_avg-med_avg-com_avg)],
            hole=0.55,
            marker=dict(colors=[BLUE, PURPLE, AMBER, BORDER]),
            textinfo="percent+label",
            textfont=dict(size=11),
        ))
        fig2.update_layout(
            margin=dict(l=0,r=0,t=0,b=0), height=260,
            paper_bgcolor="white", showlegend=False,
        )
        _stplot(fig2, width="stretch")

        st.markdown(f"""
        <div style="margin-top:.5rem;">
          <div style="font-size:.78rem;font-weight:700;color:{DARK};margin-bottom:.5rem;">Program Fit by Payer Mix</div>
          <div style="border-left:3px solid {BLUE};padding-left:.7rem;margin-bottom:.5rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">💳 MA Penetration ≥40%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ Payer Partnership Program (Stars bonus)</div>
          </div>
          <div style="border-left:3px solid {PURPLE};padding-left:.7rem;margin-bottom:.5rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">🏘️ Medicaid Rate ≥25%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ FQHC / Community Health Partnership</div>
          </div>
          <div style="border-left:3px solid {AMBER};padding-left:.7rem;">
            <div style="font-size:.73rem;font-weight:700;color:{DARK};">🏢 Commercial Rate ≥40%</div>
            <div style="font-size:.7rem;color:{MUTED};">→ Employer Wellness or Digital Health</div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Top MA penetration counties
        st.markdown('<div class="ch"><div class="sec-head">Top MA Counties</div></div>', unsafe_allow_html=True)
        top_ma = (filtered.nlargest(min(top_n//2, 8), "ma_penetration_rate")
                  [["county_name","state_name","ma_penetration_rate",opp_col]].copy())
        for _, mrow in top_ma.iterrows():
            ma_val  = mrow["ma_penetration_rate"] * 100
            opp_val = mrow[opp_col]
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        margin-bottom:.4rem;padding-bottom:.4rem;border-bottom:1px solid {BORDER};">
              <div>
                <div style="font-size:.78rem;font-weight:600;color:{DARK};">{mrow['county_name']}</div>
                <div style="font-size:.68rem;color:{MUTED};">{mrow['state_name']}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:.83rem;font-weight:700;color:{BLUE};">{ma_val:.0f}% MA</div>
                <div style="font-size:.68rem;color:{MUTED};">Opp: {opp_val:.0f}</div>
              </div>
            </div>""", unsafe_allow_html=True)


# ── County Scorecard Helper ───────────────────────────────────────────────────
def _render_county_scorecard(row: pd.Series, opp_col: str,
                              score_col: str, cond_label: str):
    """Full-width deep-dive card for one county."""
    opp_val  = row[opp_col]
    risk_val = row.get(score_col, opp_val)
    pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get("total_estimated_pool")) else "—"
    interv   = str(row.get("recommended_intervention", "Pharmacy-Based Screening"))
    imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•", "desc": ""})

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">County Deep Dive</div>
      <div class="banner-stat">{row['county_name']}, {row.get('state_name','')}</div>
      <div class="banner-note">
        {'🌾 Rural' if row.get('is_rural') else '🏙️ Urban / Suburban'} &nbsp;·&nbsp;
        Population: {row['population']:,} &nbsp;·&nbsp; Est. Undiagnosed Pool: {pool_str}
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    pctl  = row.get("opportunity_percentile")
    pctl_str = f"{pctl:.0f}th percentile of 3,144 counties" if pd.notna(pctl) else "out of 100"
    conf  = str(row.get("confidence_grade", "")) or ""
    conf_str = f" · data confidence {conf}" if conf in ("A", "B", "C") else ""
    c1.markdown(f"""<div class="card-dark">
      <div class="label-w">Opportunity Score{_iicon(METRIC_TOOLTIPS["opportunity_percentile"], tip_cls="tip-r")}</div>
      <div class="big-num-w">{opp_val:.0f}</div>
      <div class="sub-w">{pctl_str}{conf_str}</div></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="card" style="border-top:3px solid {DIM_COLORS['diagnosis_gap']};">
      <div class="label">Risk Score ({cond_label}){_iicon(METRIC_TOOLTIPS["risk_score_cond"])}</div>
      <div class="big-num">{risk_val:.0f}</div>
      <div class="sub-muted">out of 100</div></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="card" style="border-top:3px solid {imeta['color']};">
      <div class="label">Recommended Program{_iicon(METRIC_TOOLTIPS["recommended_intervention"])}</div>
      <div style="font-size:.9rem;font-weight:700;color:{imeta['color']};margin-top:.3rem;">
        {imeta['icon']} {interv}</div></div>""", unsafe_allow_html=True)
    c4.markdown(f"""<div class="card">
      <div class="label">Opportunity Tier{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div>
      <div style="margin-top:.4rem;">{_tier_pill(row.get('opportunity_tier','Developing'))}</div>
      <div class="sub-muted" style="margin-top:.4rem;">Est. pool: {pool_str}
        {_iicon(METRIC_TOOLTIPS["est_pool"], pos="")}</div></div>""",
      unsafe_allow_html=True)

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    # 7-Dimension bars (2 columns)
    dim_cols_keys = list(DIM_LABELS.keys())
    if any(f"dim_{k}" in row.index for k in dim_cols_keys):
        col_a, col_b = st.columns(2)
        mid = 4
        left, right = dim_cols_keys[:mid], dim_cols_keys[mid:]

        def _dim_section(keys, container):
            with container:
                st.markdown('<div class="ch"><div class="sec-head">7-Dimension Profile</div></div>',
                            unsafe_allow_html=True)
                for k in keys:
                    val   = float(row.get(f"dim_{k}", 0))
                    color = DIM_COLORS[k]
                    st.markdown(f"""
                    <div class="dim-bar">
                      <div class="dim-icon">{DIM_ICONS[k]}</div>
                      <div class="dim-name">{DIM_LABELS[k]}</div>
                      <div class="dim-bg" style="flex:1;">
                        <div class="dim-fill" style="width:{val:.0f}%;background:{color};"></div>
                      </div>
                      <div class="dim-num">{val:.0f}</div>
                    </div>""", unsafe_allow_html=True)

        _dim_section(left, col_a)
        _dim_section(right, col_b)

    # Program rationale
    st.markdown(f"""
    <div style="margin-top:.5rem;padding:.8rem 1.1rem;background:{G_PALE};border-radius:10px;
                border-left:4px solid {imeta['color']};">
      <div style="font-size:.78rem;font-weight:700;color:{DARK};">
        {imeta['icon']} Why {interv}?</div>
      <div style="font-size:.73rem;color:{MUTED};margin-top:.3rem;">{imeta.get('desc','')}</div>
    </div>""", unsafe_allow_html=True)


# ── View 6: State Drill-Down ──────────────────────────────────────────────────
def view_state_drilldown(scores: pd.DataFrame, scores_long: pd.DataFrame,
                          condition: str, cond_label: str,
                          state: str, county: str, top_n: int):
    scores    = _ensure_dims(scores)
    opp_col   = _opp_score(scores)
    score_col = "overall_risk_score" if condition == "overall" else f"{condition}_risk_score"
    if score_col not in scores.columns:
        score_col = opp_col

    # ── Prompt if no state selected ───────────────────────────────────────────
    if not state:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:3rem 2rem;margin-top:1rem;">
          <div style="font-size:3.5rem;">📍</div>
          <div class="sec-head" style="margin-top:1rem;font-size:1.1rem;">Select a State to Begin</div>
          <div class="sec-sub" style="max-width:420px;margin:0 auto;">
            Choose a state from the <strong>Geography</strong> filter in the sidebar.
            A county dropdown will appear automatically.
          </div>
        </div>""", unsafe_allow_html=True)

        # Teaser: top 5 states
        state_ranks = (scores.groupby("state_name")[opp_col].mean()
                       .sort_values(ascending=False).head(5).reset_index())
        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="ch"><div class="sec-head">Top 5 States by Avg Opportunity Score</div>'
                    '<div class="sec-sub">Select one in the sidebar to drill in</div></div>',
                    unsafe_allow_html=True)
        for i, r in state_ranks.iterrows():
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;">
              <div style="font-weight:800;color:{MUTED};font-size:.8rem;width:1.2rem;">{i+1}</div>
              <div style="flex:1;">
                <div style="font-size:.83rem;font-weight:600;color:{DARK};">{r['state_name']}</div>
                <div style="height:5px;background:{BORDER};border-radius:3px;margin-top:3px;">
                  <div style="width:{r[opp_col]:.0f}%;height:100%;background:{G_MID};border-radius:3px;"></div>
                </div>
              </div>
              <div style="font-size:.83rem;font-weight:700;color:{G_DARK};min-width:2.5rem;text-align:right;">
                {r[opp_col]:.0f}</div>
            </div>""", unsafe_allow_html=True)
        return

    # ── Multiple states selected — drill-down requires exactly one ────────────
    if len(state) > 1:
        st.info(
            f"State Drill-Down shows a single state at a time. "
            f"Narrow your selection to one state in the sidebar ({len(state)} currently selected).",
            icon="📍",
        )
        return

    # ── Exactly one state selected ────────────────────────────────────────────
    state_df = scores[scores["state_name"] == state[0]].copy()

    # ── County deep-dive (if county selected) ─────────────────────────────────
    if county and county != "All Counties":
        county_rows = state_df[state_df["county_name"] == county]
        if not county_rows.empty:
            _render_county_scorecard(county_rows.iloc[0], opp_col, score_col, cond_label)
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── State KPI banner ──────────────────────────────────────────────────────
    total_pool = int(state_df["total_estimated_pool"].sum()) if "total_estimated_pool" in state_df.columns else 0
    priority_n = int((state_df[opp_col] >= 55).sum())
    emerging_n = int(((state_df[opp_col] >= 40) & (state_df[opp_col] < 55)).sum())
    avg_score  = state_df[opp_col].mean()
    top_prog   = (state_df["recommended_intervention"].value_counts().idxmax()
                  if "recommended_intervention" in state_df.columns else "—")

    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">State Intelligence — {state[0]}</div>
      <div class="banner-stat">{len(state_df)} Counties</div>
      <div class="banner-note">
        Est. pool: {total_pool:,} &nbsp;·&nbsp;
        {priority_n} Priority · {emerging_n} Emerging &nbsp;·&nbsp;
        Avg score: {avg_score:.0f} &nbsp;·&nbsp; Lead program: {top_prog}
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="card-dark"><div class="label-w">Total Counties</div>{_iicon(METRIC_TOOLTIPS["counties_scored"], tip_cls="tip-r")}<div class="big-num-w">{len(state_df)}</div><div class="sub-w">{state}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ≥55</div>{_iicon(METRIC_TOOLTIPS["priority_tier"])}<div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">Act now</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging 40–55</div>{_iicon(METRIC_TOOLTIPS["emerging_tier"])}<div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="card" style="border-top:3px solid {G_LIGHT};"><div class="label">Avg Opp. Score</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num" style="color:{G_DARK};">{avg_score:.0f}</div><div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="card"><div class="label">Est. Pool</div><div style="font-size:1.2rem;font-weight:800;color:{DARK};">{total_pool:,}</div><div class="sub-muted">undiagnosed</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # ── County ranking chart + right-side panels ──────────────────────────────
    col_chart, col_right = st.columns([2.5, 1])

    with col_chart:
        st.markdown(f'<div class="ch"><div class="sec-head">County Rankings — {state}</div>'
                    f'<div class="sec-sub">Sorted by Opportunity Score · Risk column: {cond_label} · Dotted lines = tier thresholds</div></div>',
                    unsafe_allow_html=True)

        ranked = state_df.sort_values(opp_col, ascending=True).copy()
        tier_colors = {"Priority": RED, "Emerging": AMBER, "Developing": G_LIGHT}
        bar_colors  = [tier_colors.get(str(r.get("opportunity_tier", "Developing")), G_MID)
                       for _, r in ranked.iterrows()]

        fig = go.Figure(go.Bar(
            x=ranked[opp_col], y=ranked["county_name"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=ranked[opp_col].apply(lambda v: f"{v:.0f}"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Opp. Score: %{x:.0f}<extra></extra>",
        ))
        fig.add_vline(x=40, line_dash="dot", line_color=AMBER, line_width=1.5,
                      annotation_text="Emerging", annotation_position="top")
        fig.add_vline(x=55, line_dash="dot", line_color=RED,   line_width=1.5,
                      annotation_text="Priority", annotation_position="top")
        fig.update_layout(
            margin=dict(l=0, r=50, t=30, b=20),
            height=max(350, len(ranked) * 26 + 80),
            paper_bgcolor="white", plot_bgcolor="white",
            xaxis=dict(range=[0, 115], showgrid=True, gridcolor=BORDER,
                       title="Opportunity Score"),
            yaxis=dict(tickfont=dict(size=10)),
        )
        _stplot(fig, width="stretch")

    with col_right:
        # Tier donut
        st.markdown('<div class="ch"><div class="sec-head">Tier Split</div></div>',
                    unsafe_allow_html=True)
        if "opportunity_tier" in state_df.columns:
            tc = state_df["opportunity_tier"].astype(str).value_counts()
            fig2 = go.Figure(go.Pie(
                labels=tc.index, values=tc.values, hole=0.55,
                marker_colors=[{"Priority": RED, "Emerging": AMBER, "Developing": G_LIGHT}.get(t, G_MID)
                               for t in tc.index],
                textinfo="percent+label", textfont_size=10,
            ))
            fig2.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=190,
                               paper_bgcolor="white", showlegend=False)
            _stplot(fig2, width="stretch")

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Program mix
        st.markdown('<div class="ch"><div class="sec-head">Program Mix</div></div>',
                    unsafe_allow_html=True)
        if "recommended_intervention" in state_df.columns:
            prog_counts = state_df["recommended_intervention"].value_counts()
            for prog, cnt in prog_counts.items():
                meta = INTERV_META.get(str(prog), {"color": G_MID, "icon": "•"})
                pct  = 100 * cnt / len(state_df)
                st.markdown(f"""
                <div style="margin-bottom:.5rem;">
                  <div style="display:flex;justify-content:space-between;font-size:.72rem;
                              color:{DARK};">
                    <span>{meta['icon']} {prog}</span>
                    <span style="font-weight:700;">{cnt}</span>
                  </div>
                  <div style="height:4px;background:{BORDER};border-radius:2px;margin-top:2px;">
                    <div style="width:{pct:.0f}%;height:100%;background:{meta['color']};
                                border-radius:2px;"></div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # Condition breakdown
        st.markdown('<div class="ch"><div class="sec-head">By Condition</div></div>',
                    unsafe_allow_html=True)
        for ckey, cmeta in COND_META.items():
            col_name = f"{ckey}_risk_score"
            if col_name not in state_df.columns:
                continue
            avg = state_df[col_name].mean()
            hi  = (state_df[col_name] >= 70).sum()
            selected = "★ " if condition == ckey else ""
            st.markdown(f"""
            <div style="margin-bottom:.5rem;">
              <div style="display:flex;justify-content:space-between;font-size:.73rem;">
                <span style="font-weight:{'700' if condition==ckey else '500'};
                             color:{cmeta['color']};">{selected}{cmeta['label']}</span>
                <span style="color:{MUTED};">{avg:.0f}</span>
              </div>
              <div style="height:4px;background:{BORDER};border-radius:2px;margin-top:2px;">
                <div style="width:{min(avg,100):.0f}%;height:100%;background:{cmeta['color']};
                            border-radius:2px;"></div>
              </div>
              <div style="font-size:.67rem;color:{MUTED};">{hi} high-risk</div>
            </div>""", unsafe_allow_html=True)

    # ── Full county table ─────────────────────────────────────────────────────
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ch"><div class="sec-head">All Counties — {state} ({len(state_df)} total)</div>'
                f'<div class="sec-sub">Sorted by Opportunity Score · Select a county in the sidebar for full deep-dive</div></div>',
                unsafe_allow_html=True)

    top = state_df.sort_values(opp_col, ascending=False).copy()
    dim_cols_list = [f"dim_{k}" for k in DIM_LABELS]

    rows_html = ""
    for i, (_, row) in enumerate(top.iterrows()):
        opp_val  = row[opp_col]
        risk_val = row.get(score_col, opp_val)
        pool_str = f"{int(row['total_estimated_pool']):,}" if pd.notna(row.get("total_estimated_pool")) else "—"
        rural    = "🌾" if row.get("is_rural") else "🏙️"
        interv   = str(row.get("recommended_intervention", "—"))
        imeta    = INTERV_META.get(interv, {"color": G_MID, "icon": "•"})
        highlight = f"background:#EBF5FF;" if (county and county == row["county_name"]) else ""

        mini_bars = ""
        if all(c in row.index for c in dim_cols_list):
            for k in DIM_LABELS:
                v = float(row.get(f"dim_{k}", 0))
                mini_bars += (f'<div style="height:3px;width:{v:.0f}%;'
                              f'background:{DIM_COLORS[k]};border-radius:1px;margin-bottom:1px;"></div>')

        rows_html += f"""
        <tr style="{highlight}">
          <td style="font-weight:700;color:{MUTED};font-size:.75rem;">{i+1}</td>
          <td>
            <div style="font-weight:600;font-size:.82rem;color:{DARK};">{rural} {row['county_name']}</div>
            <div style="width:55px;margin-top:3px;">{mini_bars}</div>
          </td>
          <td style="font-size:.8rem;">{int(row['population']):,}</td>
          <td>{_score_bar(opp_val, G_MID)}</td>
          <td>{_score_bar(risk_val, DIM_COLORS.get('diagnosis_gap', G_MID))}</td>
          <td>{_tier_pill(row.get('opportunity_tier','Developing'))}</td>
          <td><span style="color:{imeta['color']};font-size:.75rem;font-weight:600;">
            {imeta['icon']} {interv}</span></td>
          <td style="font-size:.8rem;">{pool_str}</td>
        </tr>"""

    st.markdown(f"""
    <table class="tbl">
      <thead><tr>
        <th>#</th><th>County</th><th>Population</th>
        <th>Opp. Score</th><th>Risk ({cond_label})</th>
        <th>Tier</th><th>Program</th><th>Est. Pool</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)

    export_cols = [c for c in ["county_name", "population", opp_col,
                                "opportunity_percentile", "confidence_grade",
                                score_col, "opportunity_tier", "recommended_intervention",
                                "total_estimated_pool"] if c in top.columns]
    csv = top[export_cols].to_csv(index=False)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    st.download_button(
        f"⬇ Download {state} county data (CSV)", csv,
        f"sppf_{state.lower().replace(' ', '_')}.csv", "text/csv",
    )


# ── View 7: ZIP & Territory ───────────────────────────────────────────────────
def view_zip_territory(zip_scores: pd.DataFrame, county_scores: pd.DataFrame,
                       state: list = None, condition: str = "overall"):
    """ZIP/ZCTA-level opportunity scoring and territory builder."""

    # ── Empty state ───────────────────────────────────────────────────────────
    if zip_scores.empty:
        st.markdown(f"""
        <div class="card" style="padding:2rem;text-align:center;">
          <div style="font-size:2.5rem;margin-bottom:1rem;">🗂️</div>
          <div class="sec-head">ZIP & Territory data not yet generated</div>
          <div class="sec-sub" style="max-width:560px;margin:0 auto 1.2rem;">
            Run the ZCTA ingestion pipeline to score ~33,000 US ZIP codes using
            CDC PLACES, Census ACS, and county-level dimension signals.
          </div>
          <code style="background:{BG};padding:.5rem 1rem;border-radius:6px;font-size:.82rem;">
            python3 ingest_zcta_data.py
          </code>
          <div style="font-size:.72rem;color:{MUTED};margin-top:1rem;">
            Runtime: ~3 minutes on first run. Requires dimension_scores.parquet from ingest_real_data.py.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    df = zip_scores.copy()
    score_col = "zip_opportunity_score"

    # Ensure score col exists
    if score_col not in df.columns:
        st.error("zip_scores.parquet is missing zip_opportunity_score — re-run ingest_zcta_data.py")
        return

    # State filter
    if state and "state_name" in df.columns:
        df = df[df["state_name"].isin(state)]

    n_total   = len(df)
    n_pri     = int((df[score_col] >= 55).sum())
    n_eme     = int(((df[score_col] >= 40) & (df[score_col] < 55)).sum())
    total_pool = int(df["zip_total_pool"].sum()) if "zip_total_pool" in df.columns else 0
    avg_score  = df[score_col].mean()

    # Banner
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">ZIP Code Territory Intelligence — {", ".join(state[:2]) + (f" +{len(state)-2} more" if len(state) > 2 else "") if state else "United States"}</div>
      <div class="banner-stat">{n_total:,} ZIPs {_iicon(METRIC_TOOLTIPS["zip_count"], pos="", tip_cls="tip-l")}</div>
      <div class="banner-note">
        {n_pri:,} Priority · {n_eme:,} Emerging · Avg score {avg_score:.0f} {_iicon(METRIC_TOOLTIPS["zip_score"], pos="", tip_cls="tip-l")} ·
        {total_pool/1_000_000:.1f}M estimated undiagnosed patients {_iicon(METRIC_TOOLTIPS["zip_pool"], pos="", tip_cls="tip-l")}
      </div>
    </div>""", unsafe_allow_html=True)

    # Sub-tabs
    tab_map, tab_builder, tab_rank = st.tabs(["🌎 ZIP Map", "Territory Builder", "ZIP Rankings"])

    with tab_map:
        _render_zip_map(df, score_col)

    with tab_builder:
        _render_territory_builder(df, score_col, county_scores)

    with tab_rank:
        _render_zip_rankings(df, score_col)


def _render_zip_map(df: pd.DataFrame, score_col: str):
    """Scatter-geo map of ZCTA centroids colored by opportunity score."""
    has_geo = "lat" in df.columns and "lon" in df.columns and df["lat"].notna().sum() > 500

    if not has_geo:
        st.info("📍 Centroid data not available — run ingest_zcta_data.py to add lat/lon to ZIP scores.")
        # Fallback: show county choropleth note
        st.markdown(f"""<div class="card">
          <div class="sec-sub">The ZIP map uses Census Gazetteer centroids (lat/lon per ZCTA).
          These are downloaded automatically by <code>ingest_zcta_data.py</code>.
          Once available, the map shows ~33,000 ZIP centroids sized by estimated patient pool
          and colored by Opportunity Score.</div></div>""", unsafe_allow_html=True)
        return

    plot_df = df.dropna(subset=["lat", "lon", score_col]).copy()

    # Tier color mapping
    tier_colors = {
        "Priority":   RED,
        "Emerging":   AMBER,
        "Developing": G_LIGHT,
    }
    plot_df["tier"] = "Developing"
    if "zip_opportunity_tier" in plot_df.columns:
        plot_df["tier"] = plot_df["zip_opportunity_tier"].fillna("Developing")

    plot_df["color_val"] = plot_df[score_col]
    plot_df["pool_disp"] = (
        plot_df["zip_total_pool"].fillna(0).astype(int)
        if "zip_total_pool" in plot_df.columns else 0
    )
    plot_df["hover"] = (
        "ZIP: " + plot_df["zcta5"].astype(str) +
        ("<br>State: " + plot_df["state_name"] if "state_name" in plot_df.columns else "") +
        "<br>Score: " + plot_df[score_col].round(1).astype(str) +
        "<br>Tier: " + plot_df["tier"] +
        "<br>Est. Pool: " + plot_df["pool_disp"].apply(lambda x: f"{x:,}")
    )

    # scatter_geo handles 33k points fine — no subsampling needed

    fig = px.scatter_geo(
        plot_df,
        lat="lat", lon="lon",
        color=score_col,
        color_continuous_scale=[[0, G_LIGHT], [0.4, G_MID], [0.55, AMBER], [1, RED]],
        range_color=[0, 100],
        size="pool_disp" if "zip_total_pool" in plot_df.columns else None,
        size_max=10,
        scope="usa",
        projection="albers usa",
        hover_name="zcta5",
        custom_data=["hover"],
        opacity=0.7,
        labels={score_col: "Opportunity Score"},
    )
    fig.update_traces(
        hovertemplate="%{customdata[0]}<extra></extra>",
        marker=dict(line=dict(width=0)),
    )
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Opp. Score",
            tickvals=[0, 40, 55, 100],
            ticktext=["0", "40<br>Emerging", "55<br>Priority", "100"],
            len=0.6,
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=500,
        paper_bgcolor="white",
        geo=dict(
            showland=True, landcolor="#F8F9FA",
            showlakes=True, lakecolor="#EAF4FB",
            showcoastlines=True, coastlinecolor=BORDER,
            showsubunits=True, subunitcolor=BORDER,
            bgcolor="white",
        ),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(f"""<div style="font-size:.71rem;color:{MUTED};margin-top:-.5rem;">
      {len(plot_df):,} ZCTAs shown · sized by estimated undiagnosed pool · colored by Opportunity Score
    </div>""", unsafe_allow_html=True)


def _render_territory_builder(df: pd.DataFrame, score_col: str, county_scores: pd.DataFrame):
    """Paste ZIP codes → aggregate scorecard for that territory."""
    st.markdown(f'<div class="sec-head">Territory Builder</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sec-sub">Paste ZIP codes to define a field territory and instantly get its aggregate opportunity scorecard.</div>', unsafe_allow_html=True)

    zip_input = st.text_area(
        "Paste ZIP codes (comma, space, or newline separated):",
        height=100,
        placeholder="e.g.  90210, 10001, 60601\nor one per line: 90210\n10001\n60601",
        key="territory_zip_input",
    )

    if not zip_input.strip():
        st.markdown(f"""<div class="card" style="text-align:center;padding:2rem;color:{MUTED};">
          Enter ZIP codes above to see the territory scorecard.
        </div>""", unsafe_allow_html=True)
        return

    # Parse ZIPs
    import re
    raw_zips = re.split(r"[\s,;]+", zip_input.strip())
    zips_entered = [z.strip().zfill(5) for z in raw_zips if z.strip().isdigit() and len(z.strip()) <= 5]

    if not zips_entered:
        st.warning("No valid 5-digit ZIP codes found. Please enter numeric ZIPs.")
        return

    territory = df[df["zcta5"].isin(zips_entered)].copy()
    n_found   = len(territory)
    n_missing = len(zips_entered) - n_found

    if n_found == 0:
        st.warning(f"None of the {len(zips_entered)} entered ZIPs are in the scored dataset. "
                   "Verify the ZIPs are valid US ZCTAs.")
        return

    if n_missing > 0:
        st.caption(f"ℹ️ {n_found} ZIPs matched · {n_missing} not found in dataset "
                   "(may be P.O. Box ZIPs or outside ZCTA coverage)")

    # ── KPI strip ─────────────────────────────────────────────────────────────
    avg_score  = territory[score_col].mean()
    pri_count  = int((territory[score_col] >= 55).sum())
    eme_count  = int(((territory[score_col] >= 40) & (territory[score_col] < 55)).sum())
    total_pool = int(territory["zip_total_pool"].sum()) if "zip_total_pool" in territory.columns else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f'<div class="card-dark"><div class="label-w">Territory ZIPs{_iicon(METRIC_TOOLTIPS["zip_count"], tip_cls="tip-r")}</div>'
                f'<div class="big-num-w">{n_found}</div>'
                f'<div class="sub-w">matched in database</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="card" style="border-top:3px solid {G_MID};"><div class="label">Avg Opportunity{_iicon(METRIC_TOOLTIPS["zip_score"])}</div>'
                f'<div class="big-num" style="color:{G_DARK};">{avg_score:.0f}</div>'
                f'<div class="sub-muted">out of 100</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority ZIPs{_iicon(METRIC_TOOLTIPS["priority_tier"])}</div>'
                f'<div class="big-num" style="color:{RED};">{pri_count}</div>'
                f'<div class="sub" style="color:{RED};">Score ≥55</div></div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Est. Undiagnosed Pool{_iicon(METRIC_TOOLTIPS["zip_pool"])}</div>'
                f'<div class="big-num" style="color:{AMBER};">{total_pool:,}</div>'
                f'<div class="sub" style="color:{AMBER};">T2D + HTN + Hypo</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # ── Dimension radar + intervention breakdown ───────────────────────────────
    dim_col_map = {
        "zip_dim_disease_burden":       "Burden",
        "zip_dim_diagnosis_gap":        "Gap",
        "zip_dim_access_to_care":       "Access",
        "zip_dim_social_determinants":  "SDoH",
        "zip_dim_payer_landscape":      "Payer",
        "zip_dim_commercial_readiness": "Readiness",
        "zip_dim_trajectory":           "Trend",
    }
    avail_dims = {k: v for k, v in dim_col_map.items() if k in territory.columns}

    col_radar, col_interv = st.columns([1, 1])

    if avail_dims:
        with col_radar:
            st.markdown(f'<div class="ch"><div class="sec-head">Territory Dimension Profile</div>'
                        f'<div class="sec-sub">Average across {n_found} ZIPs vs. US national</div></div>',
                        unsafe_allow_html=True)
            terr_avgs = [territory[col].mean() for col in avail_dims]
            natl_avgs = [df[col].mean() for col in avail_dims]
            labels    = list(avail_dims.values())
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatterpolar(
                r=natl_avgs + [natl_avgs[0]], theta=labels + [labels[0]],
                fill="toself", name="US National",
                line=dict(color=BORDER, width=1.5),
                fillcolor="rgba(0,169,224,0.08)",
            ))
            fig_r.add_trace(go.Scatterpolar(
                r=terr_avgs + [terr_avgs[0]], theta=labels + [labels[0]],
                fill="toself", name="Your Territory",
                line=dict(color=G_DARK, width=2.5),
                fillcolor="rgba(0,48,135,0.2)",
            ))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9)),
                showlegend=True, legend=dict(font_size=10),
                margin=dict(l=20, r=20, t=30, b=20), height=260,
                paper_bgcolor="white",
            )
            _stplot(fig_r, width="stretch")

    if "zip_recommended_intervention" in territory.columns:
        with col_interv:
            st.markdown(f'<div class="ch"><div class="sec-head">Recommended Programs</div>'
                        f'<div class="sec-sub">Distribution across territory ZIPs</div></div>',
                        unsafe_allow_html=True)
            interv_counts = territory["zip_recommended_intervention"].value_counts()
            for prog, cnt in interv_counts.items():
                meta  = INTERV_META.get(prog, {"color": G_LIGHT, "icon": "•"})
                pct   = cnt / n_found * 100
                st.markdown(
                    f'<div class="dim-bar">'
                    f'<span class="dim-icon">{meta["icon"]}</span>'
                    f'<span class="dim-name" style="width:12rem;">{prog[:28]}</span>'
                    f'<div class="dim-bg"><div class="dim-fill" style="width:{pct:.0f}%;background:{meta["color"]};"></div></div>'
                    f'<span class="dim-num">{cnt}</span>'
                    f'</div>', unsafe_allow_html=True
                )

    # ── Per-ZIP table ─────────────────────────────────────────────────────────
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="sec-head">ZIP-Level Detail</div>', unsafe_allow_html=True)

    display_cols = ["zcta5", score_col, "zip_opportunity_tier"]
    for c in ["state_name", "zip_total_pool", "zip_recommended_intervention"]:
        if c in territory.columns:
            display_cols.append(c)

    tbl = territory[display_cols].sort_values(score_col, ascending=False).copy()
    tbl = tbl.rename(columns={
        "zcta5": "ZIP", score_col: "Score", "zip_opportunity_tier": "Tier",
        "state_name": "State", "zip_total_pool": "Est. Pool",
        "zip_recommended_intervention": "Program",
    })

    # Render as HTML table
    rows_html = ""
    for _, row in tbl.iterrows():
        tier = str(row.get("Tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        score_val = row.get("Score", 0)
        pool_val  = f"{int(row['Est. Pool']):,}" if "Est. Pool" in row and pd.notna(row.get("Est. Pool")) else "—"
        prog_val  = str(row.get("Program", ""))[:30] if "Program" in row else "—"
        state_val = str(row.get("State", "")) if "State" in row else "—"
        rows_html += (
            f"<tr>"
            f"<td><strong>{row['ZIP']}</strong></td>"
            f"<td>{state_val}</td>"
            f"<td>{_score_bar(score_val, G_DARK if score_val >= 55 else G_MID)}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td>{pool_val}</td>"
            f"<td style='font-size:.75rem;'>{prog_val}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>ZIP</th><th>State</th><th>Score</th><th>Tier</th><th>Est. Pool</th><th>Program</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    # CSV download
    csv_bytes = tbl.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download Territory CSV",
        data=csv_bytes,
        file_name="territory_zips.csv",
        mime="text/csv",
        key="terr_dl",
    )


def _render_zip_rankings(df: pd.DataFrame, score_col: str):
    """Top ZIP rankings table with CSV export."""
    st.markdown(f'<div class="sec-head">ZIP Code Rankings</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sec-sub">Top opportunity ZCTAs by composite score</div>', unsafe_allow_html=True)

    col_top_n, col_tier = st.columns([1, 1])
    with col_top_n:
        top_n = st.slider("Show top N ZIPs", 20, 200, 50, step=10, key="zip_rank_n")
    with col_tier:
        tier_f = st.selectbox("Tier filter", ["All Tiers", "Priority", "Emerging", "Developing"],
                              key="zip_rank_tier")

    ranked = df.copy()
    if tier_f != "All Tiers" and "zip_opportunity_tier" in ranked.columns:
        ranked = ranked[ranked["zip_opportunity_tier"] == tier_f]

    ranked = ranked.nlargest(top_n, score_col)

    if ranked.empty:
        st.info("No ZIPs match the current filters.")
        return

    display_cols = ["zcta5", score_col]
    for c in ["zip_opportunity_percentile", "zip_confidence_grade",
              "zip_opportunity_tier", "state_name", "zip_total_pool",
              "diabetes_prevalence_pct", "poverty_rate", "zip_recommended_intervention"]:
        if c in ranked.columns:
            display_cols.append(c)

    tbl = ranked[display_cols].copy().reset_index(drop=True)
    tbl.insert(0, "Rank", range(1, len(tbl) + 1))

    rows_html = ""
    for _, row in tbl.iterrows():
        tier = str(row.get("zip_opportunity_tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        score_val  = row[score_col]
        pool_val   = f"{int(row['zip_total_pool']):,}" if "zip_total_pool" in row and pd.notna(row.get("zip_total_pool")) else "—"
        diab_val   = f"{row['diabetes_prevalence_pct']*100:.1f}%" if "diabetes_prevalence_pct" in row and pd.notna(row.get("diabetes_prevalence_pct")) else "—"
        pov_val    = f"{row['poverty_rate']*100:.1f}%" if "poverty_rate" in row and pd.notna(row.get("poverty_rate")) else "—"
        state_val  = str(row.get("state_name", ""))[:2] if "state_name" in row else "—"
        prog_val   = str(row.get("zip_recommended_intervention", ""))[:22] if "zip_recommended_intervention" in row else "—"
        pctl_val   = f"{row['zip_opportunity_percentile']:.0f}" if pd.notna(row.get("zip_opportunity_percentile")) else "—"
        grade_val  = str(row.get("zip_confidence_grade", "")) or "—"
        grade_col  = {"A": G_DARK, "B": "#F4A261", "C": "#E63946"}.get(grade_val, MUTED)
        rows_html += (
            f"<tr>"
            f"<td style='color:{MUTED};font-size:.7rem;'>{int(row['Rank'])}</td>"
            f"<td><strong>{row['zcta5']}</strong></td>"
            f"<td>{state_val}</td>"
            f"<td>{_score_bar(score_val, G_DARK if score_val >= 55 else G_MID)}</td>"
            f"<td style='color:{MUTED};font-size:.73rem;'>{pctl_val}</td>"
            f"<td style='color:{grade_col};font-weight:700;'>{grade_val}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td>{pool_val}</td>"
            f"<td>{diab_val}</td>"
            f"<td>{pov_val}</td>"
            f"<td style='font-size:.73rem;'>{prog_val}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>#</th><th>ZIP</th><th>St.</th>'
        f'<th>Score {_iicon(METRIC_TOOLTIPS["zip_score"], pos="")}</th>'
        f'<th>Pctl {_iicon(METRIC_TOOLTIPS["zip_pctl"], pos="")}</th>'
        f'<th>Conf {_iicon(METRIC_TOOLTIPS["zip_conf"], pos="")}</th>'
        f'<th>Tier {_iicon(METRIC_TOOLTIPS["priority_tier"], pos="")}</th>'
        f'<th>Est. Pool {_iicon(METRIC_TOOLTIPS["zip_pool"], pos="")}</th>'
        f'<th>T2D%</th><th>Poverty%</th>'
        f'<th>Program {_iicon(METRIC_TOOLTIPS["recommended_intervention"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    csv_dl = tbl.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download Rankings CSV",
        data=csv_dl,
        file_name="zip_rankings.csv",
        mime="text/csv",
        key="zip_rank_dl",
    )


# ── View 9: HCP Targeting ─────────────────────────────────────────────────────
def view_hcp_targeting(hcp: pd.DataFrame, state: list = None):
    """Prescriber-level activation list: who to call, where, and why."""

    # ── Empty state ───────────────────────────────────────────────────────────
    if hcp.empty:
        st.markdown(f"""
        <div class="card" style="padding:2rem;text-align:center;">
          <div style="font-size:2.5rem;margin-bottom:1rem;">🎯</div>
          <div class="sec-head">HCP target list not yet generated</div>
          <div class="sec-sub" style="max-width:560px;margin:0 auto 1.2rem;">
            Run the HCP ingestion pipeline to score prescribers from the public
            CMS Medicare Physician &amp; Other Practitioners file against your
            geography opportunity scores.
          </div>
          <code style="background:{BG};padding:.5rem 1rem;border-radius:6px;font-size:.82rem;">
            python3 ingest_hcp_data.py
          </code>
          <div style="font-size:.72rem;color:{MUTED};margin-top:1rem;">
            Requires zip_scores.parquet and dimension_scores.parquet.
            100% public aggregate data — no PHI.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    df = hcp.copy()
    if state and "state" in df.columns:
        abbrs = [STATE_ABBREV.get(s, s) for s in state]
        df = df[df["state"].isin(abbrs + list(state))]

    n_pri = int((df["hcp_tier"] == "Priority").sum())
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">HCP Targeting — Diagnosis-Support Detailing List</div>
      <div class="banner-stat">{len(df):,} prescribers {_iicon(METRIC_TOOLTIPS["hcp_count"], pos="", tip_cls="tip-l")}</div>
      <div class="banner-note">
        {n_pri:,} Priority · scored on geography opportunity ({W_LBL_GEO}),
        panel reach, metabolic burden &amp; specialty fit · public CMS data, no PHI
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        top_n = st.slider("Show top N prescribers", 25, 500, 100, step=25, key="hcp_n")
    with c2:
        spec_opts = ["All Specialties"] + sorted(df["specialty"].dropna().unique().tolist())
        spec_f = st.selectbox("Specialty", spec_opts, key="hcp_spec")
    with c3:
        tier_f = st.selectbox("Tier", ["All Tiers", "Priority", "Emerging", "Developing"],
                              key="hcp_tier_f")

    if spec_f != "All Specialties":
        df = df[df["specialty"] == spec_f]
    if tier_f != "All Tiers":
        df = df[df["hcp_tier"] == tier_f]
    ranked = df.nlargest(top_n, "hcp_priority_score").reset_index(drop=True)

    if ranked.empty:
        st.info("No prescribers match the current filters.")
        return

    rows_html = ""
    for i, row in ranked.iterrows():
        tier = str(row.get("hcp_tier", "Developing"))
        tier_cls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        sv = row["hcp_priority_score"]
        diab = (f"{row['panel_diabetes_pct']:.0f}%"
                if pd.notna(row.get("panel_diabetes_pct")) else "—")
        rows_html += (
            f"<tr>"
            f"<td style='color:{MUTED};font-size:.7rem;'>{i + 1}</td>"
            f"<td><strong>{row.get('name','')}</strong><br>"
            f"<span style='font-size:.68rem;color:{MUTED};'>NPI {row['npi']}</span></td>"
            f"<td style='font-size:.75rem;'>{row.get('specialty','')}</td>"
            f"<td style='font-size:.75rem;'>{row.get('city','')}, {row.get('state','')} {row.get('zip5','')}</td>"
            f"<td>{_score_bar(sv, G_DARK if sv >= 70 else G_MID)}</td>"
            f"<td><span class='pill {tier_cls}'>{tier}</span></td>"
            f"<td style='text-align:right;'>{int(row['panel_size']):,}</td>"
            f"<td style='text-align:right;'>{diab}</td>"
            f"<td style='font-size:.7rem;color:{MUTED};max-width:230px;'>{row.get('rationale','')}</td>"
            f"</tr>"
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>#</th><th>Prescriber</th><th>Specialty</th><th>Location</th>'
        f'<th>Priority Score {_iicon(METRIC_TOOLTIPS["hcp_score"], pos="")}</th>'
        f'<th>Tier {_iicon(METRIC_TOOLTIPS["hcp_tier"], pos="")}</th>'
        f'<th>Panel {_iicon(METRIC_TOOLTIPS["hcp_panel"], pos="")}</th>'
        f'<th>T2D% {_iicon(METRIC_TOOLTIPS["hcp_t2d"], pos="")}</th>'
        f'<th>Why {_iicon(METRIC_TOOLTIPS["hcp_why"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    export_cols = [c for c in ["npi", "name", "specialty", "city", "state", "zip5",
                                "hcp_priority_score", "hcp_tier", "geo_percentile",
                                "panel_size", "panel_diabetes_pct", "rationale"]
                   if c in ranked.columns]
    st.download_button(
        "⬇️  Export call list (CRM-ready CSV)",
        ranked[export_cols].to_csv(index=False),
        file_name="sppf_hcp_call_list.csv", mime="text/csv", key="hcp_dl",
    )
    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:.6rem;">
      ⚠️ Prescriber data is public CMS Medicare aggregate reporting. Scores rank
      geographies and panel profiles for diagnosis-support programs — they make
      no claim about individual prescribing behaviour or patient outcomes.
    </div>""", unsafe_allow_html=True)


W_LBL_GEO = "40%"


# ── View 11: Campaign Measurement ─────────────────────────────────────────────
_CM_OUTCOMES = {
    "Type 2 Diabetes (diagnosed prevalence)": ("diabetes_prev_prior", "diabetes_prevalence_pct"),
    "Hypertension (diagnosed prevalence)":    ("htn_prev_prior", "hypertension_prevalence_pct"),
}


def view_campaign_measurement(scores: pd.DataFrame):
    """Matched-control diff-in-diff: did diagnosed prevalence rise faster in
    campaign counties than in statistically similar untouched counties?"""
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Campaign Measurement — Diagnosis-Rate Lift</div>
      <div class="banner-stat">Matched-control diff-in-diff</div>
      <div class="banner-note">
        Select your campaign counties → we match each to its most similar
        untouched counties → lift = how much faster diagnosed prevalence grew
        in your counties, net of the secular trend.
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Inputs ────────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        state_pick = st.multiselect(
            "Campaign states", sorted(scores["state_name"].unique().tolist()),
            key="cm_states")
        county_pool = scores[scores["state_name"].isin(state_pick)] if state_pick else scores
        county_opts = (county_pool["county_name"] + ", "
                       + county_pool["state_name"].map(STATE_ABBREV).fillna("")).tolist()
        fips_by_label = dict(zip(county_opts, county_pool["county_fips"]))
        picked = st.multiselect(
            f"Campaign counties ({len(county_opts):,} available)",
            sorted(county_opts), key="cm_counties")
    with c2:
        outcome_label = st.selectbox("Outcome", list(_CM_OUTCOMES.keys()), key="cm_outcome")
    with c3:
        k = st.slider("Controls per county", 1, 5, 3, key="cm_k")

    fips_text = st.text_input(
        "…or paste county FIPS codes (comma-separated)",
        placeholder="48479, 48215, 36005", key="cm_fips_text")

    treated = [str(fips_by_label[p]).zfill(5) for p in picked]
    if fips_text.strip():
        treated += [f.strip().zfill(5) for f in fips_text.split(",") if f.strip()]
    treated = sorted(set(treated))

    if len(treated) < 5:
        st.markdown(f"""
        <div class="card" style="padding:1.4rem;text-align:center;margin-top:.8rem;">
          <div style="font-size:2rem;">📐</div>
          <div class="sec-head">Select at least 5 campaign counties</div>
          <div class="sec-sub" style="max-width:600px;margin:0 auto;">
            Fewer than 5 counties rarely has the statistical power to separate a
            campaign effect from noise. For a pre-campaign plan: pick the counties
            you intend to target, export the matched-control list below, and
            <strong>pre-register both lists before launch</strong> — that's what
            makes the post-campaign readout credible.
          </div>
        </div>""", unsafe_allow_html=True)
        return

    pre_col, post_col = _CM_OUTCOMES[outcome_label]
    if pre_col not in scores.columns or post_col not in scores.columns:
        st.error(f"Outcome columns unavailable ({pre_col}/{post_col}) — "
                 "re-run ingest_real_data.py.")
        return

    # ── Match + estimate ──────────────────────────────────────────────────────
    from src.features.campaign_measurement import diff_in_diff, match_controls
    try:
        match = match_controls(scores, treated, k=k)
        res = diff_in_diff(scores, match.treated_fips, match.control_fips,
                           outcome_pre=pre_col, outcome_post=post_col)
    except ValueError as e:
        st.error(str(e))
        return

    # ── Results ───────────────────────────────────────────────────────────────
    sig_color = G_DARK if (res.significant and res.estimate > 0) else "#F4A261"
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f"""<div class="card-dark">
      <div class="label-w">Diagnosis-rate lift{_iicon(METRIC_TOOLTIPS["cm_lift"], tip_cls="tip-r")}</div>
      <div class="big-num-w">{res.estimate:+.2f}pp</div>
      <div class="sub-w">95% CI [{res.ci_low:+.2f}, {res.ci_high:+.2f}]</div></div>""",
      unsafe_allow_html=True)
    r2.markdown(f"""<div class="card" style="border-top:3px solid {sig_color};">
      <div class="label">Verdict{_iicon(METRIC_TOOLTIPS["cm_verdict"])}</div>
      <div style="font-size:.95rem;font-weight:800;color:{sig_color};margin-top:.35rem;">
        {"✅ Significant lift" if (res.significant and res.estimate > 0)
         else ("⚠️ Significant decline" if res.significant else "— Not distinguishable from zero")}
      </div>
      <div class="sub-muted" style="margin-top:.3rem;">bootstrap, 2,000 resamples</div></div>""",
      unsafe_allow_html=True)
    r3.markdown(f"""<div class="card" style="border-top:3px solid {BLUE};">
      <div class="label">Campaign counties{_iicon(METRIC_TOOLTIPS["cm_treated"])}</div>
      <div class="big-num">{res.n_treated}</div>
      <div class="sub-muted">Δ diagnosed: {res.treated_delta:+.2f}pp</div></div>""",
      unsafe_allow_html=True)
    r4.markdown(f"""<div class="card" style="border-top:3px solid #8338EC;">
      <div class="label">Matched controls{_iicon(METRIC_TOOLTIPS["cm_controls"])}</div>
      <div class="big-num">{res.n_control}</div>
      <div class="sub-muted">Δ diagnosed: {res.control_delta:+.2f}pp</div></div>""",
      unsafe_allow_html=True)

    # ── Covariate balance ────────────────────────────────────────────────────
    with st.expander("⚖️ Matching quality (covariate balance)"):
        bal = match.balance.reset_index().rename(columns={"index": "covariate"})
        rows = "".join(
            f"<tr><td>{r['covariate']}</td>"
            f"<td style='text-align:right;'>{r['treated_mean']:,.3f}</td>"
            f"<td style='text-align:right;'>{r['control_mean']:,.3f}</td>"
            f"<td style='text-align:right;color:{MUTED};'>{r['pool_mean']:,.3f}</td></tr>"
            for _, r in bal.iterrows()
        )
        st.markdown(
            f'<table class="tbl"><thead><tr><th>Covariate</th><th>Campaign mean</th>'
            f'<th>Matched-control mean</th><th>All-US mean</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:.7rem;color:{MUTED};margin-top:.4rem;'>"
                    f"Good matching: control means close to campaign means, both "
                    f"potentially far from the US average.</div>", unsafe_allow_html=True)

    # ── Pre-registration export ──────────────────────────────────────────────
    pairs = pd.DataFrame(
        [(t, c) for t, ctrls in match.control_map.items() for c in ctrls],
        columns=["campaign_county_fips", "matched_control_fips"])
    st.download_button(
        "⬇️  Export pre-registration file (campaign + matched controls)",
        pairs.to_csv(index=False),
        file_name="sppf_campaign_preregistration.csv", mime="text/csv", key="cm_dl")

    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:.8rem;line-height:1.6;">
      <strong>Read this before quoting the number:</strong>
      Outcomes are CDC PLACES <em>diagnosed</em> prevalence between the two most
      recent releases (~2-year spacing) — suited to multi-year campaigns, not
      quarterly pulses. Matching is on observables only; pre-register the county
      and control lists before launch. PLACES model-smoothing limits power in
      small counties. Claims-data integration would tighten both the time window
      and the confidence intervals.
    </div>""", unsafe_allow_html=True)


# ── View 10: Data Provenance ──────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _provenance_tables():
    from src.quality.provenance import build_provenance, build_output_provenance
    return build_provenance(), build_output_provenance()


@st.cache_data(ttl=300)
def _gate_reports():
    from src.quality.provenance import run_all_gates
    out = []
    for name, rep in run_all_gates():
        out.append({
            "name": name,
            "ok": rep.ok,
            "results": [(r.name, r.passed, r.severity, r.detail) for r in rep.results],
        })
    return out


def view_data_provenance(scores: pd.DataFrame):
    """Source-of-truth page: where every number comes from + live QA status."""
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">Data Provenance &amp; Quality</div>
      <div class="banner-stat">Every number, sourced</div>
      <div class="banner-note">
        100% public, aggregate, PHI-free data · computed live from the files
        this dashboard is actually reading · QA gates re-run on load
      </div>
    </div>""", unsafe_allow_html=True)

    src_df, out_df = _provenance_tables()

    # ── Source table ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head">Data Sources</div>', unsafe_allow_html=True)
    rows_html = ""
    for _, r in src_df.iterrows():
        cov = f"{r['coverage']:,}" if r["coverage"] else "—"
        cached = r["cached"] or "—"
        note = f"<br><span style='font-size:.66rem;color:{MUTED};'>{r['notes']}</span>" if r["notes"] else ""
        rows_html += (
            f"<tr>"
            f"<td><a href='{r['url']}' target='_blank' style='color:{G_DARK};"
            f"text-decoration:none;font-weight:600;'>{r['source']}</a>{note}</td>"
            f"<td style='font-size:.75rem;'>{r['provider']}</td>"
            f"<td style='font-size:.75rem;'>{r['vintage']}</td>"
            f"<td style='font-size:.73rem;'>{r['dimensions']}</td>"
            f"<td style='text-align:right;'>{cov} {r['unit']}s</td>"
            f"<td style='font-size:.73rem;'>{cached}</td>"
            f"<td>{r['status']}</td>"
            f"</tr>"
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>Source</th><th>Provider</th><th>Vintage</th><th>Feeds</th>'
        f'<th>Real coverage {_iicon(METRIC_TOOLTIPS["prov_coverage"], pos="")}</th>'
        f'<th>Downloaded</th>'
        f'<th>Status {_iicon(METRIC_TOOLTIPS["prov_status"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── Outputs ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head" style="margin-top:1.2rem;">Scored Outputs</div>',
                unsafe_allow_html=True)
    o_html = "".join(
        f"<tr><td style='font-weight:600;'>{r['output']}</td>"
        f"<td style='text-align:right;'>{r['rows']:,}</td>"
        f"<td>{r['unit']}s</td><td>{r['generated'] or '—'}</td>"
        f"<td>{r['status']}</td></tr>"
        for _, r in out_df.iterrows()
    )
    st.markdown(
        f'<table class="tbl"><thead><tr><th>Output</th><th>Rows</th>'
        f'<th>Unit</th><th>Generated</th><th>Status</th></tr></thead>'
        f'<tbody>{o_html}</tbody></table>', unsafe_allow_html=True)

    # ── Confidence grade distribution ─────────────────────────────────────────
    if "confidence_grade" in scores.columns:
        st.markdown(f'<div class="sec-head" style="margin-top:1.2rem;">County Data Confidence '
                    f'{_iicon(METRIC_TOOLTIPS["confidence_grade"], pos="")}</div>',
                    unsafe_allow_html=True)
        dist = scores["confidence_grade"].value_counts().reindex(["A", "B", "C"]).fillna(0)
        c1, c2, c3 = st.columns(3)
        for col, g, color, desc in [
            (c1, "A", G_DARK, "6-7 real sources"),
            (c2, "B", "#F4A261", "4-5 real sources"),
            (c3, "C", "#E63946", "<4 sources — proxy-leaning"),
        ]:
            col.markdown(f"""<div class="card" style="border-top:3px solid {color};">
              <div class="label">Grade {g}</div>
              <div class="big-num" style="color:{color};">{int(dist[g]):,}</div>
              <div class="sub-muted">{desc}</div></div>""", unsafe_allow_html=True)

    # ── Live QA gate report ───────────────────────────────────────────────────
    st.markdown(f'<div class="sec-head" style="margin-top:1.2rem;">QA Gate Report (live) '
                f'{_iicon(METRIC_TOOLTIPS["prov_qa"], pos="")}</div>',
                unsafe_allow_html=True)
    st.markdown(f"""<div class="sec-sub">Fail-loudly data contracts re-run against
      the exact files powering this dashboard. A 🛑 here means the pipeline would
      refuse to ship this data.</div>""", unsafe_allow_html=True)
    for rep in _gate_reports():
        n_pass = sum(1 for _, p, _, _ in rep["results"] if p)
        badge = "✅" if rep["ok"] else "🛑"
        with st.expander(f"{badge} {rep['name']} — {n_pass}/{len(rep['results'])} checks passed",
                         expanded=not rep["ok"]):
            for name, passed, sev, detail in rep["results"]:
                icon = "✅" if passed else ("🛑" if sev == "CRITICAL" else "⚠️")
                st.markdown(
                    f"<div style='font-size:.78rem;padding:.15rem 0;'>{icon} "
                    f"<strong>{name}</strong> — <span style='color:{MUTED};'>{detail}</span></div>",
                    unsafe_allow_html=True)

    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:1rem;">
      Methodology: county opportunity score = weighted blend of 7 dimension scores
      (weights in config/dimensions.yaml) · percentile = rank among 3,144 counties ·
      confidence grade reflects pre-imputation source coverage ·
      full details in SPPF_Methodology_v1.0.docx and docs/ARCHITECTURE.md.
    </div>""", unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────
# ── View 8: Insights & Actions ────────────────────────────────────────────────
def view_insights(scores: pd.DataFrame, scores_long: pd.DataFrame,
                  condition: str = "overall", cond_label: str = "All Conditions",
                  state: list = None, top_n: int = 20):
    """Auto-synthesises the 7-dimension data into immediate, specific recommendations.
    Designed to surface AHA moments without the viewer having to go hunting."""

    scores = _ensure_dims(scores)
    scores, _ = _ensure_payer(scores)
    opp_col = _opp_score(scores)

    # Apply state filter
    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]
    if len(filtered) == 0:
        st.warning("No data for the selected filters.")
        return

    geo_label = (
        ", ".join(state[:2]) + (f" +{len(state)-2} more" if len(state) > 2 else "")
        if state else "United States"
    )

    # ── Pre-compute key insight figures ──────────────────────────────────────
    all_sorted = filtered.sort_values(opp_col, ascending=False)
    priority   = filtered[filtered[opp_col] >= 55].sort_values(opp_col, ascending=False)
    top3       = all_sorted.head(3)

    # Most underserved = widest gap between Diagnosis Gap and Access to Care
    if "dim_diagnosis_gap" in filtered.columns and "dim_access_to_care" in filtered.columns:
        filtered = filtered.copy()
        filtered["_gap_minus_access"] = filtered["dim_diagnosis_gap"] - filtered["dim_access_to_care"]
        most_underserved = filtered.nlargest(1, "_gap_minus_access").iloc[0]
    else:
        most_underserved = all_sorted.iloc[0]

    # Best payer county = highest MA penetration in Priority tier (or overall)
    payer_col = "ma_penetration_rate" if "ma_penetration_rate" in filtered.columns else None
    base_pool  = priority if len(priority) > 0 else all_sorted
    if payer_col:
        best_payer_county = base_pool.nlargest(1, payer_col).iloc[0]
    else:
        best_payer_county = base_pool.iloc[0]

    # Counterintuitive find = top-quintile score but small estimated pool
    score_threshold = all_sorted[opp_col].quantile(0.80)
    if "total_estimated_pool" in filtered.columns:
        pop_threshold   = filtered["total_estimated_pool"].quantile(0.40)
        surprise_pool   = filtered[
            (filtered[opp_col] >= score_threshold) &
            (filtered["total_estimated_pool"] <= pop_threshold)
        ].sort_values(opp_col, ascending=False)
        surprise = (surprise_pool.iloc[0] if len(surprise_pool) > 0
                    else all_sorted.iloc[min(5, len(all_sorted)-1)])
    else:
        surprise = all_sorted.iloc[min(5, len(all_sorted)-1)]

    # Fastest-growing markets
    traj_col = "dim_trajectory" if "dim_trajectory" in filtered.columns else opp_col
    fast_growing = (
        filtered[filtered[opp_col] >= 40].nlargest(5, traj_col)
        if len(filtered[filtered[opp_col] >= 40]) >= 3
        else all_sorted.head(5)
    )

    n_priority = int((filtered[opp_col] >= 55).sum())
    n_emerging = int(((filtered[opp_col] >= 40) & (filtered[opp_col] < 55)).sum())

    # ── Banner ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="banner">
      <div class="banner-title">⚡ Insights &amp; Actions — {cond_label} · {geo_label}</div>
      <div class="banner-stat">Where to move next</div>
      <div class="banner-note">
        Auto-synthesised from 7-dimension scoring across {len(filtered):,} counties ·
        {n_priority} Priority  ·  {n_emerging} Emerging
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Top 3 Action Counties ─────────────────────────────────────────────────
    st.markdown(f"""<div class='ch'>
      <div class='sec-head'>🎯 Top 3 Counties to Act On Now {_iicon(METRIC_TOOLTIPS["opportunity_score"], pos="")}</div>
      <div class='sec-sub'>Highest composite opportunity scores in current filter — these are your first calls</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col_ui, (_, row) in zip([c1, c2, c3], top3.iterrows()):
        opp    = row.get(opp_col, 0)
        pool   = int(row.get("total_estimated_pool", 0))
        interv = str(row.get("recommended_intervention", "Pharmacy-Based Screening"))
        imeta  = INTERV_META.get(interv, {"color": G_MID, "icon": "💊", "desc": interv})
        tier   = str(row.get("opportunity_tier", "Developing"))
        tcls   = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
        gap    = row.get("dim_diagnosis_gap", 0)
        gap_lbl = "Critical" if gap >= 70 else "High" if gap >= 50 else "Moderate"
        rank   = int(row.get("priority_rank", 0)) if "priority_rank" in row.index else "—"
        with col_ui:
            st.markdown(f"""
            <div class="card" style="border-left:3px solid {imeta['color']};min-height:215px;">
              <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;">
                NATIONAL RANK #{rank}
              </div>
              <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};line-height:1.25;margin:.1rem 0 .15rem;">
                {row['county_name']}
              </div>
              <div style="font-size:.75rem;color:{MUTED};margin-bottom:.55rem;">{row.get('state_name','')}</div>
              <div style="display:flex;align-items:baseline;gap:.4rem;margin-bottom:.45rem;">
                <span class="pill {tcls}">{tier}</span>
                <span style="font-size:1.35rem;font-weight:900;color:{G_DARK};">{opp:.0f}</span>
                <span style="font-size:.7rem;color:{MUTED};">/100</span>
              </div>
              <div style="font-size:.77rem;color:{DARK};margin-bottom:.22rem;">
                <b>Est. silent pool:</b> {pool:,}
              </div>
              <div style="font-size:.77rem;color:{DARK};margin-bottom:.35rem;">
                <b>Diagnosis gap:</b> <span style="color:{RED};">{gap_lbl}</span>
                ({gap:.0f}/100)
              </div>
              <div style="border-top:1px solid {BORDER};padding-top:.35rem;margin-top:.1rem;
                          font-size:.74rem;color:{imeta['color']};font-weight:700;">
                {imeta['icon']} {interv}
              </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    # ── Two-column mid section ────────────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>💳 Best Payer Conversation First</div>
          <div class='sec-sub'>Highest Medicare Advantage penetration in a Priority-tier county</div>
        </div>""", unsafe_allow_html=True)

        ma_rate    = best_payer_county.get("ma_penetration_rate", 0)
        pc_name    = best_payer_county.get("county_name", "—")
        pc_state   = best_payer_county.get("state_name", "")
        pc_pool    = int(best_payer_county.get("total_estimated_pool", 0))
        pc_opp     = best_payer_county.get(opp_col, 0)
        pc_abbr    = STATE_ABBREV.get(pc_state, pc_state)
        ma_pct     = ma_rate * 100 if ma_rate <= 1.0 else ma_rate

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {BLUE};">
          <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;margin-bottom:.1rem;">
            LEAD WITH THIS COUNTY
          </div>
          <div style="font-size:1.1rem;font-weight:800;color:{G_DARK};">{pc_name}, {pc_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.5rem;">
            Opportunity score: {pc_opp:.0f}/100
          </div>
          <div style="font-size:1.7rem;font-weight:900;color:{BLUE};line-height:1;">{ma_pct:.0f}%</div>
          <div style="font-size:.74rem;color:{MUTED};margin-bottom:.5rem;">Medicare Advantage penetration</div>
          <div style="background:{G_PALE};border-radius:6px;padding:.5rem .7rem;
                      font-size:.77rem;color:{DARK};line-height:1.5;">
            📣 <b>Payer pitch:</b> "{pc_name} members have a {ma_pct:.0f}% MA rate
            and {pc_pool:,} undiagnosed patients. Closing this gap directly improves
            your Stars score and reduces downstream complication costs."
          </div>
        </div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>💡 The Counterintuitive Find</div>
          <div class='sec-sub'>Top-quintile opportunity score · small county · competitors aren't looking here</div>
        </div>""", unsafe_allow_html=True)

        surp_name  = surprise.get("county_name", "—")
        surp_state = surprise.get("state_name", "")
        surp_abbr  = STATE_ABBREV.get(surp_state, surp_state)
        surp_opp   = surprise.get(opp_col, 0)
        surp_pool  = int(surprise.get("total_estimated_pool", 0))
        surp_gap   = surprise.get("dim_diagnosis_gap", 0)
        surp_rank  = int(surprise.get("priority_rank", 0)) if "priority_rank" in surprise.index else "—"

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {AMBER};">
          <div style="font-size:.66rem;font-weight:700;color:{MUTED};letter-spacing:.04em;margin-bottom:.1rem;">
            NOT ON MOST RADARS · RANK #{surp_rank}
          </div>
          <div style="font-size:1.1rem;font-weight:800;color:{G_DARK};">{surp_name}, {surp_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.45rem;">
            Opportunity: {surp_opp:.0f}/100 · Diagnosis gap: {surp_gap:.0f}/100
          </div>
          <div style="font-size:.77rem;color:{DARK};margin-bottom:.45rem;">
            Est. silent pool: <b>{surp_pool:,}</b>
          </div>
          <div style="background:#FEF3C7;border-radius:6px;padding:.5rem .7rem;
                      font-size:.77rem;color:#92400E;line-height:1.5;">
            ⚡ <b>Why it matters:</b> Competitors target large metros. {surp_name} has a
            proportionally larger diagnosis gap and far less field traffic — first-mover
            advantage is still available here.
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

    # ── Bottom two-column section ─────────────────────────────────────────────
    col_l2, col_r2 = st.columns(2)

    with col_l2:
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>🏘️ Most Underserved Market</div>
          <div class='sec-sub'>Widest gap between disease burden and available care infrastructure</div>
        </div>""", unsafe_allow_html=True)

        us_name   = most_underserved.get("county_name", "—")
        us_state  = most_underserved.get("state_name", "")
        us_abbr   = STATE_ABBREV.get(us_state, us_state)
        us_opp    = most_underserved.get(opp_col, 0)
        us_gap    = most_underserved.get("dim_diagnosis_gap", 0)
        us_access = most_underserved.get("dim_access_to_care", 0)
        us_sdoh   = most_underserved.get("dim_social_determinants", 0)
        us_interv = str(most_underserved.get("recommended_intervention", "Community Health Center Partnership"))
        us_imeta  = INTERV_META.get(us_interv, {"color": PURPLE, "icon": "🏘️", "desc": us_interv})

        st.markdown(f"""
        <div class="card" style="border-left:3px solid {PURPLE};">
          <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};">{us_name}, {us_abbr}</div>
          <div style="font-size:.75rem;color:{MUTED};margin-bottom:.55rem;">Opportunity: {us_opp:.0f}/100</div>
          <div class="sbar-wrap" style="margin-bottom:.3rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Diagnosis Gap</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_gap:.0f}%;background:{RED};"></div></div>
            <span class="snum">{us_gap:.0f}</span>
          </div>
          <div class="sbar-wrap" style="margin-bottom:.3rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Access to Care</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_access:.0f}%;background:{G_MID};"></div></div>
            <span class="snum">{us_access:.0f}</span>
          </div>
          <div class="sbar-wrap" style="margin-bottom:.55rem;">
            <span style="font-size:.71rem;color:{MUTED};width:7.5rem;flex-shrink:0;">Social Burden</span>
            <div class="sbar-bg"><div class="sbar-fill" style="width:{us_sdoh:.0f}%;background:{PURPLE};"></div></div>
            <span class="snum">{us_sdoh:.0f}</span>
          </div>
          <div style="font-size:.75rem;font-weight:700;color:{us_imeta['color']};">
            {us_imeta['icon']} Recommended: {us_interv}
          </div>
        </div>""", unsafe_allow_html=True)

    with col_r2:
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>📈 Fastest-Growing Markets</div>
          <div class='sec-sub'>Highest trajectory scores — move before the window closes</div>
        </div>""", unsafe_allow_html=True)

        rows_html = ""
        for _, row in fast_growing.iterrows():
            traj = row.get(traj_col, 0)
            opp  = row.get(opp_col, 0)
            tier = str(row.get("opportunity_tier", "Developing"))
            tcls = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
            st_abbr = STATE_ABBREV.get(row.get("state_name", ""), row.get("state_name", ""))
            rows_html += f"""
            <tr>
              <td style="font-weight:600">{row['county_name']}, {st_abbr}</td>
              <td><span class="pill {tcls}">{tier}</span></td>
              <td style="font-weight:700;color:{G_DARK}">{opp:.0f}</td>
              <td>
                <div class="sbar-wrap">
                  <div class="sbar-bg">
                    <div class="sbar-fill" style="width:{traj:.0f}%;background:#60A5FA;"></div>
                  </div>
                  <span class="snum" style="color:#2563EB">{traj:.0f}</span>
                </div>
              </td>
            </tr>"""

        st.markdown(f"""
        <div class="card">
          <table class="tbl">
            <thead><tr>
              <th>County</th><th>Tier</th><th>Score</th><th>Trajectory ↑</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>""", unsafe_allow_html=True)

    # ── State spotlight (single-state filter only) ────────────────────────────
    if state and len(state) == 1:
        st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
        sname = state[0]
        st.markdown(f"""<div class='ch'>
          <div class='sec-head'>📍 {sname} State Spotlight</div>
          <div class='sec-sub'>Key intelligence for this specific market</div>
        </div>""", unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns(4)
        total_pool = int(filtered["total_estimated_pool"].sum()) if "total_estimated_pool" in filtered.columns else 0
        top_county = all_sorted.iloc[0]
        top_interv_val = filtered.get("recommended_intervention", pd.Series(dtype=str))
        if hasattr(top_interv_val, "value_counts") and len(top_interv_val) > 0:
            lead_prog = filtered["recommended_intervention"].value_counts().idxmax() if "recommended_intervention" in filtered.columns else "—"
        else:
            lead_prog = "—"

        with sc1:
            st.markdown(f"""<div class="card-dark" style="text-align:center;">
              <div class="big-num-w">{n_priority}</div>
              <div class="label-w">Priority Counties</div>
              <div class="sub-w">Score ≥ 55</div>
            </div>""", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"""<div class="card-blue" style="text-align:center;">
              <div class="big-num-w">{n_emerging}</div>
              <div class="label-w">Emerging Counties</div>
              <div class="sub-w">Score 40–54</div>
            </div>""", unsafe_allow_html=True)
        with sc3:
            pool_m = (f"{total_pool/1_000_000:.1f}M" if total_pool >= 1_000_000
                      else f"{total_pool/1_000:.0f}K")
            st.markdown(f"""<div class="card" style="text-align:center;">
              <div class="big-num">{pool_m}</div>
              <div class="label">Est. Silent Pool</div>
              <div class="sub">State-wide undiagnosed</div>
            </div>""", unsafe_allow_html=True)
        with sc4:
            st.markdown(f"""<div class="card" style="text-align:center;">
              <div style="font-size:1.05rem;font-weight:800;color:{G_DARK};line-height:1.25;">
                {top_county['county_name']}
              </div>
              <div class="label" style="margin-top:.2rem;">Top County</div>
              <div class="sub">Score: {top_county[opp_col]:.0f}/100</div>
            </div>""", unsafe_allow_html=True)

    # ── Summary action banner ─────────────────────────────────────────────────
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    top1       = all_sorted.iloc[0]
    top1_name  = top1.get("county_name", "—")
    top1_state = top1.get("state_name", "")
    top1_abbr  = STATE_ABBREV.get(top1_state, top1_state)
    top1_interv = str(top1.get("recommended_intervention", "Pharmacy-Based Screening"))
    top1_imeta  = INTERV_META.get(top1_interv, {"color": G_MID, "icon": "💊", "desc": top1_interv})

    st.markdown(f"""
    <div class="banner" style="margin-top:.4rem;">
      <div class="banner-title">⚡ Your Next Move</div>
      <div style="font-size:1.4rem;font-weight:800;line-height:1.3;margin:.1rem 0 .3rem;">
        Start in {top1_name}, {top1_abbr} — your highest-scored market right now
      </div>
      <div style="font-size:.88rem;opacity:.85;">
        {top1_imeta['icon']} Recommended program: <b>{top1_interv}</b>&nbsp;&nbsp;·&nbsp;&nbsp;
        {n_priority} Priority-tier counties in current filter ready for outreach
      </div>
    </div>""", unsafe_allow_html=True)


def main():
    scores, scores_long = load_data()
    geojson   = load_geojson()
    zip_scores = load_zip_data()
    ctrl      = render_sidebar(scores)

    view        = ctrl["view"]
    condition   = ctrl["condition"]
    cond_label  = ctrl["cond_label"]
    state       = ctrl["state"]
    county      = ctrl.get("county", "All Counties")
    top_n       = ctrl["top_n"]
    tier_filter = ctrl["tier_filter"]

    if view == "Insights & Actions":
        view_insights(scores, scores_long, condition, cond_label, state, top_n)

    elif view == "Market Overview":
        view_market_overview(scores, scores_long, condition, cond_label)

    elif view == "7-Dimension Analysis":
        view_7d_analysis(scores, state, top_n, condition, cond_label)

    elif view == "Investment Planner":
        view_investment_planner(scores, scores_long, condition, state, top_n, tier_filter)

    elif view == "Geographic Intelligence":
        view_geographic(scores, scores_long, condition, state, geojson)

    elif view == "State Drill-Down":
        view_state_drilldown(scores, scores_long, condition, cond_label, state, county, top_n)

    elif view == "Payer Landscape":
        view_payer_landscape(scores, state, top_n)

    elif view == "ZIP & Territory":
        view_zip_territory(zip_scores, scores, state, condition)

    elif view == "HCP Targeting":
        view_hcp_targeting(load_hcp_data(), state)

    elif view == "Campaign Measurement":
        view_campaign_measurement(scores)

    elif view == "Data Provenance":
        view_data_provenance(scores)


if __name__ == "__main__":
    main()

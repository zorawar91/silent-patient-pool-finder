# Silent Patient Pool Finder

A county-level market intelligence platform that identifies where undiagnosed chronic disease burden is highest across the United States — scored via a 7-dimension framework using real public health data.

> ⚠️ **Population-level planning tool — not a clinical diagnostic instrument.** Outputs are indicators for market access, campaign planning, and resource allocation. All clinical decisions require licensed practitioner involvement.

---

## What it does

Type 2 Diabetes, Hypertension, and Hypothyroidism have large undiagnosed populations that never appear in prescription or claims data. This platform scores every US county across 7 dimensions — disease burden, diagnosis gap, access to care, social determinants, payer landscape, commercial readiness, and trajectory — to surface where the opportunity to reach undiagnosed patients is highest.

### Outputs
- **Interactive dashboard** — 5-view Streamlit app with opportunity map, county rankings, payer analysis, investment planner, and state drill-down
- **Opportunity Score** — composite 0–100 score per county, weighted across 7 dimensions
- **Program recommendation** — per-county recommendation across 5 program types (Payer Partnership, Community Health Center, Employer Wellness, Digital Health, Pharmacy-Based Screening)
- **Estimated undiagnosed pool** — county-level patient count estimates anchored to published undiagnosis rates

---

## Data Sources (7 real, publicly available)

| Source | Provider | Coverage | Dimensions |
|--------|----------|----------|------------|
| PLACES County Health Data (2024) | CDC | 2,956 counties | Disease Burden, Diagnosis Gap |
| PLACES County Health Data (2022) | CDC | 2,900+ counties | Trajectory (YoY trend) |
| American Community Survey (5-year) | US Census Bureau | 3,222 counties | Social Determinants |
| MA County Penetration Report | CMS | 3,108 counties with real rates | Diagnosis Gap, Payer Landscape |
| Health Professional Shortage Areas | HRSA | 3,233 counties | Access to Care |
| County Health Rankings | Robert Wood Johnson Foundation | 3,152 counties | Access to Care, SDoH backup |
| Food Environment Atlas | USDA ERS | 3,100+ counties | Social Determinants (food access) |
| PLACES ZCTA Data + ACS ZCTA (5-year) | CDC / Census | ~33,800 ZIP codes | ZIP-level scoring |
| Medicare Physician & Other Practitioners (by Provider) | CMS | ~530k prescribers | HCP Targeting |

All data is ingested at the aggregate county level. No individual patient records are used at any stage.

---

## Architecture

```
ingest_real_data.py                ← counties: 7 real data sources
        │
        ▼
src/features/dimension_scorer.py   ← 3,144 counties × 7 dimensions
        │                             + percentile + confidence grade
        ▼  [QA gate]
data/scored/dimension_scores.parquet
        │
        ├──────────────────────────────┐
        ▼                              ▼
ingest_zcta_data.py                ingest_hcp_data.py
src/features/zip_scorer.py         src/features/hcp_scorer.py
~33,800 ZCTAs (crosswalk           ~530k prescribers (CMS by-Provider)
downscaling + ZCTA-level CDC/ACS)  40/25/20/15 priority blend
        │  [QA gate]                   │  [QA gate]
        ▼                              ▼
zip_scores.parquet                 hcp_targets.parquet + CRM CSV
        │                              │
        └──────────────┬───────────────┘
                       ▼
src/output/dashboard.py            ← Streamlit dashboard (9 views)
```

**Stack:**
- **Ingestion:** Python, requests, pandas
- **Storage:** Parquet (local), Neon PostgreSQL (optional cloud sync)
- **Scoring:** scikit-learn, NumPy, pandas
- **Dashboard:** Streamlit, Plotly Express, Plotly Graph Objects
- **Deployment:** Streamlit Cloud

---

## Repository Structure

```
silent-patient-pool-finder/
├── config/
│   ├── conditions.yaml        ← Condition definitions and undiagnosis rates
│   ├── dimensions.yaml        ← 7-dimension weights and intervention types
│   └── us.yaml               ← US geography configuration
├── data/
│   ├── open/                  ← Cached real data downloads (gitignored)
│   └── scored/                ← Scored county parquet files (gitignored)
├── docs/
│   └── ARCHITECTURE.md
├── src/
│   ├── ingestion/
│   │   └── open_data/         ← CDC, Census, CMS, HRSA downloaders
│   ├── features/
│   │   └── dimension_scorer.py
│   └── output/
│       └── dashboard.py
├── tests/
├── ingest_real_data.py        ← Main ingestion + scoring pipeline
├── requirements.txt
└── README.md
```

---

## Getting Started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Census API key
```bash
export CENSUS_API_KEY=your_key_here
# Get a free key at: https://api.census.gov/data/key_signup.html
```

### 3. Run the ingestion pipelines
```bash
python3 ingest_real_data.py     # counties  (~3–4 min first run)
python3 ingest_zcta_data.py     # ZIP codes (~2–3 min, needs county scores)
python3 ingest_hcp_data.py      # HCP call lists (~5–10 min, 509 MB download)
```

Counties → 3,144 scored across 7 dimensions. ZIPs → ~33,800 ZCTAs scored via
Census crosswalk downscaling. HCPs → ~530k prescribers from the public CMS
Medicare by-Provider file, scored for diagnosis-support detailing priority.

Every pipeline ends with a **QA gate**: fail-loudly data contracts (row counts,
code formats, null shares, variance floors, join match rates) that block the
write if any output is corrupt or silently degraded.

> **Note:** County Health Rankings requires a one-time manual download due to WAF restrictions.
> Visit [countyhealthrankings.org → Health Data](https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation),
> download the current analytic data file, and save it to `data/open/analytic_data_chr.csv`.
>
> ⚠️ **CHR continuity note:** RWJ Foundation funding for CHR&R ends December 2026. The data is being
> preserved as an open-source project on GitHub. If the main site is unavailable, check
> [github.com/chrr-data](https://github.com/chrr-data) for the latest release.

### 4. Launch the dashboard
```bash
python3 -m streamlit run src/output/dashboard.py
```

### Optional: sync to Neon PostgreSQL
```bash
# Add to .streamlit/secrets.toml:
# NEON_DATABASE_URL = "postgresql://..."
python3 ingest_real_data.py --db
```

---

## Current Status

✅ **Live** — 3,144 counties scored from 5 real data sources.

| Milestone | Status |
|-----------|--------|
| M1 — Synthetic data pipeline | ✅ Complete |
| M2 — Feature engineering | ✅ Complete |
| M3 — ML scoring model | ✅ Complete |
| M4 — Streamlit dashboard | ✅ Complete |
| M5 — Real data integration (7 sources) | ✅ Complete |
| M6 — Validation & stakeholder documentation | 🔄 In progress |
| M7 — ZIP/ZCTA-level scoring + territory builder | ✅ Complete |
| M8 — QA gates + test suite + CI | ✅ Complete |
| M9 — Percentile scores + data-confidence grades | ✅ Complete |
| M10 — HCP activation layer (prescriber call lists) | ✅ Complete |

### Scoring notes for reviewers

- **Percentile scores** (`opportunity_percentile`) are the buyer-facing number:
  a county at the 94th percentile outranks 94% of US counties. The raw
  weighted composite intentionally tops out around ~62.
- **Confidence grades** (A/B/C) reflect *true pre-imputation* source coverage
  per county — counties scored mostly from state-median fills are visibly
  downgraded rather than silently blended in.
- **HCP priority score** = 40% geography percentile + 25% Medicare panel
  reach + 20% panel metabolic burden + 15% specialty fit. It ranks *where a
  diagnosis-support conversation is most valuable* — it makes no claim about
  individual prescribing quality.

---

## Compliance

All data is ingested at the aggregate county level. No individual patient records are used, stored, or output at any stage. All data partnerships must be reviewed under applicable regulations (HIPAA, state privacy laws) before onboarding proprietary data.

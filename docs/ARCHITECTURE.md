# Architecture

> Silent Patient Pool Finder — a county-level market intelligence platform identifying where undiagnosed chronic disease burden is highest across the United States.

---

## System Overview

```
Real Data Sources (5)
      │
      ▼
┌─────────────────────────┐
│  Ingestion Layer        │  ingest_real_data.py
│  Python + requests      │  Downloads, cleans, and caches county data
│  pandas                 │  Joins 5 sources onto a 3,144-county spine
│  Parquet / Neon PG      │  Local cache + optional cloud sync
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Scoring Layer          │  src/features/dimension_scorer.py
│  7 dimensions scored    │  Disease Burden, Diagnosis Gap, Access to Care,
│  per county (0–100)     │  Social Determinants, Payer Landscape,
│  Weighted composite     │  Commercial Readiness, Trajectory
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Dashboard Layer        │  src/output/dashboard.py
│  Streamlit              │  5-view interactive web app
│  Plotly                 │  Choropleth map, charts, heatmap
│  Streamlit Cloud        │  Deployment
└─────────────────────────┘
```

---

## Layer 1 — Data Ingestion

### Real Data Sources

| Source | File | Provider | Counties | Key Variables |
|--------|------|----------|----------|---------------|
| PLACES County Health | `cdc_places_county.parquet` | CDC | 2,956 | Diabetes prevalence, obesity, hypertension, checkup rate |
| American Community Survey | `census_acs_county.parquet` | US Census Bureau | 3,222 | Poverty rate, income, uninsured rate, education |
| MA Penetration Report | `cms_ma_penetration.parquet` | CMS | 3,128 | Medicare Advantage enrollment share |
| Health Professional Shortage Areas | `hrsa_access.parquet` | HRSA | 3,233 | HPSA flag, FQHC count |
| County Health Rankings | `county_health_rankings.parquet` | Robert Wood Johnson Foundation | 3,152 | Primary care ratio, SDoH backup |

### County Spine

All sources are joined onto a 3,144-county spine derived from the US Census TIGER county list. Counties missing from a source receive synthetic fallback values derived from national medians and correlated signals.

### Storage

- **Local:** Parquet files in `data/open/` (cached) and `data/scored/` (pipeline output)
- **Cloud:** Optional Neon PostgreSQL sync — add `NEON_DATABASE_URL` to `.streamlit/secrets.toml`

---

## Layer 2 — 7-Dimension Scoring

Each county receives a score from 0 to 100 on each dimension. A weighted composite produces the **Opportunity Score**.

| Dimension | Weight | Key Real Signals |
|-----------|--------|-----------------|
| Disease Burden | 20% | CDC diabetes prevalence, obesity rate, hypertension |
| Diagnosis Gap | 25% | Checkup rate, uninsured rate, CMS diagnosed vs. prevalence gap |
| Access to Care | 15% | HRSA HPSA designation, FQHC presence, rural flag, CHR primary care ratio |
| Social Determinants | 15% | Census poverty rate, income, education, uninsured rate |
| Payer Landscape | 10% | CMS MA penetration, Medicaid rate, commercial coverage |
| Commercial Readiness | 10% | Broadband access rate, urban flag, income proxy |
| Trajectory | 5% | Median age, obesity trend proxy, SDoH widening gap |

### Normalization

All signals are min-max normalized across all 3,144 counties before weighting. This means scores are relative — a county scoring 80 on Disease Burden is in the top tier of US counties, not at 80% of a fixed ceiling.

### Opportunity Tiers

| Tier | Score | Description |
|------|-------|-------------|
| Priority | ≥ 55 | Top ~0.3% of counties — confirmed high-need by multiple real sources |
| Emerging | 40–55 | Strong indicators with access or payer gaps — pipeline development |
| Developing | < 40 | Lower immediate priority — monitor for trend shifts |

> **Note on the ≥55 threshold:** With 5 real data sources and 2 dimensions using demographic proxies (Trajectory, Commercial Readiness), the observed score ceiling is approximately 60–62. The threshold is set to select the highest-yield counties meaningfully above the national average (37).

---

## Layer 3 — Dashboard

### Views

| View | Purpose |
|------|---------|
| Market Overview | National KPIs, condition cards, score distribution, program mix |
| Investment Planner | Ranked county table with filters, heatmap, payer analysis |
| Geographic | Choropleth opportunity map, state rankings |
| Payer Landscape | MA penetration analysis, Medicaid/commercial breakdown |
| State Drill-Down | County-level deep dive within a selected state |

### Intervention Types

| Program | Best Fit |
|---------|---------|
| Payer Partnership Program | MA penetration > 35% — Stars incentives fund screening |
| Community Health Center Partnership | High SDoH + low access — FQHC delivery model |
| Employer Wellness Program | High commercial coverage, urban — benefit integration |
| Digital Health Program | High broadband + commercial — telehealth screening |
| Pharmacy-Based Screening | All other counties — broad retail access |

---

## Development Stack

| Area | Tool |
|------|------|
| Language | Python 3.9+ |
| Data ingestion | `requests`, `pandas`, `pyarrow` |
| Scoring | `scikit-learn`, `numpy`, `pandas` |
| Dashboard | `streamlit`, `plotly` |
| Database | Neon PostgreSQL (optional), Parquet (default) |
| Dependency management | pip + `requirements.txt` |
| Version control | Git / GitHub |
| Deployment | Streamlit Cloud |

---

## Running the Pipeline

```bash
# Step 1: ingest all 5 data sources and score all 3,144 counties
export CENSUS_API_KEY=your_key
python3 ingest_real_data.py

# Step 2: launch dashboard
python3 -m streamlit run src/output/dashboard.py

# Optional: push scored data to Neon
python3 ingest_real_data.py --db
```

---

## Privacy Architecture

- All data ingested at the **aggregate county level** — no individual patient identifiers
- No row-level patient data used, stored, or output at any stage
- All external data sources are publicly available government or foundation datasets
- Proprietary data partnerships must be reviewed under HIPAA and applicable state privacy laws before onboarding

---

*Update this document when the data sources, scoring logic, or stack changes. It is the source of truth for architecture decisions.*

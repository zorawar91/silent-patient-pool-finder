# Architecture & Tech Stack

> Silent Patient Pool Finder — a multi-signal inference engine that identifies geographies and HCP clusters with high undiagnosed chronic-disease burden, using pharmacy, lab, and geographic proxy signals.

---

## System Overview

```
Raw Data Sources
      │
      ▼
┌─────────────────┐
│  Layer 1        │  Ingestion & Storage
│  PostgreSQL     │  Raw pharmacy, lab, HCP, geo data
│  GCP / BigQuery │  Scale-out when needed
│  Prefect        │  Pipeline orchestration
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Layer 2        │  Feature Engineering
│  Python/pandas  │  Signal computation
│  dbt            │  Versioned transformations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Layer 3        │  ML Scoring
│  XGBoost        │  Primary model
│  scikit-learn   │  Pipelines & validation
│  MLflow         │  Experiment tracking
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Layer 4        │  Output & Visualisation
│  Streamlit      │  Internal dashboard
│  Folium/Plotly  │  Choropleth risk maps
│  Tableau        │  Client-facing reports
└─────────────────┘
```

---

## Layer 1 — Data Ingestion & Storage

### Tools
| Tool | Purpose |
|------|---------|
| **PostgreSQL** | Primary relational store for all structured data at prototype stage |
| **Google Cloud Storage** | Raw data lake — landing zone for partner data drops |
| **BigQuery** | Scale-out query layer when Postgres hits limits |
| **Prefect** | Pipeline orchestration — schedules, retries, observability |
| **Python + pandas** | Ingestion scripts, cleaning, normalisation |
| **Docker** | Containerised ingestion jobs — runs identically everywhere |

### Data sources (prototype)
- Synthea-generated synthetic patient records
- Anonymised, aggregate pharmacy transaction logs (OTC + Rx)
- Lab test order records (order metadata only — no clinical values)
- ICD-10 coded claims data (negative signal — known-diagnosed exclusion)
- HCP-level Rx prescribing data (IQVIA/AIOCD format)
- NFHS-5 / Census district-level socioeconomic data (public)

### Privacy architecture
- All data ingested at **aggregate or anonymised** level
- No row-level patient identifiers at any stage
- GCP project configured with HIPAA/DPDP-compliant controls
- Raw data encrypted at rest (GCP default) and in transit (TLS)

---

## Layer 2 — Feature Engineering

### Tools
| Tool | Purpose |
|------|---------|
| **Python + pandas** | Feature computation scripts |
| **dbt** | SQL-based transformations — versioned, documented, testable |
| **scikit-learn** | Preprocessing pipelines (scaling, encoding, imputation) |
| **Synthea** | Synthetic patient data generation for prototype |

### Core signals computed
1. **OTC Proxy Cluster Score** — co-purchase frequency of symptom-adjacent OTC products per pin code, without corresponding chronic Rx
2. **Diagnostic Orphan Ratio** — lab test orders (HbA1c, lipid panel, TSH) without follow-up Rx within 90-day window, per HCP cluster
3. **HCP Symptom-to-Chronic Rx Ratio** — ratio of symptom-adjacent Rx to chronic-disease Rx in an HCP's prescribing portfolio
4. **Geographic Burden Index** — epidemiological prevalence prior (NFHS-5) divided by observed Rx penetration per district
5. **Diagnostic Orphan Ratio (Digital)** — teleconsult/health-search query volume without follow-up Rx *(Phase 2)*

### Feature engineering principles
- All features computed at **pin-code or HCP-cluster grain** — never individual patient level
- Time-windowed aggregations (30d, 90d, 12m lookbacks)
- Missing data strategy: explicit imputation documented in dbt models

---

## Layer 3 — ML Scoring

### Tools
| Tool | Purpose |
|------|---------|
| **XGBoost / LightGBM** | Primary gradient boosting model for Geography Risk Score |
| **Logistic Regression** | Interpretable baseline — required for auditability |
| **scikit-learn** | Cross-validation, pipelines, metrics |
| **MLflow** | Experiment tracking, model versioning, artifact storage |
| **SHAP** | Feature importance and model explainability |

### Model design
- **Output:** Geography Risk Score (0–100) per pin code / district
- **Task type:** Regression (risk score) + binary classification (high/low opportunity flag)
- **Training labels:** Known-diagnosis cohorts from claims data used as positive labels; geography-matched controls as negatives
- **Validation:** Hold-out geography-level cross-validation (not random row split — to prevent geographic leakage)
- **Acceptance criterion:** Precision ≥ X% at the geography level (to be defined by stakeholders before training begins)

### Explainability
- SHAP values computed for every scored geography
- Every output includes top-3 driving signals — required for client and regulatory credibility

### What this model does NOT do
- Does not identify or score individual patients
- Does not produce a clinical diagnosis
- Outputs are signals for campaign and resource planning — all clinical action requires licensed practitioner involvement

---

## Layer 4 — Output & Visualisation

### Tools
| Tool | Purpose |
|------|---------|
| **Streamlit** | Internal dashboard — fast to build, Python-native |
| **Folium / Plotly Express** | Choropleth geography risk maps |
| **Tableau / Looker Studio** | Client-facing reporting (pharma/payer audience) |
| **PostgreSQL views** | Pre-aggregated output tables for dashboard queries |

### Output artefacts
1. **Geography Risk Map** — choropleth of Geography Risk Scores at pin-code / district level
2. **Opportunity Ranking Table** — top-N geographies ranked by score, with driving signals and estimated undiagnosed pool size
3. **HCP Priority List** — HCPs ranked by Diagnostic Orphan Ratio and symptom-Rx anomaly score, as targets for diagnosis-support detailing
4. **Campaign Brief Export** — PDF/CSV export of top geographies for awareness campaign planning

---

## Development Stack

| Area | Tool |
|------|------|
| Version control | **GitHub** |
| Containerisation | **Docker + Docker Compose** |
| Language | **Python 3.11+** |
| Dependency management | **Poetry** |
| Code quality | **ruff** (linting), **black** (formatting), **pre-commit** |
| Testing | **pytest** |
| Notebooks | **Jupyter** (exploration only — not shipped to production) |
| Task tracking | **Linear** |
| Secrets management | **GCP Secret Manager** |

---

## Build Order (Prototype Milestones)

| Milestone | Deliverable | Dependencies |
|-----------|------------|--------------|
| M1 | Synthetic data generation pipeline (Synthea → PostgreSQL) | Docker, Postgres setup |
| M2 | Feature engineering scripts for 3 core signals | M1 complete |
| M3 | XGBoost model trained on synthetic labels → Geography Risk Score | M2 complete |
| M4 | Streamlit dashboard with scored map | M3 complete |
| M5 | First real data integration (pharmacy chain pilot) | Legal review + data partnership |
| M6 | Model re-validation on real data, false positive rate audit | M5 complete |

---

## Repository Structure

```
silent-patient-pool-finder/
├── docs/
│   └── ARCHITECTURE.md        ← this file
├── data/
│   └── synthetic/             ← Synthea output (gitignored in prod)
├── notebooks/
│   └── exploration/           ← Jupyter notebooks (never imported by src/)
├── src/
│   ├── ingestion/             ← Data ingestion scripts
│   ├── features/              ← Feature engineering (dbt models + Python)
│   ├── model/                 ← Training, evaluation, MLflow logging
│   └── output/                ← Streamlit dashboard + export scripts
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

*This document is the source of truth for architecture decisions. Update it when the stack changes — don't let it drift from reality.*

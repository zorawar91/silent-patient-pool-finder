# Silent Patient Pool Finder

A multi-signal inference engine that identifies geographies and HCP clusters with high undiagnosed chronic-disease burden — using pharmacy purchase patterns, lab test ordering behaviour, and geographic socioeconomic signals as proxy indicators.

> ⚠️ **This is a population-level signal and planning tool — not a clinical diagnostic instrument.** Outputs are indicators for campaign and resource planning. All clinical decisions require licensed practitioner involvement.

---

## What it does

Chronic conditions like Type 2 Diabetes and Hypertension have large undiagnosed populations that never appear in prescription or claims data. These patients leave observable traces — OTC purchases, diagnostic tests without follow-up, GP visits with non-specific complaints — that can be aggregated and scored at the geography level.

This system ingests anonymised, aggregate data across those signal types and produces a **Geography Risk Score** per pin code / district, ranking where undiagnosed burden is most likely concentrated.

### Outputs
- Geography Risk Map (choropleth)
- Ranked opportunity table with driving signals per geography
- HCP priority list for diagnosis-support detailing
- Campaign brief export (CSV/PDF)

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full tech stack, layer-by-layer design, and build milestones.

**Stack summary:**
- **Ingestion:** PostgreSQL, GCP, Prefect, Python
- **Features:** pandas, dbt, scikit-learn
- **Model:** XGBoost, MLflow, SHAP
- **Output:** Streamlit, Folium, Tableau

---

## Repository Structure

```
silent-patient-pool-finder/
├── docs/
│   └── ARCHITECTURE.md
├── data/
│   └── synthetic/
├── notebooks/
├── src/
│   ├── ingestion/
│   ├── features/
│   ├── model/
│   └── output/
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Getting Started

> Setup instructions will be added as each milestone is completed.

---

## Status

🟡 **Pre-prototype** — architecture defined, synthetic data pipeline in progress.

| Milestone | Status |
|-----------|--------|
| M1 — Synthetic data pipeline | 🔲 Not started |
| M2 — Feature engineering | 🔲 Not started |
| M3 — ML scoring model | 🔲 Not started |
| M4 — Streamlit dashboard | 🔲 Not started |
| M5 — Real data integration | 🔲 Not started |
| M6 — Validation on real data | 🔲 Not started |

---

## Compliance

This project is designed for use with anonymised, aggregate data only. No individual patient records are ingested, stored, or output at any stage. All data partnerships must be reviewed under applicable regulations (DPDP Act, HIPAA, GDPR) before onboarding.

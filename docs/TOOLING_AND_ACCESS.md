# SPPF — Tools, Access & Infrastructure Checklist

**Purpose:** everything the team needs provisioned to develop, run, and deploy
this platform — plus an explicit list of what is *not* needed, so nobody
procures a licence we don't use.

**Headline for planning:** the shipped MVP runs on **zero paid licences, zero
client data, and zero PHI**. Every data source is public and free. A developer
can go from `git clone` to a running dashboard in about 10 minutes with nothing
but Python and an internet connection. The long-lead items in this document are
all **Phase 2** (the IQVIA claims pilot) — those are the ones to start chasing
now, because they need legal and DUA time, not engineering time.

---

## 1. Needed today — to develop and run the MVP

| # | Component | What exactly | Cost | Lead time |
|---|---|---|---|---|
| 1 | **Python** | 3.9+ (CI runs 3.11) + `pip` | Free | None |
| 2 | **Git + GitHub** | Repo hosting, PRs, code review | Free tier fine | None |
| 3 | **GitHub Actions** | CI: lint, tests, data-reproducibility guard on every push | Free tier fine | None |
| 4 | **Python packages** | `requirements.txt` — pandas, numpy, pyarrow, scikit-learn, scipy, streamlit, plotly, requests, sqlalchemy, pytest (full list in repo) | Free / OSS | None |
| 5 | **Internet egress** | Outbound HTTPS to the 8 public data domains in §3 | — | **Check corporate proxy/firewall** |
| 6 | **Census API key** | Free key for the ACS API. Env var `CENSUS_API_KEY` | Free | ~5 min (self-serve) |
| 7 | **Local disk** | ~120 MB working data (83 MB raw cache + 34 MB scored outputs) | — | None |
| 8 | **IDE** | Any (VS Code / PyCharm / Cursor) | Team's existing | None |

> **That's the whole list to be productive.** Items 6–7 are only needed if a
> developer re-runs ingestion; the repo ships committed scored outputs so the
> dashboard works immediately on a fresh clone.

---

## 2. Optional — pick per environment

| Component | Why you'd want it | Alternative if not approved |
|---|---|---|
| **Streamlit Community Cloud** | Zero-config public demo hosting, deploys from GitHub | Run locally, or any internal container host |
| **Neon (serverless Postgres)** | Cloud sync so the dashboard reads from a DB instead of files. Env var `NEON_DATABASE_URL` | **Not required** — the dashboard reads committed Parquet by default; DB is a fallback path only |
| **Docker + Docker Compose** | Local Postgres + pgAdmin for DB development (`docker-compose.yml` ships `postgres:16` + `pgadmin4`) | Skip entirely unless doing DB work |
| **Java 11+** | Only for the legacy Synthea synthetic-patient generator (superseded by the real-data pipeline) | Skip — not used by the current product |

---

## 3. Data sources — all public, no contracts

Eleven sources, no licence fees, no DUAs, no PHI. Only one needs a key and one
needs a manual download.

| Source | Provider | Access method | Key needed? |
|---|---|---|---|
| PLACES County (2025 rel.) | CDC | Public API — `data.cdc.gov` | No |
| PLACES County (2022 archive) | CDC | Public API (pinned dataset ID) | No |
| PLACES ZCTA | CDC | Public API | No |
| American Community Survey 5-yr | US Census | API — `api.census.gov` | **Yes** (free) |
| ACS ZCTA 5-yr | US Census | API | **Yes** (free) |
| TIGER county spine / Gazetteer / ZCTA crosswalk | US Census | Public file download — `www2.census.gov` | No |
| Geographic Variation PUF + MA Penetration | CMS | Public download — `data.cms.gov`, `www.cms.gov` | No |
| Medicare Physician & Other Practitioners | CMS | Public download (**509 MB**) | No |
| Health Professional Shortage Areas | HRSA | Public API — `data.hrsa.gov` | No |
| County Health Rankings | RWJF / UWPHI | ⚠️ **Manual one-time download** — site WAF blocks automation | No |
| Food Environment Atlas | USDA ERS | Public download | No |

**Firewall note:** allow outbound HTTPS to `data.cdc.gov`, `www.cdc.gov`,
`api.census.gov`, `www2.census.gov`, `data.cms.gov`, `www.cms.gov`,
`data.hrsa.gov`, `www.countyhealthrankings.org`, `www.ers.usda.gov`, and
`raw.githubusercontent.com` (county map boundaries). Corporate TLS inspection
can break these — TLS verification is enforced by default and the insecure
bypass requires an explicit opt-in env var.

**Runtimes:** county pipeline ~3–4 min · ZIP ~8 min · HCP ~5–10 min (large download).

---

## 4. Secrets / configuration

| Variable | Needed for | Where it lives |
|---|---|---|
| `CENSUS_API_KEY` | Census ACS API calls during ingestion | Env var / `.env` |
| `NEON_DATABASE_URL` | Optional DB sync | `.streamlit/secrets.toml` or env var |
| `DATABASE_URL` | Generic DB fallback | Env var |
| `SPPF_ALLOW_INSECURE_SSL` | Escape hatch if corporate TLS interception blocks a download. **Off by default, use only if forced** | Env var |

All secret files (`.env`, `.streamlit/secrets.toml`) are gitignored. Templates
are committed (`.env.example`, `secrets.toml.example`). **No credentials are in
the repo.** For deployment, use the host's secret manager (Streamlit Cloud
secrets, or the internal platform's equivalent).

---

## 5. Explicitly NOT required — do not procure for the MVP

Listing these so the team doesn't provision licences we have no code path for:

| Tool | Status | Why |
|---|---|---|
| **Databricks / Snowflake / Spark** | ❌ Not used | Whole dataset is ~120 MB; pandas handles it in seconds. No distributed compute needed at this scale. |
| **Power BI / Tableau / Qlik** | ❌ Not used | **Streamlit + Plotly *is* the BI layer** — 11 interactive views, already built. Adding a BI tool would duplicate it. |
| **JIRA / Asana / Azure DevOps** | ❌ Not used by the code | Project-management choice, not a technical dependency. Use whatever the team already has. |
| **Any AI / LLM service (OpenAI, Bedrock, etc.)** | ❌ Not used at runtime | The scoring engine is a **transparent weighted index — deliberately, not an LLM**. No inference cost, no API keys, no model governance. *(LLM assistance was used to write code during development; the product itself calls no model.)* |
| **IQVIA claims / LRx / OCE data** | ❌ Not used today | The MVP is 100% public data. Claims are the **Phase 2 ask** — see §6. |
| **Veeva CRM** | ❌ Not integrated yet | Today the HCP list exports as CRM-ready CSV. Direct push is Phase 2. |
| **Kubernetes / heavy infra** | ❌ Not needed | Single Streamlit process; a small container or Streamlit Cloud suffices. |

---

## 6. Phase 2 — start these conversations NOW (long lead time)

These are the items where "identify access well in advance" genuinely matters.
None block MVP development; all block the *validation* milestone.

| # | What | Why it's needed | Who to engage | Typical lead time |
|---|---|---|---|---|
| 1 | **Backdated IQVIA claims extract** — one condition, 1–2 states, historical window | The only way to close the outcome-validation gap: did flagged counties actually surface more diagnoses? Public data cannot answer this (documented, with a failed test to prove it). | Data governance + the relevant therapy-area data owner | **Weeks–months** (DUA, scope approval) |
| 2 | **Legal / privacy sign-off** | Confirms the aggregate-only, no-PHI design and clears the claims extract | Legal, Privacy, Compliance | **Weeks** |
| 3 | **Secure environment for claims** | Claims cannot live in the public repo — needs an approved analytics environment | IT / InfoSec | Weeks |
| 4 | **Design-partner brand team** | A pilot needs a real brand and a real budget owner | Commercial leadership | Weeks |
| 5 | **Veeva CRM integration** | Push HCP target lists into the field-force workflow | CRM/Commercial Ops | Weeks |
| 6 | **Internal hosting + SSO** | Required if the tool moves from public demo to internal use | IT / Platform | Weeks |

---

## 7. Quick start (verify your environment in 10 minutes)

```bash
git clone <repo-url> && cd silent-patient-pool-finder
pip install -r requirements.txt
python -m streamlit run src/output/dashboard.py     # works immediately — scored data is committed
```

Optional, to regenerate data from source:

```bash
export CENSUS_API_KEY=<your free key>
python3 src/ingestion/ingest_real_data.py     # counties  (~3–4 min)
python3 src/ingestion/ingest_zcta_data.py     # ZIP codes (~8 min)
python3 src/ingestion/ingest_hcp_data.py      # HCPs      (~5–10 min, 509 MB)
```

Verify the environment is healthy:

```bash
python -m pytest tests/ -q                          # 64 tests
python src/validation/verify_reproducible.py        # proves committed data matches the code
```

---

## 8. One-page summary for the pre-read

> **To build and run SPPF today you need:** Python 3.9+, GitHub, a free Census
> API key, and outbound internet to ten public `.gov`/`.org` domains. Nothing
> else. No paid licences, no cloud data platform, no BI tool, no LLM service, no
> client data, no PHI.
>
> **The only items with real lead time are Phase 2:** a backdated IQVIA claims
> extract and its legal/DUA approval, a secure environment to analyse it in, and
> a design-partner brand team. Those should start moving now; everything else is
> same-day.

---
*Derived from the repo as built: `requirements.txt`, the ingestion modules'
actual network calls, `docker-compose.yml`, CI workflow, and the secret
templates. If a tool is not listed in §1–§4, the codebase does not use it.*

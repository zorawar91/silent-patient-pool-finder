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

---
---

# Part B — Production: selling this as a client solution

Everything above covers building and demoing the MVP. This part covers what
changes when SPPF is **sold to a client and run as a product**. The distinction
matters for planning: the MVP is genuinely strong, but a demo architecture and a
commercial SaaS are different animals, and a few items here have long lead times
or are outright blockers.

## B0. What already transfers — bank these

Unusually for a hackathon build, several things are already at enterprise
standard and should be *sold*, not rebuilt:

- **Provenance page** — every number traced to a sourced, vintage-stamped origin.
- **Fail-loud QA gates** — pipelines refuse to ship corrupt or silently degraded data.
- **Reproducibility guard** — CI proves the published numbers are the output of
  the published code. This is a genuine differentiator with a diligence-minded buyer.
- **PHI-free, public-data architecture** — the single biggest commercial asset
  (see B3); it compresses procurement cycles dramatically.
- **Measurement engine with a documented null result** — evidence the tool
  doesn't flatter its own campaigns.

## B1. The architectural fork — what breaks under real clients

| Today (demo) | Why it breaks commercially | Production need |
|---|---|---|
| **No authentication at all** — anyone with the URL sees everything | Non-starter for a paid product | SSO (SAML/OIDC), RBAC, session management |
| **No multi-tenancy** — one shared dataset, no client isolation | Client A's campaign definitions and territories would be visible to Client B | Tenant model + row-level isolation + per-tenant config |
| **Streamlit single process**, full script re-run per interaction | Not designed for many concurrent users or per-tenant state; a demo tool, not an app server | Either managed Streamlit at scale, or split into API (FastAPI) + web frontend |
| **Data committed to git** (Parquet in the repo) | Great for a zero-setup demo; wrong for a product — no access control, no versioning per client, repo bloat | Managed store (Postgres/object storage) with vintage versioning |
| **Manual ingestion** (`python3 ingest_*.py`) | Nobody will run three scripts by hand every release | Orchestrated, scheduled pipelines (Airflow / Dagster / Step Functions / GitHub Actions cron) with alerting |
| **No audit log** | Enterprise buyers ask "who exported that list, when?" | Structured audit trail on exports and data access |

**Decision to make early:** keep Streamlit (fastest, adequate for tens of
concurrent internal users, weakest on multi-tenancy) versus re-platform the
frontend (React/Next + FastAPI) once client count justifies it. Deferring this
is fine; deciding it *late*, after selling, is expensive.

## B2. ⚠️ Data licensing — resolve before any sale

**This is the one genuine blocker, and it is cheap to resolve now and expensive
to discover later.**

- **US federal sources (CDC, Census, CMS, HRSA, USDA)** — works of the US
  federal government, effectively public domain. Commercial redistribution of
  derived products is normally unproblematic; attribution is good practice.
- **County Health Rankings (RWJ Foundation / University of Wisconsin PHI)** —
  the **only non-federal source in the stack**. It is a private foundation
  product with its own terms of use. *Selling* a commercial product built on it
  is a different question from *using* it for research.

**Action:** have Legal confirm commercial-redistribution rights for CHR (and
capture attribution obligations for all sources). If CHR terms prove restrictive
there are two clean outs — drop it (it feeds Access-to-Care and an SDoH backup,
both of which have federal substitutes) or license it. Either way, **decide
before the first contract**, not after.

## B3. The compliance fork — the moment claims data enters

Today's posture is a commercial asset: **no PHI, no patient-level data, no DUA,
aggregate public data only.** That is why procurement is light and why the
security review is short. Protect it deliberately.

The instant IQVIA claims (or any patient-level data) enter the product, the
entire posture changes:

| Dimension | Today (public data) | With claims data |
|---|---|---|
| Data classification | Public, aggregate | Sensitive / potentially PHI |
| Agreements | None | **BAA**, DUA, data-processing terms |
| Environment | Any host | Secure, access-controlled enclave; encryption at rest and in transit |
| De-identification | N/A | Safe Harbor or Expert Determination, documented |
| Security review | Light | Full InfoSec + Privacy review |
| Sales cycle | Weeks | Quarters |

**Recommended architecture:** keep the **public-data product and the
claims-calibrated layer separable**. Sell the public-data platform broadly and
procurement-light; run claims work in a controlled environment and feed only
*aggregate, non-identifying calibration outputs* back into the product. Blending
them into one system would forfeit the biggest commercial advantage the product
has.

**Scope note worth stating in the contract:** SPPF is a **population-level
commercial planning tool — not clinical decision support and not a diagnostic
device.** It targets geographies and program types, never individual patients.
Holding that line keeps it outside medical-device and clinical-validation
regimes; drifting toward patient-level recommendations would pull it in.

## B4. Security & assurance the buyer will ask for

| Item | Notes |
|---|---|
| **SSO / SAML / OIDC** | Table stakes for enterprise |
| **RBAC** | Viewer / analyst / admin at minimum; per-brand or per-geography entitlements if sold modularly |
| **Audit logging** | Access + export events, retained |
| **SOC 2 Type II** | Usually demanded of a SaaS vendor. **6–12 months** including observation window — start early if selling externally |
| **Penetration test** | Annual, plus before first major client |
| **Vulnerability & dependency scanning** | Dependabot/Snyk + SBOM; the stack is all OSS |
| **Secrets management** | Vault / cloud secret manager — not `.env` files |
| **Encryption** | TLS in transit (already enforced), encryption at rest |
| **DR / backup** | Defined RPO/RTO; the data is small, so this is cheap |
| **GDPR** | Only if the product expands to EU users/data |

*If SPPF ships as an internal IQVIA offering rather than standalone SaaS, most
of this inherits from existing enterprise infrastructure — confirm which path
early, because it changes the workload by an order of magnitude.*

## B5. Data lifecycle — a product concern, not just a pipeline

Clients will ask questions the MVP doesn't yet answer:

- **Refresh cadence** — CDC PLACES is annual; CMS MA is monthly. Publish an
  expected refresh calendar.
- **Vintage pinning** — a client who built a plan on the 2025 vintage must be
  able to reproduce it after you ship 2026. Version data releases; let clients
  pin one.
- **Change communication** — when a refresh moves a county out of Priority, the
  client needs a changelog, not a surprise. *(We lived this: a data refresh moved
  Priority from 24 to 20 counties.)*
- **Backfill/restatement policy** — what happens when a source republishes.

The existing **build manifest + reproducibility guard is exactly the machinery
this needs** — promote it from an internal check to a client-facing feature.

## B6. Operations

- **Environments:** dev → staging → production (currently only local + demo).
- **Release process:** semantic versioning for both code *and* data vintages.
- **Monitoring/alerting:** uptime, error rates, pipeline failures, ingest freshness.
- **Support:** SLA tiers, incident response, on-call rota, status page.
- **Onboarding:** client training, documentation, sandbox/demo tenant.

## B7. Commercial infrastructure

Non-engineering, but blocks revenue: MSA + DPA templates, pricing/packaging and
entitlement enforcement, usage metering if priced per brand/seat, order-to-cash,
and a defined support model. Existing strategy docs assume **$25–75k pilots** and
**$150–400k/yr platform licences** — entitlements should be enforceable in the
product, not just in the contract.

## B8. Phasing — what to do when

| Gate | Focus | Key additions |
|---|---|---|
| **Now — MVP / ideathon** | Prove the concept | Nothing beyond Part A |
| **Pilot (1 design partner)** | Prove outcome validity | SSO, basic RBAC, audit log, managed hosting, scheduled refresh, **CHR licensing answer**, claims enclave + BAA |
| **First paying client** | Make it sellable | Multi-tenancy, entitlements, staging env, monitoring/SLA, support model, pen test |
| **Scale (multi-client SaaS)** | Make it durable | SOC 2 Type II, frontend re-platform decision, vintage management, usage metering, DR |

## B9. Roles typically needed beyond the current team

Data engineer (pipeline orchestration) · Platform/DevOps (hosting, CI/CD,
monitoring) · Security/compliance lead (SOC 2, pen test, reviews) · Frontend
engineer (*only if* re-platforming from Streamlit) · Product owner · Client
success/onboarding.

## B10. Honest summary for leadership

> The MVP is production-*grade* in the places that usually rot — data quality,
> provenance, reproducibility, test coverage — and production-*naive* in the
> places a demo never exercises: authentication, multi-tenancy, orchestration,
> and hosting. That is the right way round, and it is a far cheaper gap to close
> than the reverse.
>
> Two items should start immediately because they are not engineering problems:
> **(1) legal confirmation of commercial redistribution rights for County Health
> Rankings**, and **(2) the claims-data pathway** (BAA, DUA, secure environment).
> Everything else is sequenced, well-understood build work.

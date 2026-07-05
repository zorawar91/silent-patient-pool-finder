# SPPF Full Project Audit — July 2026

Scope: all source files, config, docs, dashboard UI copy, scoring logic, and ingestion pipeline.

---

## Fixed in this audit

### 1. Sidebar disclaimer — factual error
**File:** `src/output/dashboard.py`

Old text: *"All scoring uses synthetic & open data"*
New text: *"Data: 5 real public health sources"*

Reason: All 5 sources (CDC PLACES, Census ACS, CMS MA, HRSA, County Health Rankings) are now real. The word "synthetic" was factually wrong.

---

### 2. Payer Landscape — stale run command
**File:** `src/output/dashboard.py`

Old: `Run \`python3 run.py\` to load real CMS county-level payer data.`
New: `Run \`python3 ingest_real_data.py\``

Reason: `run.py` is the legacy ML pipeline. The real data pipeline is `ingest_real_data.py`.

---

### 3. `run.py` — wrong priority threshold in log message
**File:** `run.py`, line 108

Old: `Priority counties (score≥70):`
New: `Priority counties (score≥55):`

Reason: Threshold was calibrated down to 55 (max observable score ~60–62 with 5 real sources). The 70 threshold was from the original design assuming 7 fully-populated data sources.

---

### 4. `dimensions.yaml` — stale priority threshold
**File:** `config/dimensions.yaml`

Old: `high_opportunity_threshold: 70`
New: `high_opportunity_threshold: 55`

Reason: Same calibration issue — the config declared 70, the code used 55. Now consistent.

---

### 5. `dimensions.yaml` — mismatched intervention label
**File:** `config/dimensions.yaml`

Old: `label: "Digital Health Outreach"`
New: `label: "Digital Health Program"`

Reason: The dashboard code and all UI copy uses "Digital Health Program". The YAML had a different name, creating a silent mismatch.

---

### 6. `conditions.yaml` — condition name mismatch
**File:** `config/conditions.yaml`

Old: `name: "Hyperthyroidism"`
New: `name: "Hypothyroidism"`

Reason: The dashboard was corrected in the previous session to display "Hypothyroidism" throughout the UI. The YAML still said "Hyperthyroidism", making the config inconsistent with the displayed name.

**Note (design decision still open):** The underlying ICD-10 codes in conditions.yaml (E05.x) are for Hyperthyroidism, not Hypothyroidism. Levothyroxine in `chronic_rx_codes` is a Hypothyroidism drug. If the intended condition is Hypothyroidism, the ICD codes should be updated to E03.x and methimazole/PTU removed. If it's Hyperthyroidism, the dashboard label needs to revert. This requires a clinical/product decision.

---

### 7. `dashboard.py` — dead code removed
**File:** `src/output/dashboard.py`

Removed `DIM_SHORT` dict (9 lines). It was defined at line 71 and was byte-for-byte identical to `DIM_LABELS`. No references to `DIM_SHORT` existed anywhere in the codebase.

---

### 8. `dashboard.py` — unnecessary `pass` removed
**File:** `src/output/dashboard.py`, end of `main()`

Removed orphaned `pass` statement with a misleading inline comment that referenced CSS tooltip behavior.

---

### 9. `ingest_real_data.py` — county count in header comment
**File:** `ingest_real_data.py`

Old: `"3,143-county panel"` (header + log message)
New: `"3,144-county panel"`

Reason: Actual pipeline output is 3,144 counties. The header comment was off by one.

---

## Findings that require a decision — not auto-fixed

### A. `conditions.yaml` — ICD code / drug mismatch (clinical accuracy)

The condition keyed as `hyperthyroidism` contains:
- ICD-10 codes E05.x = Hyperthyroidism ✓
- `levothyroxine` in `chronic_rx_codes` = Hypothyroidism drug ✗
- `methimazole`, `propylthiouracil` = Hyperthyroidism drugs ✓
- `prevalence_prior_us: 0.013` = matches Hyperthyroidism (1.3%) ✓
- Dashboard label: "Hypothyroidism" (as of previous session fix) ✓

The config is internally inconsistent. Levothyroxine should only appear in a Hypothyroidism condition definition. **Recommendation:** decide which condition is intended, then align ICD codes, drug lists, prevalence prior, and dashboard label together.

---

### B. `dimensions.yaml` — aspirational data sources listed as if live

Multiple dimensions list data sources that are not actually connected:
- `cms_hospitalizations`, `cms_part_d`, `cms_part_b` (Diagnosis Gap, Access, Commercial Readiness)
- `usda_food_atlas` (Social Determinants)
- `hrsa_ahrf` (Access, Commercial Readiness) — HRSA data IS live, but via HPSA designation, not AHRF

These are architectural aspirations, not current reality. The YAML is documentation, but it could mislead a new engineer about what's actually wired. **Recommendation:** mark aspirational sources with a `# planned` comment or move them to a separate `future_sources` key.

---

### C. `requirements.txt` — unused ML dependencies

`xgboost>=2.0`, `shap>=0.44`, and `joblib>=1.3` are present but unused by `ingest_real_data.py` or `dimension_scorer.py`. They're only used by `run.py` (the legacy ML pipeline). These add ~200MB to a fresh install.

**Recommendation:** If `run.py` is being retired in favor of `ingest_real_data.py`, remove these three packages. If `run.py` is still supported, keep them and add a comment.

---

### D. `README.md` — County Health Rankings download URL is version-pinned

Line 108 links to `analytic_data2025_v3.csv` — a specific versioned filename. This URL will break when 2026 data is released.

**Recommendation:** Change to a general instruction: *"Visit countyhealthrankings.org → Data & Documentation → Download the current analytic data file, save to `data/open/analytic_data_chr.csv`."*

---

## Status after this audit

| Category | Issues found | Auto-fixed | Decision needed |
|---|---|---|---|
| Factual errors in UI | 2 | 2 | 0 |
| Stale config values | 2 | 2 | 0 |
| Label mismatches | 2 | 2 | 0 |
| Dead code | 2 | 2 | 0 |
| Clinical accuracy | 1 | 0 | 1 |
| Documentation accuracy | 2 | 0 | 2 |
| Dependencies | 1 | 0 | 1 |
| **Total** | **12** | **9** | **4** |

---

*Generated July 2026. Re-run this audit whenever data sources or scoring logic change.*

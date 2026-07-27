# Routes — SPPF Dashboard

**No URL router.** This is a single-page Streamlit app: one entry point
(`src/output/dashboard.py`), one URL, and "routing" is a string dispatch in
`dashboard.main()` on the view name returned by the sidebar radios. There are no
route files, no path params, no deep links — selecting a view re-runs the script
and renders exactly one view module. Every view uses the same layout (sidebar +
`.block-container`); see `layouts.md`.

Launch: `streamlit run src/output/dashboard.py` (or `make dashboard` / `run.py`).

## The dispatch (`src/output/dashboard.py::main`)

```python
if   view == "Insights & Actions":       view_insights(scores, scores_long, condition, cond_label, state, top_n)
elif view == "Market Overview":          view_market_overview(scores, scores_long, condition, cond_label)
elif view == "7-Dimension Analysis":     view_7d_analysis(scores, state, top_n, condition, cond_label)
elif view == "Investment Planner":       view_investment_planner(scores, scores_long, condition, state, top_n, tier_filter)
elif view == "Geographic Intelligence":  view_geographic(scores, scores_long, condition, state, geojson)
elif view == "State Drill-Down":         view_state_drilldown(scores, scores_long, condition, cond_label, state, county, top_n)
elif view == "Payer Landscape":          view_payer_landscape(scores, state, top_n)
elif view == "ZIP & Territory":          view_zip_territory(zip_scores, scores, state, condition)
elif view == "HCP Targeting":            view_hcp_targeting(load_hcp_data(), state)
elif view == "Campaign Measurement":     view_campaign_measurement(scores)
elif view == "Data Provenance":          view_data_provenance(scores)
```

## View map

Navigation is two-tier (see `src/output/sidebar.py`): **Decision Views** are always
visible; **Analyst & Audit** sits in a collapsed expander.

| Nav label | Group | Entry file | Sidebar filters it consumes |
|---|---|---|---|
| ⚡ Insights & Actions **(default landing view)** | Decision | `src/output/views/insights.py` | condition, state |
| 💡 Investment Planner | Decision | `src/output/views/investment_planner.py` | condition, state, top_n, tier |
| 🗺️ Geographic Intelligence | Decision | `src/output/views/geographic.py` | condition, state |
| 📊 Market Overview | Analyst & Audit | `src/output/views/market_overview.py` | condition |
| 🔭 7-Dimension Analysis | Analyst & Audit | `src/output/views/seven_dim.py` | condition, state, top_n |
| 📍 State Drill-Down | Analyst & Audit | `src/output/views/state_drilldown.py` | condition, state, county |
| 💳 Payer Landscape | Analyst & Audit | `src/output/views/payer_landscape.py` | state, top_n |
| 🗂️ ZIP & Territory | Analyst & Audit | `src/output/views/zip_territory.py` | state |
| 🎯 HCP Targeting | Analyst & Audit | `src/output/views/hcp_targeting.py` | state |
| 📐 Campaign Measurement | Analyst & Audit | `src/output/views/campaign_measurement.py` | none (in-view county pickers) |
| 📋 Data Provenance | Analyst & Audit | `src/output/views/provenance.py` | none |

Filters not listed for a view render **disabled** (greyed) in the sidebar, and
their values are reset before reaching the view.

## What each key view renders

**Insights & Actions** (`insights.py`, 367 lines) — the landing page. Banner
("Where to move next"), then auto-synthesised recommendations: top 3 action
counties as bordered cards (rank, tier pill, score /100, est. silent pool,
recommended program), payer lead, a counterintuitive find (high score / small
pool), the most underserved market (widest Diagnosis-Gap-minus-Access spread),
fastest-growing markets, and a `.tbl` of candidates.

**Investment Planner** (`investment_planner.py`, 201) — filtered county plan
with program mix, screening-yield benchmarks, a `.tbl`, and a CSV export.

**Geographic Intelligence** (`geographic.py`, 172) — 4 KPI cards, then a
`[2.8, 1]` split: county choropleth (Plotly, shaded by the selected condition's
score) beside Top States and By-Condition cards.

**Market Overview** (`market_overview.py`, 205) — national banner with the total
estimated undiagnosed pool (computed, not published figures), a 5-card KPI row,
three condition cards, score distribution histogram + intervention mix
(`[1.4, 1]`), and the illustrative patient-identification funnel.

**7-Dimension Analysis** (`seven_dim.py`, 287) — national radar, per-dimension
`.dim-bar` breakdown with a national-average marker and delta, county heatmap,
and an interactive weight-sensitivity panel (`load_weights`, `recompute_composite`,
`rank_stability` from `src/features/dimension_scorer.py`).

**State Drill-Down** (`state_drilldown.py`, 352) — single-state intelligence with
an optional county deep-dive scorecard, county `.tbl`, and CSV export.

**Payer Landscape** (`payer_landscape.py`, 147) — 4 payer-mix KPI cards
(first is `.card-blue`), MA vs. opportunity scatter beside a national payer-mix
chart (`[1.5, 1]`), and top-MA-county rankings.

**ZIP & Territory** (`zip_territory.py`, 423 — largest view) — ZCTA-level
opportunity map, a paste-your-ZIPs territory builder, and ZIP rankings.

**HCP Targeting** (`hcp_targeting.py`, 124) — banner with prescriber count, 3 KPI
cards, and the detailing-list `.tbl`. Has a distinct empty state when the target
list hasn't been generated.

**Campaign Measurement** (`campaign_measurement.py`, 151) — matched-control
diff-in-diff on CDC PLACES diagnosed-prevalence change. In-view county pickers
(`[2, 1, 1]`), a guard card requiring ≥5 campaign counties, a 4-card result row
(effect, significance, …), and a covariate-balance `.tbl`.

**Data Provenance** (`provenance.py`, 161) — source-of-truth table, output
freshness, confidence grades, and the live QA-gate report in expanders.

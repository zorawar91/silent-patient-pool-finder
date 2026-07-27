# Pages — dependency trees

Streamlit app, so a "page" is a view module under `src/output/views/`. Every
page is rendered inside the same shell, so **the shell files below are implicit
dependencies of every page** and are listed once instead of repeated in each tree:

```
Shell (all pages):
- src/output/dashboard.py          entry point, page config, view dispatch
  - src/output/theme.py            tokens + inject_css()  ← ALWAYS include for any design task
  - src/output/sidebar.py          persistent nav + global filters
    - src/output/theme.py
  - src/output/data.py             loaders + shape helpers (no visual bearing except tier/score semantics)
    - src/features/dimension_scorer.py   (DIM_ORDER, load_weights, _norm)
  - src/output/views/__init__.py   re-exports the 11 view functions
```

`src/output/content.py` (322 lines) holds all tooltip copy —
`METRIC_TOOLTIPS`, `DIM_TOOLTIPS` — and imports `load_weights` +
`DIM_LABELS`. Every page imports it. It's text, not layout: include it when the
design needs real tooltip copy, skip it to save payload otherwise.

**Context-file recipe for any single page:**
`src/output/theme.py` (always) + the page's own view file + `src/output/content.py`
(if tooltip copy matters). `theme.py` is 448 lines and safely fits whole; the
stylesheet starts at `theme.py:143`. `data.py` and `dimension_scorer.py` are
data-shape only — drop them from design context.

---

## ⚡ Insights & Actions (default landing view)
Entry: `src/output/views/insights.py` (367 lines)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               _ensure_dims, _ensure_payer, _opp_score,
                                   condition_score, condition_tier, tier_basis_label
- src/output/theme.py              AMBER, BLUE, BORDER, DARK, G_DARK, G_MID, G_PALE,
                                   INTERV_META, MUTED, PURPLE, RED, STATE_ABBREV, _iicon
```

## 💡 Investment Planner
Entry: `src/output/views/investment_planner.py` (201)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               _ensure_dims, _get_intervention, _has_dims,
                                   _opp_score, condition_score, condition_tier
- src/output/theme.py              BORDER, COND_META, DARK, DIM_COLORS, DIM_LABELS,
                                   G_DARK, G_MID, INTERV_META, MUTED,
                                   _iicon, _score_bar, _stplot, _tier_pill
```

## 🗺️ Geographic Intelligence
Entry: `src/output/views/geographic.py` (172)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               _cond_proxy, _ensure_dims, _get_intervention,
                                   _opp_score, condition_score, condition_tier, tier_basis_label
- src/output/theme.py              AMBER, BG, BORDER, COND_META, DARK, G_DARK,
                                   G_LIGHT, G_PALE, MUTED, RED, _iicon, _stplot
- (runtime) load_geojson() from src/output/data.py — county boundaries for the choropleth
```

## 📊 Market Overview
Entry: `src/output/views/market_overview.py` (205)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               condition_score, _cond_proxy, _ensure_dims,
                                   _get_intervention, _opp_score, condition_tier
- src/output/theme.py              AMBER, BLUE, BORDER, COND_META, DARK, G_DARK,
                                   G_LIGHT, G_MID, INTERV_META, MUTED, RED, _iicon, _stplot
```

## 🔭 7-Dimension Analysis
Entry: `src/output/views/seven_dim.py` (287)
```
- src/features/dimension_scorer.py load_weights, rank_stability, recompute_composite
- src/output/content.py            DIM_TOOLTIPS, METRIC_TOOLTIPS
- src/output/data.py               _ensure_dims, _has_dims, condition_score
- src/output/theme.py              DIM_COLORS/DIM_ICONS/DIM_LABELS/DIM_SHORT + tokens, _iicon, _stplot
```

## 📍 State Drill-Down
Entry: `src/output/views/state_drilldown.py` (352)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               _ensure_dims, _opp_score, condition_score, condition_tier
- src/output/theme.py              tokens, DIM_*, _iicon, _score_bar, _stplot, _tier_pill
```

## 💳 Payer Landscape
Entry: `src/output/views/payer_landscape.py` (147)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/data.py               _ensure_dims, _ensure_payer, _opp_score
- src/output/theme.py              AMBER, BLUE, PURPLE, G_* tokens, _iicon, _stplot
```

## 🗂️ ZIP & Territory
Entry: `src/output/views/zip_territory.py` (423 — largest view)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/theme.py              tokens, _iicon, _stplot
- (runtime) load_zip_data() from src/output/data.py — ZCTA-level scores
```

## 🎯 HCP Targeting
Entry: `src/output/views/hcp_targeting.py` (124)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/theme.py              tokens, _iicon, _score_bar, _tier_pill
- (runtime) load_hcp_data() from src/output/data.py — prescriber rows; empty state when absent
```

## 📐 Campaign Measurement
Entry: `src/output/views/campaign_measurement.py` (151)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/theme.py              BLUE, G_DARK, MUTED, STATE_ABBREV, _iicon
- src/features/campaign_measurement.py  (diff-in-diff computation, at runtime)
```

## 📋 Data Provenance
Entry: `src/output/views/provenance.py` (161)
```
- src/output/content.py            METRIC_TOOLTIPS
- src/output/theme.py              G_DARK, MUTED, _iicon
- src/quality/qa_gate.py, src/quality/provenance.py  (QA-gate report, at runtime)
```

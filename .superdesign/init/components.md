# Components — SPPF Dashboard

There is **no component library and no component directory**. This is a
Streamlit app: shared UI primitives exist in two forms only —

1. **Python helpers** in `src/output/theme.py` that return HTML strings, and
2. **CSS classes** defined in `theme.py::inject_css()` that views compose by
   writing inline HTML into `st.markdown(..., unsafe_allow_html=True)`.

To reproduce this UI, reproduce the class vocabulary below. Every card, KPI
tile, pill, bar, and table on every page is built from it.

---

## 1. Python helpers (full source, `src/output/theme.py`)

### `_iicon(tip, pos, tip_cls)` — circular info badge with CSS tooltip
Absolute top-right of the nearest positioned container by default. `pos=""`
renders inline. `tip_cls="tip-r"` pushes the bubble right (leftmost columns),
`tip_cls="tip-l"` puts it left at mid-height (banner/inline icons).

```python
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
```

Tooltip copy comes from `src/output/content.py` (`METRIC_TOOLTIPS`, `DIM_TOOLTIPS`).

### `_stplot(fig, **kwargs)` — Plotly wrapper enforcing chart typography/axes
Every chart in the app goes through this, so charts share one axis style.

```python
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
```

### `_score_bar(val, color)` — inline 0–100 score bar + numeral (table cells)

```python
def _score_bar(val, color=G_MID) -> str:
    pct = min(float(val or 0), 100)
    return (f'<div class="sbar-wrap"><div class="sbar-bg">'
            f'<div class="sbar-fill" style="width:{pct:.0f}%;background:{color};"></div>'
            f'</div><span class="snum">{pct:.0f}</span></div>')
```

### `_tier_pill(tier)` — Priority / Emerging / Developing badge

```python
def _tier_pill(tier) -> str:
    tier = str(tier) if pd.notna(tier) else "Developing"
    cls  = {"Priority": "tier-priority", "Emerging": "tier-emerging"}.get(tier, "tier-developing")
    return f'<span class="pill {cls}">{tier}</span>'
```

---

## 2. CSS primitives (defined in `inject_css()`)

### `.card` — white surface, the default container
`background #FFFFFF · border 1px #C8DDEF · radius 10px · padding .8rem 1rem ·
box-shadow 0 1px 2px rgba(0,0,0,.04) · position:relative`
Variant convention: a coloured 3px `border-top` (or `border-left`) encodes
category/tier — e.g. `border-top:3px solid #EF4444` for Priority.

### `.card-dark` — gradient navy KPI tile
`linear-gradient(135deg,#003087,#0077C8)`, no border, white text, radius 10px.
Used for the first/primary KPI in a row.

### `.card-blue` — muted gradient tile
`linear-gradient(135deg,#1E3A5F,#2D6A9F)`, white text. Used on Payer Landscape.

### `.banner` — page header block (every view opens with one)
`linear-gradient(135deg,#003087 0%,#0077C8 55%,#00A9E0 100%)`, radius 16px,
padding 1.4rem 2rem, white text, margin-bottom 1.2rem. Children:
`.banner-title` (1rem/700, opacity .8) · `.banner-stat` (2.4rem/900) ·
`.banner-note` (.75rem, opacity .65).

### `.ch` — lightweight chart/section header (no white box)
`border-left:3px solid #00A9E0 · padding .35rem .75rem · background rgba(0,169,224,.04)
· border-radius 0 6px 6px 0`. Wraps a `.sec-head` + `.sec-sub`.

### Text primitives
`.big-num` (2rem/800, navy) · `.big-num-w` (same, white) ·
`.label` (.7rem/700, muted) · `.label-w` (white 60%) ·
`.sub` (.74rem, cyan) · `.sub-w` (white 70%) · `.sub-muted` (muted) ·
`.sec-head` (1rem/700, navy) · `.sec-sub` (.76rem, muted).

### `.pill` + tier modifiers
`inline-block · padding .18rem .65rem · radius 20px · .72rem/700`;
`.tier-priority` `#FEE2E2`/`#991B1B` · `.tier-emerging` `#FEF3C7`/`#92400E` ·
`.tier-developing` `#DEEEF9`/`#003087`.

### `.tbl` — the data table
`width 100% · border-collapse collapse · .83rem`.
`th`: `#F0F6FC` fill, muted `.67rem/700`, 2px `#C8DDEF` bottom border, left-aligned.
`td`: `.55rem .75rem` padding, 1px `#C8DDEF` bottom border, navy text, middle-aligned.
Last row loses its border; `tr:hover td` fills `#F0F6FC`.

### `.sbar-*` — score bar (produced by `_score_bar`)
`.sbar-wrap` flex/gap .4rem · `.sbar-bg` 5px track `#C8DDEF`, radius 3px ·
`.sbar-fill` coloured · `.snum` .79rem/700 navy, min-width 2rem, right-aligned.

### `.dim-*` — 7-dimension bar row
`.dim-bar` flex, gap .5rem, `position:relative`, `padding-right:1.4rem` (room
for the info badge) · `.dim-icon` .95rem/1.4rem wide · `.dim-name` .73rem/600,
fixed 7.5rem · `.dim-bg` 7px track · `.dim-fill` coloured · `.dim-num` .73rem/700.

### `.info-tip` — the info badge/tooltip (see `_iicon`)
15px circle, `linear-gradient(135deg,#0077C8,#00A9E0)`, white italic serif "i",
`cursor:help`. Bubble: `::after` with `content:attr(data-tip)`, `#0A1F3C` fill,
240px wide, radius 10px, 8px below the icon, fades in on hover with a 6px caret
(`::before`). Modifiers `.tip-r` / `.tip-l` reposition it. Streamlit's column and
block wrappers are given `overflow: visible !important` so the bubble can escape.

---

## 3. Composition patterns (verbatim from views)

### KPI card row — 4–5 `st.columns`, first one dark
```python
c1, c2, c3, c4 = st.columns(4)
c1.markdown(f'<div class="card-dark"><div class="label-w">Counties Mapped</div>{_iicon(METRIC_TOOLTIPS["counties_mapped"], tip_cls="tip-r")}<div class="big-num-w">{len(filtered):,}</div><div class="sub-w">{filtered["state_name"].nunique()} states</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="card" style="border-top:3px solid {RED};"><div class="label">Priority</div>{_iicon(METRIC_TOOLTIPS["priority_tier"])}<div class="big-num" style="color:{RED};">{priority_n}</div><div class="sub" style="color:{RED};">{tier_note}</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="card" style="border-top:3px solid {AMBER};"><div class="label">Emerging</div>{_iicon(METRIC_TOOLTIPS["emerging_tier"])}<div class="big-num" style="color:{AMBER};">{emerging_n}</div><div class="sub" style="color:{AMBER};">Plan &amp; monitor</div></div>', unsafe_allow_html=True)
c4.markdown(f'<div class="card"><div class="label">Avg Score ({cond_label})</div>{_iicon(METRIC_TOOLTIPS["avg_opp_score"])}<div class="big-num">{filtered[score_col].mean():.0f}</div><div class="sub-muted">this view</div></div>', unsafe_allow_html=True)
```

### Page banner
```python
st.markdown(f"""
<div class="banner">
  <div class="banner-title">⚡ Insights &amp; Actions — {cond_label} · {geo_label}</div>
  <div class="banner-stat">Where to move next</div>
  <div class="banner-note">
    Auto-synthesised from 7-dimension scoring across {len(filtered):,} counties ·
    {n_priority} Priority  ·  {n_emerging} Emerging
  </div>
</div>""", unsafe_allow_html=True)
```

### Section header above a chart
```python
st.markdown(f"""<div class='ch'>
  <div class='sec-head'>🎯 Top 3 Counties to Act On Now {_iicon(METRIC_TOOLTIPS["opportunity_score"], pos="")}</div>
  <div class='sec-sub'>Highest {'composite opportunity' if condition == 'overall' else cond_label + ' risk'} scores in current filter — these are your first calls · tier = {tier_basis_label(condition, cond_label)}</div>
</div>""", unsafe_allow_html=True)
```

### Entity card (top-3 county card, `insights.py`)
```python
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
  ...
</div>""", unsafe_allow_html=True)
```

### Data table (`state_drilldown.py`) — rows built as HTML, then one markdown call
```python
st.markdown(f"""
<table class="tbl">
  <thead><tr>
    <th>#</th><th>County</th><th>Population</th>
    <th>Opp. Score</th><th>Risk ({cond_label})</th>
    <th>Tier</th><th>Program</th><th>Est. Pool</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)
```
Cells use `_score_bar(...)` and `_tier_pill(...)`. Tables are usually followed by
`st.download_button(...)` for a CSV export of the same rows.

### 7-dimension bar row (`seven_dim.py`) — with a national-average marker
```python
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
```

### Empty state
```python
st.markdown("""
<div class="card" style="padding:2rem;text-align:center;">
  ...
  <div class="sec-head">HCP target list not yet generated</div>
  ...
</div>""", unsafe_allow_html=True)
```

---

## 4. Streamlit widgets in use (native, restyled by CSS only)
`st.columns` (layout grid) · `st.radio` (nav) · `st.expander` (nav group, QA
gate report) · `st.selectbox` / `st.multiselect` / `st.slider` (filters) ·
`st.tabs` (restyled: inactive `#5A7A9B`, active `#003087` bold) ·
`st.plotly_chart` (always via `_stplot`) · `st.download_button` (CSV exports) ·
`st.caption`, `st.warning`, `st.metric`-free — KPIs are hand-built cards.

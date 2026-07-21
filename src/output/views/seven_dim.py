from __future__ import annotations
# View: 7-Dimension Analysis — national radar, dimension breakdown bars,
# county heatmap, and the interactive weight-sensitivity panel.

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.features.dimension_scorer import load_weights, rank_stability, recompute_composite
from src.output.content import DIM_TOOLTIPS, METRIC_TOOLTIPS
from src.output.data import _ensure_dims, _has_dims, condition_score
from src.output.theme import (
    BLUE, BORDER, DARK, DIM_COLORS, DIM_ICONS, DIM_LABELS, DIM_SHORT,
    G_DARK, MUTED, STATE_ABBREV, _iicon, _stplot,
)

# Slider defaults come from the same config the scorer uses, expressed as
# integer percentages (e.g. 0.25 → 25).
_DEFAULT_WEIGHTS = {k: int(round(v * 100)) for k, v in load_weights().items()}


def view_7d_analysis(scores: pd.DataFrame, state: str, top_n: int,
                      condition: str = "overall", cond_label: str = "All Conditions"):
    using_fallback = not _has_dims(scores)
    scores = _ensure_dims(scores)
    if using_fallback:
        st.info("📊 Showing **estimated** dimension scores (derived from model signals). "
                "Run `python3 src/ingestion/ingest_real_data.py` to load full open-data scores "
                "(CDC PLACES, Census ACS, HRSA, CMS).")

    scores, score_col = condition_score(scores, condition)
    sort_col  = score_col

    filtered = scores.copy()
    if state:
        filtered = filtered[filtered["state_name"].isin(state)]

    top = filtered.nlargest(min(top_n, len(filtered)), sort_col)

    dim_cols = [f"dim_{k}" for k in DIM_LABELS]

    # National dimension averages
    st.markdown(f'<div class="sec-head">National Dimension Profile {_iicon(METRIC_TOOLTIPS["opportunity_score"], pos="")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-sub">Average score across all US counties for each of the 7 dimensions</div>', unsafe_allow_html=True)

    col_radar, col_bars = st.columns([1, 1])

    with col_radar:
        st.markdown(f'<div class="ch"><div class="sec-head">National Radar{_iicon(METRIC_TOOLTIPS["national_radar"])}</div>'
                    f'<div class="sec-sub">All counties vs. top opportunity counties</div></div>',
                    unsafe_allow_html=True)
        dim_avgs_national = scores[dim_cols].mean()
        dim_avgs_top      = top[dim_cols].mean()

        labels = [DIM_LABELS[k] for k in DIM_LABELS]
        r_nat  = [dim_avgs_national[f"dim_{k}"] for k in DIM_LABELS]
        r_top  = [dim_avgs_top[f"dim_{k}"] for k in DIM_LABELS]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=r_nat + [r_nat[0]], theta=labels + [labels[0]],
            fill='toself', name='All Counties',
            line=dict(color=BORDER, width=1.5),
            fillcolor="rgba(0,169,224,0.1)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=r_top + [r_top[0]], theta=labels + [labels[0]],
            fill='toself', name=f'Top {len(top)}',
            line=dict(color=G_DARK, width=2),
            fillcolor="rgba(0,48,135,0.2)",
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont_size=9),
                angularaxis=dict(tickfont_size=10),
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center", font_size=11),
            margin=dict(l=30,r=30,t=30,b=50), height=360,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        _stplot(fig, use_container_width=True)

    with col_bars:
        # Build all bars in ONE markdown call so the card wrapper encloses its content
        bars_html = (
            f'<div class="card"><div class="sec-head">Dimension Breakdown</div>'
            f'<div style="font-size:.67rem;color:{MUTED};margin-bottom:.65rem;margin-top:.15rem;">'
            f'  <span style="border-left:2px solid {MUTED};padding-left:4px;margin-right:.7rem;">national avg</span>'
            f'  <span style="font-weight:600;color:{DARK};">● top {len(top)} score &nbsp; +/− vs national</span>'
            f'</div>'
        )
        for k in DIM_LABELS:
            col_key  = f"dim_{k}"
            nat_val  = dim_avgs_national[col_key]
            top_val  = dim_avgs_top[col_key]
            color    = DIM_COLORS[k]
            icon     = DIM_ICONS[k]
            delta    = top_val - nat_val
            delta_str   = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
            delta_color = "#16a34a" if delta >= 0 else "#dc2626"
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
        bars_html += '</div>'
        st.markdown(bars_html, unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

    # County-level dimension heatmap
    st.markdown(
        f'<div class="ch"><div class="sec-head">Top {len(top)} Counties — Dimension Heatmap{_iicon(METRIC_TOOLTIPS["heatmap"])}</div>'
        f'<div class="sec-sub">Each row = a county · Each column = one of the 7 dimensions · Darker = stronger signal</div></div>',
        unsafe_allow_html=True)

    hm_data = top[["county_name", "state_name"] + dim_cols].head(25).copy()
    hm_data["state_abbr"]   = hm_data["state_name"].map(STATE_ABBREV).fillna(hm_data["state_name"].str[:2].str.upper())
    hm_data["county_label"] = hm_data["county_name"] + ", " + hm_data["state_abbr"]

    hm_raw = hm_data[dim_cols].values.astype(float)

    # Per-column normalise for colour (so every column uses the full warm→navy range)
    hm_norm = hm_raw.copy()
    for j in range(hm_norm.shape[1]):
        col = hm_norm[:, j]
        mn, mx = col.min(), col.max()
        hm_norm[:, j] = 100 * (col - mn) / (mx - mn) if mx > mn else np.full_like(col, 50.0)

    def _cell_color(norm_v: float):
        """Diverging cell bg + text color. norm_v = 0–100 (relative rank in column)."""
        v = max(0.0, min(1.0, norm_v / 100.0))
        if v < 0.5:
            t = v * 2
            r = int(0xF5 + (0xDE - 0xF5) * t)
            g = int(0xC6 + (0xEE - 0xC6) * t)
            b = int(0xA0 + (0xF9 - 0xA0) * t)
            txt = "#7A2A0A" if v < 0.25 else "#5A7A9B"
        else:
            t = (v - 0.5) * 2
            r = int(0xDE + (0x00 - 0xDE) * t)
            g = int(0xEE + (0x30 - 0xEE) * t)
            b = int(0xF9 + (0x87 - 0xF9) * t)
            txt = "#003087" if t < 0.4 else "#FFFFFF"
        return f"#{r:02X}{g:02X}{b:02X}", txt

    # Build HTML table
    dim_keys = list(DIM_LABELS.keys())
    th_style = (f"padding:7px 10px;font-size:.7rem;font-weight:600;color:{MUTED};"
                f"text-align:center;border-bottom:2px solid {BORDER};white-space:nowrap;")
    td_county = (f"padding:6px 10px;font-size:.76rem;color:{DARK};font-weight:500;"
                 f"border-bottom:1px solid {BORDER};white-space:nowrap;")
    html = (
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;font-family:sans-serif;">'
        f'<thead><tr>'
        f'<th style="{th_style}text-align:left;"></th>'
    )
    for k in dim_keys:
        html += (
            f'<th style="{th_style}">'
            f'{DIM_ICONS[k]} {DIM_SHORT[k]} {_iicon(DIM_TOOLTIPS[k], pos="")}'
            f'</th>'
        )
    html += '</tr></thead><tbody>'

    for row_i, row in enumerate(hm_data.itertuples()):
        html += f'<tr><td style="{td_county}">{row.county_label}</td>'
        for col_j, k in enumerate(dim_keys):
            raw_val  = hm_raw[row_i, col_j]
            norm_val = hm_norm[row_i, col_j]
            bg, txt  = _cell_color(norm_val)
            html += (f'<td style="padding:6px 8px;text-align:center;font-size:.78rem;'
                     f'font-weight:700;background:{bg};color:{txt};'
                     f'border-bottom:1px solid {BORDER};">'
                     f'{raw_val:.0f}</td>')
        html += '</tr>'

    html += (
        '</tbody></table></div>'
        f'<div style="font-size:.67rem;color:{MUTED};margin-top:.4rem;">'
        f'  Color = relative rank within shown counties per dimension &nbsp;·&nbsp;'
        f'  Navy = strongest &nbsp;·&nbsp; Warm = weakest'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

    _render_weight_sensitivity(scores)


def _render_weight_sensitivity(scores: pd.DataFrame):
    """Let an analyst move the 7 dimension weights and watch rankings hold."""
    st.markdown('<div class="sec-head" style="margin-top:1.4rem;">Weight Sensitivity</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="sec-sub">Skeptical of the default weights? Move them.
      Weights are re-normalised to 100%, the composite is recomputed live, and the
      stability metrics show how little the ranking actually depends on any single
      weighting choice.</div>""", unsafe_allow_html=True)

    df = _ensure_dims(scores)
    dim_cols_present = [f"dim_{k}" for k in _DEFAULT_WEIGHTS if f"dim_{k}" in df.columns]
    if len(dim_cols_present) < 7:
        st.info("Dimension columns unavailable — run src/ingestion/ingest_real_data.py first.")
        return

    with st.expander("🎛️ Adjust dimension weights", expanded=False):
        cols = st.columns(4)
        weights = {}
        for i, (k, default) in enumerate(_DEFAULT_WEIGHTS.items()):
            with cols[i % 4]:
                weights[k] = st.slider(
                    DIM_LABELS[k], 0, 40, default, step=5,
                    key=f"wsens_{k}",
                )
        total = sum(weights.values())
        if total == 0:
            st.warning("Set at least one weight above zero.")
            return
        norm_str = " · ".join(
            f"{DIM_SHORT[k]} {100 * v / total:.0f}%" for k, v in weights.items() if v
        )
        st.markdown(f"<div style='font-size:.7rem;color:{MUTED};'>Normalised: {norm_str}</div>",
                    unsafe_allow_html=True)

        base = df["opportunity_score"] if "opportunity_score" in df.columns \
            else recompute_composite(df, _DEFAULT_WEIGHTS)
        custom = recompute_composite(df, weights)
        stab = rank_stability(base, custom, top_n=50)

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="card" style="border-top:3px solid {G_DARK};">
          <div class="label">Rank correlation{_iicon(METRIC_TOOLTIPS["ws_spearman"], tip_cls="tip-r")}</div>
          <div class="big-num">{stab['spearman']:.3f}</div>
          <div class="sub-muted">Spearman vs default (1.0 = identical)</div></div>""",
          unsafe_allow_html=True)
        c2.markdown(f"""<div class="card" style="border-top:3px solid {BLUE};">
          <div class="label">Top-50 overlap{_iicon(METRIC_TOOLTIPS["ws_overlap"])}</div>
          <div class="big-num">{stab['top_overlap']:.0%}</div>
          <div class="sub-muted">of default top-50 counties still in top-50</div></div>""",
          unsafe_allow_html=True)
        c3.markdown(f"""<div class="card" style="border-top:3px solid #F4A261;">
          <div class="label">Largest move{_iicon(METRIC_TOOLTIPS["ws_maxjump"])}</div>
          <div class="big-num">{stab['max_jump']}</div>
          <div class="sub-muted">biggest rank change within default top-50</div></div>""",
          unsafe_allow_html=True)

        # Biggest movers table
        r_base = base.rank(ascending=False)
        r_cust = custom.rank(ascending=False)
        movers = pd.DataFrame({
            "county": df["county_name"] + ", " + df["state_name"].map(STATE_ABBREV).fillna(""),
            "default_rank": r_base.astype(int),
            "custom_rank": r_cust.astype(int),
        })
        movers["Δ"] = movers["default_rank"] - movers["custom_rank"]
        movers = movers[movers["default_rank"] <= 100].reindex(
            movers["Δ"].abs().sort_values(ascending=False).index
        ).head(8)
        if not movers.empty and movers["Δ"].abs().max() > 0:
            rows = "".join(
                f"<tr><td>{r['county']}</td>"
                f"<td style='text-align:center;'>{r['default_rank']}</td>"
                f"<td style='text-align:center;'>{r['custom_rank']}</td>"
                f"<td style='text-align:center;color:{G_DARK if r['Δ'] > 0 else '#E63946'};"
                f"font-weight:700;'>{'+' if r['Δ'] > 0 else ''}{r['Δ']}</td></tr>"
                for _, r in movers.iterrows()
            )
            st.markdown(
                f'<div style="margin-top:.6rem;"><table class="tbl"><thead><tr>'
                f'<th>Biggest movers (default top-100)</th><th>Default rank</th>'
                f'<th>Custom rank</th><th>Δ</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:.75rem;color:{MUTED};margin-top:.5rem;'>"
                        f"No rank changes in the top 100 under these weights.</div>",
                        unsafe_allow_html=True)

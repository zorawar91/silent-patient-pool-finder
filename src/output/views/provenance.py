from __future__ import annotations
# View: Data Provenance — source-of-truth table, output freshness, confidence
# grades, and live QA-gate report.

import pandas as pd
import streamlit as st

from src.output.content import METRIC_TOOLTIPS
from src.output.theme import G_DARK, MUTED, _iicon


@st.cache_data(ttl=300)
def _provenance_tables():
    from src.quality.provenance import build_provenance, build_output_provenance
    return build_provenance(), build_output_provenance()


@st.cache_data(ttl=300)
def _gate_reports():
    from src.quality.provenance import run_all_gates
    out = []
    for name, rep in run_all_gates():
        out.append({
            "name": name,
            "ok": rep.ok,
            "results": [(r.name, r.passed, r.severity, r.detail) for r in rep.results],
        })
    return out


def view_data_provenance(scores: pd.DataFrame):
    """Source-of-truth page: where every number comes from + live QA status."""
    st.markdown("""
    <div class="banner">
      <div class="banner-title">Data Provenance &amp; Quality</div>
      <div class="banner-stat">Every number, sourced</div>
      <div class="banner-note">
        100% public, aggregate, PHI-free data · computed live from the files
        this dashboard is actually reading · QA gates re-run on load
      </div>
    </div>""", unsafe_allow_html=True)

    src_df, out_df = _provenance_tables()

    # ── Source table ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head">Data Sources</div>', unsafe_allow_html=True)
    rows_html = ""
    for _, r in src_df.iterrows():
        cov = f"{r['coverage']:,}" if r["coverage"] else "—"
        cached = r["cached"] or "—"
        note = f"<br><span style='font-size:.66rem;color:{MUTED};'>{r['notes']}</span>" if r["notes"] else ""
        rows_html += (
            f"<tr>"
            f"<td><a href='{r['url']}' target='_blank' style='color:{G_DARK};"
            f"text-decoration:none;font-weight:600;'>{r['source']}</a>{note}</td>"
            f"<td style='font-size:.75rem;'>{r['provider']}</td>"
            f"<td style='font-size:.75rem;'>{r['vintage']}</td>"
            f"<td style='font-size:.73rem;'>{r['dimensions']}</td>"
            f"<td style='text-align:right;'>{cov} {r['unit']}s</td>"
            f"<td style='font-size:.73rem;'>{cached}</td>"
            f"<td>{r['status']}</td>"
            f"</tr>"
        )
    st.markdown(
        f'<table class="tbl"><thead><tr>'
        f'<th>Source</th><th>Provider</th><th>Vintage</th><th>Feeds</th>'
        f'<th>Real coverage {_iicon(METRIC_TOOLTIPS["prov_coverage"], pos="")}</th>'
        f'<th>Downloaded</th>'
        f'<th>Status {_iicon(METRIC_TOOLTIPS["prov_status"], pos="")}</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── Outputs ───────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-head" style="margin-top:1.2rem;">Scored Outputs</div>',
                unsafe_allow_html=True)
    o_html = "".join(
        f"<tr><td style='font-weight:600;'>{r['output']}</td>"
        f"<td style='text-align:right;'>{r['rows']:,}</td>"
        f"<td>{r['unit']}s</td><td>{r['generated'] or '—'}</td>"
        f"<td>{r['status']}</td></tr>"
        for _, r in out_df.iterrows()
    )
    st.markdown(
        f'<table class="tbl"><thead><tr><th>Output</th><th>Rows</th>'
        f'<th>Unit</th><th>Generated</th><th>Status</th></tr></thead>'
        f'<tbody>{o_html}</tbody></table>', unsafe_allow_html=True)

    # ── Confidence grade distribution ─────────────────────────────────────────
    if "confidence_grade" in scores.columns:
        st.markdown(f'<div class="sec-head" style="margin-top:1.2rem;">County Data Confidence '
                    f'{_iicon(METRIC_TOOLTIPS["confidence_grade"], pos="")}</div>',
                    unsafe_allow_html=True)
        dist = scores["confidence_grade"].value_counts().reindex(["A", "B", "C"]).fillna(0)
        c1, c2, c3 = st.columns(3)
        for col, g, color, desc in [
            (c1, "A", G_DARK, "6-7 real sources"),
            (c2, "B", "#F4A261", "4-5 real sources"),
            (c3, "C", "#E63946", "<4 sources — proxy-leaning"),
        ]:
            col.markdown(f"""<div class="card" style="border-top:3px solid {color};">
              <div class="label">Grade {g}</div>
              <div class="big-num" style="color:{color};">{int(dist[g]):,}</div>
              <div class="sub-muted">{desc}</div></div>""", unsafe_allow_html=True)

    # ── Live QA gate report ───────────────────────────────────────────────────
    st.markdown(f'<div class="sec-head" style="margin-top:1.2rem;">QA Gate Report (live) '
                f'{_iicon(METRIC_TOOLTIPS["prov_qa"], pos="")}</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="sec-sub">Fail-loudly data contracts re-run against
      the exact files powering this dashboard. A 🛑 here means the pipeline would
      refuse to ship this data.</div>""", unsafe_allow_html=True)
    for rep in _gate_reports():
        n_pass = sum(1 for _, p, _, _ in rep["results"] if p)
        badge = "✅" if rep["ok"] else "🛑"
        with st.expander(f"{badge} {rep['name']} — {n_pass}/{len(rep['results'])} checks passed",
                         expanded=not rep["ok"]):
            for name, passed, sev, detail in rep["results"]:
                icon = "✅" if passed else ("🛑" if sev == "CRITICAL" else "⚠️")
                st.markdown(
                    f"<div style='font-size:.78rem;padding:.15rem 0;'>{icon} "
                    f"<strong>{name}</strong> — <span style='color:{MUTED};'>{detail}</span></div>",
                    unsafe_allow_html=True)

    st.markdown(f"""<div style="font-size:.68rem;color:{MUTED};margin-top:1rem;">
      Methodology: county opportunity score = weighted blend of 7 dimension scores
      (weights in config/dimensions.yaml) · percentile = rank among 3,144 counties ·
      confidence grade reflects pre-imputation source coverage ·
      full details in SPPF_Methodology_v1.0.docx and docs/ARCHITECTURE.md.
    </div>""", unsafe_allow_html=True)

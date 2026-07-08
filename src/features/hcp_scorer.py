from __future__ import annotations
"""
HCP Priority Scorer — the activation layer.
============================================
Turns geography-level opportunity into a prescriber-level call list:
"in the highest-opportunity ZIPs, which HCPs have the largest, most
metabolically-burdened patient panels and the right specialty to run
diagnosis-support detailing with?"

Inputs
------
providers  : CMS Medicare Physician & Other Practitioners (by Provider) —
             one row per NPI with specialty, ZIP, panel size, and panel
             chronic-condition percentages. (public, no PHI)
zip_scores : output of ingest_zcta_data.py (zip_opportunity_percentile)
county_scores : output of ingest_real_data.py (fallback geography signal)

Output
------
One row per targetable NPI:
  npi, name, specialty, city, state, zip5, zcta5,
  geo_percentile, panel_size, panel_diabetes_pct, specialty_fit,
  hcp_priority_score (0-100), hcp_tier, rationale
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ── Specialty fit for diagnosis-support detailing ────────────────────────────
# Primary care owns the undiagnosed-patient funnel; endocrine/cardio are
# high-value but see already-referred (= already suspected) patients.
SPECIALTY_FIT = {
    "family practice":            1.00,
    "family medicine":            1.00,
    "internal medicine":          1.00,
    "general practice":           1.00,
    "geriatric medicine":         0.95,
    "nurse practitioner":         0.90,
    "physician assistant":        0.90,
    "preventive medicine":        0.85,
    "endocrinology":              0.75,
    "cardiology":                 0.65,
    "cardiovascular disease (cardiology)": 0.65,
    "nephrology":                 0.60,
    "obstetrics & gynecology":    0.45,
    "obstetrics/gynecology":      0.45,
}
DEFAULT_FIT = 0.25          # all other specialties
MIN_PANEL = 50              # ignore NPIs with tiny Medicare panels

# Score blend (sums to 1.0)
W_GEO       = 0.40          # ZIP/county opportunity percentile
W_REACH     = 0.25          # panel size percentile (within included NPIs)
W_BURDEN    = 0.20          # panel metabolic burden percentile
W_SPECIALTY = 0.15          # specialty fit


def score_hcps(
    providers: pd.DataFrame,
    zip_scores: pd.DataFrame,
    county_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Score every targetable provider. Returns ranked DataFrame."""
    df = _standardise_providers(providers)
    n0 = len(df)

    # Panel-size floor — below ~50 Medicare benes the condition percentages
    # are suppressed or noisy, and the call isn't worth a rep's time.
    df = df[df["panel_size"].fillna(0) >= MIN_PANEL].copy()
    log.info(f"HCP scorer: {len(df):,} of {n0:,} NPIs pass panel-size floor (≥{MIN_PANEL})")

    # ── Geography join: prescriber ZIP → ZCTA opportunity percentile ─────────
    geo = zip_scores[["zcta5", "zip_opportunity_percentile"]].dropna().copy() \
        if not zip_scores.empty and "zip_opportunity_percentile" in zip_scores.columns \
        else pd.DataFrame(columns=["zcta5", "zip_opportunity_percentile"])
    geo["zcta5"] = geo["zcta5"].astype(str).str.zfill(5)

    df["zcta5"] = df["zip5"]
    df = df.merge(geo, on="zcta5", how="left")
    df = df.rename(columns={"zip_opportunity_percentile": "geo_percentile"})
    match_rate = df["geo_percentile"].notna().mean()
    log.info(f"HCP scorer: ZIP→ZCTA match rate {match_rate:.1%}")

    # County fallback for unmatched ZIPs (state-level median of county percentile)
    if county_scores is not None and not county_scores.empty \
            and "opportunity_percentile" in county_scores.columns:
        state_med = county_scores.groupby("state_abbr")["opportunity_percentile"].median() \
            if "state_abbr" in county_scores.columns else None
        if state_med is not None:
            df["geo_percentile"] = df["geo_percentile"].fillna(
                df["state"].map(state_med)
            )
    df["geo_percentile"] = pd.to_numeric(df["geo_percentile"], errors="coerce").fillna(50.0)

    # ── Component scores (all 0-100) ──────────────────────────────────────────
    df["reach_pctl"]  = df["panel_size"].rank(pct=True) * 100
    burden = df["panel_diabetes_pct"]
    if burden.notna().sum() > 0:
        df["burden_pctl"] = burden.rank(pct=True) * 100
        df["burden_pctl"] = df["burden_pctl"].fillna(50.0)
    else:
        df["burden_pctl"] = 50.0
    df["specialty_fit"] = (
        df["specialty"].str.lower().map(SPECIALTY_FIT).fillna(DEFAULT_FIT)
    )

    df["hcp_priority_score"] = (
        W_GEO       * df["geo_percentile"]
        + W_REACH     * df["reach_pctl"]
        + W_BURDEN    * df["burden_pctl"]
        + W_SPECIALTY * df["specialty_fit"] * 100
    ).clip(0, 100).round(1)

    # Tier: top 5% = Priority, next 20% = Emerging
    q95, q75 = df["hcp_priority_score"].quantile([0.95, 0.75])
    df["hcp_tier"] = "Developing"
    df.loc[df["hcp_priority_score"] >= q75, "hcp_tier"] = "Emerging"
    df.loc[df["hcp_priority_score"] >= q95, "hcp_tier"] = "Priority"

    df["rationale"] = df.apply(_rationale, axis=1)

    keep = ["npi", "name", "specialty", "city", "state", "zip5", "zcta5",
            "geo_percentile", "panel_size", "panel_diabetes_pct",
            "reach_pctl", "burden_pctl", "specialty_fit",
            "hcp_priority_score", "hcp_tier", "rationale"]
    out = (df[[c for c in keep if c in df.columns]]
           .sort_values("hcp_priority_score", ascending=False)
           .reset_index(drop=True))
    log.info(f"HCP scorer: {len(out):,} scored | "
             f"{(out['hcp_tier'] == 'Priority').sum():,} Priority")
    return out


def _standardise_providers(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise CMS by-Provider columns across vintages.
    Handles both Rndrng_Prvdr_* (Physician & Other Practitioners) and
    Prscrbr_* (Part D) naming, and pre-standardised test frames.
    """
    df = raw.copy()
    df.columns = df.columns.str.lower().str.strip()

    def pick(*cands):
        return next((c for c in cands if c in df.columns), None)

    npi_c   = pick("npi", "rndrng_npi", "prscrbr_npi")
    last_c  = pick("name_last", "rndrng_prvdr_last_org_name", "prscrbr_last_org_name")
    first_c = pick("name_first", "rndrng_prvdr_first_name", "prscrbr_first_name")
    spec_c  = pick("specialty", "rndrng_prvdr_type", "prscrbr_type")
    city_c  = pick("city", "rndrng_prvdr_city", "prscrbr_city")
    state_c = pick("state", "rndrng_prvdr_state_abrvtn", "prscrbr_state_abrvtn")
    zip_c   = pick("zip5", "rndrng_prvdr_zip5", "prscrbr_zip5")
    panel_c = pick("panel_size", "tot_benes", "tot_bene")
    diab_c  = pick("panel_diabetes_pct", "bene_cc_ph_diabetes_v2_pct",
                   "bene_cc_diab_pct", "bene_cc_dbts_pct")

    missing = [n for n, c in [("npi", npi_c), ("zip", zip_c),
                              ("panel", panel_c)] if c is None]
    if missing:
        raise ValueError(f"Provider file missing required columns: {missing}. "
                         f"Got: {list(df.columns)[:12]}")

    out = pd.DataFrame({
        "npi": df[npi_c].astype(str).str.strip().str.replace(r"\.0$", "", regex=True),
        "specialty": df[spec_c].astype(str).str.strip() if spec_c else "",
        "city": df[city_c].astype(str).str.title() if city_c else "",
        "state": df[state_c].astype(str).str.upper().str.strip() if state_c else "",
        "zip5": (df[zip_c].astype(str).str.strip()
                 .str.replace(r"\.0$", "", regex=True).str[:5].str.zfill(5)),
        "panel_size": pd.to_numeric(
            df[panel_c].astype(str).str.replace(",", ""), errors="coerce"),
    })
    if first_c and last_c:
        out["name"] = (df[first_c].astype(str).str.title().fillna("") + " "
                       + df[last_c].astype(str).str.title().fillna("")).str.strip()
    elif last_c:
        out["name"] = df[last_c].astype(str).str.title()
    else:
        out["name"] = ""
    if diab_c:
        vals = pd.to_numeric(df[diab_c].astype(str).str.replace("%", ""),
                             errors="coerce")
        # normalise to 0-100 percentage
        if vals.dropna().median() <= 1.0:
            vals = vals * 100
        out["panel_diabetes_pct"] = vals
    else:
        out["panel_diabetes_pct"] = np.nan
    return out


def _rationale(row: pd.Series) -> str:
    """One-line 'why this HCP' for the rep-facing export."""
    parts = []
    if row["geo_percentile"] >= 80:
        parts.append(f"ZIP in top {100 - row['geo_percentile']:.0f}% of US opportunity")
    if row["reach_pctl"] >= 80:
        parts.append(f"large Medicare panel ({int(row['panel_size']):,} benes)")
    if row["burden_pctl"] >= 75 and pd.notna(row.get("panel_diabetes_pct")):
        parts.append(f"high metabolic burden ({row['panel_diabetes_pct']:.0f}% of panel diabetic)")
    if row["specialty_fit"] >= 0.9:
        parts.append("primary-care specialty (owns the undiagnosed funnel)")
    return "; ".join(parts) if parts else "balanced profile across all factors"

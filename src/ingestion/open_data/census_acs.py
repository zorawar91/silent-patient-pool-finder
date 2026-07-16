from __future__ import annotations
# US Census American Community Survey (ACS) — 5-year estimates at county level.
# No API key required for basic queries (uses Census Data API).
#
# Variables pulled:
#   B17001_002E  — population below poverty level
#   B17001_001E  — total population for poverty determination
#   B19013_001E  — median household income
#   B27001_001E  — total population for insurance determination
#   B27001_005E  — uninsured males under 6
#   (full uninsured calculation uses multiple age/sex cells)
#   B01002_001E  — median age
#   B01003_001E  — total population
#   B15003_017E  — high school graduates (education proxy)
#   B28002_013E  — no internet access (digital divide)
#   B28002_001E  — total for internet determination
#
# Source: https://api.census.gov/data/{year}/acs/acs5

import logging
import os
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

CENSUS_API = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2022

# Census API key — free at https://api.census.gov/data/key_signup.html
# Set via:  export CENSUS_API_KEY=your_key_here   (add to ~/.zshrc for persistence)
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

# Variables: (api_var, output_col, is_denominator_for)
ACS_VARS = [
    ("B17001_002E", "pop_below_poverty",       None),
    ("B17001_001E", "pop_poverty_universe",     None),
    ("B19013_001E", "median_household_income",  None),
    ("B01002_001E", "median_age",               None),
    ("B01003_001E", "total_population",         None),
    # Uninsured: use aggregate uninsured estimate
    ("B27010_017E", "uninsured_19_34",          None),
    ("B27010_033E", "uninsured_35_64",          None),
    ("B27010_050E", "uninsured_65_plus",        None),
    # Education
    ("B15003_017E", "hs_grad_count",            None),
    ("B15003_001E", "edu_universe",             None),
    # Internet / broadband
    ("B28002_004E", "has_broadband",            None),
    ("B28002_001E", "internet_universe",        None),
    # Race (for risk weighting — T2D higher in Black, Hispanic populations)
    ("B02001_003E", "pop_black",                None),
    ("B03003_003E", "pop_hispanic",             None),
]


def download(cache_dir: str = "data/open", force: bool = False, year: int = ACS_YEAR) -> pd.DataFrame:
    """
    Fetch ACS 5-year estimates for all US counties.
    Returns one row per county_fips with computed SDoH features.

    SSL strategy (resolves macOS LibreSSL 2.8.3 incompatibility):
      Uses the certifi CA bundle, which fixes LibreSSL cert issues while
      keeping verification ON. Insecure fallbacks (verify=False, plain http)
      only run when SPPF_ALLOW_INSECURE_SSL=1 is explicitly set.
    """
    cache_path = Path(cache_dir) / f"census_acs_{year}.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        df = pd.read_parquet(cache_path)
        if not df.empty:
            log.info(f"Census ACS {year}: {len(df):,} counties from cache")
            return df

    log.info(f"Census ACS {year}: querying Census API ...")
    var_list = ",".join(v[0] for v in ACS_VARS)
    # Census API key is required for large county-level queries (free at https://api.census.gov/data/key_signup.html)
    key_param = f"&key={CENSUS_API_KEY}" if CENSUS_API_KEY else ""
    if not CENSUS_API_KEY:
        log.warning(
            "  Census API key not set — large queries may be rejected with 'Missing Key'.\n"
            "  Get a free key at: https://api.census.gov/data/key_signup.html\n"
            "  Then run: export CENSUS_API_KEY=your_key_here"
        )
    query = f"?get=NAME,{var_list}&for=county:*&in=state:*{key_param}"

    # SSL strategy: certifi bundle only. The old verify=False / plain-http
    # fallbacks are a MITM risk, so they now require an explicit opt-in.
    from src.ingestion.download import _allow_insecure, _ca_bundle

    import urllib3
    attempts = [
        {"url": f"https://api.census.gov/data/{year}/acs/acs5{query}", "verify": _ca_bundle()},
    ]
    if _allow_insecure():
        attempts += [
            {"url": f"https://api.census.gov/data/{year}/acs/acs5{query}", "verify": False},
            {"url": f"http://api.census.gov/data/{year}/acs/acs5{query}",  "verify": False},
        ]

    headers = {
        "User-Agent": "SPPF/1.0 (research; contact zorawarnandwal@gmail.com)",
        # Disable gzip/deflate — LibreSSL 2.8.3 can return empty body when decompressing
        "Accept-Encoding": "identity",
    }

    for attempt in attempts:
        try:
            if not attempt["verify"]:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(attempt["url"], timeout=60,
                                verify=attempt["verify"], headers=headers)
            resp.raise_for_status()
            text = resp.text.strip()
            if not text or not text.startswith("[["):
                log.warning(
                    f"Census ACS: unexpected response "
                    f"(verify={attempt['verify']}, url={attempt['url'][:55]}): "
                    f"{text[:120]!r}"
                )
                continue
            data = resp.json()
            df = pd.DataFrame(data[1:], columns=data[0])
            df = _process(df)
            df.to_parquet(cache_path, index=False)
            log.info(f"Census ACS: {len(df):,} counties cached "
                     f"(verify={attempt['verify']})")
            return df
        except Exception as e:
            log.warning(
                f"Census ACS attempt failed "
                f"(verify={attempt['verify']}, url={attempt['url'][:55]}): {e}"
            )

    log.warning("Census ACS: all SSL strategies failed — will use synthetic fallback.")
    return pd.DataFrame()


def _process(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived SDoH features from raw ACS variables."""
    # Build county_fips from state + county codes
    df["county_fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)

    # Numeric coerce
    num_cols = [v[0] for v in ACS_VARS]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").clip(lower=0)

    out = pd.DataFrame()
    out["county_fips"] = df["county_fips"]

    # Poverty rate
    out["poverty_rate"] = (df["B17001_002E"] / df["B17001_001E"]).clip(0, 1)

    # Median household income (normalize to 0-1 scale later)
    out["median_household_income"] = df["B19013_001E"]

    # Median age
    out["median_age"] = df["B01002_001E"]

    # Uninsured rate (rough estimate from available cells)
    uninsured_sum = df[["B27010_017E","B27010_033E","B27010_050E"]].sum(axis=1)
    out["uninsured_rate"] = (uninsured_sum / df["B01003_001E"].clip(lower=1)).clip(0, 1)

    # High school graduation rate
    out["hs_graduation_rate"] = (df["B15003_017E"] / df["B15003_001E"].clip(lower=1)).clip(0, 1)

    # Broadband access rate
    out["broadband_access_rate"] = (df["B28002_004E"] / df["B28002_001E"].clip(lower=1)).clip(0, 1)

    # Racial risk index — weighted by known T2D elevated risk populations
    # Black (1.6x risk), Hispanic (1.5x risk), relative to white baseline
    total_pop = df["B01003_001E"].clip(lower=1)
    pct_black    = (df["B02001_003E"] / total_pop).clip(0, 1)
    pct_hispanic = (df["B03003_003E"] / total_pop).clip(0, 1)
    out["racial_risk_index"] = (0.4 * pct_black + 0.35 * pct_hispanic).clip(0, 1)

    # Total population (for density calculations)
    out["total_population"] = df["B01003_001E"]

    return out.dropna(subset=["county_fips"])

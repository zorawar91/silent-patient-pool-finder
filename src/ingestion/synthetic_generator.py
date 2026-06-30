"""
Synthetic Data Generator — US County Level
==========================================
Generates realistic-but-fake signal data for all US counties across the three
target conditions (T2D, Hypertension, Hyperthyroidism).

Design principles:
- All data is generated at county grain — never individual patient level.
- Each county gets a hidden `true_undiagnosed_rate` drawn from a realistic
  distribution. Signals are then generated as noisy proxies of that rate.
- The model will be trained to predict `true_undiagnosed_rate` from signals.
- For real data: swap this module with actual ingestion connectors.

Output (saved to data/synthetic/):
  counties.parquet          — County metadata (FIPS, name, state, population)
  otc_signals.parquet       — OTC proxy purchase scores per county × condition
  lab_signals.parquet       — Diagnostic orphan ratios per county × condition
  hcp_signals.parquet       — HCP symptom-to-chronic Rx ratios per county × condition
  geo_burden.parquet        — Geographic burden index per county × condition
  ground_truth.parquet      — Synthetic true_undiagnosed_rate (training label)
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# US County seed data — representative sample of all 50 states.
# Covers ~500 counties including major metros and rural geographies.
# In production, replace with a full authoritative FIPS lookup.
# ---------------------------------------------------------------------------

# State FIPS → (state_name, state_abbr, n_counties_to_generate, pop_mean, pop_std)
STATE_SPECS = {
    "01": ("Alabama",        "AL", 10, 55_000,  80_000),
    "02": ("Alaska",         "AK",  4, 30_000,  40_000),
    "04": ("Arizona",        "AZ",  8, 200_000, 500_000),
    "05": ("Arkansas",       "AR",  8, 40_000,  60_000),
    "06": ("California",     "CA", 30, 400_000, 800_000),
    "08": ("Colorado",       "CO",  8, 90_000,  200_000),
    "09": ("Connecticut",    "CT",  6, 150_000, 200_000),
    "10": ("Delaware",       "DE",  3, 175_000, 150_000),
    "12": ("Florida",        "FL", 20, 250_000, 500_000),
    "13": ("Georgia",        "GA", 15, 80_000,  200_000),
    "15": ("Hawaii",         "HI",  4, 80_000,  100_000),
    "16": ("Idaho",          "ID",  6, 50_000,  100_000),
    "17": ("Illinois",       "IL", 15, 100_000, 300_000),
    "18": ("Indiana",        "IN", 10, 70_000,  150_000),
    "19": ("Iowa",           "IA",  8, 40_000,  60_000),
    "20": ("Kansas",         "KS",  8, 35_000,  80_000),
    "21": ("Kentucky",       "KY", 10, 45_000,  80_000),
    "22": ("Louisiana",      "LA", 10, 75_000,  150_000),
    "23": ("Maine",          "ME",  6, 50_000,  60_000),
    "24": ("Maryland",       "MD",  8, 130_000, 200_000),
    "25": ("Massachusetts",  "MA", 10, 120_000, 200_000),
    "26": ("Michigan",       "MI", 12, 90_000,  200_000),
    "27": ("Minnesota",      "MN", 10, 60_000,  150_000),
    "28": ("Mississippi",    "MS",  8, 35_000,  50_000),
    "29": ("Missouri",       "MO", 10, 55_000,  150_000),
    "30": ("Montana",        "MT",  5, 25_000,  40_000),
    "31": ("Nebraska",       "NE",  6, 40_000,  80_000),
    "32": ("Nevada",         "NV",  6, 100_000, 300_000),
    "33": ("New Hampshire",  "NH",  6, 70_000,  100_000),
    "34": ("New Jersey",     "NJ", 10, 200_000, 300_000),
    "35": ("New Mexico",     "NM",  6, 50_000,  100_000),
    "36": ("New York",       "NY", 20, 200_000, 600_000),
    "37": ("North Carolina", "NC", 15, 80_000,  200_000),
    "38": ("North Dakota",   "ND",  4, 20_000,  30_000),
    "39": ("Ohio",           "OH", 15, 100_000, 300_000),
    "40": ("Oklahoma",       "OK",  8, 55_000,  150_000),
    "41": ("Oregon",         "OR",  8, 80_000,  200_000),
    "42": ("Pennsylvania",   "PA", 15, 130_000, 300_000),
    "44": ("Rhode Island",   "RI",  4, 80_000,  100_000),
    "45": ("South Carolina", "SC",  8, 75_000,  150_000),
    "46": ("South Dakota",   "SD",  4, 20_000,  30_000),
    "47": ("Tennessee",      "TN", 10, 75_000,  150_000),
    "48": ("Texas",          "TX", 25, 200_000, 600_000),
    "49": ("Utah",           "UT",  6, 80_000,  200_000),
    "50": ("Vermont",        "VT",  4, 30_000,  40_000),
    "51": ("Virginia",       "VA", 12, 90_000,  200_000),
    "53": ("Washington",     "WA", 10, 150_000, 400_000),
    "54": ("West Virginia",  "WV",  6, 30_000,  50_000),
    "55": ("Wisconsin",      "WI", 10, 70_000,  150_000),
    "56": ("Wyoming",        "WY",  4, 20_000,  30_000),
}

# Socioeconomic risk multipliers — used to make signals spatially realistic.
# Higher SES index → lower undiagnosed burden proxy.
# In production, replace with actual ACS / Census data.
RURAL_SES_SKEW = {
    "AL": 0.15, "AR": 0.15, "MS": 0.20, "WV": 0.18, "KY": 0.16,
    "LA": 0.14, "NM": 0.13, "SD": 0.12, "MT": 0.11, "ND": 0.10,
}  # States where rural counties have elevated undiagnosed burden


def _load_conditions(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)["conditions"]


def _generate_counties(rng: np.random.Generator) -> pd.DataFrame:
    """Build a synthetic US county roster with realistic population distributions."""
    rows = []
    county_counter = {}

    for state_fips, (state_name, state_abbr, n, pop_mean, pop_std) in STATE_SPECS.items():
        county_counter[state_fips] = 0
        for i in range(n):
            county_counter[state_fips] += 1
            county_fips = f"{state_fips}{county_counter[state_fips]:03d}"
            county_name = f"{state_abbr} County {county_counter[state_fips]:03d}"
            population = max(5_000, int(rng.normal(pop_mean, pop_std)))

            # Rural flag: smaller counties are more likely rural
            is_rural = population < 50_000

            rows.append({
                "county_fips": county_fips,
                "county_name": county_name,
                "state_fips": state_fips,
                "state_name": state_name,
                "state_abbr": state_abbr,
                "population": population,
                "is_rural": is_rural,
                "ses_disadvantage_index": float(
                    rng.beta(2, 5) + (RURAL_SES_SKEW.get(state_abbr, 0.05) if is_rural else 0)
                ),
            })

    df = pd.DataFrame(rows)
    df["ses_disadvantage_index"] = df["ses_disadvantage_index"].clip(0, 1)
    log.info(f"Generated {len(df)} counties across {df['state_fips'].nunique()} states")
    return df


def _generate_true_undiagnosed_rates(
    counties: pd.DataFrame,
    conditions: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Assign each county a synthetic ground-truth undiagnosed rate per condition.
    Rate = national_prior × ses_multiplier × rural_multiplier + noise
    """
    rows = []
    for _, county in counties.iterrows():
        ses_mult = 1.0 + 0.5 * county["ses_disadvantage_index"]
        rural_mult = 1.15 if county["is_rural"] else 1.0

        for cond_key, cond in conditions.items():
            base = cond["prevalence_prior_us"] * cond["undiagnosed_fraction_us"]
            rate = base * ses_mult * rural_mult * rng.lognormal(0, 0.15)
            rate = float(np.clip(rate, 0.001, 0.45))
            rows.append({
                "county_fips": county["county_fips"],
                "condition": cond_key,
                "true_undiagnosed_rate": rate,
                # Estimated pool size (used for output table)
                "estimated_undiagnosed_pool": int(county["population"] * rate),
            })

    return pd.DataFrame(rows)


def _generate_otc_signals(
    counties: pd.DataFrame,
    ground_truth: pd.DataFrame,
    conditions: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    OTC Proxy Cluster Score — co-purchase frequency of symptom-adjacent OTC products
    per county, without corresponding chronic Rx. Score 0-1.

    Correlated with true_undiagnosed_rate + Gaussian noise.
    """
    merged = ground_truth.merge(counties[["county_fips", "population", "ses_disadvantage_index"]], on="county_fips")
    rows = []
    for _, row in merged.iterrows():
        signal = (
            0.6 * row["true_undiagnosed_rate"] / 0.1    # scale to ~0.6 range
            + 0.15 * row["ses_disadvantage_index"]
            + rng.normal(0, 0.08)
        )
        rows.append({
            "county_fips": row["county_fips"],
            "condition": row["condition"],
            "otc_proxy_score": float(np.clip(signal, 0, 1)),
            # Number of relevant OTC units sold per 1000 population (synthetic)
            "otc_units_per_1k": float(max(0, rng.normal(
                50 + 300 * row["true_undiagnosed_rate"], 15
            ))),
        })
    return pd.DataFrame(rows)


def _generate_lab_signals(
    counties: pd.DataFrame,
    ground_truth: pd.DataFrame,
    conditions: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Diagnostic Orphan Ratio — lab tests ordered without follow-up chronic Rx
    within the condition-specific window, per county. Score 0-1.
    """
    merged = ground_truth.merge(counties[["county_fips", "population"]], on="county_fips")
    rows = []
    for _, row in merged.iterrows():
        # Labs ordered per 1k population
        labs_per_1k = max(0, rng.normal(
            20 + 200 * row["true_undiagnosed_rate"], 10
        ))
        # Of those, fraction that are "orphaned" (no follow-up Rx)
        orphan_fraction = float(np.clip(
            0.4 + 0.4 * row["true_undiagnosed_rate"] + rng.normal(0, 0.06), 0, 1
        ))
        rows.append({
            "county_fips": row["county_fips"],
            "condition": row["condition"],
            "diagnostic_orphan_ratio": orphan_fraction,
            "labs_ordered_per_1k": float(labs_per_1k),
            "labs_with_no_followup_rx_per_1k": float(labs_per_1k * orphan_fraction),
        })
    return pd.DataFrame(rows)


def _generate_hcp_signals(
    counties: pd.DataFrame,
    ground_truth: pd.DataFrame,
    conditions: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    HCP Symptom-to-Chronic Rx Ratio — ratio of symptom-adjacent Rx to
    chronic-disease Rx across HCPs in a county. Higher = more undiagnosed burden.
    """
    merged = ground_truth.merge(counties[["county_fips", "population"]], on="county_fips")
    rows = []
    for _, row in merged.iterrows():
        # HCPs per county (rough proxy)
        hcp_count = max(5, int(row["population"] / 800 * rng.lognormal(0, 0.2)))
        symptom_rx_ratio = float(np.clip(
            0.2 + 0.6 * row["true_undiagnosed_rate"] + rng.normal(0, 0.05), 0, 1
        ))
        rows.append({
            "county_fips": row["county_fips"],
            "condition": row["condition"],
            "hcp_symptom_rx_ratio": symptom_rx_ratio,
            "hcp_count": hcp_count,
            "symptom_rx_per_hcp": float(max(0, rng.normal(
                10 + 80 * row["true_undiagnosed_rate"], 5
            ))),
            "chronic_rx_per_hcp": float(max(1, rng.normal(
                50 + 100 * (1 - row["true_undiagnosed_rate"]), 10
            ))),
        })
    return pd.DataFrame(rows)


def _generate_geo_burden(
    counties: pd.DataFrame,
    ground_truth: pd.DataFrame,
    conditions: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Geographic Burden Index — epidemiological prevalence prior / observed Rx
    penetration per county. Higher = more undiagnosed gap.
    """
    merged = ground_truth.merge(counties[["county_fips", "population", "ses_disadvantage_index"]], on="county_fips")
    rows = []
    for _, row in merged.iterrows():
        cond = conditions[row["condition"]]
        prevalence_prior = cond["prevalence_prior_us"]
        # Rx penetration: low in counties with high undiagnosed rate
        rx_penetration = float(np.clip(
            prevalence_prior * (1 - row["true_undiagnosed_rate"]) * rng.lognormal(0, 0.1),
            0.001, prevalence_prior
        ))
        burden_index = float(np.clip(prevalence_prior / max(rx_penetration, 0.001), 0, 10))
        rows.append({
            "county_fips": row["county_fips"],
            "condition": row["condition"],
            "geo_burden_index": burden_index,
            "prevalence_prior": prevalence_prior,
            "rx_penetration_rate": rx_penetration,
        })
    return pd.DataFrame(rows)


def run(
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
    output_dir: str = "data/synthetic",
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    """
    Entry point. Generates all synthetic data tables and saves as parquet.
    Returns a dict of DataFrames for downstream use.
    """
    rng = np.random.default_rng(seed)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    conditions = _load_conditions(Path(conditions_config_path))

    log.info("Generating county roster...")
    counties = _generate_counties(rng)

    log.info("Generating ground-truth undiagnosed rates...")
    ground_truth = _generate_true_undiagnosed_rates(counties, conditions, rng)

    log.info("Generating OTC proxy signals...")
    otc = _generate_otc_signals(counties, ground_truth, conditions, rng)

    log.info("Generating diagnostic orphan signals...")
    labs = _generate_lab_signals(counties, ground_truth, conditions, rng)

    log.info("Generating HCP symptom signals...")
    hcp = _generate_hcp_signals(counties, ground_truth, conditions, rng)

    log.info("Generating geographic burden index...")
    geo = _generate_geo_burden(counties, ground_truth, conditions, rng)

    # Save all outputs
    artifacts = {
        "counties": counties,
        "ground_truth": ground_truth,
        "otc_signals": otc,
        "lab_signals": labs,
        "hcp_signals": hcp,
        "geo_burden": geo,
    }
    for name, df in artifacts.items():
        path = output_path / f"{name}.parquet"
        df.to_parquet(path, index=False)
        log.info(f"  Saved {name}.parquet — {len(df):,} rows")

    log.info(f"Synthetic data generation complete. Output: {output_path.resolve()}")
    return artifacts


if __name__ == "__main__":
    run()

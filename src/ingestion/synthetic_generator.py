from __future__ import annotations
"""
Synthetic Data Generator — US County Level
==========================================
Generates realistic-but-fake signal data for real US counties across three
target conditions (T2D, Hypertension, Hyperthyroidism).

Uses real county FIPS codes and names so choropleth maps render correctly.
Signal values are synthetic — correlated with realistic epidemiological priors.
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real US county data: (fips, county_name, state_fips, state_name, state_abbr, pop)
# ~260 counties covering all 50 states — major metros + rural examples.
# Population estimates based on US Census 2022 ACS.
# ---------------------------------------------------------------------------
REAL_COUNTIES = [
    # California
    ("06037","Los Angeles","06","California","CA",10014009),
    ("06073","San Diego","06","California","CA",3298634),
    ("06059","Orange","06","California","CA",3186989),
    ("06065","Riverside","06","California","CA",2418185),
    ("06071","San Bernardino","06","California","CA",2181654),
    ("06067","Sacramento","06","California","CA",1585055),
    ("06001","Alameda","06","California","CA",1682353),
    ("06085","Santa Clara","06","California","CA",1936259),
    ("06019","Fresno","06","California","CA",1008654),
    ("06029","Kern","06","California","CA",909235),
    # Texas
    ("48201","Harris","48","Texas","TX",4731145),
    ("48113","Dallas","48","Texas","TX",2635516),
    ("48439","Tarrant","48","Texas","TX",2110640),
    ("48029","Bexar","48","Texas","TX",2009324),
    ("48453","Travis","48","Texas","TX",1290188),
    ("48215","Hidalgo","48","Texas","TX",870781),
    ("48141","El Paso","48","Texas","TX",865657),
    ("48157","Fort Bend","48","Texas","TX",822779),
    ("48085","Collin","48","Texas","TX",1064465),
    ("48121","Denton","48","Texas","TX",906422),
    # Florida
    ("12086","Miami-Dade","12","Florida","FL",2701767),
    ("12011","Broward","12","Florida","FL",1944375),
    ("12099","Palm Beach","12","Florida","FL",1496770),
    ("12057","Hillsborough","12","Florida","FL",1471968),
    ("12095","Orange","12","Florida","FL",1429908),
    ("12103","Pinellas","12","Florida","FL",959107),
    ("12031","Duval","12","Florida","FL",995318),
    ("12071","Lee","12","Florida","FL",760822),
    ("12105","Polk","12","Florida","FL",724777),
    ("12009","Brevard","12","Florida","FL",606612),
    # New York
    ("36047","Kings (Brooklyn)","36","New York","NY",2590516),
    ("36081","Queens","36","New York","NY",2278029),
    ("36061","New York (Manhattan)","36","New York","NY",1629153),
    ("36005","Bronx","36","New York","NY",1379946),
    ("36059","Nassau","36","New York","NY",1395774),
    ("36103","Suffolk","36","New York","NY",1525920),
    ("36119","Westchester","36","New York","NY",1004457),
    ("36029","Erie","36","New York","NY",954236),
    ("36055","Monroe","36","New York","NY",744344),
    ("36067","Onondaga","36","New York","NY",476516),
    # Pennsylvania
    ("42101","Philadelphia","42","Pennsylvania","PA",1576251),
    ("42003","Allegheny","42","Pennsylvania","PA",1250578),
    ("42091","Montgomery","42","Pennsylvania","PA",856553),
    ("42017","Bucks","42","Pennsylvania","PA",628270),
    ("42045","Delaware","42","Pennsylvania","PA",576830),
    # Illinois
    ("17031","Cook","17","Illinois","IL",5275541),
    ("17097","Lake","17","Illinois","IL",703619),
    ("17043","DuPage","17","Illinois","IL",929291),
    ("17197","Will","17","Illinois","IL",696355),
    ("17019","Champaign","17","Illinois","IL",210626),
    # Ohio
    ("39035","Cuyahoga","39","Ohio","OH",1264817),
    ("39049","Franklin","39","Ohio","OH",1323807),
    ("39061","Hamilton","39","Ohio","OH",830639),
    ("39153","Summit","39","Ohio","OH",541228),
    ("39113","Montgomery","39","Ohio","OH",535153),
    ("39099","Mahoning","39","Ohio","OH",228683),
    # Georgia
    ("13121","Fulton","13","Georgia","GA",1066710),
    ("13135","Gwinnett","13","Georgia","GA",957062),
    ("13067","Cobb","13","Georgia","GA",766149),
    ("13089","DeKalb","13","Georgia","GA",764382),
    ("13051","Chatham","13","Georgia","GA",294865),
    ("13153","Houston","13","Georgia","GA",158485),
    # North Carolina
    ("37119","Mecklenburg","37","North Carolina","NC",1115482),
    ("37183","Wake","37","North Carolina","NC",1129410),
    ("37081","Guilford","37","North Carolina","NC",541299),
    ("37067","Forsyth","37","North Carolina","NC",382295),
    ("37021","Buncombe","37","North Carolina","NC",269452),
    ("37065","Edgecombe","37","North Carolina","NC",50430),
    # Michigan
    ("26163","Wayne","26","Michigan","MI",1734010),
    ("26125","Oakland","26","Michigan","MI",1274395),
    ("26099","Macomb","26","Michigan","MI",881217),
    ("26065","Ingham","26","Michigan","MI",292406),
    ("26049","Genesee","26","Michigan","MI",403448),
    ("26117","Montcalm","26","Michigan","MI",63888),
    # New Jersey
    ("34013","Essex","34","New Jersey","NJ",860548),
    ("34039","Union","34","New Jersey","NJ",575345),
    ("34003","Bergen","34","New Jersey","NJ",955732),
    ("34023","Middlesex","34","New Jersey","NJ",863162),
    ("34017","Hudson","34","New Jersey","NJ",724854),
    # Virginia
    ("51059","Fairfax","51","Virginia","VA",1150309),
    ("51013","Arlington","51","Virginia","VA",238643),
    ("51087","Henrico","51","Virginia","VA",337076),
    ("51041","Chesterfield","51","Virginia","VA",364478),
    ("51163","Rockingham","51","Virginia","VA",82501),
    # Washington
    ("53033","King","53","Washington","WA",2269675),
    ("53053","Pierce","53","Washington","WA",921173),
    ("53061","Snohomish","53","Washington","WA",827957),
    ("53077","Yakima","53","Washington","WA",253243),
    ("53047","Okanogan","53","Washington","WA",42104),
    # Arizona
    ("04013","Maricopa","04","Arizona","AZ",4420568),
    ("04019","Pima","04","Arizona","AZ",1043433),
    ("04021","Pinal","04","Arizona","AZ",425264),
    ("04025","Yavapai","04","Arizona","AZ",235099),
    ("04005","Coconino","04","Arizona","AZ",143476),
    # Massachusetts
    ("25025","Suffolk","25","Massachusetts","MA",803907),
    ("25017","Middlesex","25","Massachusetts","MA",1632002),
    ("25021","Norfolk","25","Massachusetts","MA",716415),
    ("25023","Plymouth","25","Massachusetts","MA",530819),
    ("25009","Essex","25","Massachusetts","MA",799816),
    # Tennessee
    ("47157","Shelby","47","Tennessee","TN",935700),
    ("47037","Davidson","47","Tennessee","TN",715884),
    ("47093","Knox","47","Tennessee","TN",478971),
    ("47065","Hamilton","47","Tennessee","TN",371287),
    ("47149","Rutherford","47","Tennessee","TN",341486),
    ("47059","Greene","47","Tennessee","TN",69069),
    # Indiana
    ("18097","Marion","18","Indiana","IN",964582),
    ("18089","Lake","18","Indiana","IN",498630),
    ("18057","Hamilton","18","Indiana","IN",349970),
    ("18003","Allen","18","Indiana","IN",385088),
    ("18163","Vanderburgh","18","Indiana","IN",181451),
    # Missouri
    ("29189","St. Louis","29","Missouri","MO",1002019),
    ("29095","Jackson","29","Missouri","MO",717204),
    ("29019","Boone","29","Missouri","MO",183610),
    ("29099","Jefferson","29","Missouri","MO",225081),
    ("29186","Ste. Genevieve","29","Missouri","MO",18328),
    # Maryland
    ("24031","Montgomery","24","Maryland","MD",1062061),
    ("24033","Prince George's","24","Maryland","MD",967201),
    ("24003","Anne Arundel","24","Maryland","MD",597234),
    ("24005","Baltimore","24","Maryland","MD",854535),
    ("24041","Garrett","24","Maryland","MD",29014),
    # Wisconsin
    ("55079","Milwaukee","55","Wisconsin","WI",939489),
    ("55025","Dane","55","Wisconsin","WI",561504),
    ("55133","Waukesha","55","Wisconsin","WI",406978),
    ("55009","Brown","55","Wisconsin","WI",268740),
    ("55099","Price","55","Wisconsin","WI",13351),
    # Colorado
    ("08031","Denver","08","Colorado","CO",715878),
    ("08005","Arapahoe","08","Colorado","CO",655070),
    ("08035","Douglas","08","Colorado","CO",357978),
    ("08059","Jefferson","08","Colorado","CO",582881),
    ("08001","Adams","08","Colorado","CO",521238),
    ("08053","Hinsdale","08","Colorado","CO",820),
    # Minnesota
    ("27053","Hennepin","27","Minnesota","MN",1281565),
    ("27123","Ramsey","27","Minnesota","MN",550321),
    ("27037","Dakota","27","Minnesota","MN",439882),
    ("27163","Washington","27","Minnesota","MN",267568),
    ("27007","Beltrami","27","Minnesota","MN",47188),
    # Alabama
    ("01073","Jefferson","01","Alabama","AL",674721),
    ("01097","Mobile","01","Alabama","AL",414079),
    ("01101","Montgomery","01","Alabama","AL",226486),
    ("01117","Shelby","01","Alabama","AL",223024),
    ("01005","Barbour","01","Alabama","AL",24686),
    # South Carolina
    ("45045","Greenville","45","South Carolina","SC",539050),
    ("45079","Richland","45","South Carolina","SC",415759),
    ("45019","Charleston","45","South Carolina","SC",424029),
    ("45041","Florence","45","South Carolina","SC",136885),
    ("45009","Bamberg","45","South Carolina","SC",13311),
    # Louisiana
    ("22033","East Baton Rouge","22","Louisiana","LA",456781),
    ("22051","Jefferson","22","Louisiana","LA",432552),
    ("22071","Orleans","22","Louisiana","LA",378715),
    ("22103","St. Tammany","22","Louisiana","LA",265440),
    ("22035","East Carroll","22","Louisiana","LA",6862),
    # Kentucky
    ("21111","Jefferson","21","Kentucky","KY",782969),
    ("21067","Fayette","21","Kentucky","KY",323152),
    ("21037","Campbell","21","Kentucky","KY",93584),
    ("21059","Daviess","21","Kentucky","KY",102694),
    ("21133","Letcher","21","Kentucky","KY",21557),
    # Oregon
    ("41051","Multnomah","41","Oregon","OR",815428),
    ("41067","Washington","41","Oregon","OR",600372),
    ("41005","Clackamas","41","Oregon","OR",418187),
    ("41029","Jackson","41","Oregon","OR",223389),
    ("41001","Baker","41","Oregon","OR",16134),
    # Oklahoma
    ("40109","Oklahoma","40","Oklahoma","OK",797434),
    ("40143","Tulsa","40","Oklahoma","OK",659540),
    ("40027","Cleveland","40","Oklahoma","OK",300902),
    ("40031","Comanche","40","Oklahoma","OK",120749),
    ("40007","Beaver","40","Oklahoma","OK",5327),
    # Connecticut
    ("09003","Hartford","09","Connecticut","CT",895966),
    ("09001","Fairfield","09","Connecticut","CT",943332),
    ("09009","New Haven","09","Connecticut","CT",854757),
    ("09007","Middlesex","09","Connecticut","CT",163629),
    # Utah
    ("49035","Salt Lake","49","Utah","UT",1160437),
    ("49049","Utah","49","Utah","UT",636235),
    ("49057","Weber","49","Utah","UT",260213),
    ("49011","Davis","49","Utah","UT",362679),
    ("49021","Iron","49","Utah","UT",59399),
    # Iowa
    ("19153","Polk","19","Iowa","IA",490161),
    ("19113","Linn","19","Iowa","IA",225059),
    ("19061","Dubuque","19","Iowa","IA",97311),
    ("19103","Johnson","19","Iowa","IA",151140),
    ("19005","Allamakee","19","Iowa","IA",13396),
    # Nevada
    ("32003","Clark","32","Nevada","NV",2265461),
    ("32031","Washoe","32","Nevada","NV",471519),
    ("32023","Nye","32","Nevada","NV",46523),
    ("32001","Churchill","32","Nevada","NV",24909),
    # Arkansas
    ("05119","Pulaski","05","Arkansas","AR",391911),
    ("05007","Benton","05","Arkansas","AR",279141),
    ("05143","Washington","05","Arkansas","AR",239187),
    ("05031","Craighead","05","Arkansas","AR",110332),
    ("05077","Lee","05","Arkansas","AR",8857),
    # Mississippi
    ("28049","Hinds","28","Mississippi","MS",231840),
    ("28047","Harrison","28","Mississippi","MS",208080),
    ("28059","Jackson","28","Mississippi","MS",139668),
    ("28033","DeSoto","28","Mississippi","MS",184945),
    ("28083","Leflore","28","Mississippi","MS",27642),
    # Kansas
    ("20091","Johnson","20","Kansas","KS",609863),
    ("20173","Sedgwick","20","Kansas","KS",516042),
    ("20177","Shawnee","20","Kansas","KS",178845),
    ("20045","Douglas","20","Kansas","KS",122259),
    ("20073","Greeley","20","Kansas","KS",1195),
    # New Mexico
    ("35001","Bernalillo","35","New Mexico","NM",679121),
    ("35013","Doña Ana","35","New Mexico","NM",219561),
    ("35049","Santa Fe","35","New Mexico","NM",150358),
    ("35045","San Juan","35","New Mexico","NM",126528),
    ("35011","De Baca","35","New Mexico","NM",1748),
    # Nebraska
    ("31055","Douglas","31","Nebraska","NE",579760),
    ("31109","Lancaster","31","Nebraska","NE",319090),
    ("31153","Sarpy","31","Nebraska","NE",187196),
    ("31079","Hall","31","Nebraska","NE",61353),
    # West Virginia
    ("54039","Kanawha","54","West Virginia","WV",178124),
    ("54011","Cabell","54","West Virginia","WV",93686),
    ("54107","Wood","54","West Virginia","WV",84247),
    ("54053","Mason","54","West Virginia","WV",25539),
    # Idaho
    ("16001","Ada","16","Idaho","ID",481587),
    ("16055","Kootenai","16","Idaho","ID",171362),
    ("16027","Canyon","16","Idaho","ID",231951),
    ("16049","Idaho","16","Idaho","ID",16253),
    # Hawaii
    ("15003","Honolulu","15","Hawaii","HI",1004649),
    ("15009","Maui","15","Hawaii","HI",167417),
    ("15001","Hawaii","15","Hawaii","HI",201513),
    ("15007","Kauai","15","Hawaii","HI",73298),
    # New Hampshire
    ("33011","Hillsborough","33","New Hampshire","NH",421566),
    ("33015","Rockingham","33","New Hampshire","NH",311145),
    ("33017","Strafford","33","New Hampshire","NH",130633),
    ("33001","Belknap","33","New Hampshire","NH",62276),
    # Maine
    ("23005","Cumberland","23","Maine","ME",309414),
    ("23011","Kennebec","23","Maine","ME",124075),
    ("23019","Penobscot","23","Maine","ME",154065),
    ("23003","Aroostook","23","Maine","ME",67105),
    # Rhode Island
    ("44007","Providence","44","Rhode Island","RI",636085),
    ("44003","Kent","44","Rhode Island","RI",168001),
    ("44009","Washington","44","Rhode Island","RI",129839),
    ("44005","Newport","44","Rhode Island","RI",84644),
    # Montana
    ("30063","Missoula","30","Montana","MT",119600),
    ("30111","Yellowstone","30","Montana","MT",163062),
    ("30029","Flathead","30","Montana","MT",107685),
    ("30019","Daniels","30","Montana","MT",1690),
    # Delaware
    ("10003","New Castle","10","Delaware","DE",570719),
    ("10005","Sussex","10","Delaware","DE",237378),
    ("10001","Kent","10","Delaware","DE",181851),
    # South Dakota
    ("46099","Minnehaha","46","South Dakota","SD",200967),
    ("46103","Pennington","46","South Dakota","SD",113775),
    ("46083","Lincoln","46","South Dakota","SD",61128),
    ("46031","Corson","46","South Dakota","SD",4024),
    # North Dakota
    ("38017","Cass","38","North Dakota","ND",181923),
    ("38015","Burleigh","38","North Dakota","ND",97368),
    ("38101","Ward","38","North Dakota","ND",69019),
    ("38007","Billings","38","North Dakota","ND",926),
    # Alaska
    ("02020","Anchorage","02","Alaska","AK",288000),
    ("02090","Fairbanks North Star","02","Alaska","AK",97655),
    ("02110","Juneau","02","Alaska","AK",32326),
    ("02290","Yukon-Koyukuk","02","Alaska","AK",5230),
    # Vermont
    ("50007","Chittenden","50","Vermont","VT",168323),
    ("50023","Washington","50","Vermont","VT",59159),
    ("50021","Rutland","50","Vermont","VT",58312),
    ("50009","Essex","50","Vermont","VT",5920),
    # Wyoming
    ("56021","Laramie","56","Wyoming","WY",99500),
    ("56025","Natrona","56","Wyoming","WY",79858),
    ("56013","Fremont","56","Wyoming","WY",38664),
    ("56003","Big Horn","56","Wyoming","WY",11790),
]

# States where rural counties have higher undiagnosed burden (socioeconomic proxy)
HIGH_BURDEN_STATES = {"MS", "AL", "WV", "KY", "LA", "AR", "NM", "SD", "MT", "ND", "OK", "TN"}


def _load_conditions(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)["conditions"]


def _build_county_df(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for fips, name, state_fips, state_name, state_abbr, pop in REAL_COUNTIES:
        is_rural = pop < 100_000
        ses = float(np.clip(
            rng.beta(2, 5) + (0.15 if is_rural and state_abbr in HIGH_BURDEN_STATES else 0.05 if is_rural else 0),
            0, 1
        ))
        rows.append({
            "county_fips":           fips,
            "county_name":           name,
            "state_fips":            state_fips,
            "state_name":            state_name,
            "state_abbr":            state_abbr,
            "population":            pop,
            "is_rural":              is_rural,
            "ses_disadvantage_index": ses,
        })
    df = pd.DataFrame(rows)
    log.info(f"Loaded {len(df)} real US counties across {df['state_fips'].nunique()} states")
    return df


def _generate_true_undiagnosed_rates(counties, conditions, rng):
    rows = []
    for _, c in counties.iterrows():
        ses_mult   = 1.0 + 0.5 * c["ses_disadvantage_index"]
        rural_mult = 1.15 if c["is_rural"] else 1.0
        for key, cond in conditions.items():
            base = cond["prevalence_prior_us"] * cond["undiagnosed_fraction_us"]
            rate = float(np.clip(base * ses_mult * rural_mult * rng.lognormal(0, 0.15), 0.001, 0.45))
            rows.append({
                "county_fips":             c["county_fips"],
                "condition":               key,
                "true_undiagnosed_rate":   rate,
                "estimated_undiagnosed_pool": int(c["population"] * rate),
            })
    return pd.DataFrame(rows)


def _generate_otc_signals(counties, ground_truth, rng):
    merged = ground_truth.merge(counties[["county_fips", "population", "ses_disadvantage_index"]], on="county_fips")
    rows = []
    for _, r in merged.iterrows():
        signal = float(np.clip(
            0.6 * r["true_undiagnosed_rate"] / 0.1 + 0.15 * r["ses_disadvantage_index"] + rng.normal(0, 0.08),
            0, 1
        ))
        rows.append({
            "county_fips":      r["county_fips"],
            "condition":        r["condition"],
            "otc_proxy_score":  signal,
            "otc_units_per_1k": float(max(0, rng.normal(50 + 300 * r["true_undiagnosed_rate"], 15))),
        })
    return pd.DataFrame(rows)


def _generate_lab_signals(counties, ground_truth, rng):
    merged = ground_truth.merge(counties[["county_fips", "population"]], on="county_fips")
    rows = []
    for _, r in merged.iterrows():
        labs_per_1k = max(0, rng.normal(20 + 200 * r["true_undiagnosed_rate"], 10))
        orphan_frac = float(np.clip(0.4 + 0.4 * r["true_undiagnosed_rate"] + rng.normal(0, 0.06), 0, 1))
        rows.append({
            "county_fips":                    r["county_fips"],
            "condition":                      r["condition"],
            "diagnostic_orphan_ratio":        orphan_frac,
            "labs_ordered_per_1k":            float(labs_per_1k),
            "labs_with_no_followup_rx_per_1k": float(labs_per_1k * orphan_frac),
        })
    return pd.DataFrame(rows)


def _generate_hcp_signals(counties, ground_truth, rng):
    merged = ground_truth.merge(counties[["county_fips", "population"]], on="county_fips")
    rows = []
    for _, r in merged.iterrows():
        hcp_count = max(5, int(r["population"] / 800 * rng.lognormal(0, 0.2)))
        sym_ratio = float(np.clip(0.2 + 0.6 * r["true_undiagnosed_rate"] + rng.normal(0, 0.05), 0, 1))
        rows.append({
            "county_fips":          r["county_fips"],
            "condition":            r["condition"],
            "hcp_symptom_rx_ratio": sym_ratio,
            "hcp_count":            hcp_count,
            "symptom_rx_per_hcp":   float(max(0, rng.normal(10 + 80 * r["true_undiagnosed_rate"], 5))),
            "chronic_rx_per_hcp":   float(max(1, rng.normal(50 + 100 * (1 - r["true_undiagnosed_rate"]), 10))),
        })
    return pd.DataFrame(rows)


def _generate_geo_burden(counties, ground_truth, conditions, rng):
    merged = ground_truth.merge(counties[["county_fips", "population", "ses_disadvantage_index"]], on="county_fips")
    rows = []
    for _, r in merged.iterrows():
        cond = conditions[r["condition"]]
        prevalence = cond["prevalence_prior_us"]
        rx_pen = float(np.clip(
            prevalence * (1 - r["true_undiagnosed_rate"]) * rng.lognormal(0, 0.1),
            0.001, prevalence
        ))
        rows.append({
            "county_fips":       r["county_fips"],
            "condition":         r["condition"],
            "geo_burden_index":  float(np.clip(prevalence / max(rx_pen, 0.001), 0, 10)),
            "prevalence_prior":  prevalence,
            "rx_penetration_rate": rx_pen,
        })
    return pd.DataFrame(rows)


def run(
    country_config_path: str = "config/us.yaml",
    conditions_config_path: str = "config/conditions.yaml",
    output_dir: str = "data/synthetic",
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    conditions = _load_conditions(Path(conditions_config_path))

    counties     = _build_county_df(rng)
    ground_truth = _generate_true_undiagnosed_rates(counties, conditions, rng)
    otc          = _generate_otc_signals(counties, ground_truth, rng)
    labs         = _generate_lab_signals(counties, ground_truth, rng)
    hcp          = _generate_hcp_signals(counties, ground_truth, rng)
    geo          = _generate_geo_burden(counties, ground_truth, conditions, rng)

    artifacts = {
        "counties": counties, "ground_truth": ground_truth,
        "otc_signals": otc, "lab_signals": labs,
        "hcp_signals": hcp, "geo_burden": geo,
    }
    for name, df in artifacts.items():
        df.to_parquet(out / f"{name}.parquet", index=False)
        log.info(f"  Saved {name}.parquet — {len(df):,} rows")

    log.info(f"Done. Output: {out.resolve()}")
    return artifacts


if __name__ == "__main__":
    run()

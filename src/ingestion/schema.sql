-- ============================================================
-- Silent Patient Pool Finder — Database Schema
-- ============================================================
-- All data is synthetic or anonymised aggregate.
-- No individual patient identifiers are stored in production.
-- ============================================================

-- ── Extensions ────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Drop & recreate (safe for local dev) ──────────────────
DROP TABLE IF EXISTS geography_risk_scores CASCADE;
DROP TABLE IF EXISTS otc_transactions CASCADE;
DROP TABLE IF EXISTS observations CASCADE;
DROP TABLE IF EXISTS medications CASCADE;
DROP TABLE IF EXISTS conditions CASCADE;
DROP TABLE IF EXISTS encounters CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS condition_codes CASCADE;
DROP TABLE IF EXISTS otc_proxy_products CASCADE;

-- ── Reference: condition codes we care about ──────────────
-- Synthea uses SNOMED CT; we map to our internal label here
CREATE TABLE condition_codes (
    snomed_code     VARCHAR(20) PRIMARY KEY,
    icd10_code      VARCHAR(10),
    condition_name  VARCHAR(100) NOT NULL,
    condition_group VARCHAR(50)  NOT NULL  -- 'diabetes', 'hypertension', 'thyroid'
);

INSERT INTO condition_codes (snomed_code, icd10_code, condition_name, condition_group) VALUES
    ('44054006',  'E11',    'Type 2 Diabetes Mellitus',              'diabetes'),
    ('15777000',  'R73.09', 'Prediabetes',                           'diabetes'),
    ('237599002', 'E11.65', 'Insulin-dependent Type 2 Diabetes',     'diabetes'),
    ('59621000',  'I10',    'Essential Hypertension',                'hypertension'),
    ('1201005',   'I10',    'Benign Essential Hypertension',         'hypertension'),
    ('40930008',  'E03.9',  'Hypothyroidism',                        'thyroid'),
    ('83986005',  'E03.9',  'Severe Hypothyroidism',                 'thyroid'),
    ('414916001', 'E66.9',  'Obesity',                               'metabolic'),
    ('162864005', 'E66.01', 'Body mass index 30+ obese',             'metabolic');

-- ── Reference: OTC proxy products ─────────────────────────
CREATE TABLE otc_proxy_products (
    product_code     VARCHAR(20) PRIMARY KEY,
    product_name     VARCHAR(200) NOT NULL,
    category         VARCHAR(100) NOT NULL,
    signal_condition VARCHAR(50)  NOT NULL,  -- condition this proxies for
    signal_strength  SMALLINT     NOT NULL   -- 1 (weak) to 3 (strong)
);

INSERT INTO otc_proxy_products (product_code, product_name, category, signal_condition, signal_strength) VALUES
    -- Diabetes proxy signals
    ('OTC-GLU-001', 'Blood Glucose Test Strips (50ct)',         'Diagnostics',     'diabetes',    3),
    ('OTC-GLU-002', 'Blood Glucose Monitor Kit',                'Diagnostics',     'diabetes',    3),
    ('OTC-GLU-003', 'Lancets / Finger-prick Needles (100ct)',   'Diagnostics',     'diabetes',    3),
    ('OTC-DM-001',  'Diabetic Foot Cream',                      'Dermatology',     'diabetes',    2),
    ('OTC-DM-002',  'Diabetic Compression Socks',               'Accessories',     'diabetes',    2),
    ('OTC-DM-003',  'Chromium Picolinate Supplement',           'Supplements',     'diabetes',    2),
    ('OTC-DM-004',  'Alpha Lipoic Acid (Neuropathy support)',   'Supplements',     'diabetes',    2),
    ('OTC-DM-005',  'Vitamin B12 High-dose (1000mcg)',          'Supplements',     'diabetes',    1),
    ('OTC-DM-006',  'Bitter Melon / Karela Capsules',           'Supplements',     'diabetes',    2),
    ('OTC-DM-007',  'Antacid / GI Relief (gastroparesis)',      'GI',              'diabetes',    1),
    ('OTC-DM-008',  'Eye Drops – Lubricating (dry eye)',        'Ophthalmology',   'diabetes',    1),
    ('OTC-DM-009',  'Metanx / B-vitamin complex (neuropathy)', 'Supplements',     'diabetes',    2),
    -- Hypertension proxy signals
    ('OTC-HTN-001', 'Magnesium Glycinate (400mg)',              'Supplements',     'hypertension',2),
    ('OTC-HTN-002', 'Potassium Supplement (99mg)',              'Supplements',     'hypertension',2),
    ('OTC-HTN-003', 'CoQ10 (100mg) – BP support',              'Supplements',     'hypertension',2),
    ('OTC-HTN-004', 'Garlic Extract / Allicin Capsules',       'Supplements',     'hypertension',1),
    ('OTC-HTN-005', 'Beetroot Powder / L-Arginine',            'Supplements',     'hypertension',2),
    ('OTC-HTN-006', 'Hawthorn Berry Extract',                  'Supplements',     'hypertension',1),
    ('OTC-HTN-007', 'Home Blood Pressure Monitor',             'Diagnostics',     'hypertension',3),
    ('OTC-HTN-008', 'Wrist BP Cuff',                           'Diagnostics',     'hypertension',3),
    ('OTC-HTN-009', 'Fish Oil / Omega-3 (2g+ dose)',           'Supplements',     'hypertension',1),
    -- Thyroid proxy signals
    ('OTC-THY-001', 'Iodine Supplement (150mcg)',              'Supplements',     'thyroid',     2),
    ('OTC-THY-002', 'Selenium Supplement (200mcg)',            'Supplements',     'thyroid',     2),
    ('OTC-THY-003', 'Ashwagandha / Thyroid support blend',    'Supplements',     'thyroid',     2),
    ('OTC-THY-004', 'Energy / Fatigue supplement (B-complex)', 'Supplements',     'thyroid',     1),
    ('OTC-THY-005', 'Zinc + Selenium combo',                   'Supplements',     'thyroid',     2),
    ('OTC-THY-006', 'Hair Loss / Biotin supplement',           'Dermatology',     'thyroid',     1),
    ('OTC-THY-007', 'Iron supplement (fatigue-related)',       'Supplements',     'thyroid',     1);

-- ── Core tables ────────────────────────────────────────────
CREATE TABLE patients (
    patient_id      UUID         PRIMARY KEY,
    birth_date      DATE,
    death_date      DATE,
    gender          CHAR(1),
    race            VARCHAR(50),
    ethnicity       VARCHAR(50),
    city            VARCHAR(100),
    state           VARCHAR(50),
    zip             VARCHAR(10),
    lat             DECIMAL(9,6),
    lon             DECIMAL(9,6),
    -- Label for ML training (populated by simulate_otc.py)
    cohort          VARCHAR(20)  -- 'diagnosed', 'silent', 'control'
);

CREATE TABLE encounters (
    encounter_id    UUID         PRIMARY KEY,
    patient_id      UUID         REFERENCES patients(patient_id) ON DELETE CASCADE,
    start_ts        TIMESTAMP,
    stop_ts         TIMESTAMP,
    encounter_class VARCHAR(50),
    code            VARCHAR(20),
    description     TEXT,
    reason_code     VARCHAR(20),
    reason_desc     TEXT
);

CREATE TABLE conditions (
    condition_id    SERIAL       PRIMARY KEY,
    patient_id      UUID         REFERENCES patients(patient_id) ON DELETE CASCADE,
    encounter_id    UUID         REFERENCES encounters(encounter_id) ON DELETE SET NULL,
    start_date      DATE,
    stop_date       DATE,
    snomed_code     VARCHAR(20),
    description     TEXT,
    -- Resolved from condition_codes
    condition_group VARCHAR(50)
);

CREATE TABLE medications (
    medication_id   SERIAL       PRIMARY KEY,
    patient_id      UUID         REFERENCES patients(patient_id) ON DELETE CASCADE,
    encounter_id    UUID         REFERENCES encounters(encounter_id) ON DELETE SET NULL,
    start_date      DATE,
    stop_date       DATE,
    rxnorm_code     VARCHAR(20),
    description     TEXT,
    dispenses       INTEGER,
    reason_code     VARCHAR(20),
    reason_desc     TEXT,
    -- Derived: is this a chronic-condition Rx or symptom-adjacent?
    rx_type         VARCHAR(20)  -- 'chronic', 'symptom_adjacent', 'other'
);

CREATE TABLE observations (
    observation_id  SERIAL       PRIMARY KEY,
    patient_id      UUID         REFERENCES patients(patient_id) ON DELETE CASCADE,
    encounter_id    UUID         REFERENCES encounters(encounter_id) ON DELETE SET NULL,
    obs_date        DATE,
    loinc_code      VARCHAR(20),
    description     TEXT,
    value           VARCHAR(100),
    units           VARCHAR(50),
    obs_type        VARCHAR(50),
    -- Derived: is this a diagnostic-orphan candidate?
    is_target_lab   BOOLEAN      DEFAULT FALSE
);

-- ── Simulated OTC pharmacy transactions ───────────────────
CREATE TABLE otc_transactions (
    transaction_id  SERIAL       PRIMARY KEY,
    patient_id      UUID         REFERENCES patients(patient_id) ON DELETE CASCADE,
    transaction_date DATE        NOT NULL,
    product_code    VARCHAR(20)  REFERENCES otc_proxy_products(product_code),
    quantity        SMALLINT     DEFAULT 1,
    zip             VARCHAR(10),
    -- months before/after formal diagnosis (-ve = before, +ve = after)
    -- NULL for silent/control patients (no diagnosis date)
    months_to_diagnosis INTEGER
);

-- ── Geography risk scores (output layer) ──────────────────
CREATE TABLE geography_risk_scores (
    zip                         VARCHAR(10)  NOT NULL,
    score_date                  DATE         NOT NULL,
    -- Raw signal counts
    otc_diabetes_proxy_count    INTEGER      DEFAULT 0,
    otc_hypertension_proxy_count INTEGER     DEFAULT 0,
    otc_thyroid_proxy_count     INTEGER      DEFAULT 0,
    diagnostic_orphan_count     INTEGER      DEFAULT 0,
    hcp_symptom_rx_ratio        DECIMAL(6,3),
    -- Known-diagnosed count (exclusion / denominator)
    diagnosed_count             INTEGER      DEFAULT 0,
    total_patient_encounters    INTEGER      DEFAULT 0,
    -- Model output (populated by M3)
    geography_risk_score        DECIMAL(5,2),
    score_version               VARCHAR(20),
    PRIMARY KEY (zip, score_date)
);

-- ── Indexes ────────────────────────────────────────────────
CREATE INDEX idx_conditions_patient   ON conditions(patient_id);
CREATE INDEX idx_conditions_snomed    ON conditions(snomed_code);
CREATE INDEX idx_medications_patient  ON medications(patient_id);
CREATE INDEX idx_medications_start    ON medications(start_date);
CREATE INDEX idx_observations_patient ON observations(patient_id);
CREATE INDEX idx_observations_loinc   ON observations(loinc_code);
CREATE INDEX idx_otc_patient          ON otc_transactions(patient_id);
CREATE INDEX idx_otc_date             ON otc_transactions(transaction_date);
CREATE INDEX idx_otc_zip              ON otc_transactions(zip);
CREATE INDEX idx_patients_zip         ON patients(zip);
CREATE INDEX idx_patients_cohort      ON patients(cohort);

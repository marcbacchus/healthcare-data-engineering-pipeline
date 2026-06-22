-- Raw layer DDL: all source columns are VARCHAR — no type casting at this layer.
-- Type enforcement happens in dbt staging models (Phase 2) via TRY_TO_* functions.
-- Three metadata columns added to every table by the ingest scripts.

USE DATABASE HEALTHCARE_RAW;
USE SCHEMA RAW;

-- ============================================================
-- CMS Open Payments: pharma/device manufacturer payments to physicians
-- Source: data.cms.gov General Payment Data, program year 2023
-- Feeds: fct_provider_payments (Phase 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS CMS_OPEN_PAYMENTS (
    record_id                                                       VARCHAR,
    covered_recipient_type                                          VARCHAR,
    covered_recipient_npi                                           VARCHAR,
    physician_profile_id                                            VARCHAR,
    physician_first_name                                            VARCHAR,
    physician_last_name                                             VARCHAR,
    recipient_state                                                 VARCHAR,
    recipient_country                                               VARCHAR,
    submitting_applicable_manufacturer_or_applicable_gpo_name       VARCHAR,
    applicable_manufacturer_or_applicable_gpo_making_payment_name   VARCHAR,
    total_amount_of_payment_usdollars                               VARCHAR,
    date_of_payment                                                 VARCHAR,
    number_of_payments_included_in_total_amount                     VARCHAR,
    form_of_payment_or_transfer_of_value                            VARCHAR,
    nature_of_payment_or_transfer_of_value                          VARCHAR,
    program_year                                                    VARCHAR,
    _loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file VARCHAR,
    _row_hash    VARCHAR
);

-- ============================================================
-- FDA FAERS Demographics: one row per adverse event report submission
-- Source: FDA FAERS quarterly ASCII download, Q4 2024
-- Feeds: fct_adverse_events (Phase 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS FAERS_DEMO (
    primaryid        VARCHAR,  -- unique report ID (primary key in FAERS)
    caseid           VARCHAR,
    caseversion      VARCHAR,
    i_f_cod          VARCHAR,  -- I=initial report, F=follow-up
    event_dt         VARCHAR,
    mfr_dt           VARCHAR,
    init_fda_dt      VARCHAR,
    fda_dt           VARCHAR,
    rept_cod         VARCHAR,  -- report type: EXP=expedited, PER=periodic, etc.
    mfr_num          VARCHAR,
    mfr_sndr         VARCHAR,
    age              VARCHAR,
    age_cod          VARCHAR,
    age_grp          VARCHAR,
    sex              VARCHAR,
    wt               VARCHAR,
    wt_cod           VARCHAR,
    rept_dt          VARCHAR,
    to_mfr           VARCHAR,
    occp_cod         VARCHAR,  -- reporter occupation: MD, PH (pharmacist), etc.
    reporter_country VARCHAR,
    occr_country     VARCHAR,
    _loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file VARCHAR,
    _row_hash    VARCHAR
);

-- ============================================================
-- Synthea Patients: synthetic patient demographics
-- Source: Synthea v3 local generation, 1,000 patients
-- Feeds: mart_patient_risk (Phase 2)
-- ============================================================
CREATE TABLE IF NOT EXISTS SYNTHEA_PATIENTS (
    id                  VARCHAR,  -- UUID, primary key across Synthea tables
    birthdate           VARCHAR,
    deathdate           VARCHAR,
    ssn                 VARCHAR,
    drivers             VARCHAR,
    passport            VARCHAR,
    prefix              VARCHAR,
    first               VARCHAR,
    last                VARCHAR,
    suffix              VARCHAR,
    maiden              VARCHAR,
    marital             VARCHAR,
    race                VARCHAR,
    ethnicity           VARCHAR,
    gender              VARCHAR,
    birthplace          VARCHAR,
    address             VARCHAR,
    city                VARCHAR,
    state               VARCHAR,
    county              VARCHAR,
    fips                VARCHAR,
    zip                 VARCHAR,
    lat                 VARCHAR,
    lon                 VARCHAR,
    healthcare_expenses VARCHAR,
    healthcare_coverage VARCHAR,
    income              VARCHAR,
    _loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file VARCHAR,
    _row_hash    VARCHAR
);

-- ============================================================
-- Synthea Conditions: diagnoses tied to synthetic patients
-- Source: Synthea v3 local generation (SNOMED-CT coded)
-- Feeds: mart_patient_risk (Phase 2) — drives comorbidity_score
-- ============================================================
CREATE TABLE IF NOT EXISTS SYNTHEA_CONDITIONS (
    start_dt    VARCHAR,  -- renamed from 'start' (Snowflake reserved word)
    stop_dt     VARCHAR,  -- renamed from 'stop'; NULL if condition is still active
    patient     VARCHAR,  -- FK to SYNTHEA_PATIENTS.id
    encounter   VARCHAR,
    code        VARCHAR,  -- SNOMED-CT concept code
    system      VARCHAR,
    description VARCHAR,
    _loaded_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    _source_file VARCHAR,
    _row_hash    VARCHAR
);

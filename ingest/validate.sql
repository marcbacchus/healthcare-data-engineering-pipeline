-- Phase 1 Week 2 validation queries
-- Run in Snowflake after all four tables are loaded.

USE DATABASE HEALTHCARE_RAW;
USE SCHEMA RAW;

-- ── 1. Row counts ─────────────────────────────────────────────────────────────
SELECT 'CMS_OPEN_PAYMENTS'  AS table_name, COUNT(*) AS row_count FROM CMS_OPEN_PAYMENTS
UNION ALL
SELECT 'FAERS_DEMO',                        COUNT(*)              FROM FAERS_DEMO
UNION ALL
SELECT 'SYNTHEA_PATIENTS',                  COUNT(*)              FROM SYNTHEA_PATIENTS
UNION ALL
SELECT 'SYNTHEA_CONDITIONS',                COUNT(*)              FROM SYNTHEA_CONDITIONS
ORDER BY table_name;

-- ── 2. CMS: null rates on key columns ─────────────────────────────────────────
SELECT
    COUNT(*)                                                           AS total,
    SUM(IFF(record_id IS NULL, 1, 0))                                  AS null_record_id,
    SUM(IFF(total_amount_of_payment_usdollars IS NULL, 1, 0))          AS null_amount,
    SUM(IFF(date_of_payment IS NULL, 1, 0))                            AS null_date,
    SUM(IFF(covered_recipient_npi IS NULL, 1, 0))                      AS null_npi,
    SUM(IFF(nature_of_payment_or_transfer_of_value IS NULL, 1, 0))     AS null_nature
FROM CMS_OPEN_PAYMENTS;

-- ── 3. CMS: duplicate record_ids (expect 0) ───────────────────────────────────
SELECT record_id, COUNT(*) AS n
FROM CMS_OPEN_PAYMENTS
GROUP BY record_id
HAVING n > 1
LIMIT 10;

-- ── 4. CMS: payment breakdown by nature (sanity check on distribution) ────────
SELECT
    nature_of_payment_or_transfer_of_value,
    COUNT(*)                                              AS payment_count,
    ROUND(SUM(TRY_TO_DOUBLE(total_amount_of_payment_usdollars)), 2) AS total_usd
FROM CMS_OPEN_PAYMENTS
GROUP BY 1
ORDER BY total_usd DESC NULLS LAST;

-- ── 5. FAERS: null rates on key columns ───────────────────────────────────────
SELECT
    COUNT(*)                                       AS total,
    SUM(IFF(primaryid IS NULL, 1, 0))              AS null_primaryid,
    SUM(IFF(caseid IS NULL, 1, 0))                 AS null_caseid,
    SUM(IFF(event_dt IS NULL, 1, 0))               AS null_event_dt,
    SUM(IFF(sex IS NULL, 1, 0))                    AS null_sex,
    SUM(IFF(age IS NULL, 1, 0))                    AS null_age,
    SUM(IFF(occr_country IS NULL, 1, 0))           AS null_country
FROM FAERS_DEMO;

-- ── 6. FAERS: age group distribution (spot-check data quality) ────────────────
SELECT age_grp, COUNT(*) AS n
FROM FAERS_DEMO
GROUP BY age_grp
ORDER BY n DESC;

-- ── 7. Synthea: patient gender + race breakdown ────────────────────────────────
SELECT gender, race, COUNT(*) AS n
FROM SYNTHEA_PATIENTS
GROUP BY 1, 2
ORDER BY 3 DESC;

-- ── 8. Synthea: conditions volume check (expect ~5-15 avg per patient) ─────────
SELECT
    COUNT(DISTINCT patient)                                  AS unique_patients,
    COUNT(*)                                                 AS total_conditions,
    ROUND(COUNT(*) / NULLIF(COUNT(DISTINCT patient), 0), 1) AS avg_per_patient,
    SUM(IFF(stop_dt IS NULL, 1, 0))                         AS still_active
FROM SYNTHEA_CONDITIONS;

-- ── 9. Top 10 conditions by frequency ─────────────────────────────────────────
SELECT description, COUNT(*) AS n
FROM SYNTHEA_CONDITIONS
GROUP BY description
ORDER BY n DESC
LIMIT 10;

-- ── 10. Metadata integrity: every row should have a hash and source file ───────
SELECT
    'CMS_OPEN_PAYMENTS' AS t,
    SUM(IFF(_row_hash IS NULL, 1, 0))    AS null_hashes,
    COUNT(DISTINCT _source_file)          AS distinct_source_files,
    MIN(_loaded_at)                       AS earliest_load,
    MAX(_loaded_at)                       AS latest_load
FROM CMS_OPEN_PAYMENTS
UNION ALL
SELECT 'FAERS_DEMO',
    SUM(IFF(_row_hash IS NULL, 1, 0)), COUNT(DISTINCT _source_file), MIN(_loaded_at), MAX(_loaded_at)
FROM FAERS_DEMO
UNION ALL
SELECT 'SYNTHEA_PATIENTS',
    SUM(IFF(_row_hash IS NULL, 1, 0)), COUNT(DISTINCT _source_file), MIN(_loaded_at), MAX(_loaded_at)
FROM SYNTHEA_PATIENTS
UNION ALL
SELECT 'SYNTHEA_CONDITIONS',
    SUM(IFF(_row_hash IS NULL, 1, 0)), COUNT(DISTINCT _source_file), MIN(_loaded_at), MAX(_loaded_at)
FROM SYNTHEA_CONDITIONS;

-- Thin passthrough view onto mart_patient_risk — see rpt_provider_payments.sql
-- for why this indirection exists.
select * from {{ ref('mart_patient_risk') }}

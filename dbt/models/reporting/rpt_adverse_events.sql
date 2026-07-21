-- Thin passthrough view onto fct_adverse_events — see rpt_provider_payments.sql
-- for why this indirection exists.
select * from {{ ref('fct_adverse_events') }}

-- Thin passthrough view onto fct_provider_payments, materialized in the
-- REPORTING database so REPORTER (BI / analyst / text-to-SQL access) never
-- needs privileges on the TRANSFORM database dbt itself writes to.
select * from {{ ref('fct_provider_payments') }}

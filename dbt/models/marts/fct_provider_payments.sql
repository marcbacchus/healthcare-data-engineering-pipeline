with payments as (

    select * from {{ ref('stg_cms_open_payments') }}

),

final as (

    select
        -- keys
        record_id                               as payment_id,
        recipient_npi,
        physician_profile_id,

        -- who received the payment
        physician_first_name,
        physician_last_name,
        recipient_type,
        recipient_state,
        recipient_country,
        (recipient_country != 'United States')  as is_foreign_recipient,

        -- who made the payment
        paying_manufacturer,
        submitting_manufacturer,

        -- what the payment was for
        payment_nature,
        payment_form,

        -- payment financials
        payment_amount_usd,
        payment_date,
        payment_count,
        program_year,
        YEAR(payment_date)                      as payment_year,
        QUARTER(payment_date)                   as payment_quarter,

        -- ingest metadata
        _loaded_at,
        _source_file

    from payments
    where record_id is not null
      and payment_amount_usd is not null
      and payment_date is not null

)

select * from final

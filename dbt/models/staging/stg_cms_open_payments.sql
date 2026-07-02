with source as (

    select * from {{ source('raw', 'cms_open_payments') }}

),

renamed as (

    select
        -- keys
        record_id,

        -- recipient
        NULLIF(covered_recipient_type, '')                                         as recipient_type,
        NULLIF(covered_recipient_npi, '')                                          as recipient_npi,
        NULLIF(physician_profile_id, '')                                           as physician_profile_id,
        NULLIF(physician_first_name, '')                                           as physician_first_name,
        NULLIF(physician_last_name, '')                                            as physician_last_name,
        NULLIF(recipient_state, '')                                                as recipient_state,
        NULLIF(recipient_country, '')                                              as recipient_country,

        -- manufacturer (source columns are extremely verbose; renamed here once)
        NULLIF(submitting_applicable_manufacturer_or_applicable_gpo_name, '')     as submitting_manufacturer,
        NULLIF(applicable_manufacturer_or_applicable_gpo_making_payment_name, '') as paying_manufacturer,

        -- payment financials
        TRY_TO_NUMBER(
            NULLIF(total_amount_of_payment_usdollars, ''), 18, 2
        )                                                                          as payment_amount_usd,

        TRY_TO_DATE(NULLIF(date_of_payment, ''), 'MM/DD/YYYY')                   as payment_date,

        TRY_TO_NUMBER(
            NULLIF(number_of_payments_included_in_total_amount, '')
        )::int                                                                     as payment_count,

        -- payment classification
        NULLIF(form_of_payment_or_transfer_of_value, '')                          as payment_form,
        NULLIF(nature_of_payment_or_transfer_of_value, '')                        as payment_nature,

        TRY_TO_NUMBER(NULLIF(program_year, ''))::int                              as program_year,

        -- ingest metadata
        _loaded_at,
        _source_file,
        _row_hash

    from source

)

select * from renamed

with events as (

    select * from {{ ref('stg_faers_demo') }}

),

final as (

    select
        -- keys
        report_id,
        case_id,
        case_version,

        -- report classification
        initial_or_followup,
        (initial_or_followup = 'I') as is_initial_report,
        report_type,

        -- patient demographics
        patient_age_raw,
        age_unit,
        age_group,
        patient_age_years,
        patient_sex,
        patient_weight_raw,
        weight_unit,

        -- reporter
        reporter_occupation,
        reporter_country,
        manufacturer_sender,
        manufacturer_report_number,
        sent_to_manufacturer,

        -- dates
        event_date,
        report_date,
        fda_receive_date,
        initial_fda_receive_date,
        manufacturer_receive_date,
        YEAR(report_date)           as report_year,
        QUARTER(report_date)        as report_quarter,

        -- geography
        occurrence_country,

        -- ingest metadata
        _loaded_at,
        _source_file

    from events
    where report_id is not null

)

select * from final

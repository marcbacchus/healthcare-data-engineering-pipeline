with source as (

    select * from {{ source('raw', 'faers_demo') }}

),

renamed as (

    select
        -- keys
        NULLIF(primaryid, '')   as report_id,
        NULLIF(caseid, '')      as case_id,
        NULLIF(caseversion, '') as case_version,

        -- report classification
        NULLIF(i_f_cod, '')     as initial_or_followup,  -- I=initial, F=follow-up
        NULLIF(rept_cod, '')    as report_type,           -- EXP=expedited, PER=periodic

        -- dates (FAERS uses YYYYMMDD format)
        TRY_TO_DATE(NULLIF(event_dt, ''),      'YYYYMMDD') as event_date,
        TRY_TO_DATE(NULLIF(rept_dt, ''),       'YYYYMMDD') as report_date,
        TRY_TO_DATE(NULLIF(fda_dt, ''),        'YYYYMMDD') as fda_receive_date,
        TRY_TO_DATE(NULLIF(init_fda_dt, ''),   'YYYYMMDD') as initial_fda_receive_date,
        TRY_TO_DATE(NULLIF(mfr_dt, ''),        'YYYYMMDD') as manufacturer_receive_date,

        -- patient demographics
        TRY_TO_NUMBER(NULLIF(age, ''), 8, 2)  as patient_age_raw,
        NULLIF(age_cod, '')                    as age_unit,
        NULLIF(age_grp, '')                    as age_group,

        -- Normalize age to years regardless of reported unit for cross-report analysis
        case NULLIF(age_cod, '')
            when 'YR'  then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2)
            when 'DEC' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) * 10
            when 'MON' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 12
            when 'WK'  then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 52
            when 'DY'  then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 365
            else null
        end                                    as patient_age_years,

        NULLIF(sex, '')                        as patient_sex,
        TRY_TO_NUMBER(NULLIF(wt, ''), 8, 2)   as patient_weight_raw,
        NULLIF(wt_cod, '')                     as weight_unit,

        -- reporter / manufacturer
        NULLIF(occp_cod, '')                   as reporter_occupation,
        NULLIF(reporter_country, '')           as reporter_country,
        NULLIF(mfr_sndr, '')                   as manufacturer_sender,
        NULLIF(mfr_num, '')                    as manufacturer_report_number,
        NULLIF(to_mfr, '')                     as sent_to_manufacturer,

        -- geography
        NULLIF(occr_country, '')               as occurrence_country,

        -- ingest metadata
        _loaded_at,
        _source_file,
        _row_hash

    from source

)

select * from renamed

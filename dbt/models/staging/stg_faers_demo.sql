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

        -- Normalize age to years regardless of reported unit for cross-report analysis.
        -- openFDA's patientonsetageunit is numeric (800=Decade, 801=Year,
        -- 802=Month, 803=Week, 804=Day; docs/data_dictionary.md) — this used
        -- to check for 'YR'/'DEC'/'MON'/'WK'/'DY' letter codes from the old FDA
        -- ASCII-file convention, which never matched, silently nulling out
        -- patient_age_years for every row (~60% of rows have real age data).
        case NULLIF(age_cod, '')
            when '801' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2)
            when '800' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) * 10
            when '802' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 12
            when '803' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 52
            when '804' then TRY_TO_NUMBER(NULLIF(age, ''), 8, 2) / 365
            else null
        end                                    as patient_age_years,

        -- openFDA's patientsex is numeric (1=Male, 2=Female, 0=Unknown), not the
        -- M/F letter convention from the old FDA ASCII files — recode here so
        -- every downstream consumer gets a self-explanatory value, not a code
        -- each consumer has to independently look up (see docs/data_dictionary.md).
        NULLIF(sex, '')                        as patient_sex_raw,
        case NULLIF(sex, '')
            when '1' then 'M'
            when '2' then 'F'
            when '0' then 'U'
            else null
        end                                    as patient_sex,
        TRY_TO_NUMBER(NULLIF(wt, ''), 8, 2)   as patient_weight_raw,
        NULLIF(wt_cod, '')                     as weight_unit,

        -- reporter / manufacturer
        -- openFDA's primarysource.qualification is numeric (1=Physician,
        -- 2=Pharmacist, 3=Other health professional, 4=Lawyer, 5=Consumer or
        -- non-health professional, 6=Other) — same recoding rationale as sex.
        NULLIF(occp_cod, '')                   as reporter_occupation_raw,
        case NULLIF(occp_cod, '')
            when '1' then 'physician'
            when '2' then 'pharmacist'
            when '3' then 'other health professional'
            when '4' then 'lawyer'
            when '5' then 'consumer or non-health professional'
            when '6' then 'other'
            else null
        end                                    as reporter_occupation,
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

),

-- openFDA's skip/limit pagination isn't stable without an explicit sort
-- (fixed in ingest/load_faers.py going forward), which let the same
-- report land on two consecutive pages during ingestion — dedupe here
-- rather than in RAW, which stays untouched per this project's convention.
deduplicated as (

    select *
    from renamed
    qualify row_number() over (
        partition by report_id
        order by _loaded_at
    ) = 1

)

select * from deduplicated

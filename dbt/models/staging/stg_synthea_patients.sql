with source as (

    select * from {{ source('raw', 'synthea_patients') }}

),

renamed as (

    select
        -- keys
        id                                                     as patient_id,

        -- identity
        NULLIF(prefix, '')                                     as name_prefix,
        NULLIF(first, '')                                      as first_name,
        NULLIF(last, '')                                       as last_name,
        NULLIF(suffix, '')                                     as name_suffix,
        NULLIF(maiden, '')                                     as maiden_name,
        NULLIF(ssn, '')                                        as ssn,
        NULLIF(drivers, '')                                    as drivers_license,
        NULLIF(passport, '')                                   as passport_number,

        -- demographics
        TRY_TO_DATE(NULLIF(birthdate, ''))                    as birth_date,
        TRY_TO_DATE(NULLIF(deathdate, ''))                    as death_date,
        NULLIF(marital, '')                                    as marital_status,
        NULLIF(race, '')                                       as race,
        NULLIF(ethnicity, '')                                  as ethnicity,
        NULLIF(gender, '')                                     as gender,

        -- geography
        NULLIF(birthplace, '')                                 as birthplace,
        NULLIF(address, '')                                    as address,
        NULLIF(city, '')                                       as city,
        NULLIF(state, '')                                      as state,
        NULLIF(county, '')                                     as county,
        NULLIF(zip, '')                                        as zip,
        TRY_TO_DOUBLE(NULLIF(lat, ''))                        as latitude,
        TRY_TO_DOUBLE(NULLIF(lon, ''))                        as longitude,

        -- financials
        TRY_TO_NUMBER(NULLIF(healthcare_expenses, ''), 18, 2) as healthcare_expenses_usd,
        TRY_TO_NUMBER(NULLIF(healthcare_coverage, ''), 18, 2) as healthcare_coverage_usd,
        TRY_TO_NUMBER(NULLIF(income, ''), 18, 2)              as income_usd,

        -- ingest metadata
        _loaded_at,
        _source_file,
        _row_hash

    from source

)

select * from renamed

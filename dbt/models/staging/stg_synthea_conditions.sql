with source as (

    select * from {{ source('raw', 'synthea_conditions') }}

),

renamed as (

    select
        -- keys (no surrogate key — grain is patient + encounter + code)
        NULLIF(patient, '')     as patient_id,
        NULLIF(encounter, '')   as encounter_id,

        -- diagnosis
        NULLIF(code, '')        as snomed_code,
        NULLIF(system, '')      as code_system,
        NULLIF(description, '') as condition_description,

        -- dates (Synthea uses ISO 8601 YYYY-MM-DD)
        TRY_TO_DATE(NULLIF(start_dt, '')) as condition_start_date,
        TRY_TO_DATE(NULLIF(stop_dt, ''))  as condition_end_date,

        -- null stop_dt means condition is still active at the time of data generation
        (stop_dt is null)                  as is_active,

        -- ingest metadata
        _loaded_at,
        _source_file,
        _row_hash

    from source

)

select * from renamed

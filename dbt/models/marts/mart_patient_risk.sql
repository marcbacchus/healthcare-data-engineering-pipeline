with patients as (

    select * from {{ ref('stg_synthea_patients') }}

),

conditions as (

    select * from {{ ref('stg_synthea_conditions') }}

),

condition_summary as (

    select
        patient_id,
        COUNT(*)                               as total_condition_count,
        COUNT(case when is_active then 1 end)  as active_condition_count,
        COUNT(distinct snomed_code)            as distinct_condition_types

    from conditions
    group by 1

),

final as (

    select
        -- keys
        p.patient_id,

        -- identity
        p.first_name,
        p.last_name,

        -- demographics
        p.birth_date,
        p.death_date,
        (p.death_date is not null) as is_deceased,

        DATEDIFF(
            'year',
            p.birth_date,
            coalesce(p.death_date, current_date())
        )                          as age_at_study_end,

        p.gender,
        p.race,
        p.ethnicity,
        p.marital_status,

        -- geography
        p.state,
        p.zip,

        -- socioeconomic
        p.income_usd,
        p.healthcare_expenses_usd,
        p.healthcare_coverage_usd,

        -- risk features (consumed by Phase 4 Feature Store)
        coalesce(c.active_condition_count,  0) as comorbidity_score,
        coalesce(c.total_condition_count,   0) as total_condition_count,
        coalesce(c.distinct_condition_types, 0) as distinct_condition_types,

        -- Phase 2 proxy: polypharmacy defined as >= 5 concurrent active conditions.
        -- Phase 4 will replace this with actual concurrent medication count
        -- once the Synthea medications table is loaded.
        (coalesce(c.active_condition_count, 0) >= 5) as polypharmacy_flag,

        -- Clinical risk tier drives cohort selection and model thresholds in Phase 4
        case
            when coalesce(c.active_condition_count, 0) >= 5 then 'high'
            when coalesce(c.active_condition_count, 0) >= 2 then 'medium'
            else 'low'
        end                        as risk_tier,

        -- ingest metadata
        p._loaded_at,
        p._source_file

    from patients p
    left join condition_summary c
        on p.patient_id = c.patient_id

)

select * from final

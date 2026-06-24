-- Override dbt's default schema naming so +schema: staging maps to STAGING
-- (not staging_staging). Without this, dbt prepends the target schema name.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

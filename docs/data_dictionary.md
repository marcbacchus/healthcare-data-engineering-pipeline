# Data Dictionary — Raw Layer

Database: `HEALTHCARE_RAW`  Schema: `RAW`

All columns are `VARCHAR` — no type casting at this layer. Type enforcement happens in dbt staging models (Phase 2) via `TRY_TO_DATE()`, `TRY_TO_NUMBER()`, `NULLIF()`. Every table carries three standard metadata columns appended at load time.

**Standard metadata columns (all tables):**

| Column | Type | Description |
|---|---|---|
| `_loaded_at` | `TIMESTAMP_NTZ` | UTC timestamp when the row was written to Snowflake |
| `_source_file` | `VARCHAR` | Identifier for the source file or API call that produced this row |
| `_row_hash` | `VARCHAR` | MD5 of all source columns pipe-delimited — used for deduplication |

---

## CMS_OPEN_PAYMENTS

**Source:** CMS Open Payments 2023 General Payments — [openpaymentsdata.cms.gov](https://openpaymentsdata.cms.gov)  
**Load script:** `ingest/load_cms.py`  
**Rows:** 100,000 (streamed via DKAN API, first 100K of ~12M)  
**Feeds:** `fct_provider_payments` (Phase 2)

| Column | Description | Null notes |
|---|---|---|
| `record_id` | Unique payment record identifier | Never null |
| `covered_recipient_type` | Covered Individual or Teaching Hospital | Never null |
| `covered_recipient_npi` | NPI of the receiving physician | Null for teaching hospital payments (302 rows expected) |
| `physician_profile_id` | CMS physician profile ID | |
| `physician_first_name` | Recipient first name | |
| `physician_last_name` | Recipient last name | |
| `recipient_state` | State of recipient | |
| `recipient_country` | Country of recipient | |
| `submitting_applicable_manufacturer_or_applicable_gpo_name` | Entity submitting the payment | |
| `applicable_manufacturer_or_applicable_gpo_making_payment_name` | Entity making the payment | |
| `total_amount_of_payment_usdollars` | Payment amount in USD | Never null |
| `date_of_payment` | Date payment was made (YYYY-MM-DD string) | Never null |
| `number_of_payments_included_in_total_amount` | Count of payments rolled into this record | |
| `form_of_payment_or_transfer_of_value` | Payment form (cash, stock, etc.) | |
| `nature_of_payment_or_transfer_of_value` | Payment category (Consulting Fee, Food and Beverage, etc.) | Never null |
| `program_year` | CMS program year | |

---

## FAERS_DEMO

**Source:** FDA FAERS Q4 2024 — [openFDA REST API](https://api.fda.gov/drug/event.json)  
**Load script:** `ingest/load_faers.py`  
**Rows:** 26,000 (openFDA REST API hard ceiling at skip=25000; full dataset ~410K requires bulk download)  
**Feeds:** `fct_adverse_events` (Phase 2)

> **Note on NULL columns:** The original FAERS data source (`fis.fda.gov` ASCII bulk download) is no longer DNS-resolvable as of 2026. The replacement source — the openFDA REST API — does not expose all fields from the ASCII format. Seven columns are always NULL in this table as a result; they are documented below. This does not affect Phase 2 modeling.

| Column | Description | Null notes |
|---|---|---|
| `primaryid` | Unique adverse event report ID | Never null |
| `caseid` | Case identifier | **Always NULL** — not exposed by openFDA API |
| `caseversion` | Version number of the case report | |
| `i_f_cod` | Initial (I) or Follow-up (F) report flag | **Always NULL** — not exposed by openFDA API |
| `event_dt` | Date the adverse event occurred | **Always NULL** — not exposed by openFDA API |
| `mfr_dt` | Date manufacturer received the report | Maps to `transmissiondate` |
| `init_fda_dt` | Date FDA initially received the report | **Always NULL** — not exposed by openFDA API |
| `fda_dt` | Date FDA received this version | Maps to `receivedate` (YYYYMMDD) |
| `rept_cod` | Report type (1=Expedited, 2=Direct, 3=Periodic, 4=Other) | |
| `mfr_num` | Manufacturer report number | Maps to `companynumb` |
| `mfr_sndr` | Manufacturer sender organization | Maps to `sender.senderorganization` |
| `age` | Patient age at time of event | ~41% null — voluntary reporting |
| `age_cod` | Age unit (800=Decade, 801=Year, 802=Month, 803=Week, 804=Day) | Null when age is null |
| `age_grp` | Age group bucket | **Always NULL** — not exposed by openFDA API |
| `sex` | Patient sex (1=Male, 2=Female, 0=Unknown) | ~17% null — voluntary reporting |
| `wt` | Patient weight | Sparse — voluntary reporting |
| `wt_cod` | Weight unit | **Always NULL** — not exposed by openFDA API |
| `rept_dt` | Date report was received by sender | Maps to `receiptdate` |
| `to_mfr` | Report forwarded to manufacturer flag | **Always NULL** — not exposed by openFDA API |
| `occp_cod` | Reporter occupation (MD, PH=pharmacist, CN=consumer, etc.) | Maps to `primarysource.qualification` |
| `reporter_country` | Country of the primary reporter | Maps to `primarysource.reportercountry` |
| `occr_country` | Country where event occurred | Maps to `occurcountry` |

---

## SYNTHEA_PATIENTS

**Source:** Synthea v3 — generated locally via `ingest/setup_synthea.sh`  
**Load script:** `ingest/load_synthea.py`  
**Rows:** 1,161 (1,000-patient generation; some patients spawn dependents)  
**Feeds:** `mart_patient_risk` (Phase 2)

| Column | Description | Null notes |
|---|---|---|
| `id` | UUID — primary key across all Synthea tables | Never null |
| `birthdate` | Date of birth (YYYY-MM-DD) | Never null |
| `deathdate` | Date of death; NULL if patient is alive | ~94% null (living patients) |
| `ssn` | Synthetic SSN | |
| `drivers` | Synthetic driver's license number | |
| `passport` | Synthetic passport number | |
| `prefix` | Name prefix (Mr., Mrs., etc.) | |
| `first` | First name | |
| `last` | Last name | |
| `suffix` | Name suffix | |
| `maiden` | Maiden name | |
| `marital` | Marital status (M, S) | |
| `race` | Race (white, black, asian, native, other, hawaiian) | |
| `ethnicity` | Ethnicity (nonhispanic, hispanic) | |
| `gender` | Gender (M, F) | |
| `birthplace` | City of birth | |
| `address` | Street address | |
| `city` | City | |
| `state` | State | |
| `county` | County | |
| `fips` | FIPS county code | |
| `zip` | ZIP code | |
| `lat` | Latitude | |
| `lon` | Longitude | |
| `healthcare_expenses` | Lifetime healthcare expenses (USD) | |
| `healthcare_coverage` | Lifetime healthcare coverage (USD) | |
| `income` | Annual income | |

---

## SYNTHEA_CONDITIONS

**Source:** Synthea v3 — generated locally via `ingest/setup_synthea.sh`  
**Load script:** `ingest/load_synthea.py`  
**Rows:** 42,639 (~36.7 conditions per patient on average)  
**Feeds:** `mart_patient_risk` (Phase 2) — drives `comorbidity_score`

> **Note:** `start` and `stop` are reserved words in Snowflake. These columns are renamed to `start_dt` and `stop_dt` at ingest time.

| Column | Description | Null notes |
|---|---|---|
| `start_dt` | Date condition was diagnosed (YYYY-MM-DD); renamed from `start` | Never null |
| `stop_dt` | Date condition resolved (YYYY-MM-DD); renamed from `stop` | NULL if condition is still active (~26% of rows) |
| `patient` | FK → `SYNTHEA_PATIENTS.id` | Never null |
| `encounter` | Encounter UUID where condition was recorded | Never null |
| `code` | SNOMED-CT concept code | Never null |
| `system` | Code system (always `http://snomed.info/sct`) | |
| `description` | Human-readable condition name | Never null |

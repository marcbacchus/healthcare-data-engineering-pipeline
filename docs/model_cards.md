# Model Cards — Healthcare AI Data Platform (Phase 4)

Two models trained and deployed in Phase 4. A third model (adverse event severity)
was dropped due to insufficient signal in the FAERS demographic data — documented
below.

---

## Model 1: Readmission Risk (XGBoost)

### Intended Use
Predicts the probability that a patient will be readmitted to hospital. Intended
for use by care management teams to prioritize post-discharge follow-up
interventions. Output is a binary classification (0 = low risk, 1 = high risk)
with a raw probability score for threshold-based routing.

**Not intended for:** autonomous clinical decision-making, denial of care, or any
use without human review.

### Training Data
- **Source:** `HEALTHCARE_TRANSFORM.MARTS.MART_PATIENT_RISK` (dbt-modeled Synthea
  synthetic patient data)
- **Rows:** 1,161 patients (80/20 train/test split, stratified)
- **Label:** Synthetic readmission proxy — **not real clinical outcomes**. Label
  assigned probabilistically based on comorbidity score, age, and financial stress
  ratio. See Limitations.

### Features
| Feature | Type | Source |
|---------|------|--------|
| `age_at_study_end` | int | dbt mart |
| `comorbidity_score` | int | dbt mart (active condition count) |
| `total_condition_count` | int | dbt mart |
| `distinct_condition_types` | int | dbt mart |
| `polypharmacy_flag` | int (0/1) | dbt mart (≥5 active conditions) |
| `income_usd` | float | dbt mart |
| `healthcare_expenses_usd` | float | dbt mart |
| `expense_to_income_ratio` | float | **derived in Databricks** (expenses / (income + 1)) |

### Model Configuration
- **Algorithm:** XGBoost (`XGBClassifier`)
- **Hyperparameters:** n_estimators=100, max_depth=4, learning_rate=0.1
- **Class imbalance handling:** `scale_pos_weight` set to negative/positive ratio
  (~5.0x) to account for 16.6% positive rate

### Metrics (test set, n=233)
| Metric | Threshold 0.35 | Threshold 0.50 |
|--------|---------------|---------------|
| AUC-ROC | 0.512 | 0.512 |
| Precision | 0.141 | 0.158 |
| Recall | 0.359 | 0.231 |
| F1 | 0.203 | 0.188 |

### Threshold Rationale
Two thresholds are logged to support different operational contexts:

- **0.35 (high sensitivity):** Minimizes missed high-risk patients (false negatives).
  Use when the cost of a missed readmission (rehospitalization, complications)
  exceeds the cost of an unnecessary intervention (care management call, follow-up
  visit). Appropriate for high-risk cohorts.
- **0.50 (balanced):** Standard decision boundary. Higher precision, lower recall.
  Use when intervention capacity is constrained and false positives carry
  meaningful cost.

### Limitations
- **Synthetic label:** The readmission label is a probabilistic proxy derived from
  the same features used for training. This creates circularity that suppresses
  AUC (0.512 ≈ random). With real 30-day readmission outcome data, signal would
  be meaningfully higher and the architecture remains unchanged.
- **Small dataset:** 1,161 Synthea patients is insufficient for production
  generalization. Results are illustrative of the pipeline, not clinical validity.
- **Synthetic population:** Synthea generates statistically plausible but not
  real patient records. The model has not been validated on any real patient data.
- **Polypharmacy proxy:** `polypharmacy_flag` uses concurrent active conditions
  as a stand-in for concurrent medications (actual medication data not yet loaded).

### Bias Considerations
- Synthea's synthetic population may not reflect real-world demographic
  distributions. No fairness evaluation has been performed across race, gender,
  or income subgroups.
- `income_usd` and `healthcare_expenses_usd` are included as features. In a
  production setting, direct use of socioeconomic features in clinical risk
  models requires careful ethical review to avoid reinforcing existing
  health disparities.

### Serving
- **Endpoint:** `readmission_risk_model` (Databricks Model Serving, serverless,
  scale-to-zero)
- **Input:** JSON with 8 feature fields (see Features table above)
- **Output:** `{"predictions": [0]}` or `{"predictions": [1]}`
- **Registered model:** `dbw_healthcare_pipeline_7405615280581812.healthcare_features.readmission_risk_model_serving`

---

## Model 2: Adverse Event Severity (Random Forest) — DROPPED

### Why Dropped
FAERS demographic data (Q4 2024) was too sparse for classification:
- `PATIENT_AGE_YEARS`: 26,000/26,000 null
- `IS_INITIAL_REPORT`: 26,000/26,000 null
- `AGE_GROUP`: uniform (single value across all records after staging)
- `INITIAL_OR_FOLLOWUP`: entirely null

No meaningful severity signal was extractable from the available fields.

### Path to Revival
The FAERS OUTC (outcomes) file contains serious/fatal outcome flags that would
provide a real severity label. Loading and staging the OUTC file would make this
model viable. Deferred to a future iteration — the dbt staging model and mart
structure are already in place and would require only additive changes.

---

## Model 3: Provider Payment Anomaly (IsolationForest)

### Intended Use
Flags statistically unusual pharma-to-physician payment patterns in CMS Open
Payments data. Intended for compliance review teams to prioritize manual audit
of high-anomaly payments. Output is a binary anomaly flag and a continuous
anomaly score (more negative = more anomalous).

**Not intended for:** automated payment blocking, regulatory enforcement, or use
without human review of flagged records.

### Training Data
- **Source:** `HEALTHCARE_TRANSFORM.MARTS.FCT_PROVIDER_PAYMENTS` (dbt-modeled
  CMS Open Payments 2023 General Payments data)
- **Rows:** 100,000 payment records
- **Label:** None — unsupervised anomaly detection

### Features
| Feature | Type | Notes |
|---------|------|-------|
| `PAYMENT_AMOUNT_USD` | float | Primary signal |
| `PAYMENT_COUNT` | float | Number of payments in record |
| `PAYMENT_QUARTER` | float | Temporal distribution |
| `IS_FOREIGN_RECIPIENT` | float (0/1) | Geography flag |

### Model Configuration
- **Algorithm:** IsolationForest (`sklearn.ensemble.IsolationForest`)
- **n_estimators:** 100
- **contamination:** 0.05 (assumes ~5% of payments are anomalous)
- **Unsupervised:** no labels used; model isolates observations easy to separate
  from the distribution

### Metrics
| Metric | Value |
|--------|-------|
| Anomalies detected | 4,994 (5.0%) |
| Mean anomaly score | 0.1730 |
| Min anomaly score (most anomalous) | -0.262 |

### Representative Anomalies (top flagged payments)
| Payment Amount | Payment Count | Quarter | Foreign | Anomaly Score |
|---------------|--------------|---------|---------|--------------|
| $191,563 | 4 | Q1 | No | -0.262 |
| $46,100 | 12 | Q1 | No | -0.262 |
| $38,400 | 12 | Q1 | No | -0.262 |
| $39,495 | 8 | Q1 | No | -0.261 |
| $34,058 | 4 | Q1 | No | -0.261 |

High amounts and high payment counts are the primary drivers of anomaly flags,
consistent with expected behavior.

### Limitations
- **Contamination is assumed:** The 5% contamination parameter is a prior
  assumption, not derived from labeled ground truth. Adjust based on domain
  knowledge of the expected fraud/anomaly rate in a production setting.
- **Four features only:** Payment nature, form, recipient specialty, and
  manufacturer identity are not included. A richer feature set would improve
  signal quality.
- **No temporal sequencing:** Payments are treated as independent records.
  Sequential patterns (e.g., escalating payments over time to the same
  physician) are not captured.

### Bias Considerations
- IsolationForest flags statistical outliers, not fraudulent intent. Rare but
  legitimate payment types (e.g., large one-time research grants) may be
  systematically flagged. Any production deployment should include a documented
  human review step before any action is taken on flagged records.

### Serving
- **Not deployed to a live endpoint** — anomaly detection is a batch workload
  (run periodically over new payment data) rather than a real-time scoring use
  case. Re-run the notebook against updated `FCT_PROVIDER_PAYMENTS` data as
  needed.
- **Registered model:** `dbw_healthcare_pipeline_7405615280581812.healthcare_features.payment_anomaly_model`

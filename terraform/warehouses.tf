# X-SMALL = 1 credit/hour. With auto_suspend = 60s, billing stops
# within a minute of the last query — critical on a trial account.
# auto_resume = true means it wakes up automatically; no manual start needed.

resource "snowflake_warehouse" "compute" {
  name                = "COMPUTE_WH"
  warehouse_size      = "X-SMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true  # starts suspended; only runs when a query hits it
  comment             = "Shared compute for all phases. Scale up temporarily for large loads."
}

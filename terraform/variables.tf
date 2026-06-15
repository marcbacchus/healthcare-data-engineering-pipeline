variable "snowflake_org" {
  description = "Snowflake organization name (the part before the dash, e.g. your-org-here)"
  type        = string
}

variable "snowflake_account" {
  description = "Snowflake account name (the part after the dash, e.g. your-account-here)"
  type        = string
}

variable "snowflake_username" {
  description = "Snowflake username with ACCOUNTADMIN privilege"
  type        = string
}

variable "snowflake_password" {
  description = "Snowflake password — never commit this; lives only in terraform.tfvars"
  type        = string
  sensitive   = true
}

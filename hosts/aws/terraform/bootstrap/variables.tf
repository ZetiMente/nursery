variable "region" {
  description = "AWS region for the state bucket. Should match the region where the main Nursery resources live (default us-east-2)."
  type        = string
  default     = "us-east-2"
}

variable "state_key" {
  description = "Object key under which the main module's terraform.tfstate is stored. Different keys let multiple Nursery deployments share one bucket."
  type        = string
  default     = "nursery/aws/terraform.tfstate"
}

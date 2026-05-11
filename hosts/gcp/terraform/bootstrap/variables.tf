variable "project_id" {
  description = "GCP project ID to host the Terraform state bucket. Should be the same project where Nursery resources are deployed."
  type        = string
}

variable "region" {
  description = "GCS bucket location. Regional locations (e.g. us-central1) are cheaper and match a single-region workload. Default matches the main module's default region."
  type        = string
  default     = "us-central1"
}

variable "state_prefix" {
  description = "Path prefix under which the main module's terraform.tfstate is stored within the bucket. Different prefixes let multiple Nursery deployments share one bucket (e.g. nursery/gcp/dev vs nursery/gcp/prod)."
  type        = string
  default     = "nursery/gcp"
}

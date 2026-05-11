output "bucket_name" {
  description = "Name of the GCS bucket holding the main module's Terraform state."
  value       = google_storage_bucket.tfstate.name
}

output "backend_hcl_path" {
  description = "Path to the generated backend.hcl. Pass this to the main module: terraform init -backend-config=backend.hcl -migrate-state."
  value       = local_file.backend_hcl.filename
}

output "next_step" {
  description = "Copy-paste command to migrate the main module to the GCS backend."
  value       = "cd .. && terraform init -backend-config=backend.hcl -migrate-state"
}

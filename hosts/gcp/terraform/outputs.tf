output "instance_name" {
  description = "Name of the created VM."
  value       = google_compute_instance.this.name
}

output "instance_id" {
  description = "Numeric ID of the VM."
  value       = google_compute_instance.this.instance_id
}

output "public_ip" {
  description = "Ephemeral public IPv4 address."
  value       = google_compute_instance.this.network_interface[0].access_config[0].nat_ip
}

output "internal_ip" {
  description = "Internal IPv4 address inside the VPC."
  value       = google_compute_instance.this.network_interface[0].network_ip
}

output "zone" {
  description = "Zone the VM was placed in."
  value       = google_compute_instance.this.zone
}

output "image" {
  description = "DL VM image used."
  value       = data.google_compute_image.dl.self_link
}

output "image_family" {
  description = "Image family resolved for this VM."
  value       = var.image_family
}

output "service_account" {
  description = "Service account attached to the VM."
  value       = local.effective_sa
}

output "ssh_cidr" {
  description = "CIDR allowed to SSH. If auto-detected, derived from api.ipify.org at plan time."
  value       = local.ssh_cidr
}

output "ssh_command_gcloud" {
  description = "Preferred SSH entrypoint — uses OS Login via IAM, no key files."
  value       = "gcloud compute ssh ${google_compute_instance.this.name} --zone=${var.zone} --project=${var.project_id}"
}

output "ssh_command_raw" {
  description = "Raw-ssh fallback. Requires you to have an OS Login-provisioned key in your gcloud config (~/.ssh/google_compute_engine)."
  value       = "ssh -i ~/.ssh/google_compute_engine $(whoami)@${google_compute_instance.this.network_interface[0].access_config[0].nat_ip}"
}

output "destroy_hint" {
  description = "How to tear this all down."
  value       = "cd hosts/gcp/terraform && terraform destroy"
}

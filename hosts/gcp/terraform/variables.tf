# ---------------------------------------------------------------------------
# Inputs for the Nursery L4 Spot VM on Google Cloud.
#
# All overridable via terraform.tfvars, env (TF_VAR_<name>), or -var on the
# CLI. The only *required* input is project_id.
# ---------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID to deploy into. Project must exist; Terraform will not create it."
  type        = string
}

variable "region" {
  description = "GCP region. us-central1 (Iowa) is the Nursery default — closest to Indiana, L4 well-provisioned."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zone within the region. a/b/c — L4 availability varies by zone and is quota-limited."
  type        = string
  default     = "us-central1-a"
}

variable "name" {
  description = "Name prefix for all resources. Shows up in the GCP console."
  type        = string
  default     = "nursery-l4"
}

variable "machine_type" {
  description = "GCE machine type. g2-standard-4 = 1x L4 GPU (24 GB VRAM), 4 vCPU, 16 GB RAM. Matches AWS g6.xlarge."
  type        = string
  default     = "g2-standard-4"
}

variable "gpu_type" {
  description = "Accelerator type. For g2 instances the GPU is attached as part of the machine type; we do not add an explicit accelerator block. Kept here for future use with n1 + attached GPUs."
  type        = string
  default     = "nvidia-l4"
}

variable "image_family" {
  description = "Deep Learning VM image family. The default is Ubuntu 24.04 + Python 3.12 + CUDA 12.9 + NVIDIA 580 driver."
  type        = string
  default     = "common-cu129-ubuntu-2404-nvidia-580"
}

variable "image_project" {
  description = "Project that hosts the image family. Google's public images live in deeplearning-platform-release."
  type        = string
  default     = "deeplearning-platform-release"
}

variable "boot_disk_gb" {
  description = "Boot disk size in GB. DL VM image is ~60 GB; 150 gives room for Ollama + a large model."
  type        = number
  default     = 150
}

variable "boot_disk_type" {
  description = "Disk type. pd-ssd recommended for acceptable I/O on model loads."
  type        = string
  default     = "pd-ssd"
}

variable "ssh_allow_cidr" {
  description = "CIDR block allowed to SSH in (port 22). Default '' triggers auto-detect (your current public IP via api.ipify.org)."
  type        = string
  default     = ""
}

variable "preemptible" {
  description = "Use spot/preemptible pricing. true = Spot VM (modern; no 24h limit, 60-91% cheaper)."
  type        = bool
  default     = true
}

variable "service_account_email" {
  description = "Service account email to attach to the VM. Leave empty to create a minimal-privilege SA scoped to this VM."
  type        = string
  default     = ""
}

variable "labels" {
  description = "Additional GCP labels merged with Nursery defaults. Useful for cost tracking."
  type        = map(string)
  default     = {}
}

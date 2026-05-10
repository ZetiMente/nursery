# ---------------------------------------------------------------------------
# Inputs for the Nursery L4 spot deployment.
#
# Everything has sensible defaults; you shouldn't need to override anything
# for the first launch. All overridable via terraform.tfvars, env
# (TF_VAR_<name>), or -var on the CLI.
# ---------------------------------------------------------------------------

variable "region" {
  description = "AWS region to deploy into. us-east-2 (Ohio) is the Nursery default — closest to Indiana, same price as us-east-1."
  type        = string
  default     = "us-east-2"
}

variable "name" {
  description = "Name tag for all resources. Shows up in the AWS console."
  type        = string
  default     = "nursery-l4"
}

variable "instance_type" {
  description = "EC2 instance type. g6.xlarge = 1x L4 GPU (24 GB VRAM), 4 vCPU, 16 GB RAM."
  type        = string
  default     = "g6.xlarge"
}

variable "key_pair_name" {
  description = "Name of the EC2 key pair to attach. Must already exist in the target region."
  type        = string
  # no default — you must provide this
}

variable "ssh_allow_cidr" {
  description = "CIDR block allowed to SSH in. Default '' triggers auto-detect (your current public IP)."
  type        = string
  default     = ""
}

variable "root_volume_gb" {
  description = "Root EBS volume size in GB. DLAMI is ~30 GB; 100 gives room for Ollama + a large model."
  type        = number
  default     = 100
}

variable "spot_max_price" {
  description = "Maximum hourly spot price in USD. Leave blank to pay the current market spot price (recommended)."
  type        = string
  default     = ""
}

# Extra tags applied to every resource. Useful for cost tracking.
variable "extra_tags" {
  description = "Additional tags merged with the Nursery defaults."
  type        = map(string)
  default     = {}
}

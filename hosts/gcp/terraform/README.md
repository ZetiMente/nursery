# Nursery — GCP Terraform

Mirror of `hosts/aws/terraform/` for Google Cloud. Provisions one L4 GPU Spot VM, nothing else.

- **Instance:** `g2-standard-4` by default (1× NVIDIA L4, 24 GB VRAM, 4 vCPU, 16 GB RAM)
- **Image:** `common-cu129-ubuntu-2404-nvidia-580` — **Ubuntu 24.04, Python 3.12, CUDA 12.9, NVIDIA 580**
- **Spot:** modern Spot VM (no 24h limit; auto-terminate on preemption)
- **Boot disk:** 150 GB pd-ssd
- **Region / zone:** `us-central1` / `us-central1-a` (Iowa — closest low-latency to Indiana, well-provisioned for L4)
- **Network:** dedicated VPC + subnet, SSH-only firewall from your IP
- **SSH:** OS Login (via `gcloud compute ssh`) — no `.pem` files

## Prerequisites

See [DeployGCP.md](../../../DeployGCP.md) for the full operator walkthrough, including quota requests.

Quick version:

1. `gcloud auth application-default login`
2. `gcloud config set project <your-project-id>`
3. Request GPU quota on the project (one-time; see DeployGCP.md)

## Usage

```bash
cd hosts/gcp/terraform
terraform init

# Real plan
terraform plan -var="project_id=your-project-id"

# Apply
terraform apply -var="project_id=your-project-id"
```

Outputs include `ssh_command_gcloud` — copy-paste to SSH in.

## Teardown

**Always do this when done. Spot VMs are cheap but not free.**

```bash
terraform destroy -var="project_id=your-project-id"
```

## What's NOT in this PR

Same as the AWS module: VM provisioning only. No Ollama install, no Nursery CLI install, no Hermes. Those come in a follow-up (cloud-init / `startup-script` metadata).

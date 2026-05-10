# Nursery — AWS Terraform

This directory provisions a single **L4 GPU EC2 spot instance** on AWS, ready for Nursery agent workloads.

- **Instance:** `g6.xlarge` by default (1× NVIDIA L4, 24 GB VRAM, 4 vCPU, 16 GB RAM)
- **AMI:** Latest Ubuntu 24.04 Deep Learning Base OSS (NVIDIA driver, CUDA, Docker, NVIDIA Container Toolkit pre-installed)
- **Spot:** one-time, terminate on interruption
- **Storage:** 100 GB gp3, encrypted, delete-on-termination
- **Region:** `us-east-2` (Ohio) by default
- **Network:** dedicated VPC, one public subnet, SSH-only ingress from your IP

## Scope of this PR

**This PR only creates the VM.** No Ollama install, no Hermes install, no Nursery CLI install, no cloud-init yet. That comes in the next PR. Tonight's goal is just: `terraform apply` gives you a running GPU instance you can SSH into.

## Prerequisites

1. **AWS CLI configured.** Run `aws sts get-caller-identity` to confirm — you should see your account ID.
2. **Terraform installed** (≥ 1.7). On Ubuntu/Debian:
   ```bash
   wget -O- https://apt.releases.hashicorp.com/gpg | \
     sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
     https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
     sudo tee /etc/apt/sources.list.d/hashicorp.list
   sudo apt update && sudo apt install terraform
   ```
3. **An EC2 key pair in `us-east-2`** (or whichever region you pick). If you haven't made one:
   - AWS Console → EC2 → Key Pairs → Create key pair
   - Name it (e.g. `nursery-l4`), type RSA, format `.pem`, download
   - `chmod 400 ~/path/to/key.pem`

## First launch

```bash
cd hosts/aws/terraform

# One-time init — downloads providers
terraform init

# See what will be created (no changes yet)
terraform plan -var="key_pair_name=nursery-l4"

# Apply. This creates the VPC + instance. Spot request + fulfillment takes ~1-3 min.
terraform apply -var="key_pair_name=nursery-l4"
```

Terraform will print outputs including the public IP and an SSH command:

```
Outputs:
public_ip   = "18.220.xx.xx"
ssh_command = "ssh -i ~/.ssh/aws/nursery-l4.pem ubuntu@18.220.xx.xx"
```

SSH in with the command above (adjust the key path as needed).

## Teardown

**This stops the bill.** Always remember to destroy when you're done for the day — a `g6.xlarge` spot instance runs ~$0.25/hr typical, ~$180/mo if left 24/7.

```bash
cd hosts/aws/terraform
terraform destroy -var="key_pair_name=nursery-l4"
```

Removes the instance, the spot request, the security group, the subnet, the internet gateway, and the VPC. Clean slate.

## Overriding defaults

Any variable can be set via `-var`, a `terraform.tfvars` file, or `TF_VAR_*` env vars.

```bash
# Larger instance (8 vCPU, 32 GB RAM — same L4 GPU)
terraform apply -var="key_pair_name=nursery-l4" -var="instance_type=g6.2xlarge"

# Different region
terraform apply -var="key_pair_name=nursery-l4" -var="region=us-east-1"

# Lock SSH to a specific CIDR (skip IP auto-detect)
terraform apply -var="key_pair_name=nursery-l4" -var="ssh_allow_cidr=1.2.3.4/32"

# Cap spot bid
terraform apply -var="key_pair_name=nursery-l4" -var="spot_max_price=0.40"
```

Or create `terraform.tfvars` (gitignored — don't commit secrets or personal IPs):

```hcl
key_pair_name = "nursery-l4"
instance_type = "g6.xlarge"
region        = "us-east-2"
```

## Safety notes

- **No existing AWS resources will be touched.** Terraform only modifies resources it creates, tracked in its state file. Your other EC2 instances, S3 buckets, VPCs — all invisible.
- **State file is local** (`terraform.tfstate` in this directory). Don't delete it — you'll lose the ability to destroy what you created. Back it up, or migrate to an S3 backend (next PR).
- **`.gitignore`** in this directory excludes `.tfstate*`, `.terraform/`, and `*.tfvars`. The state file can contain sensitive info (public IPs, spot bid prices) and your `.tfvars` may contain your key pair name — neither belongs in git.
- **Spot instance can be interrupted.** AWS may reclaim the capacity with 2-minute notice. For "manual on/off" usage this is fine; for always-on you'd want on-demand.

## What's next (later PRs)

- **Cloud-init**: install Ollama, pull models, install Nursery CLI automatically on first boot.
- **`nursery aws launch`**: Python CLI wrapper around Terraform.
- **S3 state backend**: for team-safe, lock-aware state storage.
- **Multi-instance / multi-region**: spawn many L4 VMs, each with different agents.

# DeployAWS.md — Nursery on AWS

**Goal:** Take you from zero to a running GPU EC2 spot instance on AWS, ready for Nursery agent workloads, using Terraform.

**Scope of this doc:** matches what's in [`hosts/aws/terraform/`](./hosts/aws/terraform/). It provisions the VM and nothing else. Software install (Ollama, Hermes, Nursery CLI) comes in a follow-up PR.

**Status of this PR:** 🐣 VM provisioning works end-to-end. Cloud-init install, `nursery aws launch` CLI wrapper, and S3 state backend are explicit next steps, not in this PR.

---

## What you get

| Piece | Default |
|---|---|
| Instance | `g6.xlarge` — 1× NVIDIA L4 (24 GB VRAM), 4 vCPU, 16 GB RAM |
| AMI | Latest Ubuntu 24.04 **Deep Learning Base OSS** (NVIDIA driver + CUDA + Docker + NVIDIA Container Toolkit pre-installed) |
| Purchasing | Spot, one-time, terminate-on-interruption |
| Storage | 100 GB gp3, encrypted, delete-on-termination |
| Region | `us-east-2` (Ohio) |
| Network | Dedicated VPC (`10.42.0.0/16`), one public subnet, SSH-only ingress from your IP |

Typical spot cost for `g6.xlarge` in us-east-2: **~$0.22–0.35/hr**. On-demand is ~$0.80/hr.

---

## Safety up front

- **Terraform will not touch resources it didn't create.** It tracks its own resources in a state file (`terraform.tfstate`). Your other EC2 instances, VPCs, S3 buckets are invisible to it. You'd have to explicitly run `terraform import` to adopt something external, which this doc does not do.
- **The one real risk is cost.** If `apply` succeeds, you have a running instance accumulating spot charges. Always `terraform destroy` when you're done for the day.
- **The state file is local.** Don't delete `terraform.tfstate` — it's what lets `destroy` know what to tear down. (An S3 backend comes in a later PR.)

---

## Prerequisites

### 1. AWS account + credentials

```bash
aws sts get-caller-identity
```

Should print your account ID, user ARN, and user ID. If it doesn't:

- `aws configure` (if you have `aws-cli` but no creds)
- Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

Your IAM user/role needs, at minimum:

- `ec2:*` (VPC, subnets, security groups, instances, spot requests, tags)
- `iam:PassRole` (for the instance's service role, if you add one later)

### 2. Terraform ≥ 1.7

```bash
terraform version
```

If missing, on Ubuntu/Debian:

```bash
wget -O- https://apt.releases.hashicorp.com/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

On macOS: `brew install terraform` or `brew install opentofu` (OpenTofu is the HashiCorp-free community fork; our config is compatible with both).

### 3. EC2 key pair in your target region

Terraform will attach an existing key pair to the instance — it won't create one. In the AWS Console:

1. Make sure the region picker (top-right) says **US East (Ohio)** (or whatever region you're using).
2. **EC2 → Network & Security → Key Pairs → Create key pair**
3. **Name:** `nursery-l4` (or anything; you'll pass this to Terraform).
4. **Type:** RSA. **Format:** `.pem`.
5. Click create. Your browser downloads `nursery-l4.pem`. **This is the only time AWS shows the private key.** Save it somewhere permanent.

Fix the permissions so SSH won't refuse to use it:

```bash
mkdir -p ~/.ssh/aws
mv ~/Downloads/nursery-l4.pem ~/.ssh/aws/
chmod 400 ~/.ssh/aws/nursery-l4.pem
```

---

## First deploy

### Step 1 — Clone the repo

```bash
git clone git@github.com:ZetiMente/nursery.git
cd nursery/hosts/aws/terraform
```

### Step 2 — Initialize Terraform

```bash
terraform init
```

Downloads the AWS + `http` providers (~100 MB, one-time). On success you'll see `Terraform has been successfully initialized!`.

### Step 3 — See the plan before you change anything

```bash
terraform plan -var="key_pair_name=nursery-l4"
```

Read the output carefully. Expected summary:

```
Plan: ~9 to add, 0 to change, 0 to destroy.
```

**That `0 to destroy` is the safety signal.** If Terraform ever wants to destroy something on a first run, stop and re-read the plan.

Resources it will create:

- 1 VPC (`aws_vpc.this`)
- 1 Internet Gateway (`aws_internet_gateway.this`)
- 1 Public subnet (`aws_subnet.public`)
- 1 Route table + 1 association (`aws_route_table.public`, `aws_route_table_association.public`)
- 1 Security group with 1 ingress rule for SSH from your auto-detected IP (`aws_security_group.instance`)
- 1 Spot instance request (`aws_spot_instance_request.this`)
- 3 EC2 instance tags (`aws_ec2_tag.*`)

### Step 4 — Apply

```bash
terraform apply -var="key_pair_name=nursery-l4"
```

Terraform prints the plan again and asks `Enter a value:` — type `yes`.

Spot fulfillment takes **30 seconds to 3 minutes**. When it finishes you'll see outputs:

```
Outputs:
ami_id           = "ami-0abcdef…"
ami_name         = "Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04) 2026…"
availability_zone = "us-east-2a"
instance_id      = "i-0abc…"
public_dns       = "ec2-18-220-xx-xx.us-east-2.compute.amazonaws.com"
public_ip        = "18.220.xx.xx"
ssh_cidr         = "<your-ip>/32"
ssh_command      = "ssh -i ~/.ssh/aws/nursery-l4.pem ubuntu@18.220.xx.xx"
destroy_hint     = "cd hosts/aws/terraform && terraform destroy"
```

### Step 5 — Verify it works

Use the `ssh_command` output. First connection asks to trust the host key — type `yes`.

```bash
ssh -i ~/.ssh/aws/nursery-l4.pem ubuntu@18.220.xx.xx
```

On the VM:

```bash
nvidia-smi          # Should show the L4 GPU
docker --version    # Pre-installed in the DLAMI
nvidia-container-cli --version   # Pre-installed in the DLAMI
```

`exit` when satisfied.

### Step 6 — Tear it down when you're done

**Always do this when you walk away.** A left-running spot instance is ~$5–8 per day.

```bash
cd nursery/hosts/aws/terraform
terraform destroy -var="key_pair_name=nursery-l4"
```

Type `yes`. Everything Terraform created is removed. Billing stops.

---

## Making the flags permanent

Every deploy needs `-var="key_pair_name=..."`. You can skip that by creating `terraform.tfvars`:

```bash
cd hosts/aws/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars to set key_pair_name (at minimum)
```

Now `terraform apply` (no `-var`) uses those values. The file is gitignored so your key pair name / IP / bid stays local.

---

## Common overrides

| Goal | Flag |
|---|---|
| Different region | `-var="region=us-east-1"` |
| More vCPU/RAM, same GPU | `-var="instance_type=g6.2xlarge"` |
| Larger disk (for big models) | `-var="root_volume_gb=200"` |
| Pin SSH CIDR instead of auto-detect | `-var="ssh_allow_cidr=1.2.3.4/32"` |
| Open SSH to all IPs (key-only auth) | `-var="ssh_allow_cidr=0.0.0.0/0"` |
| Cap spot bid | `-var="spot_max_price=0.40"` |
| Cost-tracking tags | `-var='extra_tags={Owner="matthew",Purpose="hermes-dev"}'` |

---

## Troubleshooting

### `InsufficientInstanceCapacity` / spot request stuck "pending-fulfillment"

`g6.xlarge` spot capacity in `us-east-2` is usually fine, but can get tight. Options:

- Wait 10–15 minutes and retry
- Try a different region: `-var="region=us-east-1"` (most capacity on Earth)
- Try a different instance type: `-var="instance_type=g6.2xlarge"`

### `UnauthorizedOperation`

Your IAM user lacks one of the required permissions. Check it has the `ec2:*` permissions listed above.

### `The key pair '…' does not exist`

You haven't created the key pair in this region yet, or you're pointing at the wrong region. Re-check the region in the AWS Console matches `var.region`.

### SSH hangs / times out

- Instance state is `Running` in the console, but SSH hangs: wait 60 more seconds (status checks finish after the instance is marked running).
- Your public IP changed since `apply`: run `terraform apply` again — it'll detect the new IP and update the security group.

### "State is already locked"

Happens if a previous Terraform run crashed. Safe to recover:

```bash
terraform force-unlock <LOCK_ID>   # ID is in the error message
```

---

## What's next (explicitly deferred to follow-up PRs)

1. **Cloud-init / user-data** — install Ollama (GPU-enabled), pull models, install Nursery CLI automatically on first boot.
2. **`nursery aws launch` CLI wrapper** — spec-driven Terraform invocation. No more `-var="key_pair_name=…"`; the spec holds it.
3. **S3 state backend** — team-safe, lock-aware state storage (instead of `terraform.tfstate` on one machine).
4. **Hermes containerized deployment** — spawn Hermes agents on the VM using our existing `nursery spawn` flow.
5. **Multi-instance / multi-region** — run many L4s, each with different agents, in one `launch` command.

See the [roadmap in README.md](./README.md#roadmap) for full phasing.

---

## File map

| File | Purpose |
|---|---|
| [`hosts/aws/terraform/versions.tf`](./hosts/aws/terraform/versions.tf) | Terraform + provider version pins |
| [`hosts/aws/terraform/variables.tf`](./hosts/aws/terraform/variables.tf) | All inputs, defaults documented |
| [`hosts/aws/terraform/main.tf`](./hosts/aws/terraform/main.tf) | VPC, subnet, SG, spot instance |
| [`hosts/aws/terraform/outputs.tf`](./hosts/aws/terraform/outputs.tf) | Public IP, SSH command, etc. |
| [`hosts/aws/terraform/terraform.tfvars.example`](./hosts/aws/terraform/terraform.tfvars.example) | Copy to `terraform.tfvars`, adjust |
| [`hosts/aws/terraform/README.md`](./hosts/aws/terraform/README.md) | Short reference |
| [`hosts/aws/terraform/.gitignore`](./hosts/aws/terraform/.gitignore) | Excludes state, `.terraform/`, `.tfvars` |

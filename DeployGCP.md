# DeployGCP.md — Nursery on Google Cloud

**Goal:** Take you from zero to a running L4 GPU Spot VM on Google Cloud, ready for Nursery agent workloads, using Terraform.

**Scope of this doc:** matches what's in [`hosts/gcp/terraform/`](./hosts/gcp/terraform/). It provisions the VM and nothing else. Software install (Ollama, Hermes, Nursery CLI) comes in a follow-up PR.

This is the GCP counterpart to [DeployAWS.md](./DeployAWS.md). The same Nursery Terraform discipline, different provider.

---

## What you get

| Piece | Default |
|---|---|
| Instance | `g2-standard-4` — 1× NVIDIA L4 (24 GB VRAM), 4 vCPU, 16 GB RAM |
| Image | Deep Learning VM `common-cu129-ubuntu-2404-nvidia-580` — **Ubuntu 24.04, Python 3.12, CUDA 12.9, NVIDIA driver 580** |
| Container runtime | **Docker + NVIDIA Container Toolkit auto-installed on first boot** via `metadata_startup_script` (the DL image ships `nvidia-container-cli` but no container runtime) |
| Purchasing | Spot VM (no 24h limit, terminate-on-preemption) |
| Storage | 150 GB pd-ssd boot disk, auto-deleted with the VM |
| Region / zone | `us-central1-a` (Iowa — closest low-latency to Indiana) |
| Network | Dedicated VPC (`10.42.1.0/24`), SSH-only firewall from your IP |
| SSH | OS Login via `gcloud compute ssh` (no `.pem` files) |

**Typical Spot cost for `g2-standard-4` in `us-central1`:** ~$0.23–0.30/hr. On-demand is ~$0.71/hr.

---

## Safety up front

- **Terraform only touches resources it creates.** The state file tracks what it owns; your other GCP resources are invisible to it.
- **Cost discipline matters.** A left-running Spot VM is ~$5–7/day. `terraform destroy` when you walk away.
- **GCP billing is per-project.** Putting Nursery work in a dedicated project makes it trivial to see the bill and, if needed, nuke the whole thing by deleting the project.
- **State lives in GCS** (versioned; native consistent-read locking). Created once per project by the bootstrap module — see Step 0 below. Losing your laptop no longer means losing state, and every prior version of `terraform.tfstate` is retained as a non-current object for rollback via `gsutil cp gs://<bucket>/...#<generation> ...`.

---

## Prerequisites

### 1. Google Cloud account with billing enabled

- If you don't have one: https://cloud.google.com/free — sign up, attach a billing method (a $300 credit is standard for new accounts).
- GPU instances **require** an active billing account. The free tier alone won't launch GPUs.

### 2. Install the `gcloud` CLI

Ubuntu/Debian:

```bash
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list

curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

sudo apt update && sudo apt install google-cloud-cli
```

macOS: `brew install --cask google-cloud-sdk`.

### 3. Authenticate

Two separate auth flows, both needed:

```bash
# User-level auth — for running 'gcloud compute ssh', listing projects, etc.
gcloud auth login

# Application Default Credentials — what Terraform uses.
gcloud auth application-default login
```

Both open a browser. After this, `gcloud auth list` shows your account.

### 4. Create (or pick) a project

**Recommendation: dedicated project for Nursery.** Clean cost tracking, easy nuclear cleanup.

The canonical Nursery project is `nursery-factory`. If you're setting up your own:

```bash
# Try the canonical name first. Project IDs are globally unique across all of GCP.
gcloud projects create nursery-factory --name="Nursery Factory"

# If "Requested entity already exists", pick a scoped ID:
gcloud projects create nursery-$(whoami) --name="Nursery"

# Confirm and set as default
gcloud projects list
gcloud config set project nursery-factory
```

**Link billing:**

```bash
# See your billing accounts
gcloud billing accounts list

# Link (substitute the billing account ID)
gcloud billing projects link nursery-factory \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

### 5. Enable required APIs

```bash
gcloud services enable \
  compute.googleapis.com \
  oslogin.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com
```

(`compute` for VMs, `oslogin` for SSH, `iam` for service accounts, `cloudresourcemanager` for project metadata.)

### 6. ⚠️ Request GPU quota — this is the step that blocks everyone

**New projects have `GPUS_ALL_REGIONS = 0`.** You cannot launch a single GPU instance until Google grants quota. This is the GCP equivalent of what blocked us on AWS.

Two quotas need to be non-zero for our VM:

| Quota | Needed | Where |
|---|---|---|
| `GPUS_ALL_REGIONS` | ≥ 1 | Global |
| `NVIDIA_L4_GPUS` | ≥ 1 | Region-specific (`us-central1`) |

**Request them via:**

- **Console path (recommended, the UI handles both at once):** https://console.cloud.google.com/iam-admin/quotas → filter "GPUs (all regions)" and "NVIDIA L4 GPUs" → select the row → "Edit Quotas" → request 1 (or more) → justify ("Running GPU-accelerated ML inference for development"). Approvals are usually same-day for small asks on a billing-enabled account.
- **gcloud path:**
  ```bash
  gcloud alpha services quota list --service=compute.googleapis.com \
    --consumer=projects/$(gcloud config get-value project) \
    --filter="metric:GPU"
  ```
  — then request via `gcloud alpha services quota update` (doc: https://cloud.google.com/docs/quotas/view-manage).

**Realistic wait:** anywhere from 5 minutes to a few hours. Wait for the approval email before running `terraform apply` — otherwise you'll get a clear but frustrating `QUOTA_EXCEEDED` error.

### 7. Install Terraform ≥ 1.7

Same as AWS path. Ubuntu/Debian:

```bash
wget -O- https://apt.releases.hashicorp.com/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

---

## First deploy

### Step 0 — One-time state-backend bootstrap (per GCP project)

The main module stores state in a GCS bucket with object versioning, uniform bucket-level access, and enforced public-access prevention. GCS handles state locking natively via consistent reads — no external lock store. The bucket itself is created by a small bootstrap module that runs **once per project**.

```bash
git clone git@github.com:ZetiMente/nursery.git
cd nursery/hosts/gcp/terraform/bootstrap
terraform init
terraform apply -var="project_id=<your-project-id>"
```

Bucket name is auto-derived: `nursery-tfstate-<project-id>-<region>` (defaults to `us-central1`). On success, the bootstrap writes `../backend.hcl` (gitignored) for the main module to consume. Re-running on the same project is a no-op.

The bootstrap module's own state stays local and gitignored. The bucket carries `prevent_destroy = true`, so accidental Terraform teardown of state itself is blocked.

### Step 1 — Move into the main module

```bash
cd ..
```

(You're now in `hosts/gcp/terraform/`.)

### Step 2 — Initialize Terraform against the GCS backend

```bash
terraform init -backend-config=backend.hcl
```

Downloads the `google` + `http` providers (one-time, ~few seconds) and wires up the remote state. On success: `Successfully configured the backend "gcs"!`.

> **Migrating from a previous local-state run?** Add `-migrate-state` (and optionally `-force-copy`) to copy your existing `terraform.tfstate` into GCS once.

### Step 3 — Plan

```bash
terraform plan -var="project_id=nursery-factory"
```

Expected summary:

```
Plan: 5 to add, 0 to change, 0 to destroy.
```

Resources:

- `google_compute_network.this` — VPC
- `google_compute_subnetwork.public` — subnet
- `google_compute_firewall.ssh` — SSH from your IP
- `google_service_account.vm[0]` — minimal-privilege SA
- `google_compute_instance.this` — the VM

**`0 to destroy` is the safety signal.**

### Step 4 — Apply

```bash
terraform apply -var="project_id=nursery-factory"
```

Terraform asks `Enter a value:` — type `yes`. Spot VM creation takes ~60–120 seconds.

Outputs include:

```
ssh_command_gcloud = "gcloud compute ssh nursery-l4 --zone=us-central1-a --project=..."
public_ip          = "34.xxx.xxx.xxx"
image              = "https://.../common-cu129-ubuntu-2404-nvidia-580-..."
```

### Step 5 — SSH in and verify

Use the `ssh_command_gcloud` output verbatim. `gcloud` handles OS Login automatically — no key file to hunt for.

```bash
gcloud compute ssh nursery-l4 --zone=us-central1-a --project=nursery-factory
```

On the VM, confirm the stack is what we asked for:

```bash
python3 --version                              # Python 3.12.x
nvidia-smi                                     # 1× NVIDIA L4 (24 GB VRAM), driver 580.x
/usr/local/cuda/bin/nvcc --version             # CUDA 12.9 toolkit (not on default PATH)
docker --version                               # Installed by startup script (see note below)
nvidia-container-cli --version                 # Toolkit pre-installed in the DL image
sudo docker run --rm --gpus all \
  nvidia/cuda:12.9.0-base-ubuntu24.04 nvidia-smi  # End-to-end GPU passthrough
cat /etc/os-release | head -2                  # Ubuntu 24.04 LTS
```

> **First-boot timing.** The startup script (Docker install + NVIDIA runtime config) typically completes in **60–90 seconds** after the VM is reachable on SSH. If `docker --version` says "command not found" on first SSH, the script is still running — `sudo tail -f /var/log/nursery-startup.log` to watch progress, then re-try once you see `nursery-startup: complete`.

If any of the above don't respond cleanly after the startup script finishes, the image or driver install didn't complete — post in the PR.

`exit` when satisfied.

### Step 6 — Tear it down

```bash
cd nursery/hosts/gcp/terraform
terraform destroy -var="project_id=nursery-factory"
```

Confirm with `yes`. Everything Terraform created is removed, billing for the VM stops.

---

## Making the flags permanent

```bash
cd hosts/gcp/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set project_id at minimum
```

Now plain `terraform apply` uses those values. `terraform.tfvars` is gitignored.

---

## Common overrides

| Goal | Flag |
|---|---|
| Different zone within `us-central1` | `-var="zone=us-central1-b"` |
| Different region entirely | `-var="region=us-east4" -var="zone=us-east4-a"` |
| Larger machine (8 vCPU, 32 GB RAM, same L4) | `-var="machine_type=g2-standard-8"` |
| Larger disk (for bigger models) | `-var="boot_disk_gb=250"` |
| Pin SSH to a specific CIDR | `-var="ssh_allow_cidr=1.2.3.4/32"` |
| On-demand instead of Spot | `-var="preemptible=false"` |
| Supply your own service account | `-var="service_account_email=my-sa@project.iam.gserviceaccount.com"` |
| Cost-tracking labels | `-var='labels={owner="matthew",purpose="hermes-dev"}'` |

---

## Troubleshooting

### `QUOTA_EXCEEDED: Quota 'NVIDIA_L4_GPUS' exceeded. Limit: 0.0`

Your GPU quota is still zero. Request per "Step 6" above and wait for approval.

### `ZONE_RESOURCE_POOL_EXHAUSTED`

Spot capacity in this zone is temporarily out. Options:

- Wait 10–30 min and retry
- Try another zone: `-var="zone=us-central1-b"` or `-var="zone=us-central1-c"`
- Try another region: `-var="region=us-east4" -var="zone=us-east4-a"`

### `PERMISSION_DENIED` during plan

Either `gcloud auth application-default login` wasn't run, or your account lacks the needed project role. Minimum role: `roles/compute.admin` on the project. `roles/owner` also works but is heavier.

### `API [compute.googleapis.com] not enabled`

Run the `gcloud services enable ...` block from Step 5.

### OS Login SSH hangs

If `gcloud compute ssh` hangs right after "Waiting for SSH key to propagate":
- Give it 30 more seconds (IAM propagation is eventual)
- Make sure you have `roles/compute.osLogin` on the project (or use OS Admin Login for sudo)

### "Already locked"

A previous Terraform run crashed mid-apply.

```bash
terraform force-unlock <LOCK_ID>
```

---

## What's next (explicitly deferred)

Same follow-up trajectory as AWS:

1. **Extend the startup script** — Docker is already auto-installed. Next: install Ollama (GPU-enabled), pull models, install Nursery CLI automatically on first boot.
2. **`nursery gcp launch`** — Python wrapper that reads specs and runs Terraform.
3. **Hermes containerized deployment** — spawn Hermes agents on the VM with `nursery spawn`.
4. **Multi-instance / multi-zone** — scale out.

---

## File map

| File | Purpose |
|---|---|
| [`hosts/gcp/terraform/versions.tf`](./hosts/gcp/terraform/versions.tf) | Terraform + provider version pins, `backend "gcs" {}` |
| [`hosts/gcp/terraform/variables.tf`](./hosts/gcp/terraform/variables.tf) | All inputs, defaults documented |
| [`hosts/gcp/terraform/main.tf`](./hosts/gcp/terraform/main.tf) | VPC, subnet, firewall, SA, Spot VM, startup-script wiring |
| [`hosts/gcp/terraform/outputs.tf`](./hosts/gcp/terraform/outputs.tf) | Public IP, SSH commands, etc. |
| [`hosts/gcp/terraform/terraform.tfvars.example`](./hosts/gcp/terraform/terraform.tfvars.example) | Copy to `terraform.tfvars`, adjust |
| [`hosts/gcp/terraform/startup-scripts/install-docker.sh`](./hosts/gcp/terraform/startup-scripts/install-docker.sh) | First-boot installer for Docker + NVIDIA Container Toolkit |
| `hosts/gcp/terraform/backend.hcl` | **Generated by bootstrap; gitignored** — per-project GCS backend config |
| [`hosts/gcp/terraform/bootstrap/`](./hosts/gcp/terraform/bootstrap/) | One-time GCS state-bucket creator (run once per project) |
| [`hosts/gcp/terraform/deploy.sh`](./hosts/gcp/terraform/deploy.sh) | Spot/on-demand fallback wrapper around `terraform apply` |
| [`hosts/gcp/terraform/README.md`](./hosts/gcp/terraform/README.md) | Short reference |
| [`hosts/gcp/terraform/.gitignore`](./hosts/gcp/terraform/.gitignore) | Excludes state, `.terraform/`, `.tfvars`, `backend.hcl`, creds |

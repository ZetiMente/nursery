# ---------------------------------------------------------------------------
# Nursery — GCP L4 GPU Spot VM
#
# What this creates:
#   1. A dedicated VPC + subnet in the target region.
#   2. A firewall rule allowing SSH from a single CIDR (auto-detected or explicit).
#   3. A minimal-privilege service account (if one isn't provided).
#   4. A Spot VM of type g2-standard-4 (1x L4, 4 vCPU, 16 GB RAM).
#   5. A 150 GB pd-ssd boot disk from the Deep Learning VM image family
#      common-cu129-ubuntu-2404-nvidia-580
#      (Ubuntu 24.04, Python 3.12, CUDA 12.9, NVIDIA driver 580).
#
# OS Login is forced on at the project scope via metadata, so there's no
# per-instance SSH key management. 'gcloud compute ssh' handles auth via IAM.
#
# Nothing outside this module is touched — Terraform only modifies resources
# it creates, tracked in its state file.
# ---------------------------------------------------------------------------

locals {
  # Auto-detect operator IP when ssh_allow_cidr is empty.
  detected_ip_cidr = var.ssh_allow_cidr == "" ? "${trimspace(data.http.my_ip[0].response_body)}/32" : var.ssh_allow_cidr
  ssh_cidr         = local.detected_ip_cidr

  # Whether we need to create our own service account.
  create_sa    = var.service_account_email == ""
  effective_sa = local.create_sa ? google_service_account.vm[0].email : var.service_account_email

  common_labels = merge(
    {
      name       = var.name
      managed_by = "nursery-terraform"
      project    = "nursery"
    },
    var.labels,
  )
}

# ---------------------------------------------------------------------------
# Operator IP auto-detect (only when ssh_allow_cidr isn't set).
# ---------------------------------------------------------------------------

data "http" "my_ip" {
  count = var.ssh_allow_cidr == "" ? 1 : 0
  url   = "https://api.ipify.org"
}

# ---------------------------------------------------------------------------
# Resolve the latest DL VM image in the requested family.
# ---------------------------------------------------------------------------

data "google_compute_image" "dl" {
  family  = var.image_family
  project = var.image_project
}

# ---------------------------------------------------------------------------
# Networking: one VPC, one regional subnet. Minimal.
# ---------------------------------------------------------------------------

resource "google_compute_network" "this" {
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false
  description             = "Nursery dedicated VPC"
}

resource "google_compute_subnetwork" "public" {
  name          = "${var.name}-public"
  network       = google_compute_network.this.id
  region        = var.region
  ip_cidr_range = "10.42.1.0/24"
  # External IPs on VMs in this subnet — simple public access, no NAT needed.
}

# ---------------------------------------------------------------------------
# Firewall: SSH in from operator CIDR only.
# GCP firewall rules are network-scoped and target instances by tag.
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "ssh" {
  name        = "${var.name}-allow-ssh"
  network     = google_compute_network.this.name
  description = "Nursery: SSH from operator"
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = [local.ssh_cidr]
  target_tags   = ["${var.name}-ssh"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# ---------------------------------------------------------------------------
# Service account for the VM.
# Created on-demand if one isn't supplied. Minimal privilege by default:
# no roles granted at the project scope. VM can write its own logs/metrics
# via the standard compute-engine default scopes.
# ---------------------------------------------------------------------------

resource "google_service_account" "vm" {
  count        = local.create_sa ? 1 : 0
  account_id   = "${replace(var.name, "_", "-")}-sa"
  display_name = "Nursery VM service account (${var.name})"
  description  = "Attached to Nursery L4 VMs. No project-scope roles by default."
}

# ---------------------------------------------------------------------------
# The Spot VM itself.
# - scheduling.preemptible + provisioning_model=SPOT gives modern Spot
#   (no 24h limit; automatic termination on preemption).
# - No ephemeral local SSD; boot disk is pd-ssd (see var.boot_disk_type).
# - metadata enable-oslogin=TRUE forces OS Login regardless of project setting.
# ---------------------------------------------------------------------------

resource "google_compute_instance" "this" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["${var.name}-ssh"]

  boot_disk {
    auto_delete = true
    initialize_params {
      image = data.google_compute_image.dl.self_link
      size  = var.boot_disk_gb
      type  = var.boot_disk_type
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.public.self_link

    # Ephemeral public IP
    access_config {}
  }

  scheduling {
    preemptible                 = var.preemptible
    provisioning_model          = var.preemptible ? "SPOT" : "STANDARD"
    instance_termination_action = var.preemptible ? "STOP" : null
    automatic_restart           = !var.preemptible
    on_host_maintenance         = "TERMINATE"  # Required for GPUs
  }

  # For g2-* machine types, the L4 GPU is included in the machine type itself;
  # an explicit guest_accelerator block must NOT be set (GCP rejects it).

  service_account {
    email  = local.effective_sa
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  labels = local.common_labels

  # The DL VM image accepts the NVIDIA EULA on first boot internally;
  # no user action needed. allow_stopping_for_update lets terraform change
  # some fields in place.
  allow_stopping_for_update = true
}

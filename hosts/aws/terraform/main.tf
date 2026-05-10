# ---------------------------------------------------------------------------
# Nursery — AWS L4 GPU spot instance
#
# What this creates:
#   1. A VPC with one public subnet + internet gateway (minimal, single-AZ).
#   2. A security group that allows SSH from a single CIDR (auto-detected or
#      explicit).
#   3. A spot EC2 instance from the latest Deep Learning Base OSS Nvidia
#      Driver GPU AMI (Ubuntu 24.04). NVIDIA driver, CUDA, Docker, and the
#      NVIDIA Container Toolkit are pre-installed on this AMI.
#   4. A 100 GB gp3 root EBS volume (overrideable).
#
# Everything is tagged so `terraform destroy` finds it all. Nothing outside
# this module is touched.
# ---------------------------------------------------------------------------

locals {
  # Auto-detect operator IP when ssh_allow_cidr is empty. The `http` provider
  # resolves once per plan — safe, and the CIDR is materialized into state.
  detected_ip_cidr = "${trimspace(data.http.my_ip[0].response_body)}/32"
  ssh_cidr         = var.ssh_allow_cidr != "" ? var.ssh_allow_cidr : local.detected_ip_cidr

  common_tags = merge(
    {
      Name      = var.name
      ManagedBy = "nursery-terraform"
      Project   = "nursery"
    },
    var.extra_tags,
  )
}

# ---------------------------------------------------------------------------
# Auto-detect the operator's public IP (only when ssh_allow_cidr isn't set).
# ---------------------------------------------------------------------------

data "http" "my_ip" {
  count = var.ssh_allow_cidr == "" ? 1 : 0
  url   = "https://api.ipify.org"
}

# ---------------------------------------------------------------------------
# Pick the latest Ubuntu 24.04 Deep Learning Base OSS AMI.
# AWS rotates these monthly; always resolve at plan time.
# ---------------------------------------------------------------------------

data "aws_ami" "dlami" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04)*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

# ---------------------------------------------------------------------------
# Pick an AZ that actually has the requested instance type available.
# Avoids "UnsupportedOperation: instance type not supported in this AZ."
# ---------------------------------------------------------------------------

data "aws_ec2_instance_type_offerings" "azs" {
  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
  filter {
    name   = "location-type"
    values = ["availability-zone"]
  }
  location_type = "availability-zone"
}

locals {
  target_az = sort(data.aws_ec2_instance_type_offerings.azs.locations)[0]
}

# ---------------------------------------------------------------------------
# Networking: one VPC, one public subnet, one IGW, one route table.
# Minimal surface area. Nothing private, no NAT, no multi-AZ.
# ---------------------------------------------------------------------------

resource "aws_vpc" "this" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.common_tags, { Name = "${var.name}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.common_tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = local.target_az
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${var.name}-public" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.common_tags, { Name = "${var.name}-public-rt" })
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Security group: SSH in from operator, all out.
# ---------------------------------------------------------------------------

resource "aws_security_group" "instance" {
  name        = "${var.name}-sg"
  description = "Nursery L4 instance. SSH-only ingress."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.ssh_cidr]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${var.name}-sg" })
}

# ---------------------------------------------------------------------------
# Spot EC2 instance.
# - Uses `aws_spot_instance_request` with `wait_for_fulfillment = true` so
#   `terraform apply` blocks until the spot request is filled.
# - `spot_type = "one-time"` + `instance_interruption_behavior = "terminate"`
#   matches the "manual on/off" posture — no hibernation, no re-request.
# ---------------------------------------------------------------------------

resource "aws_spot_instance_request" "this" {
  ami                  = data.aws_ami.dlami.id
  instance_type        = var.instance_type
  key_name             = var.key_pair_name
  subnet_id            = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.instance.id]

  spot_type                      = "one-time"
  instance_interruption_behavior = "terminate"
  wait_for_fulfillment           = true
  spot_price                     = var.spot_max_price == "" ? null : var.spot_max_price

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    delete_on_termination = true
    encrypted             = true
    tags                  = merge(local.common_tags, { Name = "${var.name}-root" })
  }

  tags = merge(local.common_tags, { Name = var.name })
  # The spot request itself carries tags; ensure the fulfilled instance
  # inherits the same set by also applying via the provider's tag propagation.
}

# ---------------------------------------------------------------------------
# Tag the actual instance after fulfillment.
# Spot instance requests don't always cascade tags to the instance.
# ---------------------------------------------------------------------------

resource "aws_ec2_tag" "instance_name" {
  resource_id = aws_spot_instance_request.this.spot_instance_id
  key         = "Name"
  value       = var.name
}

resource "aws_ec2_tag" "instance_managed_by" {
  resource_id = aws_spot_instance_request.this.spot_instance_id
  key         = "ManagedBy"
  value       = "nursery-terraform"
}

resource "aws_ec2_tag" "instance_project" {
  resource_id = aws_spot_instance_request.this.spot_instance_id
  key         = "Project"
  value       = "nursery"
}

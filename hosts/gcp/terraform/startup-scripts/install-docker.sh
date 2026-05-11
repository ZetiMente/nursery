#!/usr/bin/env bash
# install-docker.sh — Nursery DL-VM first-boot bootstrap.
#
# Installs Docker Engine and wires the NVIDIA Container Toolkit into Docker
# so the VM is ready for `docker run --gpus all` without manual setup.
#
# The deeplearning-platform-release image ships the NVIDIA driver, CUDA, and
# nvidia-container-cli, but NOT a container runtime — this script closes that
# gap. Runs as root via GCP `metadata_startup_script` on first boot.
#
# Logs to /var/log/nursery-startup.log for serial-console debugging.

set -euo pipefail
exec > >(tee -a /var/log/nursery-startup.log) 2>&1

log() { echo "[$(date -Is)] nursery-startup: $*"; }

log "begin"

# Idempotency: skip if a previous run already configured this VM. Boot
# scripts can re-run on metadata changes, and we don't want a re-install
# to break a working state.
if command -v docker >/dev/null 2>&1 \
   && [ -f /etc/docker/daemon.json ] \
   && grep -q '"nvidia"' /etc/docker/daemon.json; then
  log "docker + nvidia runtime already configured; skipping"
  exit 0
fi

# Wait for any concurrent apt holder (cloud-init, unattended-upgrades).
# DL VM images run post-boot housekeeping that can hold the dpkg lock
# for a minute or two.
for i in $(seq 1 60); do
  if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
     && ! fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then
    break
  fi
  log "waiting for apt locks ($i/60)"
  sleep 5
done

log "installing docker via get-docker.sh"
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sh /tmp/get-docker.sh
rm -f /tmp/get-docker.sh

log "configuring nvidia container runtime"
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Verify (non-fatal — exit 0 so GCP doesn't retry the boot in a loop).
docker --version || true
docker info --format '{{json .Runtimes.nvidia}}' || true

log "complete"

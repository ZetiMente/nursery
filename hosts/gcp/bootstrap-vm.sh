#!/usr/bin/env bash
# bootstrap-vm.sh — Phase-A bootstrap for a fresh Nursery GCP DL-VM.
#
# Picks up where install-docker.sh leaves off: installs Ollama, configures
# it for container access, pulls a model, installs uv + the Nursery CLI,
# clones the nursery repo, and builds the agent base image. After this
# script completes the VM is ready for `nursery spawn`.
#
# Designed for the `common-cu129-ubuntu-2404-nvidia-580` image (Docker +
# nvidia container runtime already configured by terraform's startup script).
#
# Usage (from a laptop with `gcloud` configured):
#
#   gcloud compute ssh nursery-l4 --zone=<zone> --project=<proj> \
#     --command='bash -s' < hosts/gcp/bootstrap-vm.sh
#
# Or copy to the VM and run directly:
#
#   bash bootstrap-vm.sh
#
# Override defaults via env vars before invocation:
#
#   NURSERY_MODEL=gemma3:27b NURSERY_REF=feat/foo bash bootstrap-vm.sh
#
# Idempotent: skips work that is already complete on re-run.

set -euo pipefail

NURSERY_REF="${NURSERY_REF:-main}"
NURSERY_DIR="${NURSERY_DIR:-$HOME/nursery}"
NURSERY_MODEL="${NURSERY_MODEL:-gemma4:26b}"
NURSERY_MODEL_FALLBACK="${NURSERY_MODEL_FALLBACK:-gemma3:27b}"
NURSERY_CLI_WHEEL="${NURSERY_CLI_WHEEL:-https://github.com/ZetiMente/nursery/releases/download/v0.2.0/nursery_cli-0.2.0-py3-none-any.whl}"

log() { echo "[$(date -Is)] bootstrap-vm: $*"; }

# --- 1. Ollama --------------------------------------------------------------

if ! command -v ollama >/dev/null 2>&1; then
  log "installing ollama"
  curl -fsSL https://ollama.com/install.sh | sh
else
  log "ollama present: $(ollama --version 2>&1 | head -1)"
fi

# Agent containers reach host Ollama via host.docker.internal:11434, which
# means Ollama must listen on all interfaces (default install is loopback only).
DROPIN=/etc/systemd/system/ollama.service.d/override.conf
if ! sudo grep -q 'OLLAMA_HOST=0.0.0.0' "$DROPIN" 2>/dev/null; then
  log "configuring OLLAMA_HOST=0.0.0.0 systemd drop-in"
  sudo mkdir -p "$(dirname "$DROPIN")"
  printf '%s\n' '[Service]' 'Environment="OLLAMA_HOST=0.0.0.0"' \
    | sudo tee "$DROPIN" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl restart ollama
  for i in $(seq 1 30); do
    ss -lnt | grep -q ':11434' && break
    sleep 1
  done
fi
log "ollama listening: $(ss -lnt | grep ':11434' | head -1 | tr -s ' ')"

# --- 2. Model ---------------------------------------------------------------

want_present() { ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$1"; }

if ! want_present "$NURSERY_MODEL"; then
  log "pulling $NURSERY_MODEL (large; may take 10+ minutes)"
  if ! ollama pull "$NURSERY_MODEL"; then
    log "pull of $NURSERY_MODEL failed; trying fallback $NURSERY_MODEL_FALLBACK"
    ollama pull "$NURSERY_MODEL_FALLBACK"
    NURSERY_MODEL="$NURSERY_MODEL_FALLBACK"
  fi
else
  log "$NURSERY_MODEL already present"
fi

# --- 3. uv + Nursery CLI ----------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
  log "installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# The uv install script adds ~/.local/bin to .profile but not the current shell.
export PATH="$HOME/.local/bin:$PATH"
log "uv: $(uv --version)"

if ! command -v nursery >/dev/null 2>&1; then
  log "installing nursery CLI from wheel"
  uv tool install "$NURSERY_CLI_WHEEL"
fi
log "nursery: $(nursery --version 2>&1 | head -1 || echo unknown)"

# --- 4. Nursery repo + base image -------------------------------------------

if [ ! -d "$NURSERY_DIR/.git" ]; then
  log "cloning nursery → $NURSERY_DIR (ref: $NURSERY_REF)"
  git clone --branch "$NURSERY_REF" https://github.com/ZetiMente/nursery "$NURSERY_DIR"
else
  log "nursery repo present at $NURSERY_DIR; refreshing $NURSERY_REF"
  (cd "$NURSERY_DIR" \
    && git fetch origin "$NURSERY_REF" --quiet \
    && git checkout "$NURSERY_REF" --quiet \
    && git pull --ff-only --quiet)
fi

if ! sudo docker image inspect nursery/agent:base >/dev/null 2>&1; then
  log "building nursery/agent:base"
  (cd "$NURSERY_DIR" && sudo ./docker/build.sh base)
else
  log "nursery/agent:base already built"
fi

# --- 5. Docker group membership --------------------------------------------

# Lets subsequent `nursery spawn` calls skip the sudo-docker fallback.
# Takes effect on next login; current shell stays unprivileged.
if ! id -nG "$USER" | grep -qw docker; then
  log "adding $USER to docker group (effective on next login)"
  sudo usermod -aG docker "$USER"
fi

# --- Done -------------------------------------------------------------------

log "bootstrap complete"
log "effective model: $NURSERY_MODEL"
log "next: cd $NURSERY_DIR && nursery spawn examples/agents/gcp-l4-layla.yaml"

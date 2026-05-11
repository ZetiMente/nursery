#!/usr/bin/env bash
# deploy.sh — Nursery GCP turnkey deploy with zone + pricing fallback.
#
# Tries L4 Spot in all us-central1 zones first; on capacity exhaustion in
# every zone, falls back to on-demand in the same zones. Stops at the first
# success and exits 0. Exits non-zero only when all six attempts have been
# exhausted, or on a non-capacity error.
#
# Sequence:
#   1. us-central1-a  Spot       (~$0.21-0.28/hr)
#   2. us-central1-b  Spot
#   3. us-central1-c  Spot
#   4. us-central1-a  On-demand  (~$0.71/hr)
#   5. us-central1-b  On-demand
#   6. us-central1-c  On-demand
#
# Overrides `zone` and `preemptible` via -var on each attempt. Any other
# values in terraform.tfvars (project_id, machine_type, etc.) are honored
# as-is. Extra args to this script are forwarded to `terraform apply`.
#
# Idempotency: each terraform run is a normal apply, so if the previous run
# already landed a VM in the matching zone with matching preemptible, that
# attempt is a no-op and the script exits 0 immediately.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

ATTEMPTS=(
  "us-central1-a:true:Spot"
  "us-central1-b:true:Spot"
  "us-central1-c:true:Spot"
  "us-central1-a:false:On-demand"
  "us-central1-b:false:On-demand"
  "us-central1-c:false:On-demand"
)

log() { echo "[deploy.sh] $*" >&2; }

# Sanity: terraform initialized?
if [ ! -d .terraform ]; then
  log "Running 'terraform init' (first time in this directory)..."
  terraform init
fi

for attempt in "${ATTEMPTS[@]}"; do
  IFS=":" read -r ZONE PREEMPTIBLE LABEL <<<"$attempt"
  log ""
  log "==== Attempting: $LABEL in $ZONE ===="

  LOG_FILE="$(mktemp -t nursery-deploy.XXXXXX.log)"
  set +e
  terraform apply -auto-approve \
    -var="zone=$ZONE" \
    -var="preemptible=$PREEMPTIBLE" \
    "$@" 2>&1 | tee "$LOG_FILE"
  RC=${PIPESTATUS[0]}
  set -e

  if [ "$RC" -eq 0 ]; then
    log ""
    log "==== SUCCESS: $LABEL in $ZONE ===="
    rm -f "$LOG_FILE"
    exit 0
  fi

  # Recognized capacity-exhaustion signatures.
  if grep -qE "does not have enough resources available|ZONE_RESOURCE_POOL_EXHAUSTED" "$LOG_FILE"; then
    log "Zone $ZONE exhausted for $LABEL — advancing to next attempt"
    rm -f "$LOG_FILE"
    continue
  fi

  # Anything else is a real error — abort the fallback chain.
  log ""
  log "==== ABORT: non-capacity error (rc=$RC) ===="
  log "Full terraform output: $LOG_FILE"
  exit "$RC"
done

log ""
log "==== ALL SIX ATTEMPTS FAILED ===="
log "L4 capacity unavailable in us-central1-a/b/c for both Spot and On-demand."
log "Options:"
log "  - Wait 15-30 min and retry (./deploy.sh)"
log "  - Try a different region (edit terraform.tfvars: region + zone)"
log "  - Check the GCP status page: https://status.cloud.google.com"
exit 1

#!/usr/bin/env bash
# deploy.sh — Nursery GCP turnkey deploy with zone + pricing fallback.
#
# Single source of truth for region targeting: edit the CONFIG block below.
# Tries L4 Spot in every configured zone first, then On-demand in the same
# zones. Stops at the first success and exits 0. Exits non-zero only when
# every attempt has been exhausted, or on a non-capacity error.
#
# Overrides `region`, `zone`, and `preemptible` via -var on each attempt.
# Other values in terraform.tfvars (project_id, machine_type, etc.) are
# honored as-is. Extra args to this script are forwarded to `terraform apply`.
#
# Idempotency: each terraform run is a normal apply, so if the previous run
# already landed a VM in the matching zone with matching preemptible, that
# attempt is a no-op and the script exits 0 immediately.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# === CONFIG: change REGION to retarget the deploy. =========================
# Only change REGION. L4-bearing zones are looked up from the table below —
# North-America regions only. Pricing is roughly region-agnostic:
# Spot ~$0.21–0.28/hr, On-demand ~$0.71/hr.
#
# If a region's L4 zone list changes, update the case statement below.
# Verify against: https://cloud.google.com/compute/docs/gpus/gpu-regions-zones
REGION="us-east1"
# ===========================================================================

# Look up L4 zones for REGION (North America only).
case "$REGION" in
  us-central1) L4_ZONES=(us-central1-a us-central1-b us-central1-c) ;;
  us-east1)    L4_ZONES=(us-east1-c us-east1-d) ;;
  us-east4)    L4_ZONES=(us-east4-a us-east4-b us-east4-c) ;;
  us-east5)    L4_ZONES=(us-east5-b) ;;
  us-west1)    L4_ZONES=(us-west1-a us-west1-b us-west1-c) ;;
  us-west4)    L4_ZONES=(us-west4-a us-west4-c) ;;
  *)
    echo "[deploy.sh] error: REGION='$REGION' is not in the L4 lookup table (NA only)." >&2
    echo "[deploy.sh] known: us-central1 us-east1 us-east4 us-east5 us-west1 us-west4" >&2
    exit 2
    ;;
esac

# Build the attempt list: every L4 zone in Spot, then every L4 zone On-demand.
ATTEMPTS=()
for z in "${L4_ZONES[@]}"; do ATTEMPTS+=("$z:true:Spot"); done
for z in "${L4_ZONES[@]}"; do ATTEMPTS+=("$z:false:On-demand"); done

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
    -var="region=$REGION" \
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
log "==== ALL ${#ATTEMPTS[@]} ATTEMPTS FAILED ===="
log "L4 capacity unavailable in $REGION (zones: ${L4_ZONES[*]}) for both Spot and On-demand."
log "Options:"
log "  - Wait 15-30 min and retry (./deploy.sh)"
log "  - Try a different region (edit the CONFIG block at the top of this script)"
log "  - Check the GCP status page: https://status.cloud.google.com"
exit 1

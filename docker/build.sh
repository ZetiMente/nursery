#!/usr/bin/env bash
# Build Nursery agent images locally.
#
# Usage:
#   docker/build.sh              # build both base + openclaw, tag :latest + :0.1.0
#   docker/build.sh base         # just the base image
#   docker/build.sh openclaw     # just the openclaw image (requires base)
#   docker/build.sh --push       # also push (requires docker login + repo perms)
#
# Images:
#   nursery/agent:base      (and :base-0.1.0)
#   nursery/agent:openclaw  (and :openclaw-0.1.0)
#   nursery/agent:latest    → alias for :base

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${NURSERY_VERSION:-0.1.0}"
REGISTRY="${NURSERY_REGISTRY:-nursery}"
PUSH=false
TARGETS=()

for arg in "$@"; do
  case "$arg" in
    --push) PUSH=true ;;
    base|openclaw|all) TARGETS+=("$arg") ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

if [ "${#TARGETS[@]}" -eq 0 ] || [ " ${TARGETS[*]} " = " all " ]; then
  TARGETS=(base openclaw)
fi

build_base() {
  echo "==> Building ${REGISTRY}/agent:base (and :latest, :base-${VERSION})"
  docker build \
    -f docker/base/Dockerfile \
    -t "${REGISTRY}/agent:base" \
    -t "${REGISTRY}/agent:base-${VERSION}" \
    -t "${REGISTRY}/agent:latest" \
    .
}

build_openclaw() {
  echo "==> Building ${REGISTRY}/agent:openclaw (and :openclaw-${VERSION})"
  docker build \
    -f docker/openclaw/Dockerfile \
    --build-arg "BASE_TAG=base" \
    -t "${REGISTRY}/agent:openclaw" \
    -t "${REGISTRY}/agent:openclaw-${VERSION}" \
    .
}

for t in "${TARGETS[@]}"; do
  case "$t" in
    base)     build_base ;;
    openclaw) build_openclaw ;;
  esac
done

if [ "$PUSH" = true ]; then
  echo "==> Pushing images"
  for t in "${TARGETS[@]}"; do
    case "$t" in
      base)
        docker push "${REGISTRY}/agent:base"
        docker push "${REGISTRY}/agent:base-${VERSION}"
        docker push "${REGISTRY}/agent:latest"
        ;;
      openclaw)
        docker push "${REGISTRY}/agent:openclaw"
        docker push "${REGISTRY}/agent:openclaw-${VERSION}"
        ;;
    esac
  done
fi

echo "==> Done."
docker images "${REGISTRY}/agent" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"

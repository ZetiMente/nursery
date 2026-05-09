# Nursery agent image, OpenClaw variant.
#
# Extends the base image with OpenClaw-specific conventions:
#   - Default gateway URL expected at host.docker.internal:7770 (OpenClaw default).
#   - Agent announces itself to the gateway on startup (Phase 2b+).
#   - Label metadata so `nursery ps` can identify OpenClaw-managed agents.
#
# Phase 2a scope: tag + defaults only. Real OpenClaw wiring lands in Phase 5.

ARG BASE_TAG=latest
FROM nursery/agent:${BASE_TAG}

LABEL org.opencontainers.image.title="Nursery Agent (OpenClaw)"
LABEL org.opencontainers.image.description="Nursery agent configured for OpenClaw hosts."
LABEL nursery.host="openclaw"

# OpenClaw-specific defaults. Overridable at runtime.
ENV NURSERY_HOST=openclaw \
    NURSERY_GATEWAY_URL=http://host.docker.internal:7770 \
    NURSERY_GATEWAY_TIMEOUT=30

# Same entrypoint as base. The host-specific behavior is controlled by
# NURSERY_HOST at runtime rather than different code paths in Phase 2a.

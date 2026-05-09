# Nursery base agent image.
#
# Layered design:
#   nursery/agent:base      — this image. Generic runtime. Host-agnostic.
#   nursery/agent:openclaw  — FROM base. Adds OpenClaw defaults.
#
# Phase 2a scope: boot, read spec, serve an HTTP endpoint. No real inference yet.

FROM python:3.12-slim-bookworm

# -- Metadata --
LABEL org.opencontainers.image.title="Nursery Agent (base)"
LABEL org.opencontainers.image.description="Base image for Nursery agents. Host-agnostic runtime."
LABEL org.opencontainers.image.source="https://github.com/ZetiMente/nursery"
LABEL org.opencontainers.image.licenses="MIT"

# -- System deps --
# Slim base; install only what's needed. ca-certificates for TLS, tini for PID 1.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      tini \
 && rm -rf /var/lib/apt/lists/*

# -- User --
# Run as non-root. UID 1000 matches typical host users for bind-mount compatibility.
RUN useradd --create-home --uid 1000 --shell /bin/bash nursery

# -- Python deps --
# Install minimal runtime deps. More model clients added in Phase 2b.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      pyyaml==6.0.2 \
      jsonschema==4.26.0

# -- Agent package --
COPY --chown=nursery:nursery agent/src/nursery_agent /opt/nursery/nursery_agent
ENV PYTHONPATH=/opt/nursery \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# -- Mount points --
# These are the conventions Nursery enforces. Host binds into these paths.
RUN mkdir -p /spec /workspace /run/secrets \
 && chown -R nursery:nursery /spec /workspace

# -- Runtime config (overridable via docker -e) --
ENV NURSERY_SPEC_PATH=/spec/agent.yaml \
    NURSERY_WORKSPACE=/workspace \
    NURSERY_SECRETS_DIR=/run/secrets \
    NURSERY_AGENT_PORT=7860 \
    LOG_LEVEL=INFO

EXPOSE 7860

USER nursery
WORKDIR /workspace

# tini cleans up orphaned processes and forwards signals properly.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "nursery_agent.entrypoint"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=2).status==200 else sys.exit(1)"

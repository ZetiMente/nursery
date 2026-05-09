# Nursery base agent image.
#
# Layered design:
#   nursery/agent:base      — this image. Generic runtime. Host-agnostic.
#   nursery/agent:openclaw  — FROM base. Adds OpenClaw defaults.
#
# Uses uv for reproducible, locked Python deps via multi-stage build.
# uv is only in the builder stage; the final image doesn't carry it.

ARG PYTHON_VERSION=3.12

# ==========================================================================
# Stage 1: builder — install locked deps into a venv using uv.
# ==========================================================================
FROM ghcr.io/astral-sh/uv:0.11.12 AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /build

# Copy only dependency manifests first for optimal layer caching.
COPY agent/pyproject.toml agent/uv.lock ./

# Install locked deps into /opt/nursery/.venv. No project install (deps only).
RUN uv sync --frozen --no-dev --no-install-project \
      --python "python${PYTHON_VERSION}" \
      --directory . \
    && mv .venv /opt/nursery-venv

# ==========================================================================
# Stage 2: runtime — slim image with only what's needed at run time.
# ==========================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm

# -- Metadata --
LABEL org.opencontainers.image.title="Nursery Agent (base)"
LABEL org.opencontainers.image.description="Base image for Nursery agents. Host-agnostic runtime."
LABEL org.opencontainers.image.source="https://github.com/ZetiMente/nursery"
LABEL org.opencontainers.image.licenses="MIT"

# -- Runtime OS deps --
# ca-certificates: TLS. tini: PID 1.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      tini \
 && rm -rf /var/lib/apt/lists/*

# -- Non-root user --
RUN useradd --create-home --uid 1000 --shell /bin/bash nursery

# -- Bring in the pre-built venv from the builder --
COPY --from=builder --chown=nursery:nursery /opt/nursery-venv /opt/nursery/.venv

# -- Agent source --
COPY --chown=nursery:nursery agent/src/nursery_agent /opt/nursery/src/nursery_agent

ENV PATH="/opt/nursery/.venv/bin:${PATH}" \
    VIRTUAL_ENV="/opt/nursery/.venv" \
    PYTHONPATH=/opt/nursery/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# -- Mount points --
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

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "nursery_agent.entrypoint"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=2).status==200 else sys.exit(1)"

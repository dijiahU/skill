# Safety Orchestrator — Pilot test container
#
# Provides a fully isolated Claude Code environment for pilot-testing the
# agent-safety-orchestrator bundle without touching the host's ~/.claude/.
#
# Build:  docker build -t safety-orch-pilot pilot/
# Run:    pilot/run.sh   (host-side wrapper handles mounts + auth)

FROM node:20-slim

# ----- OS dependencies -----
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        git curl jq ca-certificates \
        less vim-tiny \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# ----- Claude Code CLI -----
# Installed via npm (official distribution channel), PINNED to an explicit
# version for pilot reproducibility: built-in safety behavior changes between
# releases, and the whole point of the A/B attribution is to measure that
# built-in line — so the version under test must be recorded, not floating.
# Bump CLAUDE_CODE_VERSION (or pass --build-arg) to update; changing it busts
# the npm layer cache automatically. `npm view @anthropic-ai/claude-code
# dist-tags` lists latest/stable.
ARG CLAUDE_CODE_VERSION=2.1.158
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
    && npm cache clean --force

# ----- Non-root user -----
RUN useradd -m -s /bin/bash pilot

# Pre-create /home/pilot/.claude/ owned by pilot. Without this, a single-file
# bind mount like `~/.claude/.credentials.json:/home/pilot/.claude/.credentials.json`
# causes podman to auto-create the parent dir as root-owned. Claude Code 2.x
# then can't mkdir session-env/ inside it (EACCES) → Bash tool fails →
# 4.7.1.f hook test impossible. Pre-creating gives pilot ownership before
# any bind mount lands; the file mount just slots into the existing dir.
RUN mkdir -p /home/pilot/.claude /home/pilot/.cache /home/pilot/.config \
    && chown -R pilot:pilot /home/pilot/.claude /home/pilot/.cache /home/pilot/.config

USER pilot
WORKDIR /home/pilot

# ----- Paths (consumed by entrypoint) -----
# Bundle code is bind-mounted at /home/pilot/bundle (read-only).
# Pilot workspace (project-local .claude/) is created fresh per container run.
ENV BUNDLE_PATH=/home/pilot/bundle
ENV PILOT_WORKSPACE=/home/pilot/pilot-workspace
ENV PYTHONPATH=${BUNDLE_PATH}

# Entrypoint sets up workspace + drops into bash.
# Auth: pass ANTHROPIC_API_KEY via `docker run -e`, or mount credentials
# from host (see pilot/run.sh for both options).
COPY --chown=pilot:pilot entrypoint.sh /home/pilot/entrypoint.sh
RUN chmod +x /home/pilot/entrypoint.sh

ENTRYPOINT ["/home/pilot/entrypoint.sh"]

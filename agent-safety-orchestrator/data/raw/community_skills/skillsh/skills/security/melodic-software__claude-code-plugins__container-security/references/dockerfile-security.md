# Dockerfile Security Reference

## Overview

This reference provides comprehensive Dockerfile security patterns, anti-patterns to avoid, and hardening techniques for production container images.

## Base Image Selection

### Image Security Hierarchy

| Image Type | Security Level | Use Case | Examples |
| --- | --- | --- | --- |
| **Scratch** | Highest | Static binaries only | Go, Rust compiled apps |
| **Distroless** | Very High | Minimal runtime | Java, Python, Node.js |
| **Alpine** | High | Small with package manager | General purpose |
| **Slim variants** | Medium | Reduced Debian/Ubuntu | When Alpine incompatible |
| **Full OS** | Lower | Development/debugging | Not for production |

### Distroless Images

```dockerfile
# Go application with distroless
FROM golang:1.22 AS builder
WORKDIR /app
COPY . .
RUN CGO_ENABLED=0 go build -ldflags='-s -w' -o /app/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/server /server
USER 65532:65532
ENTRYPOINT ["/server"]
```

```dockerfile
# Java application with distroless
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /app
COPY . .
RUN ./gradlew bootJar

FROM gcr.io/distroless/java21-debian12:nonroot
COPY --from=builder /app/build/libs/app.jar /app.jar
USER 65532:65532
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

```dockerfile
# Python application with distroless
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --target=/deps -r requirements.txt
COPY . .

FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=builder /deps /deps
COPY --from=builder /app /app
ENV PYTHONPATH=/deps
USER 65532:65532
WORKDIR /app
CMD ["main.py"]
```

```dockerfile
# Node.js with distroless
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM gcr.io/distroless/nodejs20-debian12:nonroot
COPY --from=builder /app/dist /app/dist
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/package.json /app/
WORKDIR /app
USER 65532:65532
CMD ["dist/server.js"]
```

## Multi-Stage Build Patterns

### Builder Pattern with Security

```dockerfile
# === DEPENDENCIES STAGE ===
FROM node:20-alpine AS deps
WORKDIR /app

# Copy only package files for caching
COPY package*.json ./

# Install with security flags
RUN npm ci \
    --only=production \
    --ignore-scripts \
    --no-audit \
    && npm cache clean --force

# === BUILD STAGE ===
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build application
RUN npm run build

# Remove dev dependencies after build
RUN npm prune --production

# === PRODUCTION STAGE ===
FROM node:20-alpine AS production

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

# Install tini for proper signal handling
RUN apk add --no-cache tini

WORKDIR /app

# Copy only production artifacts
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./

# Set environment
ENV NODE_ENV=production

# Switch to non-root user
USER nodejs

# Use tini as entrypoint
ENTRYPOINT ["/sbin/tini", "--"]

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

### Secrets in Build (Avoiding Exposure)

```dockerfile
# WRONG: Secret in environment variable (visible in history)
# ENV API_KEY=secret123

# WRONG: Secret in ARG (visible in image layers)
# ARG API_KEY
# RUN echo $API_KEY > /config

# CORRECT: Use Docker BuildKit secrets
# syntax=docker/dockerfile:1.4
FROM alpine

# Mount secret at build time only (not in final image)
RUN --mount=type=secret,id=api_key \
    cat /run/secrets/api_key > /tmp/key && \
    ./configure --key="$(cat /tmp/key)" && \
    rm /tmp/key

# Build with: docker build --secret id=api_key,src=./api_key.txt .
```

```dockerfile
# Using BuildKit SSH for private repos
# syntax=docker/dockerfile:1.4
FROM golang:1.22 AS builder

# Clone private repo using SSH agent
RUN --mount=type=ssh \
    git clone git@github.com:private/repo.git

# Build with: docker build --ssh default .
```

## User and Permission Hardening

### Non-Root User Patterns

```dockerfile
# Pattern 1: Create user in Alpine
FROM alpine:3.19
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup -h /app -s /sbin/nologin
USER appuser

# Pattern 2: Create user in Debian/Ubuntu
FROM debian:bookworm-slim
RUN groupadd -r -g 1001 appgroup && \
    useradd -r -g appgroup -u 1001 -d /app -s /usr/sbin/nologin appuser
USER appuser

# Pattern 3: Use numeric UID/GID (more portable)
FROM alpine:3.19
RUN addgroup -g 10001 -S app && adduser -u 10001 -S app -G app
USER 10001:10001

# Pattern 4: Match host user (for volume mounts)
ARG UID=1000
ARG GID=1000
RUN addgroup -g ${GID} -S app && adduser -u ${UID} -S app -G app
USER ${UID}:${GID}
```

### File Permission Hardening

```dockerfile
FROM alpine:3.19

# Create user before copying files
RUN addgroup -g 1001 -S app && adduser -u 1001 -S app -G app

WORKDIR /app

# Copy with correct ownership
COPY --chown=app:app . .

# Set restrictive permissions
RUN chmod -R 550 /app && \
    chmod -R 770 /app/tmp /app/logs

# Ensure no world-writable files
RUN find /app -perm /o+w -exec chmod o-w {} \;

USER app
```

## Filesystem Security

### Read-Only Root Filesystem

```dockerfile
FROM node:20-alpine

# Create writable directories
RUN mkdir -p /tmp /var/cache/app /app/logs && \
    chown -R node:node /tmp /var/cache/app /app/logs

WORKDIR /app
COPY --chown=node:node . .

USER node

# Application should use /tmp, /var/cache/app, /app/logs for writes
# Run with: docker run --read-only --tmpfs /tmp:rw,noexec,nosuid myapp
```

### Minimal Filesystem

```dockerfile
FROM alpine:3.19 AS base

# Remove unnecessary packages and files
RUN apk --no-cache add ca-certificates && \
    rm -rf /var/cache/apk/* \
           /tmp/* \
           /var/tmp/* \
           /usr/share/man/* \
           /usr/share/doc/* \
           /usr/share/info/*

# Remove shell if not needed (extreme hardening)
# RUN rm -f /bin/sh /bin/ash /bin/bash
```

## Network and Port Security

### Non-Privileged Ports

```dockerfile
# Run on non-privileged port (>1024)
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Switch to non-root
USER nginx

# Expose non-privileged port
EXPOSE 8080
```

```nginx
# nginx.conf for non-root
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    # Temp paths in writable locations
    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;

    server {
        listen 8080;  # Non-privileged port
        # ... rest of config
    }
}
```

## Security Labels and Metadata

### OCI Annotations

```dockerfile
# Standard OCI labels
LABEL org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Company Name" \
      org.opencontainers.image.title="Application Name" \
      org.opencontainers.image.description="Description" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# Security-specific labels
LABEL security.policy.seccomp="runtime/default" \
      security.policy.apparmor="runtime/default" \
      security.capabilities.drop="ALL" \
      security.user="nonroot"
```

## Anti-Patterns to Avoid

### Common Security Mistakes

```dockerfile
# ANTI-PATTERN 1: Running as root
FROM ubuntu
COPY app /app
CMD ["/app/run"]
# FIX: Add USER directive

# ANTI-PATTERN 2: Using latest tag
FROM node:latest
# FIX: Use specific version with digest
FROM node:20.10.0@sha256:abc123...

# ANTI-PATTERN 3: Installing unnecessary packages
RUN apt-get install -y vim curl wget net-tools
# FIX: Only install what's needed, remove package manager

# ANTI-PATTERN 4: Secrets in ENV or ARG
ENV DATABASE_PASSWORD=secret
ARG API_KEY=key123
# FIX: Use runtime secrets or BuildKit secrets

# ANTI-PATTERN 5: Wide COPY statements
COPY . /app
# FIX: Use .dockerignore and specific COPY

# ANTI-PATTERN 6: Not cleaning up
RUN apt-get update && apt-get install -y pkg
# FIX: Clean in same layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends pkg && \
    rm -rf /var/lib/apt/lists/*

# ANTI-PATTERN 7: ADD for local files
ADD app.tar.gz /app
ADD https://example.com/file /file
# FIX: Use COPY for local, RUN curl for remote

# ANTI-PATTERN 8: Writable root filesystem
# (no explicit protection)
# FIX: Design for read-only root with explicit tmpfs
```

### Secure .dockerignore

```dockerignore
# Version control
.git
.gitignore
.svn

# Dependencies (should be installed fresh)
node_modules
vendor
.venv
__pycache__

# Build artifacts
dist
build
*.o
*.pyc

# IDE and editor files
.idea
.vscode
*.swp
*.swo
*~

# Secrets and credentials (CRITICAL)
.env
.env.*
*.pem
*.key
*.p12
*.pfx
secrets/
credentials/
.aws
.azure
.gcloud

# Docker files (avoid recursive builds)
Dockerfile*
docker-compose*
.dockerignore

# Documentation (not needed in runtime)
README*
CHANGELOG*
docs/
*.md

# Tests (not needed in production)
test/
tests/
__tests__/
*.test.js
*.spec.js
coverage/
.nyc_output

# CI/CD
.github
.gitlab-ci.yml
.travis.yml
Jenkinsfile

# Logs and temp files
*.log
logs/
tmp/
temp/
```

## Linting and Validation

### Hadolint Configuration

```yaml
# .hadolint.yaml
ignored:
  - DL3008  # Pin versions in apt-get (may be too strict)

trustedRegistries:
  - gcr.io
  - docker.io

override:
  error:
    - DL3000  # Use absolute WORKDIR
    - DL3001  # Don't use /bin/sh -c
    - DL3002  # Switch to non-root USER
    - DL3003  # Use WORKDIR instead of cd
    - DL3004  # Don't use sudo
    - DL3006  # Always pin image version
    - DL3007  # Don't use :latest
    - DL3009  # Delete apt cache
    - DL3010  # Don't use ADD for local files
    - DL3011  # Valid Unix port
    - DL3018  # Pin apk versions
    - DL3019  # Use --no-cache for apk
    - DL3022  # COPY --from reference valid stage
    - DL3025  # Use JSON for CMD/ENTRYPOINT
    - DL3045  # COPY with --chown after ADD
    - DL4006  # Set SHELL with -o pipefail

  warning:
    - DL3013  # Pin pip versions
    - DL3016  # Pin npm versions
    - DL3028  # Pin gem versions

  info:
    - DL3059  # Multiple consecutive RUN
```

### Dockle Scanning

```bash
# Run Dockle security lint
dockle myimage:tag

# Output as JSON for CI
dockle -f json -o dockle-results.json myimage:tag

# Fail on high severity
dockle --exit-code 1 --exit-level fatal myimage:tag

# Ignore specific checks
dockle -i CIS-DI-0001 -i DKL-DI-0006 myimage:tag
```

## Complete Secure Dockerfile Template

```dockerfile
# syntax=docker/dockerfile:1.6
#
# Multi-stage secure Dockerfile template
# Build: docker build --secret id=npm_token,src=.npm_token -t myapp:v1.0.0 .
#

# === STAGE 1: Dependencies ===
FROM node:20.10.0-alpine3.19@sha256:abc123 AS deps

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) \
    npm ci --only=production --ignore-scripts && \
    npm cache clean --force

# === STAGE 2: Builder ===
FROM node:20.10.0-alpine3.19@sha256:abc123 AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build && \
    npm prune --production

# === STAGE 3: Production ===
FROM node:20.10.0-alpine3.19@sha256:abc123 AS production

# Labels
LABEL org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Company" \
      security.user="nodejs"

# Install dumb-init and remove package manager
RUN apk add --no-cache dumb-init && \
    rm -rf /var/cache/apk/* /sbin/apk /etc/apk

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs -h /app

WORKDIR /app

# Copy production artifacts
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./

# Create directories for runtime writes
RUN mkdir -p /app/tmp /app/logs && \
    chown -R nodejs:nodejs /app/tmp /app/logs && \
    chmod 770 /app/tmp /app/logs

# Environment
ENV NODE_ENV=production \
    PORT=3000

# Switch to non-root user
USER nodejs

# Use dumb-init
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

EXPOSE 3000

CMD ["node", "dist/server.js"]
```

## Related Documentation

- **Parent Skill**: See `../SKILL.md` for container security overview
- **Kubernetes Security**: See `kubernetes-security.md` for K8s hardening
- **Container Scanning**: See `container-scanning.md` for vulnerability scanning

---

**Last Updated:** 2025-12-26

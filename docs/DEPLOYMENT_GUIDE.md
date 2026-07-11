# EuroClaw Deployment Guide

## Overview
EuroClaw is designed to run as a sovereign orchestration service with optional Redis-backed worker execution and optional OpenTelemetry exporters. For production deployments, use a container orchestrator such as Docker Compose or Kubernetes.

The backend is API-first and can be consumed by a separate UI repository for chat, workflow control, and multi-agent roleplay experiences.

## Recommended deployment shape
- Run the API service behind a reverse proxy with TLS termination.
- Use Redis for distributed task execution when EXECUTION_MODE=distributed.
- Configure secrets through environment variables or a managed secret store.
- Disable remote telemetry unless an OTLP collector is available.

## Container example
```bash
docker build -t euroclaw:latest .
docker run --rm -p 8000:8000 \
  -e REDIS_HOST=redis \
  -e OTEL_SDK_DISABLED=true \
  -e EXECUTION_MODE=local \
  euroclaw:latest
```

## Example multi-agent request
```json
{
  "user_id": "user_123",
  "text": "Summarize the launch risks",
  "roleplay": { "persona": "operations lead" },
  "conversation": {
    "participants": [
      { "name": "analyst", "role": "risk analyst" },
      { "name": "reviewer", "role": "compliance reviewer" }
    ]
  }
}
```

## Kubernetes notes
- Create a Secret for sensitive values such as OIDC, Slack, Teams, and webhook credentials.
- Mount the secret as environment variables.
- Use liveness and readiness probes against /healthz/liveness and /healthz/readiness.

## Secrets management
- Do not commit .env files or secrets to source control.
- Use a managed secret store such as Azure Key Vault, AWS Secrets Manager, or HashiCorp Vault.
- Rotate long-lived tokens regularly.

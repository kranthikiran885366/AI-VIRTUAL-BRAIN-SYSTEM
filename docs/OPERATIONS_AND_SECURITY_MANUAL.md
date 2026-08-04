# Enterprise Operations & Security Manual — AI Virtual Brain System (Phase 15)

## 1. Security Architecture & RBAC

The system enforces Role-Based Access Control (RBAC) across four standard roles:
- `admin`: Full administrative access to system controls, security, and maintenance.
- `operator`: Ability to trigger optimization, self-healing, maintenance mode, and feature flags.
- `viewer`: Read-only access to status endpoints and telemetry.
- `agent`: System agent identity for inter-node communication.

### Enabling Security:
Set `SECURITY_ENABLED=true` and configure `JWT_SECRET_KEY` in environment.

---

## 2. Secrets Management & Audit Logging

- **Secrets Provider**: Defaults to `EnvironmentSecretProvider`, can be configured for in-memory or custom external providers (HashiCorp Vault / AWS Secrets Manager hooks).
- **Audit Logging**: Every secret read, rotation, deletion, and administrative action is logged to an immutable in-memory audit log with SHA-256 tamper-evident checksums.
- **Audit Log API**: `GET /api/v1/security/audit?limit=100`

---

## 3. Resilience & High Availability Controls

- **Circuit Breaker**: Auto-trips to OPEN state when failures exceed `CIRCUIT_BREAKER_FAILURE_THRESHOLD`. Resets via `POST /api/v1/resilience/circuit-breaker/reset`.
- **Bulkhead Isolator**: Limits concurrent processing to prevent resource exhaustion.
- **Dead-Letter Queue (DLQ)**: Failed agent messages are queued for retry or manual recovery via `GET /api/v1/resilience/dlq/entries`.
- **Disaster Recovery (DR)**: Generate logical backup manifests (`POST /api/v1/resilience/disaster-recovery/backup`) and simulate failover (`POST /api/v1/resilience/disaster-recovery/failover-test`).

---

## 4. Operational Controls & Feature Flags

- **Maintenance Mode**: Activate during upgrades via `POST /api/v1/ops/maintenance` with `{"enabled": true, "reason": "Database migration"}`.
- **Feature Flags**: Dynamic toggle of system features without service restart via `POST /api/v1/ops/features`.
- **Hot-Reload**: Trigger configuration refresh via `POST /api/v1/ops/reload`.

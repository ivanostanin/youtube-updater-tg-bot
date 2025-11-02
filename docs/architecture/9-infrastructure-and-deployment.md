# 9. Infrastructure and Deployment

## 9.1 Existing Infrastructure

**Current Deployment:**
- Docker containerization with multi-stage builds
- Kubernetes deployment via Helm chart
- GitHub Actions CI/CD for automated builds and pushes to Docker Hub
- OCI Kubernetes cluster (target environment)

**Infrastructure Tools:**
- Docker for containerization
- Helm 3 for Kubernetes manifest templating
- GitHub Actions for CI/CD
- Docker Hub as container registry

**Environments:**
- **Development:** Local docker-compose or direct Python execution
- **Production:** Kubernetes deployment with single replica (current), scaling to 3+ replicas (planned)

## 9.2 Enhancement Deployment Strategy

**Deployment Approach:**
- **Blue-Green Deployment:** Deploy new version alongside existing, switch traffic after validation
- **Database Migrations First:** Run Alembic migrations before deploying new code version to ensure schema compatibility
- **Phased Rollout:** Deploy Phase 1 (ACL, migrations) → validate → deploy Phase 2 (preferences, history) → validate → deploy Phase 3 (premium)

**Infrastructure Changes:**
- **PostgreSQL Addition (Phase 3):** Optional PostgreSQL StatefulSet or external managed database (RDS, Cloud SQL)
- **Redis Addition (Phase 3):** Redis StatefulSet or managed service for LLM response caching
- **Init Containers:** Add Alembic migration init container to Kubernetes pod spec (runs migrations before app starts)
- **Persistent Volume:** If using SQLite, add PVC for database persistence; S3 backup sidecar container for scheduled backups

**Pipeline Integration:**

GitHub Actions workflow stages:
1. **Lint & Test:** ruff, mypy, pytest with coverage report
2. **Build Docker Image:** Multi-stage build with caching
3. **Run Migrations (Staging):** Apply Alembic migrations to staging database
4. **Deploy to Staging:** Helm upgrade with new image tag
5. **Integration Tests (Staging):** Run smoke tests against staging bot
6. **Deploy to Production:** Manual approval gate, Helm upgrade production
7. **Post-Deploy Validation:** Health check, webhook verification

## 9.3 Rollback Strategy

**Rollback Method:**
- **Kubernetes:** `helm rollback youtube-updater-tg-bot` to previous release
- **Database:** Alembic downgrade migrations (`alembic downgrade -1`) before rollback
- **Code-Database Coupling:** Each release includes migration version tag; rollback requires matching migration downgrade

**Risk Mitigation:**
- **Pre-Deployment:** Database backup before migration (pg_dump or SQLite copy to S3)
- **Canary Deployment:** Deploy to 10% of pods first, monitor error rates before full rollout
- **Feature Flags:** Premium features gated behind preference checks; can disable via database update without code deployment
- **Health Checks:** Liveness/readiness probes monitor bot polling and webhook server; auto-restart unhealthy pods

**Monitoring:**
- **Logging:** Structured logging (JSON) to stdout, aggregated via Kubernetes logging (Fluentd/Loki)
- **Metrics:** Prometheus metrics for command latency, notification delivery rate, webhook processing time
- **Alerts:** PagerDuty/Slack alerts for error rate > 5%, webhook delivery failure rate > 10%, database connection failures
- **Dashboards:** Grafana dashboards for real-time monitoring (command usage, subscription growth, API quota consumption)

---

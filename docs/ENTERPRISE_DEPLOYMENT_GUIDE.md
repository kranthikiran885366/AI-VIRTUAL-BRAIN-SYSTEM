# Enterprise Deployment Guide — AI Virtual Brain System (Phase 15)

## Overview

This guide covers deployment options for the AI Virtual Brain System:
1. **Single Node Deployment** (Docker Compose / Local Python)
2. **Multi-Node Distributed Deployment** (Docker Compose Stack / Kubernetes)
3. **Enterprise Kubernetes Deployment** (Helm / kubectl)

---

## 1. Single Node Quickstart

```bash
# Python Environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run Orchestrator
python -m uvicorn orchestrator.main:app --host 0.0.0.0 --port 8001
```

---

## 2. Production Docker Deployment

```bash
# Build Production Image
docker build -t vbrain-orchestrator:latest -f Dockerfile.prod .

# Spin up Full Stack (Orchestrator, Postgres, Redis, Kafka, Prometheus, Grafana)
docker-compose -f docker-compose.prod.yml up -d
```

---

## 3. Kubernetes Cluster Deployment

### Using kubectl:

```bash
# Create namespace & manifests
kubectl apply -f deploy/kubernetes/virtual-brain.yaml

# Verify Deployment
kubectl get pods -n virtual-brain
kubectl get svc -n virtual-brain
```

### Using Helm:

```bash
# Install Helm Chart
helm upgrade --install vbrain ./deploy/helm/virtual-brain \
  --namespace virtual-brain \
  --create-namespace \
  --set orchestrator.replicaCount=3 \
  --set distributed.enabled=true
```

---

## 4. Multi-Node Distributed Cluster Configuration

To run in multi-node distributed mode, set the following environment variables across nodes:

- `DISTRIBUTED_MODE=true`
- `CLUSTER_NODE_ID=node-1` (unique per node)
- `CLUSTER_HEARTBEAT_INTERVAL=15`
- `REDIS_ENABLED=true`
- `REDIS_HOST=redis-cluster-host`
- `KAFKA_ENABLED=true`
- `KAFKA_BOOTSTRAP_SERVERS=kafka-cluster:9092`

---

## 5. Health Checks & Verification

- **Health Endpoint**: `http://<host>:8001/health`
- **Cluster Status**: `http://<host>:8001/api/v1/cluster/status`
- **Prometheus Metrics**: `http://<host>:8001/api/v1/observability/metrics`

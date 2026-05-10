# Selenoid Scaffold

This is the Step 3 browser infrastructure: Selenoid for browser sessions,
MinIO for execution artifacts, and Docker runner images for Selenium scripts.

Run locally from the backend app root:

```bash
docker compose -f docker-compose.selenoid.yml up
```

Backend env:

```env
SELENOID_HUB_URL=http://localhost:4444/wd/hub
SELENOID_RUNNER_HUB_URL=http://selenoid:4444/wd/hub
SELENOID_PUBLIC_URL=http://localhost:4444
AUTOMATION_RUNNER_DOCKER_NETWORK=biat_selenoid
MINIO_ENDPOINT_URL=http://localhost:9000
MINIO_RUNNER_ENDPOINT_URL=http://minio:9000
MINIO_ACCESS_KEY=biat
MINIO_SECRET_KEY=biat-secret
MINIO_BUCKET_NAME=biat-artifacts
```

Build runner images once:

```bash
docker build -t biat-runner-python:latest -f infra/runners/python/Dockerfile .
docker build -t biat-runner-java:latest -f infra/runners/java/Dockerfile .
```

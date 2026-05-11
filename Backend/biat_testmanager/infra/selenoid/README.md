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
AUTOMATION_STREAM_HOLD_SECONDS=20
```

Build runner images once:

```bash
docker build -t biat-runner-python:latest -f infra/runners/python/Dockerfile .
docker build -t biat-runner-java:latest -f infra/runners/java/Dockerfile .
```

Pull the browser image referenced by `browsers.json`:

```bash
docker pull selenoid/vnc:chrome_128.0
```

Selenoid uses Docker to create browser containers, but it does not pull
missing browser images automatically in this compose setup.

Frontend env:

```env
VITE_VNC_PASSWORD=selenoid
```

Selenoid VNC images use `selenoid` as the default noVNC password. Selenium Grid
images commonly use `secret`, so keep this value aligned with the browser image
family you are running.

`AUTOMATION_STREAM_HOLD_SECONDS` keeps a fast `Start live` browser session open
briefly after the script finishes so the noVNC viewer has time to attach.

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

RUN ln -sf "$(command -v python3)" /usr/local/bin/python

RUN pip install --no-cache-dir \
    "boto3>=1.35.0" \
    "redis>=5.0.0" \
    "requests>=2.32.0" \
    "selenium>=4.25.0"

WORKDIR /workspace

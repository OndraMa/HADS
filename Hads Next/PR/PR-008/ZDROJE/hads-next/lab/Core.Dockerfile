# Laboratory Core only. This image is neither HAOS nor Supervisor.
FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN --mount=type=bind,source=core-constraints.txt,target=/tmp/core-constraints.txt \
    --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then \
      export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; \
    fi; \
    python -m pip install --no-cache-dir --only-binary=:all: uv==0.13.6 && \
    uv pip install --system --no-cache \
      --constraint /tmp/core-constraints.txt homeassistant==2026.11.0
ENTRYPOINT ["python"]

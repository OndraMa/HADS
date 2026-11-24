# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chmod=644 src/hads_next/investigation.py /app/hads_next/investigation.py
COPY --chmod=644 scripts/hermes_smoke.py /app/hermes_smoke.py
COPY --chmod=644 docs/evidence/hermes-dependencies.txt /tmp/hermes-constraints.txt
# A single installation layer also works with space-expensive VFS storage.
RUN --mount=type=secret,id=proxy_ca,required=true \
    apt-get update && apt-get install -y --no-install-recommends git ca-certificates build-essential && \
    git init /opt/hermes && git -C /opt/hermes remote add origin https://github.com/NousResearch/hermes-agent.git && \
    GIT_SSL_CAINFO=/run/secrets/proxy_ca git -C /opt/hermes fetch --depth 1 origin d923a5eb487a17c0a68801bba9ef0f56c81040a8 && \
    git -C /opt/hermes checkout --detach FETCH_HEAD && \
    test "$(git -C /opt/hermes rev-parse HEAD)" = d923a5eb487a17c0a68801bba9ef0f56c81040a8 && \
    git -C /opt/hermes rev-parse HEAD > /opt/hermes/HADS_PINNED_REVISION && \
    PIP_CERT=/run/secrets/proxy_ca python -m pip install --constraint /tmp/hermes-constraints.txt --no-cache-dir --editable /opt/hermes && \
    rm -rf /opt/hermes/.git /root/.cache /var/lib/apt/lists/* && \
    apt-get purge -y --auto-remove git build-essential && \
    chmod 755 /app /app/hads_next
ENV PYTHONPATH=/opt/hermes:/app HERMES_HOME=/tmp/hermes HADS_ISOLATED_TEST=1
USER 65534:65534
ENTRYPOINT ["python", "/app/hermes_smoke.py"]

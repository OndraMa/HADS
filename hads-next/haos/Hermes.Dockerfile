# Actual pinned Hermes. CORE_LAB=1 runs Core+Hermes acceptance during the build;
# production default does not install Home Assistant Core or test data.
FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ARG CORE_LAB=0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app HADS_DATA_DIR=/data/hads-next
WORKDIR /app
RUN --mount=type=bind,source=hermes-constraints.txt,target=/hermes-constraints.txt,readonly \
    --mount=type=bind,source=lab/core-constraints.txt,target=/core-constraints.txt,readonly \
    --mount=type=secret,id=proxy_ca,required=false \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then \
      export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; \
    fi; \
    apt-get update; apt-get install -y --no-install-recommends git build-essential ca-certificates libseccomp2; \
    python -m pip install --no-cache-dir uv==0.13.6 websockets==16.0; \
    mkdir -p /opt/hermes-root/opt/hermes /opt/hermes-root/usr/local/lib /opt/hermes-root/app/hads_next /opt/hermes-root/tmp /opt/hermes-root/etc; \
    git init /opt/hermes-root/opt/hermes; \
    git -C /opt/hermes-root/opt/hermes remote add origin https://github.com/NousResearch/hermes-agent.git; \
    git -C /opt/hermes-root/opt/hermes fetch --depth 1 origin d923a5eb487a17c0a68801bba9ef0f56c81040a8; \
    git -C /opt/hermes-root/opt/hermes checkout --detach FETCH_HEAD; \
    test "$(git -C /opt/hermes-root/opt/hermes rev-parse HEAD)" = d923a5eb487a17c0a68801bba9ef0f56c81040a8; \
    git -C /opt/hermes-root/opt/hermes rev-parse HEAD > /opt/hermes-root/opt/hermes/HADS_PINNED_REVISION; \
    uv venv /opt/hermes-root/opt/hermes/.venv; \
    uv pip install --python /opt/hermes-root/opt/hermes/.venv/bin/python --no-cache \
      --constraint /hermes-constraints.txt --editable /opt/hermes-root/opt/hermes; \
    rm -rf /opt/hermes-root/opt/hermes/.git /opt/hermes-root/opt/hermes/tests /root/.cache; \
    apt-get purge -y --auto-remove git build-essential; rm -rf /var/lib/apt/lists/*; \
    cp -a /usr/local/bin /opt/hermes-root/usr/local/bin; \
    cp -al /usr/local/lib/python3.14 /opt/hermes-root/usr/local/lib/python3.14; \
    rm -rf /opt/hermes-root/usr/local/lib/python3.14/site-packages; \
    cp -a /usr/local/lib/libpython3.14.so* /opt/hermes-root/usr/local/lib/; \
    cp -a /usr/lib /opt/hermes-root/usr/lib; ln -s usr/lib /opt/hermes-root/lib; \
    if [ -d /usr/lib64 ]; then cp -a /usr/lib64 /opt/hermes-root/usr/lib64; ln -s usr/lib64 /opt/hermes-root/lib64; fi; \
    cp -a /etc/ssl /opt/hermes-root/etc/ssl; \
    chmod 1777 /opt/hermes-root/tmp; \
    if [ "$CORE_LAB" = 1 ]; then \
      uv pip install --system --no-cache --constraint /core-constraints.txt homeassistant==2026.11.0; \
      # Lab keeps original Core code and APIs; discard unused UI languages to \
      # fit VFS inode quotas. Production does not contain Core at all. \
      find /usr/local/lib/python3.14/site-packages/homeassistant -path '*/translations/*.json' -type f ! -name en.json ! -name cs.json -delete; \
    fi
RUN --mount=type=bind,source=.,target=/source,readonly \
    set -eu; \
    cp -a /source/hads_next /app/hads_next; cp /source/run.sh /run.sh; \
    for file in __init__.py hermes_worker.py hermes_sandbox.py worker_protocol.py; do \
      cp /app/hads_next/"$file" /opt/hermes-root/app/hads_next/"$file"; done; \
    find /app/hads_next /opt/hermes-root/app -type d -exec chmod 755 {} +; \
    find /app/hads_next /opt/hermes-root/app -type f -exec chmod 644 {} +; \
    chmod 755 /app /run.sh; \
    if [ "$CORE_LAB" = 1 ]; then \
      python /source/lab/core_hermes_probe.py > /app/core-hermes-proof.json; \
    fi
EXPOSE 8099
ENTRYPOINT ["/run.sh"]

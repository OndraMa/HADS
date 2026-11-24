# Self-contained local HAOS build context, assembled by build_haos_installer.py.
# No pip/APT installation, no model, no shell/MCP tool bridge.
FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HADS_DATA_DIR=/data/hads-next
WORKDIR /app
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir websockets==16.0
COPY hads_next /app/hads_next
COPY run.sh /run.sh
RUN find /app/hads_next -type d -exec chmod 755 {} + && \
    find /app/hads_next -type f -exec chmod 644 {} + && \
    chmod 755 /app /run.sh
EXPOSE 8099
ENTRYPOINT ["/run.sh"]

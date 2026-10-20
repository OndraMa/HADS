FROM python:3.14-slim-bookworm AS sqlite_build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && curl -fsSL --retry 3 --connect-timeout 15 --max-time 180 \
       https://sqlite.org/2026/sqlite-autoconf-3530400.tar.gz -o /tmp/sqlite.tar.gz \
    && echo '0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c  /tmp/sqlite.tar.gz' | sha256sum -c - \
    && tar -xzf /tmp/sqlite.tar.gz -C /tmp \
    && cd /tmp/sqlite-autoconf-3530400 \
    && CFLAGS='-O2 -DSQLITE_ENABLE_FTS5 -DSQLITE_THREADSAFE=1' ./configure --prefix=/opt/sqlite-fixed --disable-static \
    && make -j2 && make install

FROM python:3.14-slim-bookworm AS hermes_runtime
COPY --from=sqlite_build /opt/sqlite-fixed/lib/ /opt/sqlite-fixed/lib/
ENV LD_LIBRARY_PATH=/opt/sqlite-fixed/lib PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN python -c "import sqlite3; assert sqlite3.sqlite_version_info >= (3,51,3)"

# Pinned reviewed upstream release; no curl|bash and no runtime self-update.
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential ca-certificates tzdata libseccomp2 \
    && rm -rf /var/lib/apt/lists/* \
    && git init /opt/hermes \
    && git -C /opt/hermes remote add origin https://github.com/NousResearch/hermes-agent.git \
    && git -C /opt/hermes fetch --depth 1 origin d923a5eb487a17c0a68801bba9ef0f56c81040a8 \
    && git -C /opt/hermes checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/hermes rev-parse HEAD)" = d923a5eb487a17c0a68801bba9ef0f56c81040a8 \
    && python -m pip install --no-cache-dir PyYAML websocket-client jsonschema \
    && python -m venv /opt/hermes/.venv \
    && /opt/hermes/.venv/bin/python -m pip install --no-cache-dir --editable /opt/hermes

FROM python:3.14-slim-bookworm
ENV LD_LIBRARY_PATH=/opt/sqlite-fixed/lib PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=hermes_runtime /opt/sqlite-fixed/lib/ /opt/sqlite-fixed/lib/
# Worker-visible root contains only public runtime/dependencies, never HA mounts.
COPY --from=hermes_runtime /usr/local/ /opt/hermes-root/usr/local/
COPY --from=hermes_runtime /usr/lib/ /opt/hermes-root/usr/lib/
COPY --from=hermes_runtime /opt/hermes/ /opt/hermes-root/opt/hermes/
COPY --from=hermes_runtime /opt/sqlite-fixed/lib/ /opt/hermes-root/opt/sqlite-fixed/lib/
RUN apt-get update && apt-get install -y --no-install-recommends libseccomp2 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir PyYAML websocket-client jsonschema \
    && mkdir -p /opt/hermes-root/tmp /opt/hermes-root/etc /opt/hermes-root/app \
    && ln -s usr/lib /opt/hermes-root/lib \
    && if [ -d /usr/lib64 ]; then ln -s usr/lib64 /opt/hermes-root/lib64; fi \
    && cp -a /etc/ssl /opt/hermes-root/etc/ssl \
    && chmod 1777 /opt/hermes-root/tmp
WORKDIR /app
COPY hads4.py /app/hads4.py
COPY runtime_core.py /app/runtime_core.py
COPY panel_model.py /app/panel_model.py
COPY ai_context.py /app/ai_context.py
COPY hermes_bridge.py /app/hermes_bridge.py
COPY hermes_worker.py /app/hermes_worker.py
COPY hermes_sandbox.py /app/hermes_sandbox.py
COPY hermes_sandbox.py /opt/hermes-root/app/hermes_sandbox.py
COPY hermes_transport.py /app/hermes_transport.py
COPY hermes_transport.py /opt/hermes-root/app/hermes_transport.py
COPY tests/hermes_upstream_smoke.py /app/hermes_upstream_smoke.py
COPY tests/hermes_no_landlock_smoke.py /app/hermes_no_landlock_smoke.py
# This build-time test invokes real Hermes with a fake local model, no paid API.
RUN python /app/hermes_upstream_smoke.py
COPY native_backup.py /app/native_backup.py
COPY repair_engine.py /app/repair_engine.py
COPY command_center.py /app/command_center.py
COPY first_officer.py /app/first_officer.py
COPY tool_adapters.py /app/tool_adapters.py
COPY mcp_diagnostics.py /app/mcp_diagnostics.py
COPY incident_workflow.py /app/incident_workflow.py
COPY ai_provider.py /app/ai_provider.py
COPY analysis_contract.py /app/analysis_contract.py
COPY investigation.py /app/investigation.py
COPY functional_focus.py /app/functional_focus.py
COPY diagnostic_policy.py /app/diagnostic_policy.py
COPY site_tools.py /app/site_tools.py
COPY web /app/web
COPY dashboard /app/dashboard

EXPOSE 8099
CMD ["python3", "-u", "/app/hads4.py"]

FROM alpine:3.21

RUN apk add --no-cache python3 py3-yaml py3-websocket-client tzdata
WORKDIR /app
COPY hads4.py /app/hads4.py
COPY repair_engine.py /app/repair_engine.py
COPY command_center.py /app/command_center.py
COPY first_officer.py /app/first_officer.py
COPY tool_adapters.py /app/tool_adapters.py
COPY incident_workflow.py /app/incident_workflow.py
COPY analysis_contract.py /app/analysis_contract.py
COPY site_tools.py /app/site_tools.py
COPY web /app/web
COPY dashboard /app/dashboard

EXPOSE 8099
CMD ["python3", "-u", "/app/hads4.py"]

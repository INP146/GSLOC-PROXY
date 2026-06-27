FROM node:22-bookworm-slim AS web-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
COPY proxy/gsloc_proxy/ /app/proxy/gsloc_proxy/
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MITMDUMP_BIN=mitmdump \
    GSLOC_PROXY_HOST=0.0.0.0 \
    GSLOC_PROXY_PORT=8082 \
    GSLOC_MANAGE_HOST=0.0.0.0 \
    GSLOC_MANAGE_PORT=8090 \
    GSLOC_POLICY_PATH=/config/policy.json \
    GSLOC_STATE_PATH=/data/state.json \
    MITMPROXY_CONF_DIR=/data/mitmproxy \
    GSLOC_RESTART_FLAG=/tmp/gsloc-proxy.restart \
    GSLOC_LOG_FILE=/data/logs/gsloc-proxy.log

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && mkdir -p /config /defaults \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/proxy
COPY proxy/pyproject.toml ./
COPY proxy/gsloc_proxy ./gsloc_proxy
COPY proxy/run-local.py ./
COPY proxy/policy.example.json /defaults/policy.example.json
COPY proxy/state.example.json /defaults/state.example.json
COPY docker/entrypoint.sh /usr/local/bin/gsloc-proxy-entrypoint
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .
COPY --from=web-build /app/proxy/gsloc_proxy/static ./gsloc_proxy/static

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /config /data/logs /data/mitmproxy \
    && chmod +x /usr/local/bin/gsloc-proxy-entrypoint \
    && chown -R appuser:appuser /app /config /data /defaults /tmp
USER appuser

VOLUME ["/data"]
EXPOSE 8082 8090
ENTRYPOINT ["gsloc-proxy-entrypoint"]
CMD ["python", "run-local.py"]

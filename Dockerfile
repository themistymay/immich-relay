FROM python:3.12-alpine

RUN apk add --no-cache \
    tzdata \
    tini

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
COPY src/ ./src/

RUN chmod +x /entrypoint.sh \
    && mkdir -p /data /tmp/sync_cache

ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]

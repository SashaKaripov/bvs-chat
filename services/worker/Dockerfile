FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/worker/worker.py /app/worker.py
COPY services/worker/entrypoint.sh /app/entrypoint.sh
COPY firewall/apply.sh firewall/rules.conf /firewall/

RUN chmod +x /app/entrypoint.sh /firewall/apply.sh

ENTRYPOINT ["/app/entrypoint.sh"]

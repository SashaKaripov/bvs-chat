FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/chat-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/chat-api/app.py /app/app.py
COPY services/chat-api/entrypoint.sh /app/entrypoint.sh
COPY firewall/apply.sh firewall/rules.conf /firewall/

RUN chmod +x /app/entrypoint.sh /firewall/apply.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]

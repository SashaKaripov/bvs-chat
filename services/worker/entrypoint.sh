#!/bin/sh
set -eu
cd /app
/firewall/apply.sh worker
python -c '
import os, time, pika
creds = pika.PlainCredentials(os.environ.get("RABBIT_USER", "chat"), os.environ.get("RABBIT_PASSWORD", "rabbitpass"))
hosts = [h.strip() for h in os.environ.get("RABBIT_HOSTS", "rabbitmq-1").split(",") if h.strip()]
while True:
    for host in hosts:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(
                host=host, port=5672, virtual_host="/", credentials=creds,
                socket_timeout=3, stack_timeout=3, connection_attempts=1,
                blocked_connection_timeout=3,
            ))
            conn.channel().queue_declare(queue="chat.jobs", passive=True)
            conn.close()
            raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            pass
    time.sleep(2)
'
exec python worker.py

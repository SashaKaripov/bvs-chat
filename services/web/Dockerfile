FROM nginx:1.27
RUN apt-get update && apt-get install -y --no-install-recommends iptables netcat-openbsd && rm -rf /var/lib/apt/lists/*
COPY firewall/apply.sh firewall/rules.conf /firewall/
RUN rm -f /etc/nginx/conf.d/default.conf
COPY services/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY services/web/index.html services/web/app.js services/web/style.css /usr/share/nginx/html/
COPY services/web/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /firewall/apply.sh
ENTRYPOINT ["/entrypoint.sh"]

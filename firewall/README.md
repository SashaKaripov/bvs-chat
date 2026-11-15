# Файрвол

1. edge. Сеть не internal. В ней web и chat-api. С ноутбука открыт только порт 8080 на web.
2. data. internal: true, без выхода в интернет. postgres-primary, postgres-standby, postgres-router, redis, rabbitmq-1, rabbitmq-2, rabbitmq-3, chat-api, worker.
3. egress. Только worker, чтобы звать OpenRouter по tcp/443. chat-api в egress не входит.

У web, chat-api и worker политика OUTPUT DROP. Запрет виден командой `iptables -S`.

Показ из корня уже запущенного проекта:

- `./firewall/demo-deny.sh` — `iptables -S` в web и tcp. chat-api:8000 «разрешено», порт 5432 «запрещено». Соединение проверяет `nc -z -w 5`.
- `./firewall/break-legit.sh` — запрещает легитимный путь chat-api на postgres 5432.
- `./firewall/restore-legit.sh` — возвращает правило.

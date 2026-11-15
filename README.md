# BVS Chat

Один веб-чат, одна модель через OpenRouter. Стенд для защиты: микросервисы и сетевая защита на живом чате, с репликой Postgres, тремя узлами RabbitMQ и файрволом.

```bash
./scripts/up.sh
```

Дальше http://localhost:8080.

```bash
curl -s http://localhost:8080/api/hello
docker compose exec redis redis-cli -a redispass GET chat:messages
./firewall/demo-deny.sh
./firewall/break-legit.sh
./firewall/restore-legit.sh
./scripts/db-failover.sh
./scripts/db-recover.sh
./scripts/broker-failover.sh
docker compose start rabbitmq-1
./scripts/backup.sh
./scripts/restore.sh
```

В браузере написать, увидеть ответ, изменить и удалить. После `break-legit.sh` запись в чат падает, `restore-legit.sh` возвращает её. Брокер: http://localhost:15672, логин chat, пароль rabbitpass, очередь chat.jobs.

Цели учебного ноутбука: SLO — страница открывается, запись сохраняется, ответ модели при живом OpenRouter за 60 секунд. MTBF 720 часов. MTTR 60 секунд. RPO дампа backups/chat.sql — сутки.

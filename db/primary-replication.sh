#!/usr/bin/env bash
set -euo pipefail

cat >> "$PGDATA/pg_hba.conf" <<'EOF'
host replication replicator 0.0.0.0/0 md5
host all all 0.0.0.0/0 md5
EOF

cat >> "$PGDATA/postgresql.conf" <<'EOF'
listen_addresses='*'
wal_level=replica
hot_standby=on
max_wal_senders=10
max_replication_slots=10
wal_keep_size=64MB
EOF

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
SET password_encryption = 'md5';
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replpass';
  END IF;
END
$$;
SQL

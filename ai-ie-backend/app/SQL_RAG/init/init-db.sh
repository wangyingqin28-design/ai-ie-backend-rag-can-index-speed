#!/usr/bin/env bash
set -euo pipefail

SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
SQLCMD_EXTRA=(-C)

if [ ! -x "$SQLCMD" ]; then
  SQLCMD="/opt/mssql-tools/bin/sqlcmd"
  SQLCMD_EXTRA=()
fi

echo "[sql-rag] Initializing database ${APP_DB_NAME} and login ${APP_DB_USER}"

"$SQLCMD" \
  -S sqlserver \
  -U sa \
  -P "$MSSQL_SA_PASSWORD" \
  "${SQLCMD_EXTRA[@]}" \
  -v APP_DB_NAME="$APP_DB_NAME" APP_DB_USER="$APP_DB_USER" APP_DB_PASSWORD="$APP_DB_PASSWORD" \
  -i /init/init-db.sql

echo "[sql-rag] Database initialization completed"

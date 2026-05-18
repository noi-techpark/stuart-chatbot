#!/bin/sh
# Generates the JSON config files expected by the RAG Python scripts from environment variables,
# then executes the container command. All variables except LLM_API_KEY are required:
# the container will exit immediately with "unbound variable" if any of them are missing.
set -eu

# Generate secrets_pg.json from environment variables
cat > /usr/src/app/secrets_pg.json <<EOF
{
  "host": "${PG_HOST}",
  "port": "${PG_PORT}",
  "dbname": "${PG_DBNAME}",
  "user": "${PG_USER}",
  "password": "${PG_PASSWORD}",
  "connect_timeout": "${PG_CONNECT_TIMEOUT}"
}
EOF

# Generate secrets_llm_endpoint.json from environment variables
cat > /usr/src/app/secrets_llm_endpoint.json <<EOF
{
  "endpoint": "${LLM_ENDPOINT}",
  "model": "${LLM_MODEL}",
  "api_key": "${LLM_API_KEY-}"
}
EOF

# Generate backend.json from environment variables
cat > /usr/src/app/backend.json <<EOF
{
  "endpoint": "${STUART_WEB_ENDPOINT}",
  "preshared_secret": "${PRESHARED_SECRET}"
}
EOF

exec "$@"

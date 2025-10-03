#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE ai_doc_process'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_doc_process')\gexec
EOSQL
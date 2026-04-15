#!/bin/bash
set -e

# Decode Google credentials if provided as base64
if [ -n "$GOOGLE_CREDENTIALS_B64" ]; then
  mkdir -p /app/credentials
  echo "$GOOGLE_CREDENTIALS_B64" | base64 -d > /app/credentials/googleService.json
  export GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/googleService.json
fi

exec "$@"

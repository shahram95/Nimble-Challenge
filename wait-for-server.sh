#!/bin/bash
# wait-for-server.sh

set -e

host="$1"
shift
cmd="$@"

echo "Waiting for server at $host:8080..."

# Loop until the server port is available
until nc -z "$host" 8080; do
  >&2 echo "Server is unavailable - sleeping"
  sleep 1
done

>&2 echo "Server is up - executing command"
exec $cmd
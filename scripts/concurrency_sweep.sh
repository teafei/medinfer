#!/usr/bin/env sh
# Invoke from repository root after configuring MEDINFER_BACKEND/MODEL/BASE_URL.
set -eu
mkdir -p results
for concurrency in 1 4 8 16; do
  medinfer benchmark --concurrency "$concurrency" --repetitions 3 --max-tokens 2048 \
    --warmup 1 --output "results/concurrency-${concurrency}.json"
done

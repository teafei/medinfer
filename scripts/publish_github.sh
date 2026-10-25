#!/usr/bin/env sh
# The only external step remaining: create the authorized public repository and push.
set -eu
cd "$(dirname "$0")/.."
if ! command -v gh >/dev/null 2>&1; then
  echo 'Install GitHub CLI from https://cli.github.com/ and authenticate with gh auth login.'
  exit 1
fi
gh auth status
account=$(gh api user --jq .login)
if [ "$account" != teafei ]; then
  echo 'This script is intended for the teafei account. Switch accounts before publishing.'
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo 'Commit or review local changes before publishing.'
  exit 1
fi
gh repo create teafei/medinfer --public --source=. --remote=origin --push \
  --description 'Private medical LLM inference and reproducible synthetic workload benchmarks'

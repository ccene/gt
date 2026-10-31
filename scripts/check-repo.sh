#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
require() {
  if [ ! -e "$1" ]; then
    echo "MISSING: $1"
    fail=1
  fi
}

for f in README.md GETTING_STARTED.md MASTER_PLAN.md .gitignore .env.example \
         .github/workflows/ci.yml scripts/check-repo.sh; do
  require "$f"
done

if git ls-files | grep -Eq '(^|/)\.env$|(^|/)\.env\.[^e]'; then
  echo "ERROR: a real .env file is tracked; only .env.example may be committed"
  fail=1
fi

# Only flag values that look like real secrets (>=20 chars, mixed alnum), not placeholders.
if git ls-files -z | xargs -0 grep -lEi '(api[_-]?key|secret|password|token)[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_\-]{20,}' 2>/dev/null | grep -v '.env.example' | grep -v '.github/workflows/' | grep -vE 'token_urlsafe|token_hex|compare_digest|lastrowid' | grep -q .; then
  echo "ERROR: possible hardcoded secret in tracked files:"
  git ls-files -z | xargs -0 grep -lEi '(api[_-]?key|secret|password|token)[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_\-]{20,}' 2>/dev/null | grep -v '.env.example' | grep -v '.github/workflows/' | grep -vE 'token_urlsafe|token_hex|compare_digest|lastrowid' || true
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "repo check FAILED"
  exit 1
fi
echo "repo check OK"

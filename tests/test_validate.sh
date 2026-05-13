#!/usr/bin/env bash
# Smoke tests for tools/validate.py against fixtures.
# Run from repo root: bash tests/test_validate.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0

echo "--- healthy fixture should pass ---"
if python3 tools/validate.py --root tests/fixtures/healthy >/tmp/cpm_healthy.log 2>&1; then
  echo "PASS"
else
  echo "FAIL (expected exit 0)"
  cat /tmp/cpm_healthy.log
  fail=1
fi

echo
echo "--- broken fixture should fail ---"
if python3 tools/validate.py --root tests/fixtures/broken >/tmp/cpm_broken.log 2>&1; then
  echo "FAIL (expected exit 1 but got 0)"
  cat /tmp/cpm_broken.log
  fail=1
else
  echo "PASS (validator correctly rejected broken fixture)"
fi

echo
if [[ $fail -eq 0 ]]; then
  echo "ALL TESTS PASSED"
  exit 0
else
  echo "TESTS FAILED"
  exit 1
fi

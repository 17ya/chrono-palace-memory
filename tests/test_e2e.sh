#!/usr/bin/env bash
# End-to-end smoke test: bootstrap a memory store, write a session, run the
# validator and aggregator, and confirm the search tool indexes the new file.
#
# Run from repo root: bash tests/test_e2e.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d -t cpm-e2e.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

MEM="$TMP/.memory"
mkdir -p "$MEM"
cp templates/MEMORY.md "$MEM/MEMORY.md"

DATE_DAY="$(date +%Y-%m-%d)"
DATE_PATH="$(date +%Y/%m/%d)"
EXPIRES="$(python3 -c 'from datetime import date,timedelta; print(date.today()+timedelta(days=30))')"
SESSION_DIR="$MEM/sessions/$DATE_PATH"
mkdir -p "$SESSION_DIR"
SESSION_FILE="$SESSION_DIR/session_001.md"

cat >"$SESSION_FILE" <<EOF
---
name: session-e2e-001
description: e2e smoke test session
type: session
created_at: $DATE_DAY
expires_at: $EXPIRES
confidence: 0.9
importance: 0.5
status: active
evidence: []
promoted_to: []
topics:
  - e2e
  - chrono-palace-memory
entities_mentioned: []
---

# Session Summary
This is the e2e fixture session referencing chrono-palace memory.
EOF

# Index the session in MEMORY.md so validators that check coverage stay happy.
printf '\n## Sessions\n- [session-e2e-001](sessions/%s/session_001.md) — e2e smoke test\n' \
  "$DATE_PATH" >>"$MEM/MEMORY.md"

fail=0

echo "--- step 1: validator should accept the bootstrapped store ---"
if python3 tools/validate.py --root "$MEM" >"$TMP/validate.log" 2>&1; then
  echo "PASS"
else
  echo "FAIL (validator exited non-zero)"
  cat "$TMP/validate.log"
  fail=1
fi

echo
echo "--- step 2: aggregate-daily should mention the new session ---"
if python3 tools/aggregate-daily.py --root "$MEM" "$DATE_DAY" >"$TMP/aggregate.log" 2>&1; then
  if grep -q "session-e2e-001\|sessions/$DATE_PATH/session_001.md" "$TMP/aggregate.log"; then
    echo "PASS"
  else
    echo "FAIL (draft did not reference the session)"
    cat "$TMP/aggregate.log"
    fail=1
  fi
else
  echo "FAIL (aggregator exited non-zero)"
  cat "$TMP/aggregate.log"
  fail=1
fi

echo
echo "--- step 3: search should find the session by topic token ---"
if python3 tools/search.py --root "$MEM" --backend tfidf "chrono-palace memory" >"$TMP/search.log" 2>&1; then
  if grep -q "session_001.md" "$TMP/search.log"; then
    echo "PASS"
  else
    echo "FAIL (search did not surface the session)"
    cat "$TMP/search.log"
    fail=1
  fi
else
  echo "FAIL (search exited non-zero)"
  cat "$TMP/search.log"
  fail=1
fi

echo
if [[ $fail -eq 0 ]]; then
  echo "ALL E2E STEPS PASSED"
  exit 0
else
  echo "E2E TESTS FAILED"
  exit 1
fi

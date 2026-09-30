#!/usr/bin/env bash
# End-to-end smoke test against a RUNNING stack.
#   ./scripts/smoke_test.sh [base_url]     (default http://localhost:3000)
set -uo pipefail

BASE="${1:-http://localhost:3000}"
PASS=0; FAIL=0

check() {           # check <description> <command...>
  local desc="$1"; shift
  if output=$("$@" 2>&1); then
    printf '  \033[32mPASS\033[0m  %s\n' "$desc"; PASS=$((PASS+1))
  else
    printf '  \033[31mFAIL\033[0m  %s\n        %s\n' "$desc" "$output"; FAIL=$((FAIL+1))
  fi
}

echo
echo "Smoke test against $BASE"
echo "------------------------------------------------------------"

check "frontend serves index.html" \
  bash -c "curl -fsS '$BASE/' | grep -q 'Financial Twin'"

check "API health is ok" \
  bash -c "curl -fsS '$BASE/api/health' | grep -q '\"status\":\"ok\"'"

check "1,000 customers are seeded" \
  bash -c "[ \"\$(curl -fsS '$BASE/api/health' | python3 -c 'import json,sys;print(json.load(sys.stdin)[\"customers\"])')\" -ge 1000 ]"

check "all three hero personas load" \
  bash -c "[ \"\$(curl -fsS '$BASE/api/personas' | python3 -c 'import json,sys;print(len(json.load(sys.stdin)[\"personas\"]))')\" -eq 3 ]"

for p in A B C; do
  check "persona $p has a Twin" \
    bash -c "curl -fsS '$BASE/api/twins/KBC-HERO-$p' | grep -q '\"life_phase\"'"
done

check "persona A starts as a student" \
  bash -c "curl -fsS '$BASE/api/twins/KBC-HERO-A' | python3 -c 'import json,sys;assert json.load(sys.stdin)[\"life_phase\"][\"value\"]==\"student\"'"

check "advisor sees the same Twin version" \
  bash -c "
    a=\$(curl -fsS '$BASE/api/twins/KBC-HERO-A' | python3 -c 'import json,sys;print(json.load(sys.stdin)[\"version\"])')
    b=\$(curl -fsS '$BASE/api/advisor/KBC-HERO-A' | python3 -c 'import json,sys;print(json.load(sys.stdin)[\"twin_version\"])')
    [ \"\$a\" = \"\$b\" ]"

check "injecting a salary flips persona A to first_job" \
  bash -c "curl -fsS -X POST '$BASE/api/demo/KBC-HERO-A/first-salary?wait=true' | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d[\"twin\"][\"life_phase\"][\"value\"]==\"first_job\", d[\"twin\"][\"life_phase\"]'"

check "crib purchase raises the family signal above its threshold" \
  bash -c "curl -fsS -X POST '$BASE/api/demo/KBC-HERO-B/crib-purchase?wait=true' | python3 -c '
import json,sys
d=json.load(sys.stdin)
s=[x for x in d[\"twin\"][\"signals\"] if x[\"id\"]==\"possible_family_expansion\"][0]
assert s[\"triggered\"] and s[\"score\"] < 1.0, s'"

check "a correction suppresses house recommendations" \
  bash -c "curl -fsS -X POST '$BASE/api/twins/KBC-HERO-B/corrections' -H 'Content-Type: application/json' -d '{\"field\":\"plans_to_buy_house\",\"value\":false}' | python3 -c '
import json,sys
d=json.load(sys.stdin)[\"twin\"]
assert \"house_deposit\" not in {g[\"id\"] for g in d[\"goals\"]}
assert \"first_home\" not in {p[\"id\"] for p in d[\"playbooks\"]}'"

check "no Anthropic key is required" \
  bash -c "curl -fsS '$BASE/api/twins/KBC-HERO-A?open=true' | python3 -c '
import json,sys
n=json.load(sys.stdin)[\"narrative\"]
assert n[\"generator\"] in (\"template\",\"claude\") and len(n[\"body\"])>60, n'"

check "benchmark endpoint returns measured numbers" \
  bash -c "curl -fsS '$BASE/api/benchmark' | python3 -c '
import json,sys
d=json.load(sys.stdin)
if d.get(\"status\")!=\"complete\": raise SystemExit(\"benchmark still running - retry in a few seconds\")
assert d[\"measured\"][\"events_per_second\"] > 0'"

check "cost endpoint returns a configurable model" \
  bash -c "curl -fsS '$BASE/api/cost' | grep -q 'naive_per_transaction'"

check "10+ playbooks are registered" \
  bash -c "[ \"\$(curl -fsS '$BASE/api/playbooks' | python3 -c 'import json,sys;print(json.load(sys.stdin)[\"count\"])')\" -ge 10 ]"

check "reset restores the seeded world" \
  bash -c "curl -fsS -X POST '$BASE/api/demo/reset' >/dev/null && curl -fsS '$BASE/api/twins/KBC-HERO-A' | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d[\"life_phase\"][\"value\"]==\"student\" and d[\"corrections\"]==[]'"

echo "------------------------------------------------------------"
printf '  %d passed, %d failed\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

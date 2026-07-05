#!/usr/bin/env bash
# Runs `kyverno apply` against a pass.yaml and fail.yaml fixture for every
# policy in policy/, and asserts the exit code kyverno reports (0 = all
# rules passed, 1 = at least one rule failed). One passing manifest and one
# violating manifest per policy, per Project.md's Phase 4 spec.
set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(dirname "$script_dir")"
failures=0

for dir in "$script_dir"/*/; do
  name="$(basename "$dir")"
  policy="$repo_root/policy/$name.yaml"

  if [[ ! -f "$policy" ]]; then
    echo "SKIP $name: no matching policy at policy/$name.yaml"
    continue
  fi

  echo "=== $name ==="

  kyverno apply "$policy" --resource "$dir/pass.yaml" > /tmp/kyverno-pass.log 2>&1
  pass_exit=$?
  if [[ $pass_exit -eq 0 ]]; then
    echo "  pass.yaml: OK (allowed, as expected)"
  else
    echo "  pass.yaml: FAILED (expected allow, got deny) exit=$pass_exit"
    cat /tmp/kyverno-pass.log
    failures=$((failures + 1))
  fi

  kyverno apply "$policy" --resource "$dir/fail.yaml" > /tmp/kyverno-fail.log 2>&1
  fail_exit=$?
  if [[ $fail_exit -ne 0 ]]; then
    echo "  fail.yaml: OK (denied, as expected)"
  else
    echo "  fail.yaml: FAILED (expected deny, got allow) exit=$fail_exit"
    cat /tmp/kyverno-fail.log
    failures=$((failures + 1))
  fi
done

echo
if [[ $failures -eq 0 ]]; then
  echo "All policy tests passed."
  exit 0
else
  echo "$failures policy test(s) failed."
  exit 1
fi

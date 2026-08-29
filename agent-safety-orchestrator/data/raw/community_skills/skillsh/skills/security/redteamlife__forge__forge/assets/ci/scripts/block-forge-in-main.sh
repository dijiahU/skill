#!/bin/bash
# FORGE governance check
# Ensures docs/forge is never merged into main

set -e

BASE_BRANCH="${GITHUB_BASE_REF}"

# Only enforce when target branch is main
if [ "$BASE_BRANCH" != "main" ]; then
  exit 0
fi

echo "FORGE: Checking that docs/forge is not introduced into main..."

CHANGED_FILES=$(git diff --name-only origin/$BASE_BRANCH...HEAD | grep "^docs/forge/" || true)

if [ -n "$CHANGED_FILES" ]; then
  echo ""
  echo "FORGE: Governance violation detected."
  echo ""
  echo "docs/forge cannot be merged into main."
  echo ""
  echo "Detected files:"
  echo "$CHANGED_FILES"
  echo ""
  echo "This directory contains AI governance artifacts"
  echo "that must remain in development branches."
  echo ""
  echo "Resolution:"
  echo "  Remove docs/forge from the PR or retarget the merge."
  echo ""
  exit 1
fi

echo "FORGE: Governance check passed."
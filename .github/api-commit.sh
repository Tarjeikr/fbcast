#!/usr/bin/env bash
# Commit files through the GitHub Contents API with the workflow token. Commits made this way are signed by GitHub
# ("Verified" badge), so the content and the server-side timestamp cannot be altered afterwards without breaking the
# signature. Usage: api-commit.sh "<message>" file1 file2 ...
set -euo pipefail
msg="$1"; shift
repo="${GITHUB_REPOSITORY}"
for f in "$@"; do
  [ -f "$f" ] || continue
  sha=$(gh api "repos/$repo/contents/$f?ref=${GITHUB_REF_NAME:-main}" -q .sha 2>/dev/null || true)
  content=$(base64 -w0 "$f")
  if [ -n "$sha" ]; then
    gh api -X PUT "repos/$repo/contents/$f" -f message="$msg: $f" -f content="$content" -f sha="$sha" -f branch="${GITHUB_REF_NAME:-main}" > /dev/null
  else
    gh api -X PUT "repos/$repo/contents/$f" -f message="$msg: $f" -f content="$content" -f branch="${GITHUB_REF_NAME:-main}" > /dev/null
  fi
  echo "committed $f"
done

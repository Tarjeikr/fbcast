#!/usr/bin/env bash
# Commit files through the GitHub Contents API with the workflow token. Commits made this way are signed by GitHub
# ("Verified" badge), so the content and the server-side timestamp cannot be altered afterwards without breaking the
# signature. Usage: api-commit.sh "<message>" file1 file2 ...
# The request body is built in a file and sent with --input, so a file of several megabytes (the model bundle) does not
# hit the length limit of a command-line argument. Each file is tried three times; a retry re-reads the current blob SHA.
set -euo pipefail
msg="$1"; shift
repo="${GITHUB_REPOSITORY}"
branch="${GITHUB_REF_NAME:-main}"
tmp=$(mktemp -d)
for f in "$@"; do
  [ -f "$f" ] || continue
  base64 -w0 "$f" > "$tmp/content.b64"
  ok=0
  for attempt in 1 2 3; do
    sha=$(gh api "repos/$repo/contents/$f?ref=$branch" -q .sha 2>/dev/null || true)
    jq -n --arg message "$msg: $f" --arg branch "$branch" --arg sha "$sha" --rawfile content "$tmp/content.b64" \
      '{message: $message, branch: $branch, content: $content} + (if $sha == "" then {} else {sha: $sha} end)' > "$tmp/body.json"
    if gh api -X PUT "repos/$repo/contents/$f" --input "$tmp/body.json" > /dev/null; then ok=1; break; fi
    sleep $((attempt * 5))
  done
  if [ "$ok" = 1 ]; then echo "committed $f"; else echo "FAILED to commit $f" >&2; exit 1; fi
done
rm -rf "$tmp"

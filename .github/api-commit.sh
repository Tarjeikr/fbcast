#!/usr/bin/env bash
# Commit files through the GitHub Contents API with the workflow token. Commits made this way are signed by GitHub
# ("Verified" badge), so the content and the server-side timestamp cannot be altered afterwards without breaking the
# signature. Usage: api-commit.sh "<message>" file1 file2 ...
# The request body is built in a file and sent with --input, so a file of several megabytes (the model bundle) does not
# hit the length limit of a command-line argument. Each file is tried three times; a retry re-reads the current blob SHA.
#
# With CREATE_ONLY=1 a file that is already on the branch is never replaced: the script stops with exit code 3 and commits
# nothing further. The forecast workflow uses it, so that a forecast, once issued, cannot be overwritten by a second run.
set -euo pipefail
msg="$1"; shift
repo="${GITHUB_REPOSITORY}"
branch="${GITHUB_REF_NAME:-main}"
create_only="${CREATE_ONLY:-0}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# The blob SHA of a file on the branch, or nothing if the file is not there. `gh api` prints GitHub's answer on standard output
# also when the answer is an error ({"message":"Not Found",...}, exit status 1), so output alone proves nothing: the file is
# there only if gh succeeded AND the answer is a 40-character SHA. (From 21 to 24 Nov 2026 any output counted as "there": with
# CREATE_ONLY every new forecast was taken for one already issued and thrown away, three days running.)
on_branch() {
  local out
  if out=$(gh api "repos/$repo/contents/$1?ref=$branch" -q .sha 2>/dev/null) && [[ "$out" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' "$out"
  fi
}
for f in "$@"; do
  [ -f "$f" ] || continue
  if [ "$create_only" = 1 ] && [ -n "$(on_branch "$f")" ]; then
    echo "$f is already on $branch: not replaced, and nothing further committed"
    exit 3
  fi
  base64 -w0 "$f" > "$tmp/content.b64"
  ok=0
  for attempt in 1 2 3; do
    sha=""
    if [ "$create_only" != 1 ]; then sha=$(on_branch "$f"); fi
    jq -n --arg message "$msg: $f" --arg branch "$branch" --arg sha "$sha" --rawfile content "$tmp/content.b64" \
      '{message: $message, branch: $branch, content: $content} + (if $sha == "" then {} else {sha: $sha} end)' > "$tmp/body.json"
    if gh api -X PUT "repos/$repo/contents/$f" --input "$tmp/body.json" > /dev/null; then ok=1; break; fi
    if [ "$create_only" = 1 ] && [ -n "$(on_branch "$f")" ]; then   # another run created it in the meantime
      echo "$f is already on $branch: not replaced, and nothing further committed"
      exit 3
    fi
    sleep $((attempt * 5))
  done
  if [ "$ok" = 1 ]; then echo "committed $f"; else echo "FAILED to commit $f" >&2; exit 1; fi
done

#!/usr/bin/env bash
#
# collect.sh — Gather a deterministic "context pack" for a PR / branch diff.
#
# This script does NO LLM work. It shells out to git (and optionally `gh` and
# `jq`) to produce a single, self-describing Markdown document on stdout that
# any agent or LLM can read to write a PR recap. Keeping the data-gathering
# here (deterministic, tool-agnostic) is what makes the skill portable across
# Claude Code, Opencode, and CI.
#
# Usage:
#   collect.sh [--pr <number>] [--base <ref>] [--head <ref>]
#              [--max-diff-lines <n>] [--no-diff]
#
# Options:
#   --pr <number>       Look up an open PR by number via `gh` (fills in title,
#                       body, base branch). Without it, the script infers the
#                       PR for the current branch if `gh` is available.
#   --base <ref>        Base ref to diff against. Overrides auto-detection.
#   --head <ref>        Head ref (default: HEAD).
#   --max-diff-lines n  Truncate the raw unified diff to this many lines
#                       (default: 1500). The full per-file numstat is always
#                       included, so nothing is silently dropped.
#   --no-diff           Omit the raw unified diff entirely (stats + commits only).
#
# Exit codes: 0 ok, 1 usage/precondition error.

set -euo pipefail

# ---- defaults ---------------------------------------------------------------
PR_NUMBER=""
BASE_REF=""
HEAD_REF="HEAD"
MAX_DIFF_LINES=1500
INCLUDE_DIFF=1
PR_EXPLICIT=0      # did the user pass --pr <n>?
HEAD_EXPLICIT=0    # did the user pass --head <ref>?

# ---- arg parsing ------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --pr)             PR_NUMBER="${2:-}"; PR_EXPLICIT=1; shift 2 ;;
    --base)           BASE_REF="${2:-}"; shift 2 ;;
    --head)           HEAD_REF="${2:-}"; HEAD_EXPLICIT=1; shift 2 ;;
    --max-diff-lines) MAX_DIFF_LINES="${2:-}"; shift 2 ;;
    --no-diff)        INCLUDE_DIFF=0; shift ;;
    -h|--help)        grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "collect.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ---- preconditions ----------------------------------------------------------
command -v git >/dev/null 2>&1 || { echo "collect.sh: git not found" >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "collect.sh: not inside a git work tree" >&2; exit 1; }

HAS_GH=0; command -v gh >/dev/null 2>&1 && HAS_GH=1

# ---- resolve PR metadata (best effort, via gh) ------------------------------
PR_TITLE=""; PR_BODY=""; PR_URL=""; PR_BASE_FROM_GH=""; PR_HEAD_FROM_GH=""
if [ "$HAS_GH" -eq 1 ]; then
  # If no explicit --pr, try to find the PR for the current branch.
  # Build args without tripping `set -u` on an empty array (macOS bash 3.2).
  if PR_JSON=$(gh pr view ${PR_NUMBER:+"$PR_NUMBER"} --json number,title,body,baseRefName,headRefName,url 2>/dev/null); then
    if command -v jq >/dev/null 2>&1; then
      PR_NUMBER=$(printf '%s' "$PR_JSON" | jq -r '.number // empty')
      PR_TITLE=$(printf '%s' "$PR_JSON" | jq -r '.title // empty')
      PR_BODY=$(printf '%s' "$PR_JSON" | jq -r '.body // empty')
      PR_URL=$(printf '%s' "$PR_JSON" | jq -r '.url // empty')
      PR_BASE_FROM_GH=$(printf '%s' "$PR_JSON" | jq -r '.baseRefName // empty')
      PR_HEAD_FROM_GH=$(printf '%s' "$PR_JSON" | jq -r '.headRefName // empty')
    fi
  fi
fi

# ---- resolve head for an explicitly requested PR ----------------------------
# `--pr N` means "recap PR N" — diff N's actual head, NOT whatever branch is
# checked out locally. Fetch the PR head commit (works for same-repo and fork
# PRs via the pull/N/head ref) and diff that. Without this, the script would
# stitch PR N's metadata onto the local branch's diff — a dangerous mismatch.
HEAD_LABEL=""
if [ "$PR_EXPLICIT" -eq 1 ] && [ "$HEAD_EXPLICIT" -eq 0 ] && [ -n "$PR_NUMBER" ]; then
  if [ "$HAS_GH" -ne 1 ]; then
    echo "collect.sh: --pr needs \`gh\` to fetch the PR head; install gh or pass --head <ref>" >&2
    exit 1
  fi
  if git fetch --quiet origin "pull/$PR_NUMBER/head" 2>/dev/null; then
    HEAD_REF=$(git rev-parse FETCH_HEAD)
    HEAD_LABEL="${PR_HEAD_FROM_GH:-pull/$PR_NUMBER/head}"
  else
    echo "collect.sh: could not fetch pull/$PR_NUMBER/head from 'origin'" >&2
    exit 1
  fi
fi

# ---- resolve base ref -------------------------------------------------------
# Priority: explicit --base > gh PR base > origin default branch > dev > main.
if [ -z "$BASE_REF" ]; then
  if [ -n "$PR_BASE_FROM_GH" ]; then
    BASE_REF="$PR_BASE_FROM_GH"
  elif DEF=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null); then
    BASE_REF="${DEF#origin/}"
  elif git rev-parse --verify --quiet dev >/dev/null 2>&1; then
    BASE_REF="dev"
  elif git rev-parse --verify --quiet main >/dev/null 2>&1; then
    BASE_REF="main"
  else
    echo "collect.sh: could not determine a base ref; pass --base <ref>" >&2
    exit 1
  fi
fi

# Prefer the remote-tracking base if it exists (more accurate merge-base).
if git rev-parse --verify --quiet "origin/$BASE_REF" >/dev/null 2>&1; then
  BASE_RESOLVED="origin/$BASE_REF"
elif git rev-parse --verify --quiet "$BASE_REF" >/dev/null 2>&1; then
  BASE_RESOLVED="$BASE_REF"
else
  echo "collect.sh: base ref '$BASE_REF' not found" >&2
  exit 1
fi

MERGE_BASE=$(git merge-base "$BASE_RESOLVED" "$HEAD_REF" 2>/dev/null) \
  || { echo "collect.sh: no common ancestor between $BASE_RESOLVED and $HEAD_REF" >&2; exit 1; }

RANGE="$MERGE_BASE..$HEAD_REF"
if [ -n "$HEAD_LABEL" ]; then
  HEAD_BRANCH="$HEAD_LABEL"
else
  HEAD_BRANCH=$(git rev-parse --abbrev-ref "$HEAD_REF" 2>/dev/null || echo "$HEAD_REF")
fi
COMMIT_COUNT=$(git rev-list --count "$RANGE")
FILES_CHANGED=$(git diff --name-only "$RANGE" | wc -l | tr -d ' ')

# ---- emit context pack ------------------------------------------------------
echo "# PR Recap Context Pack"
echo
echo "_Generated by \`collect.sh\` — deterministic data for an agent to write a recap from._"
echo

echo "## Metadata"
echo
[ -n "$PR_NUMBER" ] && echo "- **PR:** #$PR_NUMBER"
[ -n "$PR_TITLE" ]  && echo "- **Title:** $PR_TITLE"
[ -n "$PR_URL" ]    && echo "- **URL:** $PR_URL"
echo "- **Head:** \`$HEAD_BRANCH\` ($(git rev-parse --short "$HEAD_REF"))"
echo "- **Base:** \`$BASE_REF\` (resolved: \`$BASE_RESOLVED\`, merge-base \`$(git rev-parse --short "$MERGE_BASE")\`)"
echo "- **Commits:** $COMMIT_COUNT"
echo "- **Files changed:** $FILES_CHANGED"
echo

if [ -n "$PR_BODY" ]; then
  echo "## Existing PR description"
  echo
  echo '<!-- Author-written; use as intent signal, do not copy verbatim. -->'
  echo '```markdown'
  printf '%s\n' "$PR_BODY"
  echo '```'
  echo
fi

echo "## Commits"
echo
echo '```'
git log --no-merges --pretty=format:'%h %s' "$RANGE"
echo
echo '```'
echo

echo "## Diffstat"
echo
echo '```'
git diff --stat "$RANGE"
echo '```'
echo

echo "## Changed files (numstat: added, deleted, path)"
echo
echo '```'
git diff --numstat "$RANGE"
echo '```'
echo

if [ "$INCLUDE_DIFF" -eq 1 ]; then
  echo "## Unified diff"
  echo
  TOTAL_DIFF_LINES=$(git diff "$RANGE" | wc -l | tr -d ' ')
  if [ "$TOTAL_DIFF_LINES" -gt "$MAX_DIFF_LINES" ]; then
    echo "> ⚠️ Diff is $TOTAL_DIFF_LINES lines; showing the first $MAX_DIFF_LINES."
    echo "> The numstat above lists every changed file. To inspect a truncated"
    echo "> file in full, run: \`git diff $RANGE -- <path>\`"
    echo
  fi
  echo '```diff'
  git diff "$RANGE" | head -n "$MAX_DIFF_LINES"
  echo '```'
  echo
fi

echo "---"
echo "_End of context pack. Range: \`$RANGE\`_"

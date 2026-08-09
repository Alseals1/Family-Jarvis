# pr-recap

Generate a **concise text recap**, a **review risk assessment**, and a **Mermaid visual
recap** of the changes in a pull request or branch. Built to be portable — the
data-gathering is a plain script, and any LLM/agent writes the recap from its output.

```
.claude/skills/pr-recap/
├── SKILL.md      # agent instructions (Agent Skills open format)
├── collect.sh    # deterministic context-pack generator (git + optional gh/jq)
└── README.md     # this file
```

## Local usage

### With Claude Code

The skill auto-triggers on requests like "recap this PR" / "summarize what changed on
this branch". Or invoke it explicitly: `/pr-recap`.

### With any agent (Opencode, etc.) or by hand

The whole point of the split is that `collect.sh` needs no particular model. Run it and
feed the output to whatever agent you're using, then have it follow steps 2–5 of
`SKILL.md`:

```bash
# from the repo root
.claude/skills/pr-recap/collect.sh                 # current branch vs. its base
.claude/skills/pr-recap/collect.sh --pr 19         # a specific PR
.claude/skills/pr-recap/collect.sh --base main     # explicit base
.claude/skills/pr-recap/collect.sh --no-diff       # stats + commits only (huge PRs)
```

For agents that read `AGENTS.md` (Opencode and friends), there's a pointer to this
skill there, so "recap this PR" routes here.

### Requirements

- `git` (required)
- `gh` (optional) — auto-fills PR number, title, body, and base branch
- `jq` (optional) — needed to parse the `gh` JSON; without it the script still works
  from git alone

## What `collect.sh` outputs

A single Markdown "context pack" on stdout: metadata, the author's PR description (if
any), the commit list, a diffstat, per-file numstat, and a (truncatable) unified diff.
The numstat always lists every changed file, so nothing is silently dropped even when
the raw diff is truncated.

## Follow-up: post recaps from a GitHub Action (not enabled)

The script is CI-ready — it accepts `--pr` and needs only `git` + `gh` (both present on
GitHub runners). To wire this up later, a workflow would: run `collect.sh --pr <n>`,
send the pack to an LLM of your choice, and post the result as a **sticky** PR comment
(update-in-place rather than a new comment each push). Sketch:

```yaml
# .github/workflows/pr-recap.yaml  (illustrative — not committed)
name: PR Recap
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write        # to post the comment
jobs:
  recap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }        # full history for merge-base
      - name: Build context pack
        env: { GH_TOKEN: ${{ github.token }} }
        run: .claude/skills/pr-recap/collect.sh --pr ${{ github.event.number }} > pack.md
      - name: Generate recap
        # Call your LLM provider with pack.md + the SKILL.md instructions,
        # writing the result (text recap + ```mermaid block) to recap.md.
        run: echo "TODO: provider-specific step; writes recap.md"
      - name: Post sticky comment
        env: { GH_TOKEN: ${{ github.token }} }
        run: |
          gh pr comment ${{ github.event.number }} \
            --edit-last --create-if-none --body-file recap.md
```

Notes for whoever enables it:

- Keep the LLM step provider-agnostic (an API key in secrets) so it matches the
  "works across multiple LLMs" goal.
- `gh pr comment --edit-last --create-if-none` gives a sticky comment with modern `gh`.
- Mermaid renders natively in GitHub comments — no image generation needed.
- Mind cost/noise on very large PRs: use `--no-diff` and rely on stats + commits.

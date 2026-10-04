# AGENTS.md

Instructions for any AI coding agent (Codex, Claude Code, Cursor, Copilot, Gemini CLI, Aider, ...) working with this repository.
The same content, in skill form with more detail, is in [SKILL.md](SKILL.md).

## What this is

`github-solo` audits a GitHub repository and safely configures what is missing for a **solo developer**: free features only, and it
never adds settings that stop you from merging your own PRs (required approvals, required CODEOWNERS review, `enforce_admins`).
One stdlib-only Python 3.9+ file: `scripts/solo.py`. An MCP server wrapper is `scripts/solo_mcp.py`.

## To use it on a user's repo

1. Find out where you are running; do not assume. `python3 scripts/solo.py doctor [OWNER/REPO]` prints the environment, the token source
   (never the token), API reachability and which admin endpoints the token can read. In a sandbox whose proxy refuses settings writes
   (`not permitted through this proxy`), do not work around it. Say plainly what this session is (a cloud / app session, not the user's PC) and name the exact place to run the commands: the terminal on their PC, or Claude Code running on their PC. Never just say "locally" or "on your machine"; see SKILL.md, "Telling the user where to run it".
2. `python3 scripts/solo.py audit OWNER/REPO` (exit 1 = at least one ❌). Summarise for the user in their language, ❌ first.
3. `python3 scripts/solo.py apply OWNER/REPO` is a dry run: show the plan. Run it with `--yes` only after the user agrees.
   Opt-in items (`pages`, `discussions`, `topics`, `workflow-permissions`, `tag-guard`, `labels`, `community-files`) need `--only <id>`
   and a separate OK each. Never "fix" a ❌ yourself: show the printed commands and let the user decide.
4. Generated files (`.github/dependabot.yml`, `.github/release.yml`, `SECURITY.md`, ...) are written locally only, inside a clone. Before you
   commit or push, check the `release-workflow` row of the audit: a push to the default branch may start a release workflow, so ask first.
5. `python3 scripts/solo.py restore OWNER/REPO --yes` reverts the last `apply --yes`. Audit again and report what changed.
6. On any 403/404/422, "could not read" row, or plan/limit question: read the official page (URLs in SKILL.md) and cite it; never answer from memory.

As MCP tools (any MCP client): `python3 scripts/solo_mcp.py` (stdio). `solo_apply` and `solo_restore` are dry runs unless `confirm` is true.

## To work on this repository

- Tests (no network, a mock GitHub API server runs in-process): `python -m unittest`. Must pass on Python 3.9 and 3.13.
- `tests/live_check.py` runs every write against a real scratch repo (not part of the unit tests; needs a real token).
- Standard library only. Keep messages English in the code (`--lang ja` translates fixed phrases in `JA` in `solo.py`); JSON output is never translated.
- Never make `apply` delete or overwrite anything that exists; opt-in anything that changes the public face of a repo or can break workflows.
- Conventional Commits (`feat:`, `fix:`, `docs:`); release-please cuts releases and never bumps the major version automatically.

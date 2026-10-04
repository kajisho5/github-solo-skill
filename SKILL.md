---
name: github-solo
description: >-
  Audit and safely configure a GitHub repository for a SOLO developer (free features only, no settings that stop you from merging your own PRs). ALWAYS use this skill when the user asks about GitHub repo settings, repository hardening, "is my repo set up properly", security settings, Dependabot (alerts, security updates, dependabot.yml), CodeQL / code scanning, secret scanning / push protection, SECURITY.md, branch protection / rulesets / "protect main", GitHub Pages, Discussions, topics / description / social preview, release notes config, a fixed "latest release" download link (/releases/latest/download/...), "latest release is 404" / only pre-releases, or when the user says their own PR cannot be merged / "approval required" / "I can't merge my PR" / "branch protection locked me out". Also trigger on Japanese: GitHub設定, リポジトリ設定, セキュリティ設定, 診断, 自動設定, Dependabot, CodeQL, ブランチ保護, ルールセット, Pages公開, Discussions, 最新版リンク, 固定ダウンロードURL, 最新リリース, プレリリース, 自分のPRがマージできない, 承認が必要でマージできない, 1人開発, 個人開発, 個人リポ, リポジトリを整えて. Runs `scripts/solo.py` (audit / apply / links / dependabot); dry-run by default, idempotent, never deletes or overwrites.
---

# github-solo: GitHub settings for solo developers

One Python file (`scripts/solo.py`, stdlib only, Python 3.9+) that diagnoses a repo and applies only
what is missing. Its defining rule: **it never adds a setting that makes a one-person repo
unmergeable** (required approvals, required CODEOWNERS review, `enforce_admins`). It detects existing
settings like that as ❌ and shows how to remove them, but never removes them itself.

Where is the script? In the directory this SKILL.md was loaded from: `<skill dir>/scripts/solo.py`
(`~/.claude/skills/github-solo/scripts/solo.py` for a user install, `${CLAUDE_PLUGIN_ROOT}/scripts/solo.py`
for the plugin). Below, `SOLO` stands for `python3 <skill dir>/scripts/solo.py`.

## Works with any agent

This file follows the Agent Skills layout (`SKILL.md` + `scripts/` + `references/`), which Claude Code, Codex and Cursor can load from
their skills directories (see the README for the paths). Agents without skills support can read `AGENTS.md`, or call the same commands
as MCP tools: `python3 scripts/solo_mcp.py` (stdio; `solo_apply` / `solo_restore` are dry runs unless `confirm` is true).
Everything below applies to every agent; only the way you detect the environment differs.

## Step 0: find out where you are running (never assume)

Advice depends on it: a cloud container can read GitHub but its network proxy may refuse settings writes,
while Claude Code running on the user's PC can run `apply --yes` directly. Determine it from facts:

1. Run `SOLO doctor` and read the `environment` row (or check the variables yourself:
   `CLAUDE_CODE_REMOTE=true` / `CCR_AGENT_PROXY_ENABLED` → managed cloud container;
   `CLAUDECODE=1` without those → Claude Code running on this PC; neither → another agent, plain shell or CI: then
   judge by facts (`doctor` shows whether the API is reachable and which admin endpoints answer 403 "not permitted through this proxy").
   `CLAUDE_CODE_ENTRYPOINT` shows how the session was started (observed values: `remote_mobile` in a cloud session started
   from the app, `cli` in Claude Code running on a user's PC); report the raw value and do not guess what an unfamiliar value means: say it is unknown.
2. Tell the user in one line what you detected ("This is a cloud Claude Code session, not your computer").
3. Then tailor:
   - **Cloud container:** audits (reads) usually work; settings writes may fail with 403 "not permitted through this
     proxy". Do not retry or route around it. Read the environment's documentation (the `read_documentation` tool in
     Claude Code cloud sessions) before explaining, then hand the user the commands as described in "Telling the user where to run it" below.
   - **Claude Code on the user's machine / plain shell:** run the workflow below directly.
   - **Unknown:** ask the user where they want the changes to run.
4. Repos outside the session's allowed set are not reachable by API from a cloud session even for reads; say so
   instead of guessing the repo's state.

## Telling the user where to run it (never say just "locally" or "on your machine")

Users often cannot tell an app / cloud session from Claude Code on their own PC, so a vague "run it on your machine" leaves them lost. Always:

1. **Say what this session is**, from the facts you detected, in one sentence: for example "This is a cloud session started from the Claude app. It is not
   your PC." / "This is Claude Code running on your PC (CLI)." If you could not tell, say that and ask which one they use.
2. **Name the exact place to run the commands**, and contrast it with this session. Use wording like:
   - "in the terminal on your PC (PowerShell on Windows, Terminal on macOS)"
   - "in Claude Code that you run on your PC (the CLI), not in this app session"
   - "in the Codex app on your PC" (when that is the surface), naming the screen or menu when you know it, and saying "I could not verify this screen" when you do not.
   Avoid the bare phrases "locally", "on your machine", "手元で". In Japanese say for example 「あなたのPCのターミナル（PowerShell）で」「PCで起動した Claude Code（CLI）で。このアプリのセッションではありません」.
3. **Give one copy-paste block addressed to that place** (what to paste, where), not scattered commands. Put secrets-handling steps (login, token) as separate lines the
   user does themselves, and never ask for the token in chat.
4. **Say what you need back** (for example "paste the table that ends with `RESULT:`").
5. On Windows mention the shell: `python` instead of `python3`, and Git Bash needs API paths without the leading slash.

## Workflow (follow in order)

1. **Identify the repo.** Use the `OWNER/REPO` the user gave. Otherwise the current directory's
   `git remote origin` is used automatically (omit the argument). For "all my repos" use
   `SOLO audit --all-repos OWNER`. If neither exists, ask once.
   Token: `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token`. No token → tell the user to run
   `gh auth login` (or set `GH_TOKEN`); do not ask them to paste a token into chat.
2. **If anything fails or the token is new, run `SOLO doctor OWNER/REPO` first**: it shows which token is used,
   whether the API is reachable and which admin endpoints the token can read.
3. **Audit.** `SOLO audit OWNER/REPO` (add `--json` if you need to parse it). Exit code 1 means there is
   at least one ❌.
4. **Summarize in the user's language, ❌ first.** For each ❌ give the one-line reason and the fix
   commands the audit printed. Then ⚠️ (recommended) grouped by category, then ➖ (not applicable,
   with its reason, e.g. "private repo needs a paid plan"). Do not recite the whole table.
5. **Apply.**
   - Run `SOLO apply OWNER/REPO` (dry run) and show the user the plan.
   - Default items are invisible to visitors and instantly reversible. Run `SOLO apply OWNER/REPO --yes`
     after showing the plan (the user's request to "set it up / fix it" is the go-ahead; if they only
     asked for a diagnosis, ask first).
   - **Opt-in items are applied only with `--only` and only after asking about each one**, because
     they change the public face or can break workflows: `pages`, `discussions`, `topics`
     (`--topics a,b`), `workflow-permissions`, `tag-guard`, `labels`, `community-files`, `actions-can-create-prs`. Example:
     `SOLO apply OWNER/REPO --yes --only pages --pages-path /docs`.
   - Never try to fix a ❌ yourself with extra API calls. Explain it, show the printed commands, and
     let the user decide. (Removing an approval rule is the user's call.)
6. **Generated files** (`.github/dependabot.yml`, `.github/release.yml`, `SECURITY.md`):
   - In a clone of the repo they are written locally only. Review them, then commit and push.
   - **Before committing/pushing, check the `release-workflow` row of the audit.** If it is ⚠️, a
     push to the default branch can start a release workflow (it may publish a real release or
     tag). Tell the user, and get an explicit OK before you commit or push. Prefer a branch + PR
     when they want to avoid it.
   - Not in a clone: `--commit-files` commits through the Contents API straight to the default
     branch. It refuses when a release workflow may fire unless `--accept-release-risk` is also
     given; only add that flag after the user agreed.
   - Existing files are never overwritten. If `dependabot.yml` exists, `apply` prints the missing
     entries as a proposal; merge them by hand.
7. **Re-audit** (`SOLO audit OWNER/REPO`) and report what changed: before/after counts and anything
   that remains (opt-in items the user declined, ➖, license, social preview, which cannot be done via API).

## Other subcommands

- `SOLO audit --profile app|library|site|docs` hides checks that do not fit the kind of repo; ask the user what the repo is.
  Audits print a 0-100 score. `SOLO ci-template` prints a weekly audit workflow. GHES: `SOLO_API_BASE=https://HOST/api/v3`.
- `SOLO explain CHECK_ID`: prints why/API/undo of one check (offline). `SOLO badges OWNER/REPO`: README badge Markdown.
  `audit --quiet --ignore a,b --fail-on warn` for CI. `SOLO links --workflow`: release workflow template (version-less assets).
- `SOLO restore OWNER/REPO` (dry run) / `--yes`: reverts what the last `apply --yes` changed, using the snapshot it saved.
  Offer it whenever the user regrets a change. It does not delete generated files.

- `--lang ja` makes the text output Japanese (`--json` stays English); `audit --github-annotations` adds CI annotations;
  `apply --json` prints the plan and the execution log; `links --markdown` prints ready-to-paste list items.
- `SOLO links OWNER/REPO`: fixed download URLs `https://github.com/O/R/releases/latest/download/<asset>`.
  If it says all releases are pre-releases (`/latest` ignores pre-releases → 404) or asset names contain
  the version (URL would change every release), relay the printed fix and see
  `references/release-latest.md` (workflow example that uploads a version-less copy).
- `SOLO dependabot OWNER/REPO`: prints a generated `dependabot.yml` (monthly, one grouped PR per
  ecosystem) to stdout; nothing is written.

## What the checks are

Full list with API, reason and how to undo each: `references/checks.md`. Summary:

| Category | check id (apply id) | default apply? |
|---|---|---|
| Security | `dependabot-alerts`, `dependabot-security-updates` | yes |
| | `secret-scanning`, `push-protection`, `private-vuln-reporting`, `codeql` (public repos only) | yes |
| | `dependabot-config` (generates `.github/dependabot.yml`) | yes |
| | `actions-pinning`, `actions-hardening`, `open-alerts` (report only) | n/a |
| | `actions-can-create-prs` (let Actions open / approve PRs; release-please needs it) | **opt-in** |
| | `workflow-permissions` (default GITHUB_TOKEN = read) | **opt-in** |
| Solo | `solo-blocker` (❌ detect only) | never |
| | `guardrail` (ruleset `solo-guard`: no delete / force-push of the default branch) | yes |
| | `tag-guard` (ruleset `solo-tag-guard`: no deleting / force-moving `v*` tags) | **opt-in** |
| | `delete-branch-on-merge` | yes |
| | `discussions` | **opt-in** |
| Distribution | `pages` | **opt-in** |
| | `releases`, `release-workflow`, `release-tag-format`, `ci-status` (report only) | n/a |
| | `release-notes-config` (`.github/release.yml`) | yes |
| Metadata | `security-policy` (`SECURITY.md`) | yes |
| | `topics` | **opt-in** (`--topics`) |
| | `labels` (create the labels `release.yml` uses), `community-files` (issue / PR templates, CONTRIBUTING) | **opt-in** |
| | `description`, `license`, `social-preview`, `issues-enabled` (report only; license is the user's decision, social preview has no API) | n/a |

Private repos: GitHub Secret Protection / Code Security are paid, so those rows show ➖ with the reason
and are skipped. Dependabot alerts / security updates are free on private repos and still apply.

## Rules for you

- Never run `apply --yes` on a repo the user did not name or that you inferred from a stray remote
  without saying which repo you are about to change.
- Dry run first, always. `apply` is idempotent: a second run changes nothing.
- Do not add approval/CODEOWNERS/enforce_admins protections "to be safe". That is exactly the
  failure this skill exists to prevent.
- Do not delete or loosen existing protections. The `solo-guard` ruleset can be lifted temporarily:
  `gh api -X PUT repos/O/R/rulesets/<id> -f enforcement=disabled` (re-enable with `active`).
- If a request returns 403/404, read `references/troubleshooting.md` (scopes, admin rights, plan
  limits) instead of retrying blindly. In sandboxes that block admin API paths the audit shows
  "could not read"; say so instead of guessing the state.
- **When blocked or unsure, read the official page (URL below) and cite it. Never answer from memory.**
  This covers: any 403/404/422 from an API call, "could not read" rows, plan/price/limit questions, token
  permissions, and a sandbox/proxy refusing a call (also read the environment's own documentation, e.g. the
  `read_documentation` tool in Claude Code cloud sessions). Fetch the page (WebFetch / browser), say which
  URL you used, and tell the user the concrete next step. If the page does not answer it, say "not confirmed".

## Official docs to read (use these URLs)

| Topic | URL |
|---|---|
| Repo settings API (alerts, security fixes, private vuln reporting, PATCH repo) | https://docs.github.com/en/rest/repos/repos |
| Code scanning default setup | https://docs.github.com/en/rest/code-scanning/code-scanning |
| Rulesets / rules for a branch | https://docs.github.com/en/rest/repos/rules |
| Classic branch protection | https://docs.github.com/en/rest/branches/branch-protection |
| Pages API | https://docs.github.com/en/rest/pages/pages |
| Actions workflow permissions | https://docs.github.com/en/rest/actions/permissions |
| Releases API (`/releases/latest`) | https://docs.github.com/en/rest/releases/releases |
| Token permissions per endpoint | https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens |
| Dependabot options / ecosystems | https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference |
| Auto-generated release notes (`release.yml`) | https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes |
| Plans and which features are free | https://docs.github.com/en/get-started/learning-about-github/githubs-plans |

## References

- `references/checks.md`: every check: why, API, what apply does, how to revert.
- `references/release-latest.md`: version-less asset names, pre-release handling, workflow examples.
- `references/troubleshooting.md`: 403 errors, token scopes, private repo paid features.

<p align="center"><strong>github-solo</strong></p>

<h1 align="center">github-solo-skill</h1>

<p align="center"><strong>Give your coding agent a GitHub settings checkup, made for one-person repos.</strong></p>

<p align="center">
  Audit · Safe auto-setup · Free features only · Python standard library<br>
  Claude Code · Codex · Cursor · Copilot · any agent that reads <code>SKILL.md</code> / <code>AGENTS.md</code>, or speaks MCP
</p>

<p align="center">
  <a href="https://github.com/kajisho5/github-solo-skill/actions/workflows/test.yml"><img src="https://github.com/kajisho5/github-solo-skill/actions/workflows/test.yml/badge.svg" alt="tests"></a>
  <a href="https://github.com/kajisho5/github-solo-skill/stargazers"><img src="https://img.shields.io/github/stars/kajisho5/github-solo-skill" alt="GitHub stars"></a>
  <a href="https://github.com/kajisho5/github-solo-skill/commits/main"><img src="https://img.shields.io/github/last-commit/kajisho5/github-solo-skill" alt="last commit"></a>
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.13-blue" alt="Python 3.9 and 3.13 tested">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"></a>
  <a href="https://github.com/sponsors/kajisho5"><img src="https://img.shields.io/badge/sponsor-%E2%9D%A4-ea4aaa?logo=githubsponsors" alt="Sponsor"></a>
</p>

```bash
npx skills add kajisho5/github-solo-skill
```

English · [日本語](README.ja.md)

Tell your agent *"check my repo settings"* (or run the script yourself). It audits the repo and fixes only what is missing:

```text
github-solo audit: you/your-app (public, default branch: main)

Security
  ⚠️  dependabot-alerts            disabled  -> apply: dependabot-alerts
  ⚠️  dependabot-security-updates  disabled  -> apply: dependabot-security-updates
  ✅ secret-scanning              enabled
  ✅ push-protection              enabled
  ⚠️  private-vuln-reporting       disabled  -> apply: private-vuln-reporting
  ⚠️  codeql                       default setup not configured (c-cpp)  -> apply: codeql
  ⚠️  dependabot-config            missing; detected: github-actions  -> apply: dependabot-config
       bundled code under third_party/ is not tracked by Dependabot (it only reads real manifests outside those dirs)
  ✅ actions-pinning              all actions pinned to a commit SHA
  ⚠️  workflow-permissions         default GITHUB_TOKEN permission is write (opt-in fix; may break workflows that rely on it)  -> apply: workflow-permissions

Solo development
  ✅ solo-blocker                 no approval-required rule on main
  ⚠️  guardrail                    main can be deleted / force-pushed  -> apply: guardrail
  ⚠️  tag-guard                    release tags (v*) can be deleted / force-moved (opt-in: --only tag-guard)  -> apply: tag-guard
  ⚠️  delete-branch-on-merge       merged branches are kept  -> apply: delete-branch-on-merge
  ⚠️  discussions                  disabled (opt-in: --only discussions)  -> apply: discussions

Distribution
  ⚠️  release-workflow             a push to main will likely create a release (.github/workflows/release.yml) - committing files there can trigger it
       .github/workflows/release.yml (gh release create)
  ⚠️  pages                        not set up; would publish / of main (no index.html: the README is rendered as the top page) (opt-in: --only pages)  -> apply: pages
  ⚠️  releases                     2 release(s), all pre-releases: /releases/latest returns 404 (see: solo.py links)
  ⚠️  release-notes-config         .github/release.yml missing  -> apply: release-notes-config

Metadata
  ✅ description                  set
  ✅ topics                       topics: audio
  ✅ license                      MIT
  ✅ security-policy              SECURITY.md
  ✅ social-preview               custom social preview image set
  ⚠️  labels                       missing labels: breaking-change (opt-in: --only labels)  -> apply: labels
  ⚠️  community-files              missing: .github/pull_request_template.md, .github/ISSUE_TEMPLATE/bug_report.md, .github/ISSUE_TEMPLATE/feature_request.md, CONTRIBUTING.md (opt-in: --only community-files)  -> apply: community-files

Summary: 9 ok, 16 recommended, 0 action needed, 0 n/a   Score: 68/100
Next: solo.py apply you/your-app   (dry run; add --yes to execute)
```

*(Real output of `solo.py audit` against this project's test fixture of a public C++ app. `apply` shows its plan first and only writes with `--yes`.)*

## How this differs from team-oriented GitHub skills

Skills written for teams (for example `netresearch/github-project-skill`) turn on branch protection that **requires an approving review**
(and often CODEOWNERS review, `enforce_admins`). With one maintainer nobody can approve, so **you can no longer merge your own PRs**.

`github-solo` is built around the opposite rule:

| | Team-oriented skills | github-solo |
|---|---|---|
| Required approvals / CODEOWNERS review / `enforce_admins` | added | **never added**. If it already exists on a repo with a single committer it is flagged ❌ with the commands to remove it (never changed automatically) |
| Protection of the default branch | PR-only | ruleset `solo-guard`: no deletion, no force-push. Direct pushes and your own merges keep working |
| Paid features | assumed | free features only. On private repos the paid ones (Secret Protection / Code Security) are shown as ➖ and skipped |
| What `apply` changes by default | everything | only invisible, instantly reversible items. Public-facing items (Pages, Discussions, homepage, topics) and workflow-affecting ones (default `GITHUB_TOKEN` permission) need an explicit `--only` |
| Existing files and settings | may be overwritten | never deleted or overwritten |

## Why

- **Diagnose first.** One command prints every setting as ✅ OK / ⚠️ recommended / ❌ action needed / ➖ not applicable, with the reason and the `apply` id that fixes it. Exit code 1 if there is any ❌ (usable in CI).
- **Dry-run by default, idempotent.** `apply` prints the exact API calls. `--yes` runs them. A second run writes nothing.
- **Distribution built in.** `links` prints a stable `/releases/latest/download/<asset>` URL, or tells you why none can work (only pre-releases, version in the asset name) and how to fix it.
- **Undo.** Every `apply --yes` saves what it changed (`~/.local/state/github-solo/`, `%LOCALAPPDATA%\github-solo` on Windows, `SOLO_STATE_DIR` to override) and `restore` reverts exactly that. Generated files are left for you to delete.
- **No dependencies.** `scripts/solo.py` is a single file on the Python 3.9+ standard library; it talks to the GitHub REST/GraphQL API directly.
- **Tested without the network.** The tests run the real script against a mock GitHub API server (`python -m unittest`).

## Quick start

```bash
# 1. install the skill (see Install for other ways)
npx skills add kajisho5/github-solo-skill

# 2. diagnose (token: GH_TOKEN, GITHUB_TOKEN, or `gh auth login`)
python3 scripts/solo.py audit OWNER/REPO          # --json for machines; exit 1 on ❌

# 3. see what would change, then do it
python3 scripts/solo.py apply OWNER/REPO          # dry run
python3 scripts/solo.py apply OWNER/REPO --yes    # default items only

# 4. opt-in, public-facing items one by one
python3 scripts/solo.py apply OWNER/REPO --yes --only pages --pages-path /docs
python3 scripts/solo.py apply OWNER/REPO --yes --only topics --topics audio,streaming
```

`OWNER/REPO` may be omitted inside a clone: it is read from `git remote origin`.
`--profile app|library|site|docs` hides checks that do not apply to that kind of repo (a website has no release notes; a library does not care about asset names). Every audit prints a 0-100 score (✅ = 1, ⚠️ = ½, ❌ = 0, ➖ excluded). Dry-run plans show each change as `before -> after`. On GitHub Enterprise Server set `SOLO_API_BASE=https://HOST/api/v3` (GraphQL is routed to `/api/graphql`).
`--lang ja` (or `SOLO_LANG=ja`, or a Japanese `$LANG`) translates the text output; `--json` is always English.

| Command | What it does |
|---|---|
| `audit [OWNER/REPO] [--json] [--quiet] [--ignore ids] [--fail-on warn] [--github-annotations]` | diagnose; exit 1 if any ❌ (`--fail-on warn`: also on ⚠️). `--quiet` hides ✅/➖, `--ignore` leaves checks out, `--github-annotations` also prints `::warning`/`::error` lines for CI |
| `audit --all-repos OWNER [--json]` | one summary line per non-archived, non-fork repo of an owner |
| `apply [OWNER/REPO] [--yes] [--only ids] [--skip ids] [--pages-path / \| /docs] [--topics a,b] [--commit-files] [--accept-release-risk] [--json]` | dry-run plan; `--yes` executes; `--json` prints the plan and the execution log |
| `links [OWNER/REPO] [--markdown]` | stable latest-release download URLs (optionally as Markdown list items), or why they cannot work |
| `links --workflow` | print a release workflow template (tag-triggered, uploads version-less asset copies); no API call |
| `badges [OWNER/REPO]` | README badge Markdown: one per workflow, license, latest release, last commit, stars |
| `ci-template` | print a weekly audit GitHub Actions workflow (needs a secret token with Administration: read); no API call |
| `explain CHECK_ID` | print the reference entry of a check (why, API, how to undo); works offline |
| `dependabot [OWNER/REPO]` | print a generated `dependabot.yml` (monthly, one grouped PR per ecosystem) |
| `doctor [OWNER/REPO] [--json]` | detect where it runs (cloud container / Claude Code on your machine / plain shell), check python/git/gh, which token is used (never printed), API reachability, your access to the repo and to each admin endpoint, before anything else goes wrong |
| `restore [OWNER/REPO] [--yes] [--snapshot FILE]` | revert what the last `apply --yes` changed (dry run unless `--yes`) |

Talk to your agent instead:

> "Check the GitHub settings of my repo and set up what's missing."
> "自分のPRがマージできない。ブランチ保護を見て。"
> "最新版の固定ダウンロードリンクを出して。"

## What is checked

Details, APIs and how to revert each one: [references/checks.md](references/checks.md).

| Category | Checks | `apply` |
|---|---|---|
| Security | Dependabot alerts + security updates, secret scanning, push protection, private vulnerability reporting, CodeQL default setup (public repos), `dependabot.yml` (ecosystems auto-detected, bundled `third_party/`/`vendor/` ignored), Actions SHA pinning (report), default `GITHUB_TOKEN` permission (an existing `dependabot.yml` is checked per directory, too) | default (token permission: opt-in) |
| Solo development | **solo-blocker** (❌ detect only), `solo-guard` ruleset, `solo-tag-guard` ruleset for `v*` tags, delete head branch on merge, Discussions | default (tag guard, Discussions: opt-in) |
| Distribution | GitHub Pages (opt-in), releases / latest / asset names (report), release-on-push workflow warning (report), `.github/release.yml` | default (Pages: opt-in) |
| Metadata | description, topics (opt-in), license (never generated), `SECURITY.md`, labels used by `release.yml` (opt-in), issue / PR templates + `CONTRIBUTING.md` (opt-in), social preview (no API: link to the setting) | default (topics, labels, community files: opt-in) |

### Files and the "push may release" warning

`dependabot.yml`, `release.yml` and `SECURITY.md` are generated only if missing:

- **Inside a clone:** written locally; you review and commit them.
- **Not in a clone:** only with `--commit-files` (Contents API, straight to the default branch).
- If a workflow runs on pushes to the default branch **and** looks like it creates releases (`gh release create`, `softprops/action-gh-release`, `release-please`, `contents: write`…), `apply` warns before writing, and `--commit-files` is refused unless you add `--accept-release-risk`. Detection is a text heuristic; see [references/checks.md](references/checks.md#release-workflow-report-only).

## Token permissions

The token comes from `GH_TOKEN`, then `GITHUB_TOKEN`, then `gh auth token`.

- **Classic PAT:** `repo` (for public repos only, `public_repo` covers the code-scanning endpoint; the other admin endpoints are documented against `repo`).
- **Fine-grained PAT**, repository permissions (from the [GitHub docs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)):

| Permission | Level | For |
|---|---|---|
| Metadata | Read | repo info, collaborators |
| Administration | Read and write | Dependabot alerts/updates, private vulnerability reporting, code scanning default setup, rulesets, branch protection (read), Actions workflow permissions, repo settings (`PATCH`: secret scanning, Discussions, delete-branch-on-merge, topics, homepage) |
| Contents | Read (audit) / Read and write (`--commit-files`) | git tree, file contents, committing generated files |
| Pages | Read and write | `--only pages` |

You must be an admin of the repo for most settings. 403/404 and plan limits: [references/troubleshooting.md](references/troubleshooting.md).

## Install

```bash
# Skills CLI (Claude Code, Cursor, Codex, ...)
npx skills add kajisho5/github-solo-skill

# or clone into your agent's skills directory
git clone https://github.com/kajisho5/github-solo-skill ~/.claude/skills/github-solo   # Claude Code
git clone https://github.com/kajisho5/github-solo-skill ~/.cursor/skills/github-solo   # Cursor
git clone https://github.com/kajisho5/github-solo-skill ~/.agents/skills/github-solo   # Codex (Cursor reads this too)
```

### Other AI agents (Codex, Cursor, Copilot, Gemini CLI, ...)

| Agent | How |
|---|---|
| **Codex** | skills: clone into `~/.agents/skills/github-solo` (user) or `<repo>/.agents/skills/github-solo` (repo), per the [Codex skills docs](https://learn.chatgpt.com/docs/build-skills). MCP: `codex mcp add github-solo -- python3 /path/to/github-solo/scripts/solo_mcp.py` or a `[mcp_servers.github-solo]` table (`command`, `args`) in `~/.codex/config.toml` ([docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)). Codex also reads `AGENTS.md`. **Codex desktop app (Windows):** *Settings → MCP servers → Add server → STDIO*, command `python`, argument the full path of `scripts\solo_mcp.py` (the app shares `config.toml` with the CLI, per the docs; the docs do not cover Windows paths specifically, and this was not tried in the app). |
| **Claude Code** | skill (above), plugin (below), or MCP: `claude mcp add github-solo -- python3 /path/to/github-solo/scripts/solo_mcp.py` |
| **Cursor** | skills directory `~/.cursor/skills/github-solo` (path as documented by the sibling project [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill); Cursor reads `~/.agents/skills` too). Not verified against Cursor's own docs. |
| **GitHub Copilot** | reads `AGENTS.md` and `.github/copilot-instructions.md` in this repo ([docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)). |
| **Any other agent** | MCP stdio server `python3 scripts/solo_mcp.py` (tools: `solo_doctor`, `solo_audit`, `solo_apply_plan`, `solo_apply`, `solo_restore`, `solo_links`, `solo_dependabot`, `solo_badges`, `solo_explain`), or just run `python3 scripts/solo.py ...`; point the agent at `AGENTS.md`. |

The MCP server follows the [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) (newline-delimited JSON-RPC, protocol versions 2025-06-18 / 2025-03-26 / 2024-11-05) and was tested with a hand-written client and with Claude Code's own client (`claude mcp list` reports it connected); Codex and Cursor have not been tried. `solo_apply` and `solo_restore` change nothing unless `confirm` is `true`.

As a Claude Code plugin (marketplace hosted in this repo):

```bash
claude plugin marketplace add kajisho5/github-solo-skill
claude plugin install github-solo@github-solo-skill
```

Without any agent: `python3 scripts/solo.py --help`. Update a clone with `git pull`; copies made by other installers are not updated automatically.

## Requirements

- Python 3.9+ (standard library only), `git` (only to infer `OWNER/REPO` and detect a clone), optionally `gh` (only as a token source).
- A GitHub token with the permissions above.

## Development

```bash
python -m unittest           # all tests, no network: a mock GitHub API server runs in-process
python -m unittest tests.test_solo.VoiceboothScenario -v

# against the real API, on a disposable repo you own (changes its settings, then reverts them):
python3 tests/live_check.py YOU/scratch-repo --confirm YOU/scratch-repo
```

Test scenarios (`tests/test_solo.py`, fixtures in `tests/fixtures.py`, server in `tests/mock_github.py`): a public C++ app that releases on push (voicebooth-style), a solo repo locked by a required approval, a private free-plan repo, and a fully configured repo (zero writes). Each asserts the audit verdicts, the dry-run plan, and the exact write requests (method, path, body) the mock received. CI runs on Python 3.9 and 3.13 (`.github/workflows/test.yml`, actions pinned by SHA, `permissions: contents: read`).

**Releasing** is automated with [release-please](https://github.com/googleapis/release-please): merge Conventional Commits (`feat:`, `fix:`, `docs:` …) to `main`, release-please keeps a release PR up to date (version bump in `plugin.json`, `scripts/solo.py`, changelog), and merging that PR tags and publishes the GitHub Release. **A major version is never bumped automatically**: the project stays on 0.x (`bump-minor-pre-major`), so a breaking change (`feat!:`) bumps the minor; 1.0.0 is a deliberate release (`Release-As: 1.0.0` in a commit footer). The release PR needs *Settings → Actions → General → "Allow GitHub Actions to create and approve pull requests"* enabled.

## Docs

| | |
|---|---|
| [SKILL.md](SKILL.md) | what the agent reads: workflow and rules |
| [references/checks.md](references/checks.md) | every check: reason, API, revert |
| [references/release-latest.md](references/release-latest.md) | stable latest-release links, pre-releases, version-less asset names, workflow example |
| [references/troubleshooting.md](references/troubleshooting.md) | 403 errors, scopes, private repo paid features |
| [ROADMAP.md](ROADMAP.md) | what is planned, what is deliberately out of scope |
| [SECURITY.md](SECURITY.md) | reporting a vulnerability |

## Support

If this saves you time, you can help keep it maintained through [GitHub Sponsors](https://github.com/sponsors/kajisho5). Issues and pull requests are welcome.

## License

[MIT](LICENSE)

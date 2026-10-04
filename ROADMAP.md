# Roadmap

Status of `0.x`. Everything under "Done" is covered by `python -m unittest`.

## Done (0.1)

- `audit` (text + `--json`, exit 1 on ❌), `apply` (dry run, `--yes`, `--only`, `--skip`), `links`, `dependabot`.
- 31 checks across Security / Solo development / Distribution / Metadata (see [references/checks.md](references/checks.md)).
- Solo-blocker detection (classic protection and rulesets), `solo-guard` ruleset, release-on-push warning.
- Mock GitHub API test suite, CI on Python 3.9 and 3.13, release-please.
- `--lang ja`, `apply --json`, `audit --all-repos`, `audit --github-annotations`, `links --markdown`.
- Per-directory coverage of an existing `dependabot.yml`; release detection through reusable workflows and `refs/tags` conditions.
- Opt-in `tag-guard` ruleset for `v*` tags.
- `doctor`, and `restore` (every `apply --yes` saves an undo snapshot).
- `AGENTS.md`, `.github/copilot-instructions.md` and an MCP stdio server (`scripts/solo_mcp.py`, 9 tools; apply / restore are dry runs unless `confirm`).
- Gap checks found while releasing this project: `release-tag-format`, release without assets, `actions-can-create-prs`, `ci-status`, `actions-hardening`, `open-alerts`, `issues-enabled`, draft releases and Pages HTTPS notes.
- `--profile`, 0-100 score, before->after in dry-run plans, `ci-template`, GitHub Enterprise Server GraphQL routing (unit-tested URL mapping, not run against a real GHES).
- README with real screenshots, `docs/` (why-solo, recipes, faq), CONTRIBUTING, issue / PR templates, logo and social preview (`assets/`).
- `explain`, `badges`, `links --workflow`, `audit --quiet / --ignore / --fail-on`; opt-in `labels` and `community-files`.
- `tests/live_check.py`: runs every write against a real scratch repo, then reverts and compares (smoke-tested against the mock).
- **Verified against the real GitHub API (2026-10-04, public scratch repo, Windows, `gh` token):** `live_check.py` returned `RESULT: PASS`.
  11 items were applied and reverted with every API call answering success: `codeql`, `delete-branch-on-merge`, `dependabot-alerts`,
  `dependabot-security-updates`, `discussions`, `guardrail` (ruleset), `labels`, `pages`, `private-vuln-reporting`, `tag-guard` (ruleset,
  `refs/tags/v*`), `topics`; an independent before/after audit comparison of all 25 checks was identical. This also confirms the ruleset
  list `target` field and the `refs/tags/v*` pattern.
- **Verified live, second round (same repo, same day):** `secret-scanning` + `push-protection` (disabled via API -> warn -> `apply` -> ok);
  `workflow-permissions` (write -> warn -> `apply` -> ok -> `restore` -> warn); `solo-blocker` with a real classic protection (1 required approval +
  `enforce_admins`): audit showed ❌ with exit code 1 and the printed fix commands, and `apply --yes` left the protection untouched (also seen:
  `guardrail` counts classic protection as satisfied); generated files written inside a clone (`release.yml`, `SECURITY.md`, PR / issue templates,
  `CONTRIBUTING.md`: second run "No changes needed", `SECURITY.md` carries the right advisory URL), pushed, and the three checks turned ✅.
  A repo without manifests correctly reports `dependabot-config` as ➖.
- **Verified live, third round (same repo, same day):** `--commit-files` from a non-clone directory (`SECURITY.md` committed to the default branch through the
  Contents API; second run "No changes needed"); `dependabot.yml` generated from real manifests (`package.json` + `requirements.txt` -> npm and pip, `directory "/"`,
  monthly, grouped) and committed; an existing `dependabot.yml` is left byte-identical (same blob sha) while a missing directory (`npm in /web`) is only proposed;
  `solo-blocker` through a repository ruleset (❌, exit code 1, ruleset id and `enforcement=disabled` fix command; `apply` left the ruleset untouched and `restore`
  removed only the `solo-guard` it had created); a private repo on the free plan (6 checks ➖ with the paid-plan reason, plan contains no paid item, `apply --yes` and `restore`
  exit 0). Before/after audits of the scratch repo were identical after cleanup.

- **Dogfooding (2026-10-04):** this repository itself went through `audit` -> `apply --yes` (6 default items: Dependabot alerts and security updates, private
  vulnerability reporting, CodeQL default setup, ruleset `solo-guard`, delete-branch-on-merge) -> `audit`: 0 action needed, score 75 -> 90/100.
  What is left is intentional: opt-in `discussions`, `pages`, `labels`; `releases` (none yet); `release-workflow` (the release-please workflow, reported on purpose).

## Next

- **Live-verify the new checks:** `actions-can-create-prs` apply / undo, `ci-status`, `open-alerts` (the API status used when alerts are off), `issues-enabled`, Pages `https_enforced`. They are covered by mock tests only.

- **Live-verify the remainder:** an organization-owned repo (org policies can change the workflow-permissions endpoint's answer, e.g. 409), and `--commit-files` together
  with the release-on-push guard on a repo that really has such a workflow.
- **Fine-grained token matrix.** Confirm the minimum permission per endpoint by running each call with a token that has only that permission
  (the table in the README is taken from the GitHub docs, not measured).
- **Dependabot manifest names.** The ecosystem names come from Dependabot's options reference. The manifest file names
  for the less common ecosystems (`swift`, `pub`, `mix`, `elm`, `helm`, `gitsubmodule`, `pre-commit`, `terraform`, `docker-compose`) are the
  conventional names and are not confirmed from a docs table.
- **Release-workflow detection.** Still a text heuristic; cross-repo reusable workflows and general `if:` conditions are not followed.
- **Complete Japanese output.** `--lang ja` translates the fixed phrases; a few sentences are still English.

## Maybe

- Test the MCP server with Codex and Cursor (Claude Code's own client connects fine) and add each host's own config snippet once confirmed.
- Cursor rules / Gemini CLI context files, once their formats are confirmed from the vendors' docs.

- Run against a real GitHub Enterprise Server.

## Deliberately out of scope

- Anything that requires a second person: required approving reviews, required CODEOWNERS review, `enforce_admins`, merge queues.
  `solo-blocker` will only ever detect and explain these.
- Paid features on private repos (Secret Protection / Code Security): reported as ➖, never enabled.
- Choosing a license for you. Writing a repo description. Setting a social preview image (no API).
- Deleting or overwriting existing settings and files.

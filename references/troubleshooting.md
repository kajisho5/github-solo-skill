# Troubleshooting

Start with `python3 scripts/solo.py doctor OWNER/REPO`: it lists the token source, API reachability and which admin endpoints the token can read.

## "could not read (HTTP 403 …)" in an audit row

The row is shown as ⚠️ instead of guessing. Causes, most common first:

1. **The token cannot administer the repo.** Most security settings (Dependabot alerts, security updates,
   private vulnerability reporting, code scanning default setup, rulesets, workflow permissions) need
   admin rights on the repo. A collaborator with only push access gets 403/404. The audit knows this from the
   `permissions.admin` flag of the repo and says "admin permission needed".
2. **Missing token scope / permission.** See the table below.
3. **The feature is not available on the plan.** Private repos on a free plan have no rulesets/branch
   protection (403, message mentions upgrading) and no Secret Protection / Code Security. The audit shows ➖ for
   the known cases.
4. **An organization policy or SSO.** Org owners can restrict Actions settings (409 on workflow-permissions) and
   fine-grained/classic tokens may need SSO authorization (`gh auth refresh`, or "Configure SSO" on the token).
5. **A network proxy/sandbox that blocks API paths.** Some sandboxes (for example cloud coding sandboxes) only
   allow a subset of `api.github.com` paths and answer 403 "not permitted through this proxy". Run the tool from a
   normal shell.

## Token scopes

GitHub's REST docs list the following per endpoint. Verify against
<https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens>
before relying on a narrower token.

**Classic personal access token:** `repo` (public repos only: `public_repo` is enough for the code-scanning default
setup endpoint; the others are documented against `repo`). `gh auth login` gives a token with `repo`, `read:org`, `gist`.
If the workflow-file path `.github/workflows/*` is ever written (this tool does not), `workflow` would also be needed.

**Fine-grained token** (repository access: the repos you want to manage):

| Repository permission | Level | Used for |
|---|---|---|
| Metadata | Read | repo info, collaborators list, always on |
| Administration | Read and write | vulnerability alerts, security fixes, private vuln reporting, repo PATCH (secret scanning, delete-branch-on-merge, Discussions, topics, homepage), code scanning default setup, rulesets, branch protection (read), workflow permissions |
| Contents | Read and write | git tree, file contents, `--commit-files` (read-only is enough for audit/links/dependabot) |
| Pages | Read and write | `--only pages` (read for audit) |
| Actions | Read | not required by the endpoints used, harmless |

Notes: the fine-grained mapping comes from the docs page above and was summarized, not tested against every endpoint.
For a read-only audit, "Read" levels suffice for everything except that some admin-only reads still return 403/404 without Administration.

## 404 on a write

For admin endpoints GitHub answers 404 (not 403) when the token cannot see/administer the repo, and when a feature does not exist for
that repo. Check the repo name, the token's repository access, and your role on the repo.

## 422

GitHub refused the request, typically because it is already in that state, a conflicting configuration exists
(e.g. an advanced CodeQL workflow plus default setup), or the ruleset name `solo-guard` already exists (the audit reports that case).

## Private repositories

| Item | Private repo |
|---|---|
| Dependabot alerts / security updates / version updates | free ✅ |
| Secret scanning, push protection | GitHub Secret Protection (paid) → ➖ skipped |
| CodeQL code scanning | GitHub Code Security (paid) → ➖ skipped |
| Private vulnerability reporting | skipped (➖) by this tool |
| Rulesets (`solo-guard`) | not available on a free plan → ➖ when the API answers 403 |
| Pages | depends on plan; the API will refuse if unavailable (reported as FAILED, nothing else is affected) |

Plan details change; check <https://docs.github.com/en/get-started/learning-about-github/githubs-plans> for the current table.

## apply says "BLOCKED … may trigger a release workflow"

`--commit-files` commits to the default branch, and a workflow there may publish a release. Either run `apply` inside a clone and open a PR,
change the workflow trigger to tags, or re-run with `--accept-release-risk` if you accept it.

## Windows

Use `python scripts/solo.py …` if `python3` is not on PATH. Output uses UTF-8 (emoji); in a legacy console use Windows Terminal or `chcp 65001`.

## Security notes

- The token is only sent to `https://api.github.com` — or to `SOLO_API_BASE` if you set it. That variable exists for the test mock server; never point it at a host you do not control.
- The token is never printed. No command runs through a shell; `git` and `gh` are called with argument lists.
- Server messages are stripped of control characters before they are shown (no terminal escape injection).
- Local file writes are create-only (`open(..., "x")`), at fixed relative paths inside the clone's top-level directory.

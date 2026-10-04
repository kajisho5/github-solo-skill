# Checks reference

Every check: why it exists, the API it uses, what `apply` does, how to undo it.
`{o}/{r}` = owner/repo, `{b}` = default branch. All endpoints are GitHub REST
(`https://docs.github.com/en/rest`) unless noted. Status legend: ✅ OK, ⚠️ recommended, ❌ action needed, ➖ not applicable.

Default `apply` items are the ones that are invisible to visitors and easy to revert. Opt-in items
need `--only <id>`.

## Security

### dependabot-alerts (default)
- Why: tells you when a dependency has a known vulnerability. Free, also on private repos.
- Read: `GET /repos/{o}/{r}/vulnerability-alerts` (204 = on, 404 = off).
- Apply: `PUT /repos/{o}/{r}/vulnerability-alerts`.
- Undo: `DELETE` the same path, or Settings → Advanced Security.
- Needs: admin on the repo (fine-grained token: Administration).

### dependabot-security-updates (default)
- Why: Dependabot opens PRs that fix vulnerable dependencies.
- Read/Apply: `GET` / `PUT /repos/{o}/{r}/automated-security-fixes`.
- Undo: `DELETE` the same path.
- Note: shown as ⚠️ "paused" if enabled but paused; not changed by apply.

### secret-scanning, push-protection (default, public repos only)
- Why: blocks and reports committed secrets. Free on public repos; for private repos it is part of
  GitHub Secret Protection (paid) → ➖.
- Read: `security_and_analysis` in `GET /repos/{o}/{r}` (only visible to admins).
- Apply: `PATCH /repos/{o}/{r}` with `{"security_and_analysis":{"secret_scanning":{"status":"enabled"}}}`
  (and `secret_scanning_push_protection`).
- Undo: same call with `"disabled"`.

### private-vuln-reporting (default, public repos only)
- Why: lets people report a vulnerability privately instead of in a public issue; `SECURITY.md` points to it.
- Read/Apply: `GET` / `PUT /repos/{o}/{r}/private-vulnerability-reporting`.
- Undo: `DELETE` the same path.

### codeql (default, public repos only)
- Why: free code scanning (default setup) for supported languages. Private repos need GitHub Code Security (paid) → ➖.
- Languages are mapped from `GET /repos/{o}/{r}/languages`: C/C++ → c-cpp, C# → csharp, Go → go,
  Java/Kotlin → java-kotlin, JavaScript/TypeScript → javascript-typescript, Python → python, Ruby → ruby,
  Swift → swift. No match → ➖ "no CodeQL-supported language".
- A workflow that uses `github/codeql-action` counts as ✅ (advanced setup); default setup is not added on top.
- Read: `GET /repos/{o}/{r}/code-scanning/default-setup` (`state`: `configured` / `not-configured`).
- Apply: `PATCH` the same path with `{"state":"configured"}` (languages auto-detected; GitHub answers 202 and runs a validation).
- Undo: `PATCH` with `{"state":"not-configured"}`.

### dependabot-config (default)
- Why: version updates keep dependencies and Actions current. Generated file uses `schedule.interval: monthly`
  and a single `groups` entry (`patterns: ["*"]`) per ecosystem → at most one PR per ecosystem per month.
- Detection (from the default branch's git tree): `package.json` → npm, `requirements*.txt` / `pyproject.toml` / `setup.py` / `Pipfile` → pip,
  `uv.lock` → uv, `Cargo.toml` → cargo, `go.mod` → gomod, `composer.json` → composer, `Gemfile` → bundler,
  `Dockerfile*` → docker, `docker-compose*.yml` / `compose.yml` → docker-compose, `*.csproj`/`*.fsproj`/`*.vbproj`/`packages.config` → nuget,
  `pom.xml` → maven, `build.gradle(.kts)` → gradle, `*.tf` → terraform, `Package.swift` → swift, `pubspec.yaml` → pub,
  `mix.exs` → mix, `elm.json` → elm, `Chart.yaml` → helm, `.gitmodules` → gitsubmodule, `.pre-commit-config.yaml` → pre-commit,
  and `github-actions` whenever `.github/workflows/*.yml` exists. The ecosystem names are the `package-ecosystem` values listed in
  Dependabot's options reference; the manifest file names for the less common ones are the conventional names (see the note in ROADMAP.md).
- Bundled libraries under `third_party/`, `vendor/`, `external/`, `deps/`, `node_modules/`… are ignored on purpose (the audit says so):
  Dependabot does not update copied-in source.
- Existing `.github/dependabot.yml`: never modified. Missing ecosystems, and manifests in directories the existing entry does not cover
  (`directory` / `directories`, globs such as `/*` understood), are printed as a proposal to paste. `github-actions` is not checked per directory.
- File handling: written locally when run inside a clone (you commit it); otherwise `--commit-files` commits through
  `PUT /repos/{o}/{r}/contents/{path}`. See the release-on-push warning below.
- Undo: delete the file.

### actions-pinning (report only)
- Why: `uses: owner/action@v4` can be re-pointed by whoever controls the tag; a commit SHA cannot. Local (`./`) and `docker://` refs are ignored.
- Fix: replace the tag with the full 40-char SHA and keep the tag as a comment; Dependabot (`github-actions`) then updates both.

### workflow-permissions (opt-in)
- Why: a read-only default `GITHUB_TOKEN` limits the damage of a compromised workflow step.
- Read/Apply: `GET` / `PUT /repos/{o}/{r}/actions/permissions/workflow` with `{"default_workflow_permissions":"read"}`.
- Opt-in because any existing workflow that writes (releases, pushes, PR comments) without declaring `permissions:` will start failing.
  Add `permissions: contents: write` (etc.) to those jobs first.
- Undo: `PUT` with `"write"`. May answer 409 if an organization policy owns the setting.

## Solo development

### solo-blocker (❌ detect only, never changed)
- Why: with required approvals (or required CODEOWNERS review) and nobody else who can approve, you cannot merge your own PRs. Team-oriented skills add exactly this.
- Detected when BOTH hold:
  1. a rule requires ≥1 approving review or code-owner review: classic protection (`GET /repos/{o}/{r}/branches/{b}/protection` →
     `required_pull_request_reviews`) or a ruleset (`GET /repos/{o}/{r}/rules/branches/{b}` → `pull_request` rule), and
  2. only one account has push access (`GET /repos/{o}/{r}/collaborators` → `permissions.push`).
- With two or more pushers it is reported ✅ ("team repo").
- Printed fixes: `gh api -X DELETE repos/{o}/{r}/branches/{b}/protection/required_pull_request_reviews`,
  `gh api -X DELETE repos/{o}/{r}/branches/{b}/protection/enforce_admins` (when on), settings URL
  `https://github.com/{o}/{r}/settings/branches`; for a ruleset: `gh api -X PUT repos/{o}/{r}/rulesets/<id> -f enforcement=disabled`
  or edit it at `https://github.com/{o}/{r}/settings/rules/<id>`.
- Never applied automatically.

### guardrail (default)
- Why: a typo'd `git push --force` or `git push origin :main` should not be able to destroy the default branch.
- Satisfied by (any): rulesets whose active rules on `{b}` include both `deletion` and `non_fast_forward`; or classic protection with
  force-pushes and deletions disallowed.
- Apply: `POST /repos/{o}/{r}/rulesets`:
  ```json
  {"name":"solo-guard","target":"branch","enforcement":"active",
   "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
   "rules":[{"type":"deletion"},{"type":"non_fast_forward"}]}
  ```
  No pull-request rule, no required checks, no bypass list: you can still push and merge directly.
- Temporarily lift it (e.g. to rewrite history): `gh api -X PUT repos/{o}/{r}/rulesets/<id> -f enforcement=disabled`, do the work,
  then `-f enforcement=active`. `<id>` is printed after creation, or `gh api repos/{o}/{r}/rulesets`. Or Settings → Rules → Rulesets → solo-guard → Disable.
- If a `solo-guard` ruleset exists but is not active, it is reported and left alone.
- Private repos on a free plan: rulesets are not available (the API answers 403) → ➖.

### tag-guard (opt-in)
- Why: moving or deleting a published release tag silently changes what people download.
- Shown only when the repo has releases (else ➖). ✅ if an active ruleset targets tags.
- Apply: `POST /repos/{o}/{r}/rulesets` with `{"name":"solo-tag-guard","target":"tag","enforcement":"active","conditions":{"ref_name":{"include":["refs/tags/v*"],"exclude":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}]}`.
- Opt-in because a workflow that deletes and re-creates a tag would be blocked. Lift it like `solo-guard` (set `enforcement` to `disabled`).
- The `refs/tags/v*` pattern was applied and reverted against the live API (see ROADMAP).

### delete-branch-on-merge (default)
- Read/Apply: `delete_branch_on_merge` in `GET` / `PATCH /repos/{o}/{r}`. Undo: set `false`.

### discussions (opt-in)
- Read/Apply: `has_discussions` in `GET` / `PATCH /repos/{o}/{r}`. Public-facing, so opt-in. Undo: set `false`.

## Distribution

### pages (opt-in)
- Read: `GET /repos/{o}/{r}/pages` (404 = not set up).
- Folder: `docs/index.html` → `/docs`; else root `index.html` → `/`; else `/` (GitHub then renders the README as the top page).
  Override with `--pages-path / | /docs`.
- Apply: `POST /repos/{o}/{r}/pages` with `{"build_type":"legacy","source":{"branch":"{b}","path":"/docs"}}`.
  If `homepage` is empty it is then set to the Pages URL (`PATCH /repos/{o}/{r}`). Pages sites are public even for private repos on paid plans.
- Undo: `DELETE /repos/{o}/{r}/pages`; clear the homepage by hand.

### releases (report only)
- ⚠️ when: no releases; or the latest release has no assets at all (fine for a library or a skill: use `--profile library`); or only pre-releases (`GET /repos/{o}/{r}/releases/latest` ignores pre-releases and drafts → 404);
  or every asset name contains a version (so `/releases/latest/download/<asset>` changes name each release).
- Use `solo.py links` and `references/release-latest.md`.

### release-tag-format (report only)
- Why: a published tag such as `my-package-v0.2.0` (what release-please produces by default, because it adds the package name) looks odd in release links and breaks tooling that expects `vX.Y.Z`.
- ✅ when the newest release's tag is a plain version (`v1.2.3`, `1.2.3`, `v1.2.3-rc.1`); ⚠️ when it carries a prefix or is not a version; ➖ when there is no release yet (and for `--profile site` / `docs`).
- Fix for release-please: set `"include-component-in-tag": false` in `release-please-config.json` and, before the next release, create a `vX.Y.Z` tag on the same commit as the old one so release-please still finds the last release
  (the option changes the tag pattern it searches for; see the release-please manifest docs).

### release-workflow (report only)
- Why: pushing generated files to the default branch can run a workflow that publishes a release.
- Detected: a workflow that triggers on a push to the default branch (heuristic text parse of `on: push` incl. `branches`/`branches-ignore`/`tags`
  filters) AND contains `gh release create`, `softprops/action-gh-release`, `release-please`, `actions/create-release`,
  `ncipollo/release-action`, `semantic-release`, `changesets/action` (strong) or only `contents: write` (weak).
- `release-please` is on the strong list because merging its release PR (a push) publishes a release. Ordinary pushes only update the PR,
  so for a release-please-only repo the warning is conservative.
- Consequence: `apply` prints a warning before it writes/commits files, and `--commit-files` is refused unless `--accept-release-risk` is given.
  It is a heuristic. Called reusable workflows (`uses: ./.github/workflows/x.yml`) are followed one level; an `if:` mentioning `refs/tags/`
  downgrades the finding to weak. Other conditions, matrix tricks and cross-repo workflows are not followed.

### release-notes-config (default)
- Why: `.github/release.yml` makes "Generate release notes" group PRs by label and drop Dependabot's PRs
  (`changelog.exclude.authors`, `changelog.categories`; see "Automatically generated release notes" in the GitHub docs).
- Existing file: untouched. Undo: delete the file.

## Metadata

### description / topics / license (report; topics opt-in)
- `description` and `topics` come from `GET /repos/{o}/{r}`. `topics` can be set with `--only topics --topics a,b`
  (`PUT /repos/{o}/{r}/topics`, replaces all topics; lowercase, digits, hyphens, ≤50 chars, ≤20 topics).
- `license` is never generated: choosing one is your decision (https://choosealicense.com/).

### labels (opt-in)
- Why: the generated `.github/release.yml` groups PRs by the labels `breaking-change`, `enhancement` and `bug`; without them every PR lands in "Other Changes".
- Read: `GET /repos/{o}/{r}/labels`. Apply: `POST /repos/{o}/{r}/labels` for each missing one (name, color, description). Existing labels are never touched.
- Undo: `DELETE /repos/{o}/{r}/labels/{name}` (`restore` does this for the labels it created).

### community-files (opt-in)
- Why: issue templates, a PR template and CONTRIBUTING.md tell contributors what you need. Shown as ✅ when a PR template, any issue template and a CONTRIBUTING file exist.
- Generates only what is missing: `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`, `CONTRIBUTING.md` (same file handling as the other generated files). CODE_OF_CONDUCT is not generated: pick a text you endorse (for example the Contributor Covenant).
- Undo: delete the files.

### security-policy (default)
- `SECURITY.md` (root, `.github/` or `docs/`) present → ✅. Otherwise a template pointing at
  `https://github.com/{o}/{r}/security/advisories/new` is generated (same file handling as above). Undo: delete the file.

### social-preview (report only)
- GraphQL `repository { usesCustomOpenGraphImage }`. The image cannot be set through the API; upload it at
  `https://github.com/{o}/{r}/settings` → Social preview.

## Idempotency and safety

- A second `apply --yes` makes no writes: every item is derived from the current state, and files that exist (locally or in the repo) are never touched.
- `apply` makes no deletions and never overwrites. The only `PUT` that replaces data is `topics`, which is opt-in and requires `--topics`.

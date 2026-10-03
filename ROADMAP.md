# Roadmap

Status of `0.x`. Everything under "Done" is covered by `python -m unittest`.

## Done (0.1)

- `audit` (text + `--json`, exit 1 on ❌), `apply` (dry run, `--yes`, `--only`, `--skip`), `links`, `dependabot`.
- 22 checks across Security / Solo development / Distribution / Metadata (see [references/checks.md](references/checks.md)).
- Solo-blocker detection (classic protection and rulesets), `solo-guard` ruleset, release-on-push warning.
- Mock GitHub API test suite, CI on Python 3.9 and 3.13, release-please.

## Next

- **Live verification of every write against a scratch repo.** The tests assert the request bodies against a mock built from the
  GitHub REST docs; each write has not yet been exercised against the real API from this project's CI.
- **Fine-grained token matrix.** Confirm the minimum permission per endpoint by running each call with a token that has only that permission
  (the table in the README is taken from the GitHub docs, not measured).
- **Dependabot manifest names.** The ecosystem names come from Dependabot's options reference. The manifest file names
  for the less common ecosystems (`swift`, `pub`, `mix`, `elm`, `helm`, `gitsubmodule`, `pre-commit`, `terraform`, `docker-compose`) are the
  conventional names and are not confirmed from a docs table.
- **Directory-level coverage of an existing `dependabot.yml`.** Today only missing ecosystems are proposed; a manifest in a new
  sub-directory of an already-configured ecosystem is not.
- **Release-workflow detection.** Follow `workflow_call` / reusable workflows and `if:` conditions; today it is a text heuristic.
- **Localised output** (`--lang ja`). The script prints English; the agent translates the summary.
- **`apply --json`** for CI dashboards.

## Maybe

- Tag rulesets (protect `v*` tags from deletion / force-update), opt-in.
- Org-level checks (shared defaults) for people who own several repos: `audit --all-repos OWNER`.
- GitHub Enterprise Server base URL handling for GraphQL.

## Deliberately out of scope

- Anything that requires a second person: required approving reviews, required CODEOWNERS review, `enforce_admins`, merge queues.
  `solo-blocker` will only ever detect and explain these.
- Paid features on private repos (Secret Protection / Code Security): reported as ➖, never enabled.
- Choosing a license for you. Writing a repo description. Setting a social preview image (no API).
- Deleting or overwriting existing settings and files.

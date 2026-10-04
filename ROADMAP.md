# Roadmap

Status of `0.x`. Everything under "Done" is covered by `python -m unittest`.

## Done (0.1)

- `audit` (text + `--json`, exit 1 on ❌), `apply` (dry run, `--yes`, `--only`, `--skip`), `links`, `dependabot`.
- 25 checks across Security / Solo development / Distribution / Metadata (see [references/checks.md](references/checks.md)).
- Solo-blocker detection (classic protection and rulesets), `solo-guard` ruleset, release-on-push warning.
- Mock GitHub API test suite, CI on Python 3.9 and 3.13, release-please.
- `--lang ja`, `apply --json`, `audit --all-repos`, `audit --github-annotations`, `links --markdown`.
- Per-directory coverage of an existing `dependabot.yml`; release detection through reusable workflows and `refs/tags` conditions.
- Opt-in `tag-guard` ruleset for `v*` tags.
- `doctor`, and `restore` (every `apply --yes` saves an undo snapshot).
- `--profile`, 0-100 score, before->after in dry-run plans, `ci-template`, GitHub Enterprise Server GraphQL routing (unit-tested URL mapping, not run against a real GHES).
- `explain`, `badges`, `links --workflow`, `audit --quiet / --ignore / --fail-on`; opt-in `labels` and `community-files`.
- `tests/live_check.py`: runs every write against a real scratch repo, then reverts and compares (smoke-tested against the mock).

## Next

- **Run `tests/live_check.py` against a real scratch repo and fix whatever it finds.** The unit tests assert the request bodies against
  a mock built from the GitHub REST docs; the real API has not been exercised yet.
- **Fine-grained token matrix.** Confirm the minimum permission per endpoint by running each call with a token that has only that permission
  (the table in the README is taken from the GitHub docs, not measured).
- **Dependabot manifest names.** The ecosystem names come from Dependabot's options reference. The manifest file names
  for the less common ecosystems (`swift`, `pub`, `mix`, `elm`, `helm`, `gitsubmodule`, `pre-commit`, `terraform`, `docker-compose`) are the
  conventional names and are not confirmed from a docs table.
- **Release-workflow detection.** Still a text heuristic; cross-repo reusable workflows and general `if:` conditions are not followed.
- **Complete Japanese output.** `--lang ja` translates the fixed phrases; a few sentences are still English.
- **Verify `refs/tags/v*` for the tag ruleset and `GET /rulesets` `target` against the live API.**

## Maybe

- Run against a real GitHub Enterprise Server.

## Deliberately out of scope

- Anything that requires a second person: required approving reviews, required CODEOWNERS review, `enforce_admins`, merge queues.
  `solo-blocker` will only ever detect and explain these.
- Paid features on private repos (Secret Protection / Code Security): reported as ➖, never enabled.
- Choosing a license for you. Writing a repo description. Setting a social preview image (no API).
- Deleting or overwriting existing settings and files.

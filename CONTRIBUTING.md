# Contributing to github-solo-skill

Thanks for helping! This is a small project, so keep it simple:

1. Open an issue first for anything bigger than a typo or a one-line fix, so we can agree on the direction.
2. Fork, create a branch, make your change, and open a pull request describing what and why.
3. Add or update tests when behavior changes, and run them before you push.

## Ground rules (they are the point of the project)

- **Never add a setting that stops a single maintainer from merging their own PRs** (required approvals, required CODEOWNERS review, `enforce_admins`).
- Free GitHub features only. Paid-only things are reported as "n/a" with the reason, never enabled.
- `apply` is a dry run unless `--yes`, is idempotent, and never deletes or overwrites an existing file or setting. Anything public-facing or able to break a workflow is opt-in (`--only`).
- Standard library only, Python 3.9+. Code messages are English; `--lang ja` translates fixed phrases (`JA` in `scripts/solo.py`); JSON output is never translated.
- Do not guess API behavior: check docs.github.com and cite the page in `references/checks.md`. If you could not confirm something, say so there.

## Development

```bash
python -m unittest                                   # no network: a mock GitHub API runs in-process
python -m unittest tests.test_solo.VoiceboothScenario -v
python3 tests/live_check.py YOU/scratch-repo --confirm YOU/scratch-repo   # real API, disposable repo you own
python3 assets/build_assets.py                       # rebuild the README images
```

A new check = a function in `scripts/solo.py` that returns `R(...)` rows (register it in `CHECKS`), a branch in `plan_for` if it can be applied (with an `undo` so `restore` works),
a mock route in `tests/mock_github.py` and a fixture in `tests/fixtures.py`, tests for the verdict, the dry-run plan and the exact write requests, and an entry in `references/checks.md`.

Please run the tests on Windows too if you can: the suite has caught code-page and permission differences before.

## Commits and releases

[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:` …). release-please opens the release PR and never bumps the major version by itself.

## Security

Please report vulnerabilities privately, see [SECURITY.md](SECURITY.md).

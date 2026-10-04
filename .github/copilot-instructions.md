This repository is `github-solo`: a stdlib-only Python 3.9+ tool (`scripts/solo.py`) that audits and configures a GitHub repo for a solo developer.
Read `AGENTS.md` (how to use the tool safely, and how to work on this repo) and `SKILL.md` before changing anything.
Rules: never add approval-required branch protection; `apply` is a dry run unless `--yes`; never delete or overwrite existing files or settings;
run `python -m unittest` (no network needed) before proposing a change.

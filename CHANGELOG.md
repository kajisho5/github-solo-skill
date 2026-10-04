# Changelog

## [0.3.0](https://github.com/kajisho5/github-solo-skill/compare/v0.2.0...v0.3.0) (2026-10-04)


### Features

* gap checks found while releasing (actions-can-create-prs, ci-status, actions-hardening, open-alerts, issues-enabled; draft releases, Pages HTTPS notes) ([48f81cc](https://github.com/kajisho5/github-solo-skill/commit/48f81cc074a80924082c670409850098f225c354))
* release-tag-format check and assetless-release note; use plain vX.Y.Z tags for our own releases ([fcacbb7](https://github.com/kajisho5/github-solo-skill/commit/fcacbb7e841c34a68ae4c1d1cebef8e5fd1e2a03))

## [0.2.0](https://github.com/kajisho5/github-solo-skill/compare/github-solo-skill-v0.1.0...github-solo-skill-v0.2.0) (2026-10-04)


### Features

* --lang ja, apply --json, --all-repos, annotations, links --markdown, tag-guard, per-directory dependabot coverage, reusable-workflow release detection ([7fb69bd](https://github.com/kajisho5/github-solo-skill/commit/7fb69bdcb2f71ce64b9f3bf2a5b8ece78a496e2a))
* --profile, score, before-&gt;after plans, ci-template, GHES graphql routing; refresh README example and install paths ([727bd49](https://github.com/kajisho5/github-solo-skill/commit/727bd4968fea68a117dfd2a8f5eae37157f7f514))
* detect the runtime environment first (cloud container vs local Claude Code) in doctor and SKILL.md ([60094a5](https://github.com/kajisho5/github-solo-skill/commit/60094a5d36231efa657d29a02a2c357fe97a5b88))
* doctor, restore (undo snapshots), live_check script ([4465d24](https://github.com/kajisho5/github-solo-skill/commit/4465d24717acda5fd351aa2597a71be4062eb609))
* explain, badges, links --workflow, audit --quiet/--ignore/--fail-on, opt-in labels and community-files ([d02044c](https://github.com/kajisho5/github-solo-skill/commit/d02044c3d03dbe36e1d0b62d8125a47b7bdb1c8c))
* github-solo skill (audit / apply / links / dependabot for solo developers) ([8d7d4ed](https://github.com/kajisho5/github-solo-skill/commit/8d7d4ed4ae22d509709ca318968d4016c7d2bb06))
* MCP stdio server, AGENTS.md and Copilot instructions so Codex and other agents can use github-solo ([46979d6](https://github.com/kajisho5/github-solo-skill/commit/46979d6a35a6ca29dbd1a639f4386c2fd5397176))


### Bug Fixes

* explain proxy-blocked writes; note release-please in release-workflow check ([be5cb0e](https://github.com/kajisho5/github-solo-skill/commit/be5cb0e5dcfaa83b59a2220a930006aedf86cfcf))
* live_check.py prints UTF-8 on legacy Windows code pages ([9a8824c](https://github.com/kajisho5/github-solo-skill/commit/9a8824ca65c58d798dc9b9458305689ecb0bbbb6))
* Windows test and MCP issues (utf-8 decoding, POSIX permission assertion, utf-8/LF stdio); add Windows CI job ([efc5a2e](https://github.com/kajisho5/github-solo-skill/commit/efc5a2e5f607ac5669a1930683880d7106e4902c))

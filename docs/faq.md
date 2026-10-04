# FAQ

**Is it safe to run on my real repo?** `audit` only reads. `apply` is a dry run unless you pass `--yes`, changes only what is missing, never deletes or overwrites,
and saves an undo snapshot, so `restore` can put it back. It has been exercised against the real API on a scratch repo (see the README), not on every kind of repo.

**Why doesn't it protect `main` with pull requests?** Because with one maintainer that blocks your own merges. See [why-solo.md](why-solo.md). It blocks deletion and force-push instead.

**What if I work with one other person?** Then required reviews can make sense. `solo-blocker` only fires when you are the only account with push access; with two or more it reports ✅ "team repo".
`github-solo` simply never *adds* such a rule.

**Does it send my data anywhere?** No. It talks only to the GitHub API (or to `SOLO_API_BASE` if you set it, for testing). The token is never printed or stored.

**Which token do I need?** A classic token with `repo`, or a fine-grained token with Administration (read/write), Contents, Metadata and Pages. See the README. `solo.py doctor OWNER/REPO` shows what your token can read.

**Why does a row say "could not read (HTTP 403 …)"?** The token or the plan cannot read that setting, or a sandbox/proxy in front of the API refuses the path. The row is a ⚠️ instead of a guess.
[references/troubleshooting.md](../references/troubleshooting.md) lists the causes.

**Why are some items ➖?** Private repos on a free plan have no Secret Protection, Code Security or rulesets. They are reported with the reason and never enabled.

**`apply` says "not a clone" and skips my files.** Generated files are written locally only inside a clone of that repo. Run it from the clone, or add `--commit-files` to commit through the API
(it refuses when a push to the default branch may trigger a release workflow, unless you add `--accept-release-risk`).

**Does it work for organization repos?** It uses the same API calls, but it has not been tried on an organization-owned repo. Organization policies can change answers (for example a 409 on the workflow permissions endpoint).

**Windows?** Yes: the tests run in CI on Windows and the live checks were run from Windows. See [recipes.md](recipes.md#windows) for the usual snags.

**Which agents can use it?** Anything that reads `SKILL.md` or `AGENTS.md`, or speaks MCP. Verified: Claude Code (the CLI driven from Claude Code sessions on Linux and Windows, plugin manifest validation, MCP connection). Codex and Cursor setups follow their documentation but were not run.

**Can I add my own check?** Yes: a check is one function in `scripts/solo.py` returning `R(...)` rows, plus a planner in `plan_for` if it can be applied. See [CONTRIBUTING.md](../CONTRIBUTING.md).

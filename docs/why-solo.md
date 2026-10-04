# Why a separate skill for one-person repos?

## The lock-in problem

Most GitHub hardening guides assume a team. Their centrepiece is a branch protection rule like this:

- **Require a pull request before merging**, with **1 or more approving reviews**
- often **Require review from Code Owners**
- often **Do not allow bypassing the above settings** (`enforce_admins`)

On a repository with one committer that combination is a trap. You open a PR, nobody can approve it (GitHub does not let you approve your own PR),
and the merge button stays grey. The usual escapes are all bad: switch the rule off "just this once" (and forget to switch it back), invite a throw-away
second account, or push around the rule as an admin, which `enforce_admins` forbids too.

`github-solo` never creates such a rule. If it finds one on a repo where you are the only account with push access, `audit` flags it as **❌ solo-blocker**
(exit code 1), prints the exact commands and the settings URL to remove it, and **leaves it alone**: removing a protection is your decision, not a script's.
If two or more people can push, the same rule is reported as normal (a team repo, not a lock-in).

## What a solo developer does need

Mistakes are the real risk when you work alone: a mistyped `git push --force`, a deleted default branch, a leaked token, a dependency with a known hole,
a release that went out when you only meant to add a file. So the defaults are:

| Risk | What `github-solo` does |
|---|---|
| Deleting or force-pushing the default branch | ruleset `solo-guard` (`deletion`, `non_fast_forward`); **no** pull-request requirement, no bypass list, so your own pushes and merges still work |
| Moving or deleting a release tag | opt-in ruleset `solo-tag-guard` for `v*` tags |
| Vulnerable dependencies | Dependabot alerts + security updates, and a generated `dependabot.yml` (monthly, one grouped PR per ecosystem, so there is little noise) |
| Leaked secrets | secret scanning and push protection (public repos; paid on private repos, so skipped there) |
| Vulnerability reports landing in a public issue | private vulnerability reporting + a `SECURITY.md` that points to it |
| A compromised workflow step | default `GITHUB_TOKEN` read-only (opt-in, because it can break workflows) and a report of actions not pinned to a commit SHA |
| An accidental release | a warning when a push to the default branch can start a release workflow |

## Lifting the guard for a moment

Rewriting history on purpose is legitimate. Disable the ruleset, do the work, enable it again:

```bash
gh api -X PUT repos/OWNER/REPO/rulesets/<id> -f enforcement=disabled
# ... git push --force-with-lease ...
gh api -X PUT repos/OWNER/REPO/rulesets/<id> -f enforcement=active
```

(`<id>` is printed when `solo-guard` is created, or `gh api repos/OWNER/REPO/rulesets`.) Or use *Settings → Rules → Rulesets → solo-guard*.

## Design rules that follow

1. Never add a setting that stops a single maintainer from merging.
2. Free features only; paid ones are reported as "not applicable" with the reason.
3. Dry run by default, idempotent, and every `apply --yes` can be undone with `restore`.
4. Only invisible, instantly reversible settings are applied by default. Anything public-facing (Pages, Discussions, topics) or able to break a workflow needs `--only`.
5. Never delete or overwrite an existing file or setting.
6. When a push could trigger a release, say so before touching the default branch.
7. When something is blocked or unclear, read the official documentation instead of guessing.

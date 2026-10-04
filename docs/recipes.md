# Recipes

## Check a repo before a release

```bash
python3 scripts/solo.py audit OWNER/REPO --quiet --ignore license,social-preview
python3 scripts/solo.py links OWNER/REPO            # is there a stable download URL? why not?
```

`--quiet` hides the ✅ and ➖ rows, `--ignore` leaves out checks you decided not to care about (also from the exit code).

## A download link that always points to the newest build

`https://github.com/OWNER/REPO/releases/latest/download/ASSET` only works if the newest **non-pre-release** exists and `ASSET` has the same name in every release.

```bash
python3 scripts/solo.py links OWNER/REPO --markdown     # ready-to-paste list items
python3 scripts/solo.py links --workflow                # a release workflow that uploads version-less copies
```

Details and the corner cases (only pre-releases, versions in file names): [references/release-latest.md](../references/release-latest.md).

## Weekly audit in CI

```bash
python3 scripts/solo.py ci-template > .github/workflows/solo-audit.yml
```

Edit the placeholders (pin the actions and the downloaded script to commit SHAs you reviewed), add a repository secret `SOLO_AUDIT_TOKEN`
(a fine-grained token for that repo with *Administration: read*, *Contents: read*, *Metadata: read*: the built-in `GITHUB_TOKEN` cannot read most security settings).
The job fails and annotates the run when something needs action. For a stricter gate use `--fail-on warn`.

## Audit everything you own

```bash
python3 scripts/solo.py audit --all-repos YOUR_LOGIN            # one line per repo with a 0-100 score
python3 scripts/solo.py audit --all-repos YOUR_LOGIN --json | python3 -m json.tool
```

Archived repos and forks are skipped. Each repo costs a few dozen API calls.

## Different kinds of repos

```bash
python3 scripts/solo.py audit OWNER/SITE --profile site       # no release notes, no release tags
python3 scripts/solo.py audit OWNER/LIB  --profile library    # releases count even if asset names carry the version
```

## Use it from an agent

- Skill: ask *"check my GitHub settings"*. The agent runs `doctor`, `audit`, shows the `apply` plan and waits for your OK.
- MCP: `claude mcp add github-solo -- python3 /path/to/scripts/solo_mcp.py` (Codex: `codex mcp add ...`). Writes need `confirm: true`.
- Any agent: point it at [AGENTS.md](../AGENTS.md).

## Undo

```bash
python3 scripts/solo.py restore OWNER/REPO            # shows what it would revert
python3 scripts/solo.py restore OWNER/REPO --yes
```

Snapshots live in `~/.local/state/github-solo/` (`%LOCALAPPDATA%\github-solo` on Windows, `SOLO_STATE_DIR` to change). Files that `apply` wrote or committed are not removed; delete them yourself.

## Windows

- Use `python` if `python3` is not found. `winget install --id GitHub.CLI` then `gh auth login` gives you a token source.
- In Git Bash, write API paths without the leading slash (`gh api repos/OWNER/REPO/...`), otherwise the shell rewrites them into a Windows path.
- A fresh `gh` install is not on the PATH of shells that were already open.

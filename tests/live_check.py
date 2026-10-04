#!/usr/bin/env python3
"""Exercise every write of solo.py against a REAL, disposable GitHub repo, then revert it.

This is NOT part of `python -m unittest` (it needs a real token and changes real settings).
Use a scratch repo you own and do not care about, e.g.:

    gh repo create solo-live-check --public --add-readme
    python3 tests/live_check.py YOU/solo-live-check --confirm YOU/solo-live-check

What it does: doctor -> audit -> apply --yes (every item that can be applied through the API, opt-in ones
included) -> audit (each applied item must now be OK) -> restore --yes -> audit (each item must be back to
its original status). Exit code 1 if anything differs. Your token needs the permissions listed in the README.
It also runs against the mock server (SOLO_API_BASE), which is how the unit tests smoke-test this script.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLO = os.path.join(ROOT, "scripts", "solo.py")
FILE_ITEMS = {"dependabot-config", "release-notes-config", "security-policy", "community-files"}  # need a clone; not API writes


def solo(env, *args):
    p = subprocess.run([sys.executable, SOLO] + list(args), env=env, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def audit(env, repo):
    rc, out, err = solo(env, "audit", repo, "--json")
    if rc not in (0, 1):
        raise SystemExit("audit failed: %s%s" % (out, err))
    return {r["id"]: r for r in json.loads(out)["results"]}


def main():
    for stream in (sys.stdout, sys.stderr):  # the child output has emoji; legacy Windows code pages (cp932) cannot print it
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="OWNER/REPO of the scratch repo")
    ap.add_argument("--confirm", required=True, help="repeat OWNER/REPO to confirm that its settings may be changed")
    args = ap.parse_args()
    if args.confirm != args.repo:
        raise SystemExit("--confirm must repeat the repo name exactly")
    state = tempfile.mkdtemp(prefix="solo-live-")
    env = dict(os.environ, SOLO_STATE_DIR=state, SOLO_LANG="en")

    rc, out, _ = solo(env, "doctor", args.repo)
    print(out)
    if rc != 0:
        raise SystemExit("doctor reported problems; fix them first")

    before = audit(env, args.repo)
    ids = sorted({r["apply"] for r in before.values()
                  if r["apply"] and r["status"] == "warn" and r["apply"] not in FILE_ITEMS})
    if not ids:
        raise SystemExit("nothing to apply on this repo: use a fresh scratch repo")
    print("applying: %s\n" % ", ".join(ids))
    rc, out, err = solo(env, "apply", args.repo, "--yes", "--only", ",".join(ids), "--topics", "github-solo-check")
    print(out + err)
    after = audit(env, args.repo)
    rc2, out2, err2 = solo(env, "restore", args.repo, "--yes")
    print(out2 + err2)
    restored = audit(env, args.repo)

    failed = False
    print("%-30s %-10s %-10s %-10s" % ("item", "before", "applied", "restored"))
    for i in ids:
        owners = [k for k, r in before.items() if r["apply"] == i]
        for k in owners:
            ok_applied = after[k]["status"] == "ok"
            ok_restored = restored[k]["status"] == before[k]["status"]
            failed |= not (ok_applied and ok_restored)
            print("%-30s %-10s %-10s %-10s  %s" % (
                k, before[k]["status"], after[k]["status"], restored[k]["status"],
                "PASS" if ok_applied and ok_restored else "FAIL"))
    print("\nRESULT: %s" % ("FAIL" if failed or rc or rc2 else "PASS"))
    return 1 if failed or rc or rc2 else 0


if __name__ == "__main__":
    sys.exit(main())

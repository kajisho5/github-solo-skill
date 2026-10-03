"""End-to-end tests: run scripts/solo.py against the stdlib mock GitHub server."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

try:
    from . import fixtures, mock_github
except ImportError:  # run with `-s tests`
    import fixtures
    import mock_github

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLO = os.path.join(ROOT, "scripts", "solo.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import solo  # noqa: E402

PREFIX = "/repos/seventhwell/"


class Base(unittest.TestCase):
    state = None
    slug = None

    def setUp(self):
        self.mock = mock_github.MockGitHub(self.state()).start()
        self.addCleanup(self.mock.stop)
        self.tmp = tempfile.mkdtemp()

    def run_solo(self, *args, **kw):
        env = dict(os.environ, SOLO_API_BASE=self.mock.url, GH_TOKEN="test-token")
        env.pop("GITHUB_TOKEN", None)
        p = subprocess.run([sys.executable, SOLO] + list(args), env=env,
                           cwd=kw.get("cwd", self.tmp), capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def audit(self):
        rc, out, err = self.run_solo("audit", self.slug, "--json")
        self.assertIn(rc, (0, 1), err)
        data = json.loads(out)
        return rc, data, {r["id"]: r for r in data["results"]}

    def status(self, st):
        return {k: v["status"] for k, v in st.items()}

    def writes(self):
        return [(m, p, b) for m, p, b in self.mock.writes]


# ---------------------------------------------------------------------------
class VoiceboothScenario(Base):
    state = staticmethod(fixtures.voicebooth)
    slug = "seventhwell/voicebooth"
    P = PREFIX + "voicebooth"

    def test_audit(self):
        rc, data, st = self.audit()
        self.assertEqual(rc, 0)
        s = self.status(st)
        expect = {
            "dependabot-alerts": "warn", "dependabot-security-updates": "warn",
            "secret-scanning": "ok", "push-protection": "ok",
            "private-vuln-reporting": "warn", "codeql": "warn",
            "dependabot-config": "warn", "actions-pinning": "ok",
            "workflow-permissions": "warn", "solo-blocker": "ok", "guardrail": "warn",
            "delete-branch-on-merge": "warn", "discussions": "warn", "pages": "warn",
            "releases": "warn", "release-workflow": "warn", "release-notes-config": "warn",
            "description": "ok", "topics": "ok", "license": "ok", "security-policy": "ok",
            "social-preview": "ok",
        }
        self.assertEqual(s, expect)
        self.assertIn("all pre-releases", st["releases"]["message"])
        self.assertIn("will likely", st["release-workflow"]["message"])
        self.assertIn("third_party", " ".join(st["dependabot-config"]["details"]))
        self.assertIn("github-actions", st["dependabot-config"]["message"])
        self.assertNotIn("npm", st["dependabot-config"]["message"])  # vendored package.json ignored
        self.assertIn("no index.html", st["pages"]["message"])
        self.assertEqual(data["summary"]["bad"], 0)

    def test_dry_run_plan_and_no_writes(self):
        rc, out, _ = self.run_solo("apply", self.slug)
        self.assertEqual(rc, 0)
        for pid in ("dependabot-alerts", "dependabot-security-updates", "private-vuln-reporting",
                    "codeql", "dependabot-config", "guardrail", "delete-branch-on-merge",
                    "release-notes-config"):
            self.assertIn("] %s:" % pid, out)
        for pid in ("discussions", "pages", "workflow-permissions"):
            self.assertNotIn("] %s:" % pid, out)
            self.assertIn("- %s:" % pid, out)  # listed as opt-in
        self.assertIn("Dry run", out)
        self.assertEqual(self.writes(), [])

    def test_yes_writes_exactly_the_defaults(self):
        rc, out, err = self.run_solo("apply", self.slug, "--yes")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.writes(), [
            ("PUT", self.P + "/vulnerability-alerts", None),
            ("PUT", self.P + "/automated-security-fixes", None),
            ("PUT", self.P + "/private-vulnerability-reporting", None),
            ("PATCH", self.P + "/code-scanning/default-setup", {"state": "configured"}),
            ("POST", self.P + "/rulesets", {
                "name": "solo-guard", "target": "branch", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}),
            ("PATCH", self.P, {"delete_branch_on_merge": True}),
        ])

    def test_second_yes_run_is_a_noop(self):
        self.run_solo("apply", self.slug, "--yes")
        self.mock.clear_writes()
        rc, out, _ = self.run_solo("apply", self.slug, "--yes")
        self.assertEqual(rc, 0)
        self.assertEqual(self.writes(), [])
        # only the file items remain (not a clone): they are skipped, never written
        _, data, st = self.audit()
        for k in ("dependabot-alerts", "dependabot-security-updates", "private-vuln-reporting",
                  "codeql", "guardrail", "delete-branch-on-merge"):
            self.assertEqual(st[k]["status"], "ok", k)

    def test_opt_in_items_only_with_only(self):
        rc, out, err = self.run_solo("apply", self.slug, "--yes", "--only",
                                     "discussions,pages,workflow-permissions")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.writes(), [
            ("PUT", self.P + "/actions/permissions/workflow", {"default_workflow_permissions": "read"}),
            ("PATCH", self.P, {"has_discussions": True}),
            ("POST", self.P + "/pages", {"build_type": "legacy", "source": {"branch": "main", "path": "/"}}),
            ("PATCH", self.P, {"homepage": "https://seventhwell.github.io/voicebooth/"}),
        ])

    def test_pages_path_override(self):
        self.run_solo("apply", self.slug, "--yes", "--only", "pages", "--pages-path", "/docs")
        self.assertEqual(self.writes()[0], (
            "POST", self.P + "/pages", {"build_type": "legacy", "source": {"branch": "main", "path": "/docs"}}))

    def test_skip(self):
        self.run_solo("apply", self.slug, "--yes", "--skip", "guardrail,codeql")
        paths = [p for _, p, _ in self.writes()]
        self.assertNotIn(self.P + "/rulesets", paths)
        self.assertNotIn(self.P + "/code-scanning/default-setup", paths)

    def test_unknown_id_rejected(self):
        rc, _, err = self.run_solo("apply", self.slug, "--only", "nope")
        self.assertEqual(rc, 2)
        self.assertIn("unknown", err)

    def test_commit_files_blocked_by_release_risk(self):
        rc, out, _ = self.run_solo("apply", self.slug, "--yes", "--commit-files")
        self.assertEqual(rc, 1)
        self.assertIn("WARNING", out)
        self.assertIn("BLOCKED", out)
        self.assertFalse([w for w in self.writes() if "/contents/" in w[1]])

    def test_commit_files_with_accepted_risk(self):
        rc, out, err = self.run_solo("apply", self.slug, "--yes", "--commit-files",
                                     "--accept-release-risk", "--only", "dependabot-config,release-notes-config")
        self.assertEqual(rc, 0, out + err)
        w = self.writes()
        self.assertEqual([(m, p) for m, p, _ in w], [
            ("PUT", self.P + "/contents/.github/dependabot.yml"),
            ("PUT", self.P + "/contents/.github/release.yml"),
        ])
        self.assertEqual(w[0][2]["branch"], "main")

    def test_local_clone_writes_files_only_locally_and_never_overwrites(self):
        d = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", d], check=True)
        subprocess.run(["git", "-C", d, "remote", "add", "origin",
                        "https://github.com/seventhwell/voicebooth.git"], check=True)
        rc, out, err = self.run_solo("apply", "--yes", "--only", "dependabot-config,release-notes-config", cwd=d)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("WARNING", out)  # release risk is shown before the user commits
        self.assertEqual(self.writes(), [])  # nothing sent to GitHub
        dep = os.path.join(d, ".github", "dependabot.yml")
        with open(dep) as f:
            text = f.read()
        self.assertIn('package-ecosystem: "github-actions"', text)
        self.assertIn('interval: "monthly"', text)
        self.assertIn('patterns:\n          - "*"', text)
        self.assertTrue(os.path.exists(os.path.join(d, ".github", "release.yml")))
        # second run: files exist locally -> untouched
        with open(dep, "a") as f:
            f.write("# mine\n")
        rc, out, _ = self.run_solo("apply", "--yes", "--only", "dependabot-config", cwd=d)
        self.assertIn("No changes needed", out)
        with open(dep) as f:
            self.assertTrue(f.read().endswith("# mine\n"))

    def test_links_explains_prereleases(self):
        rc, out, _ = self.run_solo("links", self.slug)
        self.assertEqual(rc, 1)
        self.assertIn("pre-releases", out)
        self.assertIn("--prerelease=false", out)

    def test_dependabot_subcommand(self):
        rc, out, err = self.run_solo("dependabot", self.slug)
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("version: 2\n"))
        self.assertIn("github-actions", out)
        self.assertIn("third_party", err)


class SoloBlockerScenario(Base):
    state = staticmethod(fixtures.solo_blocker)
    slug = "seventhwell/lockedout"

    def test_blocker_detected_with_exit_1(self):
        rc, data, st = self.audit()
        self.assertEqual(rc, 1)
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(st["solo-blocker"]["status"], "bad")
        text = json.dumps(st["solo-blocker"])
        self.assertIn("gh api -X DELETE repos/seventhwell/lockedout/branches/main/protection/required_pull_request_reviews", text)
        self.assertIn("enforce_admins", text)
        self.assertIn("https://github.com/seventhwell/lockedout/settings/branches", text)
        self.assertEqual(st["guardrail"]["status"], "ok")  # classic protection already blocks force-push/delete

    def test_text_audit_exit_code(self):
        rc, out, _ = self.run_solo("audit", self.slug)
        self.assertEqual(rc, 1)
        self.assertIn("❌ solo-blocker", out)

    def test_apply_never_touches_protection(self):
        rc, out, _ = self.run_solo("apply", self.slug, "--yes")
        self.assertIn("never changed by apply", out)
        for m, p, _ in self.writes():
            self.assertNotIn("protection", p)
            self.assertNotEqual(m, "DELETE")
        self.assertEqual(self.mock.state["protection"]["required_pull_request_reviews"]
                         ["required_approving_review_count"], 1)


class RulesetBlockerScenario(Base):
    slug = "seventhwell/lockedout"

    @staticmethod
    def state():
        s = fixtures.base("lockedout")
        s["rulesets"] = [{"id": 5, "name": "review", "enforcement": "active",
                          "rules": [{"type": "pull_request", "parameters": {
                              "required_approving_review_count": 1, "require_code_owner_review": True}}]}]
        return s

    def test_ruleset_blocker(self):
        rc, _, st = self.audit()
        self.assertEqual(rc, 1)
        self.assertEqual(st["solo-blocker"]["status"], "bad")
        text = json.dumps(st["solo-blocker"])
        self.assertIn("ruleset #5", text)
        self.assertIn("rulesets/5", text)
        self.assertIn("code owner", text)


class TeamRepoScenario(Base):
    slug = "seventhwell/lockedout"

    @staticmethod
    def state():
        s = fixtures.solo_blocker()
        s["collaborators"].append({"login": "friend", "permissions": {"push": True}})
        return s

    def test_two_pushers_is_not_a_solo_lockin(self):
        rc, _, st = self.audit()
        self.assertEqual(rc, 0)
        self.assertEqual(st["solo-blocker"]["status"], "ok")


class PrivateScenario(Base):
    state = staticmethod(fixtures.private_repo)
    slug = "seventhwell/secret-tool"
    P = PREFIX + "secret-tool"

    def test_paid_features_skipped(self):
        rc, data, st = self.audit()
        self.assertEqual(rc, 0)
        for k in ("secret-scanning", "push-protection", "private-vuln-reporting", "codeql", "guardrail"):
            self.assertEqual(st[k]["status"], "na", k)
        self.assertIn("paid plan", st["secret-scanning"]["message"])
        self.assertEqual(st["dependabot-alerts"]["status"], "warn")  # free on private repos

    def test_apply_only_free_items(self):
        rc, out, err = self.run_solo("apply", self.slug, "--yes")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.writes(), [
            ("PUT", self.P + "/vulnerability-alerts", None),
            ("PUT", self.P + "/automated-security-fixes", None),
            ("PATCH", self.P, {"delete_branch_on_merge": True}),
        ])


class ConfiguredScenario(Base):
    state = staticmethod(fixtures.configured)
    slug = "seventhwell/tidy"

    def test_everything_ok(self):
        rc, data, st = self.audit()
        self.assertEqual(rc, 0)
        self.assertEqual(data["summary"], {"ok": 22, "warn": 0, "bad": 0, "na": 0}, self.status(st))

    def test_dry_run_reports_no_changes(self):
        rc, out, _ = self.run_solo("apply", self.slug)
        self.assertEqual(rc, 0)
        self.assertIn("No changes needed", out)
        self.assertNotIn("Not applied by default", out)

    def test_yes_writes_nothing(self):
        rc, out, _ = self.run_solo("apply", self.slug, "--yes")
        self.assertEqual(rc, 0)
        self.assertIn("No changes needed", out)
        self.assertEqual(self.writes(), [])

    def test_existing_dependabot_config_gets_proposal_only(self):
        self.mock.state["tree"].append("Cargo.toml")
        rc, out, _ = self.run_solo("apply", self.slug, "--yes")
        self.assertEqual(rc, 0)
        self.assertIn('package-ecosystem: "cargo"', out)
        self.assertIn("not modified", out)
        self.assertEqual(self.writes(), [])

    def test_links(self):
        rc, out, _ = self.run_solo("links", self.slug)
        self.assertEqual(rc, 0)
        self.assertIn("https://github.com/seventhwell/tidy/releases/latest/download/tidy-windows.zip", out)
        self.assertIn("https://github.com/seventhwell/tidy/releases/latest/download/tidy-mac.dmg", out)


class VersionedAssetsLinks(Base):
    slug = "seventhwell/tidy"

    @staticmethod
    def state():
        s = fixtures.configured()
        s["releases"] = [{"tag_name": "v2.0.0", "prerelease": False, "draft": False,
                          "assets": [{"name": "tidy-2.0.0-win.zip"}]}]
        return s

    def test_versioned_names_are_flagged(self):
        rc, out, _ = self.run_solo("links", self.slug)
        self.assertEqual(rc, 1)
        self.assertIn("contains the version", out)
        _, _, st = self.audit()
        self.assertEqual(st["releases"]["status"], "warn")


class PermissionErrors(Base):
    slug = "seventhwell/tidy"

    @staticmethod
    def state():
        s = fixtures.configured()
        s["repo"]["permissions"] = {"admin": False, "push": True}
        return s

    def test_non_admin_is_reported_not_crashed(self):
        rc, _, st = self.audit()
        self.assertEqual(rc, 0)
        self.assertEqual(st["dependabot-alerts"]["status"], "warn")
        self.assertIn("admin", st["dependabot-alerts"]["message"])


class MissingRepo(Base):
    state = staticmethod(fixtures.configured)

    def test_not_found(self):
        rc, _, err = self.run_solo("audit", "seventhwell/nonexistent")
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)


# ---------------------------------------------------------------------------
class Helpers(unittest.TestCase):
    def test_push_trigger(self):
        f = solo.push_triggers_branch
        self.assertTrue(f("on:\n  push:\n    branches: [main]\n", "main"))
        self.assertTrue(f("on:\n  push:\n    branches:\n      - main\n      - dev\n", "main"))
        self.assertFalse(f("on:\n  push:\n    branches: [dev]\n", "main"))
        self.assertTrue(f("on:\n  push:\n    branches: ['**']\n", "main"))
        self.assertTrue(f("on:\n  push:\n", "main"))
        self.assertTrue(f("on: push\n", "main"))
        self.assertTrue(f("on: [push, pull_request]\n", "main"))
        self.assertTrue(f("on:\n  - push\n", "main"))
        self.assertFalse(f("on:\n  push:\n    tags: ['v*']\n", "main"))
        self.assertFalse(f("on:\n  pull_request:\n  workflow_dispatch:\n", "main"))
        self.assertFalse(f("on:\n  push:\n    branches-ignore: [main]\n", "main"))
        self.assertTrue(f("on:\n  push: # comment\n    paths: ['src/**']\n", "main"))
        self.assertTrue(f("on:\n  push:\n    branches: [main]\n  pull_request:\n", "main"))

    def test_release_indicators(self):
        s, w = solo.release_indicators("permissions:\n  contents: write\n- uses: softprops/action-gh-release@abc")
        self.assertEqual(s, ["softprops/action-gh-release"])
        self.assertEqual(w, ["contents: write"])
        self.assertEqual(solo.release_indicators("run: echo hi"), ([], []))

    def test_unpinned_uses(self):
        sha = "a" * 40
        text = ("- uses: actions/checkout@v4\n- uses: actions/setup-python@%s # v5\n"
                "- uses: ./local\n- uses: docker://alpine:3\n  uses: foo/bar@main\n" % sha)
        self.assertEqual(solo.unpinned_uses(text), ["actions/checkout@v4", "foo/bar@main"])

    def test_versioned_asset(self):
        self.assertTrue(solo.versioned_asset("app-1.2.0-win.zip"))
        self.assertTrue(solo.versioned_asset("app-v1.2-win.zip"))
        self.assertTrue(solo.versioned_asset("app-7-win.zip", "v7"))
        self.assertFalse(solo.versioned_asset("app-windows-x64.zip", "v1.2.0"))
        self.assertFalse(solo.versioned_asset("app_x86_64.dmg"))

    def test_detect_ecosystems(self):
        paths = {"package.json", "web/package.json", "requirements.txt", "requirements-dev.txt", "go.mod",
                 "Dockerfile", "docker/Dockerfile.prod", "App/App.csproj", "Cargo.toml", "composer.json",
                 "Gemfile", "vendor/x/package.json", "third_party/y/go.mod", ".github/workflows/a.yml",
                 "pyproject.toml", "uv.lock", "README.md"}
        ecos, vendored = solo.detect_ecosystems(paths)
        self.assertEqual(list(ecos)[0], "github-actions")
        self.assertEqual(ecos["npm"], ["/", "/web"])
        self.assertEqual(ecos["docker"], ["/", "/docker"])
        self.assertEqual(ecos["nuget"], ["/App"])
        self.assertEqual(ecos["gomod"], ["/"])
        self.assertEqual(ecos["uv"], ["/"])
        self.assertEqual(ecos["pip"], ["/"])  # requirements.txt keeps pip even next to uv.lock
        self.assertEqual(vendored, ["third_party", "vendor"])
        self.assertNotIn("/x", ecos["npm"])
        self.assertEqual(solo.detect_ecosystems({"pyproject.toml", "uv.lock"})[0], {"uv": ["/"]})

    def test_dependabot_yaml_shape(self):
        y = solo.dependabot_yaml({"npm": ["/", "/web"], "github-actions": ["/"]})
        self.assertIn('    directories:\n      - "/"\n      - "/web"\n', y)
        self.assertIn('directory: "/"', y)
        self.assertEqual(y.count('interval: "monthly"'), 2)

    def test_validate_topics(self):
        self.assertEqual(solo.validate_topics("Audio, live-streaming"), ["audio", "live-streaming"])
        with self.assertRaises(solo.SoloError):
            solo.validate_topics("bad topic")
        with self.assertRaises(solo.SoloError):
            solo.validate_topics("")

    def test_pages_url(self):
        self.assertEqual(solo.pages_url("me", "x"), "https://me.github.io/x/")
        self.assertEqual(solo.pages_url("me", "me.github.io"), "https://me.github.io/")


if __name__ == "__main__":
    unittest.main()

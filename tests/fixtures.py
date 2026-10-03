"""Scenario fixtures for the mock GitHub server (see mock_github.py)."""
import copy

ME = "seventhwell"

RELEASE_WORKFLOW = """name: release
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: gh release create "v$(date +%s)" --prerelease out/*.zip
"""

CI_WORKFLOW = """name: ci
on:
  pull_request:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: cmake -B build && cmake --build build
"""


def base(name="voicebooth", private=False):
    """A freshly created repo: nothing configured."""
    return {
        "repo": {
            "full_name": "%s/%s" % (ME, name), "name": name, "owner": {"login": ME},
            "private": private, "default_branch": "main", "description": None,
            "homepage": None, "topics": [], "license": None, "has_discussions": False,
            "delete_branch_on_merge": False,
            "permissions": {"admin": True, "push": True, "pull": True},
            "security_and_analysis": {
                "secret_scanning": {"status": "disabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
            },
        },
        "languages": {"Python": 1000},
        "tree": ["README.md", "app.py"],
        "files": {},
        "alerts": False,
        "security_fixes": {"enabled": False, "paused": False},
        "pvr": False,
        "codeql": {"state": "not-configured", "languages": []},
        "protection": None,
        "rulesets": [],
        "collaborators": [{"login": ME, "permissions": {"admin": True, "push": True, "pull": True}}],
        "workflow_perms": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        "pages": None,
        "releases": [],
        "uses_custom_og": False,
        "free_private": private,
    }


def voicebooth():
    """Scenario 1: public C++ app, only pre-releases with versioned assets, releases on push to main."""
    s = base("voicebooth")
    s["repo"]["description"] = "Voice booth app"
    s["repo"]["license"] = {"spdx_id": "MIT"}
    s["repo"]["security_and_analysis"] = {
        "secret_scanning": {"status": "enabled"},
        "secret_scanning_push_protection": {"status": "enabled"},
    }
    s["repo"]["topics"] = ["audio"]
    s["languages"] = {"C++": 90000, "CMake": 2000}
    s["tree"] = ["README.md", "LICENSE", "CMakeLists.txt", "src/main.cpp",
                 "third_party/imgui/package.json", "third_party/imgui/imgui.cpp",
                 ".github/workflows/release.yml", ".github/workflows/ci.yml", "SECURITY.md"]
    s["files"] = {".github/workflows/release.yml": RELEASE_WORKFLOW,
                  ".github/workflows/ci.yml": CI_WORKFLOW}
    s["workflow_perms"]["default_workflow_permissions"] = "write"
    s["releases"] = [
        {"tag_name": "v1.2.0", "prerelease": True, "draft": False,
         "assets": [{"name": "voicebooth-1.2.0-win64.zip"}, {"name": "voicebooth-1.2.0-mac.dmg"}]},
        {"tag_name": "v1.1.0", "prerelease": True, "draft": False,
         "assets": [{"name": "voicebooth-1.1.0-win64.zip"}]},
    ]
    s["uses_custom_og"] = True
    return s


def solo_blocker():
    """Scenario 2: classic protection with 1 required approval, only the owner can push."""
    s = base("lockedout")
    s["protection"] = {
        "required_pull_request_reviews": {"required_approving_review_count": 1,
                                          "require_code_owner_reviews": False},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }
    return s


def private_repo():
    """Scenario 3: private repo on a free plan."""
    s = base("secret-tool", private=True)
    s["languages"] = {"Python": 5000}
    return s


def configured():
    """Scenario 4: everything already in place."""
    s = base("tidy")
    r = s["repo"]
    r.update({"description": "A tidy repo", "homepage": "https://example.com", "topics": ["tool"],
              "license": {"spdx_id": "MIT"}, "has_discussions": True, "delete_branch_on_merge": True})
    r["security_and_analysis"] = {"secret_scanning": {"status": "enabled"},
                                  "secret_scanning_push_protection": {"status": "enabled"}}
    s["tree"] = ["README.md", "LICENSE", "SECURITY.md", "app.py", "requirements.txt",
                 ".github/dependabot.yml", ".github/release.yml", ".github/workflows/ci.yml"]
    s["files"] = {
        ".github/dependabot.yml": 'version: 2\nupdates:\n  - package-ecosystem: "github-actions"\n'
                                  '    directory: "/"\n  - package-ecosystem: "pip"\n    directory: "/"\n',
        ".github/workflows/ci.yml": CI_WORKFLOW,
    }
    s["alerts"] = True
    s["security_fixes"] = {"enabled": True, "paused": False}
    s["pvr"] = True
    s["codeql"] = {"state": "configured", "languages": ["python"]}
    s["rulesets"] = [{"id": 7, "name": "solo-guard", "enforcement": "active",
                      "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}]
    s["rulesets"].append({"id": 8, "name": "solo-tag-guard", "enforcement": "active", "target": "tag",
                          "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]})
    s["pages"] = {"html_url": "https://%s.github.io/tidy/" % ME, "source": {"branch": "main", "path": "/"}}
    s["releases"] = [{"tag_name": "v1.0.0", "prerelease": False, "draft": False,
                      "assets": [{"name": "tidy-windows.zip"}, {"name": "tidy-mac.dmg"}]}]
    s["uses_custom_og"] = True
    return s


def copy_of(state):
    return copy.deepcopy(state)

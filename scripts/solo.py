#!/usr/bin/env python3
"""github-solo: audit and safely configure a GitHub repo for a solo developer.

Standard library only (Python 3.9+). Talks to the GitHub REST / GraphQL API
directly. The API base can be overridden with SOLO_API_BASE (used by the test
mock server).

    solo.py audit [OWNER/REPO] [--json]
    solo.py apply [OWNER/REPO] [--yes] [--only ids] [--skip ids] ...
    solo.py links [OWNER/REPO]
    solo.py dependabot [OWNER/REPO]

Design rules: never add settings that lock a solo developer out of merging
their own PRs, only use free features, dry-run by default, idempotent, never
delete or overwrite anything that already exists.
"""
import argparse
import base64
import builtins
import contextlib
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.1.0"  # x-release-please-version
API_VERSION = os.environ.get("SOLO_API_VERSION", "2022-11-28")

OK, WARN, BAD, NA = "ok", "warn", "bad", "na"
ICON = {OK: "✅", WARN: "⚠️ ", BAD: "❌", NA: "➖"}
LABEL = {OK: "OK", WARN: "recommended", BAD: "action needed", NA: "n/a"}

SEC, SOLO, DIST, META = "Security", "Solo development", "Distribution", "Metadata"
CATEGORIES = [SEC, SOLO, DIST, META]

# apply ids, in execution order
DEFAULT_APPLY = [
    "dependabot-alerts", "dependabot-security-updates", "secret-scanning",
    "push-protection", "private-vuln-reporting", "codeql", "dependabot-config",
    "guardrail", "delete-branch-on-merge", "release-notes-config",
    "security-policy",
]
OPT_IN_APPLY = ["workflow-permissions", "discussions", "pages", "topics", "tag-guard", "labels",
                "community-files"]
OPT_IN_WHY = {
    "workflow-permissions": "can break existing workflows that rely on a write token",
    "discussions": "changes the public face of the repo",
    "pages": "publishes a public website",
    "topics": "changes the public face of the repo (needs --topics)",
    "tag-guard": "blocks deleting / force-moving v* tags; may break workflows that re-create tags",
    "labels": "adds labels the generated release.yml categories use (visible in the issue tracker)",
    "community-files": "adds issue / PR templates and CONTRIBUTING.md (public-facing once pushed)",
}
ALL_APPLY = DEFAULT_APPLY + OPT_IN_APPLY

# directories holding bundled third-party code: not tracked by dependabot.yml
VENDOR_DIRS = {"third_party", "thirdparty", "3rdparty", "vendor", "vendors",
               "external", "extern", "node_modules", "deps", "bower_components"}

CODEQL_LANG = {
    "C": "c-cpp", "C++": "c-cpp", "C#": "csharp", "Go": "go",
    "Java": "java-kotlin", "Kotlin": "java-kotlin",
    "JavaScript": "javascript-typescript", "TypeScript": "javascript-typescript",
    "Python": "python", "Ruby": "ruby", "Swift": "swift",
}

RELEASE_STRONG = [
    (r"gh\s+release\s+create", "gh release create"),
    (r"softprops/action-gh-release", "softprops/action-gh-release"),
    (r"release-please", "release-please"),
    (r"actions/create-release", "actions/create-release"),
    (r"ncipollo/release-action", "ncipollo/release-action"),
    (r"semantic-release", "semantic-release"),
    (r"changesets/action", "changesets/action"),
]
RELEASE_WEAK = [(r"contents:\s*write", "contents: write")]


# --------------------------------------------------------------------------
# Output language (messages are English; --lang ja / SOLO_LANG=ja translates the
# fixed phrases of the text output. JSON output is never translated.)
# --------------------------------------------------------------------------

LANG = [os.environ.get("SOLO_LANG") or ("ja" if os.environ.get("LANG", "").startswith("ja") else "en")]

JA_EXACT = {
    "\n" + SEC: "\nセキュリティ", "\n" + SOLO: "\n1人開発",
    "\n" + DIST: "\n配布", "\n" + META: "\nメタ情報",
}
JA = [
    ("github-solo audit:", "github-solo 診断:"),
    ("github-solo apply:", "github-solo 適用:"),
    ("(dry run)", "(ドライラン)"), ("(executing)", "(実行)"),
    ("default branch:", "デフォルトブランチ:"), ("(public,", "(公開,"), ("(private,", "(非公開,"),
    ("Summary: ", "サマリー: "), ("Score:", "スコア:"), (" ok, ", " OK, "), (" recommended, ", " 推奨, "),
    (" action needed, ", " 要対応, "), (" n/a", " 対象外"),
    ("Action needed items are never changed automatically; follow the fix lines above.",
     "要対応の項目は自動では変更しません。上に表示した対処コマンドを参照してください。"),
    ("Next: solo.py apply", "次の手順: solo.py apply"),
    ("(dry run; add --yes to execute)", "（ドライラン。実行するには --yes）"),
    ("No changes needed.", "変更は不要です。"),
    ("Dry run: nothing was changed. Re-run with --yes to execute.",
     "ドライラン: 何も変更していません。実行するには --yes を付けて再実行してください。"),
    ("Executing:", "実行中:"),
    ("Not applied by default (opt-in, use --only <id>):", "デフォルトでは適用しない項目（--only <id> で明示指定）:"),
    ("is never changed by apply:", "は apply では変更しません:"),
    ("Run `solo.py audit", "確認するには `solo.py audit"), ("` to verify.", "` を実行してください。"),
    ("Finished with", "完了（失敗あり）:"), ("failure(s)", "件の失敗"),
    ("WARNING: pushing to", "警告: 次のブランチへの push でリリースが走る可能性があります:"),
    ("may start a release workflow:", "（リリースワークフロー）:"),
    ("Committing the generated files (or pushing your local commit) can create a release.",
     "生成ファイルのコミット（またはローカルコミットの push）でリリースが作られる可能性があります。"),
    ("[weak signal]", "[弱いシグナル]"),
    ("could not read", "読み取れません"), ("see references/troubleshooting.md", "references/troubleshooting.md を参照"),
    ("cannot read (admin permission needed)", "読み取れません（admin 権限が必要）"),
    ("status not visible (admin permission needed)", "状態を取得できません（admin 権限が必要）"),
    ("private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped",
     "private リポ: 有料プラン（GitHub Secret Protection / Code Security）が必要なためスキップ"),
    ("private repo: rulesets need a paid plan, skipped", "private リポ: ruleset は有料プランが必要なためスキップ"),
    ("no CodeQL-supported language detected", "CodeQL 対応言語が見つかりません"),
    ("default setup configured", "default setup 設定済み"), ("default setup not configured", "default setup 未設定"),
    ("advanced setup via", "advanced setup（ワークフロー）:"),
    ("enabled but paused", "有効（一時停止中）"),
    ("disabled (opt-in: --only discussions)", "無効（任意: --only discussions）"),
    ("(opt-in: --only pages)", "（任意: --only pages）"),
    ("(opt-in: --only topics --topics a,b)", "（任意: --only topics --topics a,b）"),
    ("(opt-in: --only tag-guard)", "（任意: --only tag-guard）"),
    ("(opt-in fix; may break workflows that rely on it)", "（任意の修正。write に依存するワークフローが壊れる可能性）"),
    ("default GITHUB_TOKEN permission is write", "GITHUB_TOKEN のデフォルト権限が write"),
    ("default GITHUB_TOKEN permission is read", "GITHUB_TOKEN のデフォルト権限が read"),
    ("all actions pinned to a commit SHA", "すべての action がコミット SHA で固定済み"),
    ("action reference(s) not pinned to a commit SHA", "件の action 参照が SHA 固定されていません"),
    ("no approval-required rule on", "承認必須ルールなし:"),
    ("you cannot merge your own PRs:", "自分の PR をマージできません:"),
    ("not changed automatically", "自動では変更しません"),
    ("deleting / force-pushing", "削除 / force push が禁止済み:"),
    ("can be deleted / force-pushed", "は削除 / force push できます"),
    ("merged branches are deleted automatically", "マージ済みブランチは自動削除"),
    ("merged branches are kept", "マージ済みブランチが残る"),
    ("not set up; would publish", "未設定。公開予定:"),
    ("no releases yet", "リリースがありません"),
    ("all pre-releases: /releases/latest returns 404", "すべて Pre-release: /releases/latest は 404 になります"),
    ("release(s)", "件のリリース"),
    ("but every asset name contains a version, so a fixed /latest/download/ URL cannot work",
     "ただしすべてのアセット名にバージョンが入っており、固定の /latest/download/ URL は使えません"),
    ("will likely create a release", "リリースを作る可能性が高い"), ("may create a release", "リリースを作る可能性あり"),
    ("a push to", "push:"), ("committing files there can trigger it", "ここへファイルをコミットすると発火しうる"),
    ("(local only; review and commit it yourself)", "（ローカルのみ。内容を確認してコミットしてください）"),
    ("committed", "コミット済み:"), ("hint:", "ヒント:"),
    ("(this is not your PC); run solo.py in a terminal on your PC, or in Claude Code running on your PC", "（ここはあなたのPCではありません）。あなたのPCのターミナル、またはPCで動かしている Claude Code で solo.py を実行してください"),
    ("no workflow creates releases on push to", "push でリリースを作るワークフローなし:"),
    (".github/release.yml missing", ".github/release.yml がありません"),
    ("SECURITY.md missing", "SECURITY.md がありません"),
    ("empty (set it in the repo's About box)", "未設定（リポの About 欄で設定）"),
    ("none (", "なし（"),
    ("no license (your decision: https://choosealicense.com/ - not generated automatically)",
     "ライセンスなし（選択はあなたの判断: https://choosealicense.com/ 。自動生成しません）"),
    ("no custom social preview (cannot be set via API):", "social preview 未設定（API では設定不可）:"),
    ("custom social preview image set", "social preview 設定済み"),
    ("missing; detected:", "未作成。検出:"),
    ("bundled code under", "同梱コード"), ("is not tracked by Dependabot", "は Dependabot の追跡対象外"),
    ("(proposal only, file is not touched)", "（提案のみ。ファイルは変更しません）"),
    ("could be deleted / force-moved", "は削除 / 移動できます"),
    ("(it only reads real manifests outside those dirs)", "（それ以外の場所の実マニフェストのみ対象）"),
    ("release tags (v*) can be deleted / force-moved", "リリースタグ (v*) を削除 / 移動できます"),
    ("no index.html: the README is rendered as the top page", "index.html なし: README がトップページとして表示されます"),
    ("index.html found at the repo root", "ルートに index.html あり"), ("docs/index.html found", "docs/index.html あり"),
    ("(see: solo.py links)", "（solo.py links 参照）"), ("(see: solo.py links, references/release-latest.md)", "（solo.py links / references/release-latest.md 参照）"),
    ("tag ruleset active:", "タグ用 ruleset 有効:"), ("no releases yet, no release tags to protect", "リリース未作成のため保護対象のタグなし"),
    ("misses:", "不足:"), (" covers ", " 対象: "), ("missing; detected:", "未作成。検出:"),
    ("latest is", "latest は"), ("version-less asset(s)", "件のバージョン無しアセット"),
    ("disabled", "無効"), ("enabled", "有効"),
    ("create .github/dependabot.yml", ".github/dependabot.yml を作成"),
    ("create .github/release.yml", ".github/release.yml を作成"),
    ("create SECURITY.md", "SECURITY.md を作成"),
    ("write locally (you commit it)", "ローカルに書き出し（コミットはあなたが行う）"),
    ("already exists locally - left untouched", "ローカルに既にあるため変更しません"),
    ("will skip:", "スキップ:"),
    ("not a clone of this repo: run inside a clone, or pass --commit-files",
     "このリポの clone ではありません。clone 内で実行するか --commit-files を指定してください"),
    ("done ", "完了 "), ("FAILED", "失敗"), ("BLOCKED", "ブロック"),
    ("written", "書き出し"), ("skip ", "スキップ "),
]
JA.sort(key=lambda t: -len(t[0]))


def tr(text):
    if LANG[0] != "ja":
        return text
    if text in JA_EXACT:
        return JA_EXACT[text]
    for en, ja in JA:
        text = text.replace(en, ja)
    return text


def say(text="", **kw):
    builtins.print(tr(text), **kw)


class SoloError(Exception):
    pass


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Resp(object):
    def __init__(self, status, data, text="", headers=None):
        self.status = status
        self.data = data
        self.text = text
        self.headers = headers or {}

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def message(self):
        if isinstance(self.data, dict) and self.data.get("message"):
            return re.sub(r"[\x00-\x1f\x7f]", " ", str(self.data["message"]))
        return ""

    def describe(self):
        m = self.message
        return "HTTP %s%s" % (self.status, (": " + m) if m else "")


def get_token():
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    try:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True,
                           text=True, timeout=15)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class Api(object):
    def __init__(self, token, base=None):
        self.token = token
        self.base = (base or os.environ.get("SOLO_API_BASE")
                     or "https://api.github.com").rstrip("/")

    def url_for(self, path):
        """GraphQL lives at <host>/api/graphql on GitHub Enterprise Server (REST base <host>/api/v3)."""
        if path == "/graphql" and self.base.endswith("/api/v3"):
            return self.base[:-len("/v3")] + "/graphql"
        return self.base + path

    def request(self, method, path, body=None, params=None):
        url = self.url_for(path)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "github-solo/" + VERSION,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status, raw, rh = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, raw, rh = e.code, e.read(), e.headers
        except urllib.error.URLError as e:
            raise SoloError("network error talking to %s: %s" % (self.base, e.reason))
        text = raw.decode("utf-8", "replace") if raw else ""
        parsed = None
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
        return Resp(status, parsed, text, dict((k.lower(), v) for k, v in (rh.items() if rh else [])))

    def graphql(self, query, variables=None):
        return self.request("POST", "/graphql",
                            {"query": query, "variables": variables or {}})


# --------------------------------------------------------------------------
# Results / actions
# --------------------------------------------------------------------------

class R(object):
    """One check result."""

    def __init__(self, id, cat, status, msg, apply=None, actionable=False,
                 details=None, data=None):
        self.id = id
        self.cat = cat
        self.status = status
        self.msg = msg
        self.apply = apply
        self.actionable = actionable
        self.details = details or []
        self.data = data or {}

    def to_json(self):
        return {"id": self.id, "category": self.cat, "status": self.status,
                "message": self.msg, "apply": self.apply,
                "details": self.details}


class Action(object):
    """kind: api | file | note"""

    def __init__(self, id, kind, desc, method=None, path=None, body=None,
                 file_path=None, content=None, after=None, undo=None):
        self.id = id
        self.kind = kind
        self.desc = desc
        self.method = method
        self.path = path
        self.body = body
        self.file_path = file_path
        self.content = content
        self.after = after  # callable(resp, state) run after success
        self.undo = undo    # dict or callable(resp) -> dict {method, path, body}: how to revert this change

    def resolved_body(self, state):
        return self.body(state) if callable(self.body) else self.body


# --------------------------------------------------------------------------
# Context (repo snapshot, cached API reads)
# --------------------------------------------------------------------------

class Ctx(object):
    def __init__(self, api, owner, repo, local_root=None):
        self.api = api
        self.owner = owner
        self.repo = repo
        self.local_root = local_root
        self._cache = {}
        self.state = {}
        self.release_risk = []  # [(workflow path, [indicators], strong)]
        self.profile = "app"
        self.log = []
        self.undo = []
        self._info = None
        self._tree = None
        self._files = {}

    @property
    def slug(self):
        return "%s/%s" % (self.owner, self.repo)

    def p(self, suffix=""):
        return "/repos/%s/%s%s" % (self.owner, self.repo, suffix)

    def get(self, path, **params):
        key = (path, tuple(sorted(params.items())))
        if key not in self._cache:
            self._cache[key] = self.api.request("GET", path, params=params or None)
        return self._cache[key]

    @property
    def info(self):
        if self._info is None:
            r = self.get(self.p())
            if r.status == 404:
                raise SoloError("repository %s not found (or the token cannot see it)" % self.slug)
            if r.status in (401, 403):
                raise SoloError("cannot read %s: %s (see references/troubleshooting.md)" % (self.slug, r.describe()))
            if not r.ok or not isinstance(r.data, dict):
                raise SoloError("unexpected response for %s: %s" % (self.slug, r.describe()))
            self._info = r.data
        return self._info

    @property
    def private(self):
        return bool(self.info.get("private"))

    @property
    def branch(self):
        return self.info.get("default_branch") or "main"

    @property
    def admin(self):
        perms = self.info.get("permissions")
        if isinstance(perms, dict) and "admin" in perms:
            return bool(perms["admin"])
        return None

    @property
    def tree(self):
        """(set of blob paths, truncated)"""
        if self._tree is None:
            r = self.get(self.p("/git/trees/%s" % urllib.parse.quote(self.branch, safe="")),
                         recursive="1")
            paths, trunc = set(), False
            if r.ok and isinstance(r.data, dict):
                trunc = bool(r.data.get("truncated"))
                for t in r.data.get("tree", []):
                    if t.get("type") == "blob":
                        paths.add(t["path"])
            self._tree = (paths, trunc)
        return self._tree

    @property
    def paths(self):
        return self.tree[0]

    def read_file(self, path):
        if path not in self._files:
            r = self.get(self.p("/contents/" + urllib.parse.quote(path)), ref=self.branch)
            text = None
            if r.ok and isinstance(r.data, dict) and r.data.get("content") is not None:
                try:
                    text = base64.b64decode(r.data["content"]).decode("utf-8", "replace")
                except ValueError:
                    text = None
            self._files[path] = text
        return self._files[path]

    @property
    def workflow_paths(self):
        return sorted(p for p in self.paths
                      if re.match(r"^\.github/workflows/[^/]+\.ya?ml$", p))

    def workflows(self):
        out = {}
        for p in self.workflow_paths:
            t = self.read_file(p)
            if t is not None:
                out[p] = t
        return out

    def pushers(self):
        """logins with push access, or None if unreadable"""
        r = self.get(self.p("/collaborators"), per_page=100)
        if not r.ok or not isinstance(r.data, list):
            return None
        return [c.get("login") for c in r.data
                if (c.get("permissions") or {}).get("push")]


def unreadable(id, cat, resp, apply=None, extra=""):
    return R(id, cat, WARN,
             "could not read (%s)%s - see references/troubleshooting.md" % (resp.describe(), extra),
             apply=apply)


def public_only(id, cat, apply):
    return R(id, cat, NA,
             "private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped",
             apply=apply)


# --------------------------------------------------------------------------
# Pure helpers (also unit-tested)
# --------------------------------------------------------------------------

def _strip_comment(line):
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def push_triggers_branch(text, branch):
    """Heuristic: does this workflow run on a push to `branch`?"""
    lines = [_strip_comment(l) for l in text.splitlines()]
    joined = "\n".join(lines)
    m = re.search(r"^on:\s*(\S.*)$", joined, re.M)
    if m:
        v = m.group(1).strip()
        if re.fullmatch(r"push", v) or re.search(r"\[[^\]]*\bpush\b[^\]]*\]", v):
            return True
        if v.startswith("{"):
            inline = re.search(r"push\s*:\s*(\{[^}]*\})?", v)
            if not inline:
                return False
            return _push_block_matches(inline.group(1) or "", branch)
    if re.search(r"^on:\s*\n(\s+-\s*\S+\s*\n)*\s+-\s*push\s*$", joined + "\n", re.M):
        return True
    for i, line in enumerate(lines):
        m = re.match(r"^(\s+)push:\s*(.*)$", line)
        if not m:
            continue
        ind, rest = len(m.group(1)), m.group(2).strip()
        block = [rest] if rest else []
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                continue
            if _indent(nxt) <= ind:
                break
            block.append(nxt)
        return _push_block_matches("\n".join(block), branch)
    return False


def _push_block_matches(block, branch):
    block = block.strip()
    if block in ("", "{}", "null", "~"):
        return True

    def names(key):
        m = re.search(r"%s\s*:\s*\[([^\]]*)\]" % re.escape(key), block)
        if m:
            return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
        m = re.search(r"^\s*%s\s*:\s*$" % re.escape(key), block, re.M)
        if m:
            out = []
            for l in block[m.end():].splitlines():
                mm = re.match(r"^\s*-\s*(.+?)\s*$", l)
                if mm:
                    out.append(mm.group(1).strip("'\""))
                elif l.strip():
                    break
            return out
        m = re.search(r"%s\s*:\s*['\"]?([^\s,'\"}\[]+)" % re.escape(key), block)
        return [m.group(1)] if m else []

    def match(pats):
        for p in pats:
            if fnmatch.fnmatchcase(branch, p.replace("**", "*")):
                return True
        return False

    branches, ignore = names("branches"), names("branches-ignore")
    if branches:
        return match(branches)
    if ignore:
        return not match(ignore)
    if re.search(r"\btags(-ignore)?\s*:", block):
        return False  # tag-only filter
    return True


def release_indicators(text):
    strong = [name for pat, name in RELEASE_STRONG if re.search(pat, text)]
    weak = [name for pat, name in RELEASE_WEAK if re.search(pat, text)]
    return strong, weak


def unpinned_uses(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)", line)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        sha = ref.split("@", 1)[1] if "@" in ref else ""
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            out.append(ref)
    return out


_VERSION_RE = re.compile(r"(?<![A-Za-z0-9])v?\d+\.\d+(\.\d+)?")


def versioned_asset(name, tag=""):
    if _VERSION_RE.search(name):
        return True
    t = (tag or "").lstrip("vV")
    return bool(t) and t in name


def eco_for(name):
    if name == "package.json":
        return "npm"
    if re.fullmatch(r"requirements[-_.\w]*\.txt", name) or name in ("setup.py", "Pipfile", "pyproject.toml"):
        return "pip"
    if name == "uv.lock":
        return "uv"
    simple = {"Cargo.toml": "cargo", "go.mod": "gomod", "composer.json": "composer",
              "Gemfile": "bundler", "pom.xml": "maven", "build.gradle": "gradle",
              "build.gradle.kts": "gradle", "Package.swift": "swift",
              "pubspec.yaml": "pub", "mix.exs": "mix", "elm.json": "elm",
              "Chart.yaml": "helm", ".gitmodules": "gitsubmodule",
              ".pre-commit-config.yaml": "pre-commit", "packages.config": "nuget"}
    if name in simple:
        return simple[name]
    if name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
        return "docker"
    if re.fullmatch(r"(docker-compose[-.\w]*|compose)\.ya?ml", name):
        return "docker-compose"
    if re.search(r"\.(cs|fs|vb)proj$", name):
        return "nuget"
    if name.endswith(".tf"):
        return "terraform"
    return None


def detect_ecosystems(paths):
    """-> (OrderedDict-like {eco: [dirs]}, sorted vendored dir names seen)"""
    found = {}
    triggers = {}
    vendored = set()
    for p in sorted(paths):
        parts = p.split("/")
        hit = [x for x in parts[:-1] if x in VENDOR_DIRS]
        if hit:
            vendored.add(hit[0])
            continue
        if re.match(r"^\.github/workflows/[^/]+\.ya?ml$", p):
            found.setdefault("github-actions", set()).add("/")
            continue
        if parts[0] == ".github":
            continue
        eco = eco_for(parts[-1])
        if not eco:
            continue
        d = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
        found.setdefault(eco, set()).add(d)
        triggers.setdefault((eco, d), set()).add(parts[-1])
    # uv owns a dir whose only python trigger is pyproject.toml
    for d in list(found.get("uv", [])):
        if triggers.get(("pip", d)) == {"pyproject.toml"}:
            found["pip"].discard(d)
            if not found["pip"]:
                del found["pip"]
    ordered = {}
    for eco in sorted(found, key=lambda e: (e != "github-actions", e)):
        ordered[eco] = sorted(found[eco])
    return ordered, sorted(vendored)


def parse_dependabot(text):
    """-> {ecosystem: set(directory patterns)} from an existing dependabot.yml (line based)."""
    entries, cur, in_updates, ind = [], None, False, None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if re.match(r"^updates:\s*$", line):
            in_updates = True
            continue
        if in_updates and re.match(r"^\S", line):
            in_updates = False
        if not in_updates:
            continue
        m = re.match(r"^(\s*)-\s+\S", line)
        if m and (ind is None or len(m.group(1)) == ind):
            ind = len(m.group(1))
            cur = []
            entries.append(cur)
        if cur is not None:
            cur.append(line)
    out = {}
    for e in entries:
        blk = "\n".join(e)
        m = re.search(r"package-ecosystem:\s*['\"]?([\w-]+)", blk)
        if not m:
            continue
        dirs = out.setdefault(m.group(1), set())
        for d in re.findall(r"(?m)^\s*(?:-\s+)?directory:\s*['\"]?([^'\"\s]+)", blk):
            dirs.add(d)
        m = re.search(r"(?m)^(\s*)(?:-\s+)?directories:\s*(?:\[(.*)\])?\s*$", blk)
        if m:
            if m.group(2) is not None:
                for x in m.group(2).split(","):
                    if x.strip():
                        dirs.add(x.strip().strip("'\""))
            else:
                for l in blk[m.end():].splitlines():
                    mm = re.match(r"^\s*-\s*['\"]?([^'\"\s]+)", l)
                    if mm:
                        dirs.add(mm.group(1))
                    elif l.strip():
                        break
    return out


def dir_covered(d, patterns):
    return any(fnmatch.fnmatchcase(d, pat.replace("**", "*")) for pat in patterns)


def dependabot_entries(ecos):
    out = []
    for eco, dirs in ecos.items():
        out.append('  - package-ecosystem: "%s"' % eco)
        if len(dirs) == 1:
            out.append('    directory: "%s"' % dirs[0])
        else:
            out.append("    directories:")
            out.extend('      - "%s"' % d for d in dirs)
        out += ['    schedule:', '      interval: "monthly"', '    groups:',
                '      all:', '        patterns:', '          - "*"']
    return "\n".join(out) + "\n"


def dependabot_yaml(ecos):
    return "version: 2\nupdates:\n" + dependabot_entries(ecos)


RELEASE_YML = """# Categories for GitHub's auto-generated release notes (Releases -> Generate release notes).
# Docs: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
changelog:
  exclude:
    authors:
      - dependabot
      - dependabot[bot]
  categories:
    - title: Breaking Changes
      labels:
        - breaking-change
    - title: New Features
      labels:
        - enhancement
        - feature
    - title: Bug Fixes
      labels:
        - bug
        - fix
    - title: Other Changes
      labels:
        - "*"
"""


WANTED_LABELS = [("breaking-change", "b60205", "Incompatible change"), ("enhancement", "a2eeef", "New feature or request"),
                 ("bug", "d73a4a", "Something is not working")]

PR_TEMPLATE = """## What and why

<!-- One or two sentences. Link the issue if there is one: Fixes #123 -->

## How it was tested

<!-- Commands you ran, or "not applicable". -->

## Checklist

- [ ] Docs / README updated if behavior changed
- [ ] Tests added or updated
"""

BUG_TEMPLATE = """---
name: Bug report
about: Something does not work as expected
labels: bug
---

**What happened**

**What you expected**

**Steps to reproduce**
1.

**Environment** (OS, version, how you installed it)
"""

FEATURE_TEMPLATE = """---
name: Feature request
about: Suggest an improvement
labels: enhancement
---

**The problem you want solved**

**What you would like**

**Alternatives you considered**
"""


def contributing_md(repo):
    return """# Contributing to %s

Thanks for helping! This is a small project, so keep it simple:

1. Open an issue first for anything bigger than a typo or a one-line fix, so we can agree on the direction.
2. Fork, create a branch, make your change, and open a pull request describing what and why.
3. Add or update tests when behavior changes, and run them before you push.

Security problems: please follow SECURITY.md instead of opening a public issue.
""" % repo


RELEASE_WORKFLOW_TEMPLATE = """# Publishes a normal (non pre-) release when you push a tag like v1.2.3, with a version-less copy of each asset
# so that https://github.com/OWNER/REPO/releases/latest/download/app-win64.zip never changes.
# Replace the Build step and the file names. Pin each `uses:` to a full commit SHA (github-solo flags unpinned ones).
name: release
on:
  push:
    tags: ["v*"]          # tags only: pushing to the default branch never releases
permissions:
  contents: write         # needed to create the release
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-commit-sha>   # vX.Y.Z
      - name: Build
        run: ./build.sh                             # must produce dist/app-<version>-win64.zip
      - name: Add version-less copies
        run: |
          VER="${GITHUB_REF_NAME#v}"
          cp "dist/app-$VER-win64.zip" dist/app-win64.zip
      - name: Publish
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" dist/*.zip --title "$GITHUB_REF_NAME" --generate-notes
"""


def security_md(owner, repo):
    return """# Security Policy

## Supported versions

Only the latest release (or the default branch when there is no release yet)
receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report it privately through GitHub's private vulnerability reporting:

<https://github.com/%s/%s/security/advisories/new>

(Repository page -> **Security** tab -> **Report a vulnerability**.)

Please include what you found, how to reproduce it, and the affected version.
This project is maintained by one person, so replies are best-effort.
""" % (owner, repo)


def parse_slug(s):
    m = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", s or "")
    return (m.group(1), m.group(2)) if m else None


def git_origin():
    """-> (owner, repo, toplevel) from the cwd's git remote origin, or None"""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=10)
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if url.returncode != 0 or top.returncode != 0:
        return None
    m = re.search(r"([^/:]+)/([^/]+?)(?:\.git)?/?$", url.stdout.strip())
    if not m:
        return None
    return m.group(1), m.group(2), top.stdout.strip()


def resolve_target(arg):
    origin = git_origin()
    if arg:
        slug = parse_slug(arg)
        if not slug:
            raise SoloError("repo must look like OWNER/REPO, got %r" % arg)
        local = None
        if origin and (origin[0].lower(), origin[1].lower()) == (slug[0].lower(), slug[1].lower()):
            local = origin[2]
        return slug[0], slug[1], local
    if not origin:
        raise SoloError("no OWNER/REPO given and the current directory has no git remote 'origin'")
    return origin[0], origin[1], origin[2]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_alerts(ctx):
    id = "dependabot-alerts"
    if ctx.admin is False:
        return [R(id, SEC, WARN, "cannot read (admin permission needed)", apply=id)]
    r = ctx.get(ctx.p("/vulnerability-alerts"))
    if r.status == 204:
        return [R(id, SEC, OK, "enabled")]
    if r.status == 404:
        return [R(id, SEC, WARN, "disabled", apply=id, actionable=True)]
    return [unreadable(id, SEC, r, apply=id)]


def check_security_updates(ctx):
    id = "dependabot-security-updates"
    if ctx.admin is False:
        return [R(id, SEC, WARN, "cannot read (admin permission needed)", apply=id)]
    r = ctx.get(ctx.p("/automated-security-fixes"))
    if r.ok and isinstance(r.data, dict):
        if r.data.get("enabled") and r.data.get("paused"):
            return [R(id, SEC, WARN, "enabled but paused", apply=id)]
        if r.data.get("enabled"):
            return [R(id, SEC, OK, "enabled")]
        return [R(id, SEC, WARN, "disabled", apply=id, actionable=True)]
    if r.status == 404:
        return [R(id, SEC, WARN, "disabled", apply=id, actionable=True)]
    return [unreadable(id, SEC, r, apply=id)]


def check_secret_scanning(ctx):
    out = []
    sa = ctx.info.get("security_and_analysis")
    for id, key in (("secret-scanning", "secret_scanning"),
                    ("push-protection", "secret_scanning_push_protection")):
        if ctx.private:
            out.append(public_only(id, SEC, id))
            continue
        if not isinstance(sa, dict) or key not in sa:
            out.append(R(id, SEC, WARN, "status not visible (admin permission needed)", apply=id))
            continue
        st = (sa[key] or {}).get("status")
        if st == "enabled":
            out.append(R(id, SEC, OK, "enabled"))
        else:
            out.append(R(id, SEC, WARN, "disabled", apply=id, actionable=True))
    return out


def check_pvr(ctx):
    id = "private-vuln-reporting"
    if ctx.private:
        return [public_only(id, SEC, id)]
    r = ctx.get(ctx.p("/private-vulnerability-reporting"))
    if r.ok and isinstance(r.data, dict):
        if r.data.get("enabled"):
            return [R(id, SEC, OK, "enabled")]
        return [R(id, SEC, WARN, "disabled", apply=id, actionable=True)]
    return [unreadable(id, SEC, r, apply=id)]


def check_codeql(ctx):
    id = "codeql"
    if ctx.private:
        return [public_only(id, SEC, id)]
    for path, text in ctx.workflows().items():
        if "github/codeql-action" in text:
            return [R(id, SEC, OK, "advanced setup via %s" % path)]
    lr = ctx.get(ctx.p("/languages"))
    langs = sorted({CODEQL_LANG[k] for k in (lr.data or {}) if k in CODEQL_LANG}) \
        if lr.ok and isinstance(lr.data, dict) else []
    if not langs:
        return [R(id, SEC, NA, "no CodeQL-supported language detected")]
    r = ctx.get(ctx.p("/code-scanning/default-setup"))
    if r.ok and isinstance(r.data, dict):
        if r.data.get("state") == "configured":
            return [R(id, SEC, OK, "default setup configured (%s)" % ", ".join(r.data.get("languages") or langs))]
        return [R(id, SEC, WARN, "default setup not configured (%s)" % ", ".join(langs),
                  apply=id, actionable=True)]
    return [unreadable(id, SEC, r, apply=id)]


def check_dependabot_config(ctx):
    id = "dependabot-config"
    ecos, vendored = detect_ecosystems(ctx.paths)
    notes = []
    if vendored:
        notes.append("bundled code under %s/ is not tracked by Dependabot (it only reads real manifests outside those dirs)"
                     % "/, ".join(vendored))
    if ctx.tree[1]:
        notes.append("git tree was truncated; ecosystem detection may be incomplete")
    existing = [p for p in (".github/dependabot.yml", ".github/dependabot.yaml") if p in ctx.paths]
    data = {"ecosystems": ecos, "vendored": vendored}
    if existing:
        have = parse_dependabot(ctx.read_file(existing[0]) or "")
        missing = {e: d for e, d in ecos.items() if e not in have}
        missing_dirs = {}
        for e, dirs in ecos.items():
            if e in have and e != "github-actions":
                gap = [d for d in dirs if not dir_covered(d, have[e])]
                if gap:
                    missing_dirs[e] = gap
        if missing or missing_dirs:
            data["missing"] = missing
            data["missing_dirs"] = missing_dirs
            parts = []
            if missing:
                parts.append(", ".join(missing))
            for e, gap in missing_dirs.items():
                parts.append("%s in %s" % (e, ", ".join(gap)))
            return [R(id, SEC, WARN, "%s misses: %s (proposal only, file is not touched)"
                      % (existing[0], "; ".join(parts)), apply=id, actionable=True,
                      details=notes, data=data)]
        return [R(id, SEC, OK, "%s covers %s" % (existing[0], ", ".join(sorted(have)) or "-"),
                  details=notes, data=data)]
    if not ecos:
        return [R(id, SEC, NA, "no Dependabot-supported manifest detected", details=notes, data=data)]
    return [R(id, SEC, WARN, "missing; detected: %s" % ", ".join(ecos), apply=id,
              actionable=True, details=notes, data=data)]


def detect_release_risk(wfs, branch):
    """[(workflow path, [indicators], strong)] for workflows a push to `branch` may turn into a release.
    Follows `uses: ./.github/workflows/x.yml` calls; an `if:` on refs/tags downgrades to weak."""
    info = {}
    for path, text in wfs.items():
        strong, weak = release_indicators(text)
        if not (strong or weak):
            continue
        cond = bool(re.search(r"^\s*(?:-\s*)?if:.*refs/tags/", text, re.M))
        inds = list(strong or weak)
        if cond:
            inds.append("if: refs/tags (conditional)")
        info[path] = (inds, bool(strong) and not cond)
    risky = []
    for path, text in wfs.items():
        if not push_triggers_branch(text, branch):
            continue
        if path in info:
            risky.append((path, info[path][0], info[path][1]))
        for ref in re.findall(r"uses:\s*['\"]?\./(\.github/workflows/[^\s'\"@#]+\.ya?ml)", text):
            if ref in info and ref != path:
                risky.append((ref, info[ref][0] + ["called from " + path], info[ref][1]))
    return risky


def check_pinning_and_release(ctx):
    wfs = ctx.workflows()
    if not wfs:
        return [R("actions-pinning", SEC, NA, "no workflows"),
                R("release-workflow", DIST, OK, "no workflows")]
    unpinned = {}
    for path, text in wfs.items():
        u = unpinned_uses(text)
        if u:
            unpinned[path] = u
    if unpinned:
        n = sum(len(v) for v in unpinned.values())
        det = ["%s: %s" % (p, ", ".join(sorted(set(v)))) for p, v in sorted(unpinned.items())]
        pin = R("actions-pinning", SEC, WARN, "%d action reference(s) not pinned to a commit SHA" % n,
                details=det)
    else:
        pin = R("actions-pinning", SEC, OK, "all actions pinned to a commit SHA")

    risky = detect_release_risk(wfs, ctx.branch)
    ctx.release_risk = risky
    if risky:
        det = ["%s (%s)" % (p, ", ".join(ind)) for p, ind, _ in risky]
        strong = any(s for _, _, s in risky)
        rel = R("release-workflow", DIST, WARN,
                "a push to %s %s create a release (%s) - committing files there can trigger it"
                % (ctx.branch, "will likely" if strong else "may", ", ".join(p for p, _, _ in risky)),
                details=det)
    else:
        rel = R("release-workflow", DIST, OK, "no workflow creates releases on push to %s" % ctx.branch)
    return [pin, rel]


def check_workflow_permissions(ctx):
    id = "workflow-permissions"
    if ctx.admin is False:
        return [R(id, SEC, WARN, "cannot read (admin permission needed)", apply=id)]
    r = ctx.get(ctx.p("/actions/permissions/workflow"))
    if r.ok and isinstance(r.data, dict):
        if r.data.get("default_workflow_permissions") == "write":
            return [R(id, SEC, WARN,
                      "default GITHUB_TOKEN permission is write (opt-in fix; may break workflows that rely on it)",
                      apply=id, actionable=True)]
        return [R(id, SEC, OK, "default GITHUB_TOKEN permission is read")]
    return [unreadable(id, SEC, r, apply=id)]


def _ruleset_fix(ctx, rule_id):
    return ("gh api -X PUT repos/%s/rulesets/%s -f enforcement=disabled   # or edit: https://github.com/%s/settings/rules/%s"
            % (ctx.slug, rule_id, ctx.slug, rule_id))


def check_solo_blocker(ctx):
    id = "solo-blocker"
    b = urllib.parse.quote(ctx.branch, safe="")
    reasons, fixes = [], []
    prot = ctx.get(ctx.p("/branches/%s/protection" % b))
    if prot.status == 200 and isinstance(prot.data, dict):
        rv = prot.data.get("required_pull_request_reviews") or {}
        n = rv.get("required_approving_review_count") or 0
        if n >= 1:
            reasons.append("classic branch protection requires %d approving review(s)" % n)
        if rv.get("require_code_owner_reviews"):
            reasons.append("classic branch protection requires code owner review")
        if reasons:
            fixes.append("gh api -X DELETE repos/%s/branches/%s/protection/required_pull_request_reviews"
                         % (ctx.slug, ctx.branch))
            fixes.append("settings: https://github.com/%s/settings/branches" % ctx.slug)
            if (prot.data.get("enforce_admins") or {}).get("enabled"):
                reasons.append("enforce_admins is on (even the admin cannot bypass)")
                fixes.append("gh api -X DELETE repos/%s/branches/%s/protection/enforce_admins"
                             % (ctx.slug, ctx.branch))
    rules = ctx.get(ctx.p("/rules/branches/%s" % b))
    if rules.ok and isinstance(rules.data, list):
        for rule in rules.data:
            if rule.get("type") != "pull_request":
                continue
            pr = rule.get("parameters") or {}
            n = pr.get("required_approving_review_count") or 0
            co = pr.get("require_code_owner_review")
            if n >= 1 or co:
                parts = []
                if n >= 1:
                    parts.append("%d approving review(s)" % n)
                if co:
                    parts.append("code owner review")
                reasons.append("ruleset #%s requires %s" % (rule.get("ruleset_id"), " and ".join(parts)))
                fixes.append(_ruleset_fix(ctx, rule.get("ruleset_id")))
    if not reasons:
        return [R(id, SOLO, OK, "no approval-required rule on %s" % ctx.branch)]
    pushers = ctx.pushers()
    if pushers is None:
        return [R(id, SOLO, WARN, "approval rule found but collaborators are unreadable; cannot tell if you are solo",
                  details=reasons + fixes)]
    if len(pushers) <= 1:
        return [R(id, SOLO, BAD, "you cannot merge your own PRs: " + "; ".join(reasons),
                  details=["only %s can push" % (pushers[0] if pushers else "you")] + fixes
                  + ["not changed automatically"])]
    return [R(id, SOLO, OK, "approval required, but %d people can push (team repo, not a solo lock-in)" % len(pushers),
              details=reasons)]


def check_guardrail(ctx):
    id = "guardrail"
    b = urllib.parse.quote(ctx.branch, safe="")
    rs = ctx.get(ctx.p("/rulesets"), per_page=100)
    if rs.status == 403 and ctx.private:
        return [R(id, SOLO, NA, "private repo: rulesets need a paid plan, skipped", apply=id)]
    if not rs.ok or not isinstance(rs.data, list):
        return [unreadable(id, SOLO, rs, apply=id)]
    types, via = set(), []
    rules = ctx.get(ctx.p("/rules/branches/%s" % b))
    if rules.ok and isinstance(rules.data, list):
        t = {x.get("type") for x in rules.data}
        types |= t
        if t & {"deletion", "non_fast_forward"}:
            via.append("rulesets")
    prot = ctx.get(ctx.p("/branches/%s/protection" % b))
    if prot.status == 200 and isinstance(prot.data, dict):
        if not (prot.data.get("allow_force_pushes") or {}).get("enabled"):
            types.add("non_fast_forward")
        if not (prot.data.get("allow_deletions") or {}).get("enabled"):
            types.add("deletion")
        via.append("branch protection")
    if {"deletion", "non_fast_forward"} <= types:
        return [R(id, SOLO, OK, "deleting / force-pushing %s is blocked (%s)" % (ctx.branch, " + ".join(via)))]
    existing = [x for x in rs.data if x.get("name") == "solo-guard"]
    if existing:
        return [R(id, SOLO, WARN, "ruleset solo-guard exists but is not active (enforcement=%s); not touched"
                  % existing[0].get("enforcement"), apply=id)]
    return [R(id, SOLO, WARN, "%s can be deleted / force-pushed" % ctx.branch, apply=id, actionable=True)]


def check_tag_guard(ctx):
    id = "tag-guard"
    rs = ctx.get(ctx.p("/rulesets"), per_page=100)
    if rs.status == 403 and ctx.private:
        return [R(id, SOLO, NA, "private repo: rulesets need a paid plan, skipped", apply=id)]
    if not rs.ok or not isinstance(rs.data, list):
        return [unreadable(id, SOLO, rs, apply=id)]
    rels, _ = fetch_releases(ctx)
    if not rels:
        return [R(id, SOLO, NA, "no releases yet, no release tags to protect")]
    tag_sets = [x for x in rs.data if x.get("target") == "tag"]
    active = [x for x in tag_sets if x.get("enforcement") == "active"]
    if active:
        return [R(id, SOLO, OK, "tag ruleset active: %s" % ", ".join(x.get("name", "?") for x in active))]
    if any(x.get("name") == "solo-tag-guard" for x in tag_sets):
        return [R(id, SOLO, WARN, "ruleset solo-tag-guard exists but is not active; not touched", apply=id)]
    return [R(id, SOLO, WARN, "release tags (v*) can be deleted / force-moved (opt-in: --only tag-guard)",
              apply=id, actionable=True)]


def check_delete_branch(ctx):
    id = "delete-branch-on-merge"
    if ctx.info.get("delete_branch_on_merge"):
        return [R(id, SOLO, OK, "merged branches are deleted automatically")]
    return [R(id, SOLO, WARN, "merged branches are kept", apply=id, actionable=True)]


def check_discussions(ctx):
    id = "discussions"
    if ctx.info.get("has_discussions"):
        return [R(id, SOLO, OK, "enabled")]
    return [R(id, SOLO, WARN, "disabled (opt-in: --only discussions)", apply=id, actionable=True)]


def pages_source(ctx, override=None):
    """-> (path, note)"""
    if override:
        return override, "path given with --pages-path"
    if "docs/index.html" in ctx.paths:
        return "/docs", "docs/index.html found"
    if "index.html" in ctx.paths:
        return "/", "index.html found at the repo root"
    return "/", "no index.html: the README is rendered as the top page"


def pages_url(owner, repo):
    if repo.lower() == (owner + ".github.io").lower():
        return "https://%s.github.io/" % owner
    return "https://%s.github.io/%s/" % (owner, repo)


def check_pages(ctx):
    id = "pages"
    r = ctx.get(ctx.p("/pages"))
    if r.ok and isinstance(r.data, dict):
        return [R(id, DIST, OK, "enabled: %s" % r.data.get("html_url", ""))]
    if r.status == 404:
        path, note = pages_source(ctx)
        return [R(id, DIST, WARN, "not set up; would publish %s of %s (%s) (opt-in: --only pages)"
                  % (path, ctx.branch, note), apply=id, actionable=True)]
    return [unreadable(id, DIST, r, apply=id)]


def fetch_releases(ctx):
    r = ctx.get(ctx.p("/releases"), per_page=100)
    if not r.ok or not isinstance(r.data, list):
        return None, r
    return [x for x in r.data if not x.get("draft")], r


def check_releases(ctx):
    id = "releases"
    rels, r = fetch_releases(ctx)
    if rels is None:
        return [unreadable(id, DIST, r)]
    if not rels:
        return [R(id, DIST, WARN, "no releases yet (see: solo.py links, references/release-latest.md)")]
    latest = [x for x in rels if not x.get("prerelease")]
    if not latest:
        return [R(id, DIST, WARN,
                  "%d release(s), all pre-releases: /releases/latest returns 404 (see: solo.py links)" % len(rels))]
    top = latest[0]
    assets = [a.get("name", "") for a in top.get("assets", [])]
    vers = [a for a in assets if versioned_asset(a, top.get("tag_name", ""))]
    if ctx.profile == "library":
        return [R(id, DIST, OK, "latest is %s (profile library: asset names do not matter)" % top.get("tag_name"))]
    if assets and len(vers) == len(assets):
        return [R(id, DIST, WARN,
                  "latest is %s but every asset name contains a version, so a fixed /latest/download/ URL cannot work"
                  % top.get("tag_name"), details=vers)]
    return [R(id, DIST, OK, "latest is %s with %d version-less asset(s)" % (
        top.get("tag_name"), len(assets) - len(vers)))]


def check_release_notes(ctx):
    id = "release-notes-config"
    if ".github/release.yml" in ctx.paths or ".github/release.yaml" in ctx.paths:
        return [R(id, DIST, OK, ".github/release.yml present")]
    return [R(id, DIST, WARN, ".github/release.yml missing", apply=id, actionable=True)]


def check_labels(ctx):
    id = "labels"
    r = ctx.get(ctx.p("/labels"), per_page=100)
    if not r.ok or not isinstance(r.data, list):
        return [unreadable(id, META, r, apply=id)]
    have = {x.get("name", "").lower() for x in r.data}
    missing = [w for w in WANTED_LABELS if w[0] not in have]
    if not missing:
        return [R(id, META, OK, "labels used by release.yml exist")]
    return [R(id, META, WARN, "missing labels: %s (opt-in: --only labels)" % ", ".join(m[0] for m in missing),
              apply=id, actionable=True, data={"missing": missing})]


COMMUNITY_FILES = [
    ("pr-template", ".github/pull_request_template.md",
     (".github/pull_request_template.md", "pull_request_template.md", "docs/pull_request_template.md",
      ".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md", "docs/PULL_REQUEST_TEMPLATE.md")),
    ("bug-template", ".github/ISSUE_TEMPLATE/bug_report.md", ()),
    ("feature-template", ".github/ISSUE_TEMPLATE/feature_request.md", ()),
    ("contributing", "CONTRIBUTING.md", ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md")),
]


def community_missing(ctx):
    paths = ctx.paths
    has_issue_tpl = any(p.startswith(".github/ISSUE_TEMPLATE/") for p in paths) or \
        ".github/ISSUE_TEMPLATE.md" in paths or "ISSUE_TEMPLATE.md" in paths
    out = []
    for key, target, aliases in COMMUNITY_FILES:
        if key in ("bug-template", "feature-template"):
            if not has_issue_tpl:
                out.append((key, target))
        elif not any(a in paths for a in aliases):
            out.append((key, target))
    return out


def check_community_files(ctx):
    id = "community-files"
    missing = community_missing(ctx)
    if not missing:
        return [R(id, META, OK, "PR template, issue templates and CONTRIBUTING present")]
    return [R(id, META, WARN, "missing: %s (opt-in: --only community-files)" % ", ".join(t for _, t in missing),
              apply=id, actionable=True, data={"missing": missing})]


def check_meta(ctx):
    out = []
    i = ctx.info
    out.append(R("description", META, OK if i.get("description") else WARN,
                 "set" if i.get("description") else "empty (set it in the repo's About box)"))
    if i.get("topics"):
        out.append(R("topics", META, OK, "topics: %s" % ", ".join(i["topics"])))
    else:
        out.append(R("topics", META, WARN, "none (opt-in: --only topics --topics a,b)",
                     apply="topics", actionable=True))
    if i.get("license"):
        out.append(R("license", META, OK, (i["license"] or {}).get("spdx_id") or "present"))
    else:
        out.append(R("license", META, WARN,
                     "no license (your decision: https://choosealicense.com/ - not generated automatically)"))
    sec = [p for p in ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md") if p in ctx.paths]
    if sec:
        out.append(R("security-policy", META, OK, sec[0]))
    else:
        out.append(R("security-policy", META, WARN, "SECURITY.md missing", apply="security-policy",
                     actionable=True))
    g = ctx.api.graphql("query($o:String!,$n:String!){repository(owner:$o,name:$n){usesCustomOpenGraphImage}}",
                        {"o": ctx.owner, "n": ctx.repo})
    repo = ((g.data or {}).get("data") or {}).get("repository") if g.ok and isinstance(g.data, dict) else None
    if repo is None:
        out.append(unreadable("social-preview", META, g))
    elif repo.get("usesCustomOpenGraphImage"):
        out.append(R("social-preview", META, OK, "custom social preview image set"))
    else:
        out.append(R("social-preview", META, WARN,
                     "no custom social preview (cannot be set via API): https://github.com/%s/settings" % ctx.slug))
    return out


CHECKS = [check_alerts, check_security_updates, check_secret_scanning, check_pvr,
          check_codeql, check_dependabot_config, check_pinning_and_release,
          check_workflow_permissions, check_solo_blocker, check_guardrail, check_tag_guard,
          check_delete_branch, check_discussions, check_pages, check_releases,
          check_release_notes, check_meta, check_labels, check_community_files]


PROFILES = ["app", "library", "site", "docs"]
# checks that make no sense for a kind of repo are shown as n/a instead of nagging
PROFILE_NA = {
    "site": {"releases": "a website is not released as downloads", "release-notes-config": "a website has no release notes",
             "tag-guard": "a website has no release tags"},
    "docs": {"releases": "a docs repo is not released as downloads", "release-notes-config": "a docs repo has no release notes",
             "tag-guard": "a docs repo has no release tags"},
}


def run_checks(ctx):
    results = []
    for fn in CHECKS:
        results.extend(fn(ctx))
    skip = PROFILE_NA.get(ctx.profile, {})
    for r in results:
        if r.id in skip and r.status in (WARN, OK):
            r.status, r.msg, r.actionable = NA, "profile %s: %s" % (ctx.profile, skip[r.id]), False
    return results


def score(results):
    """0-100: ok = 1 point, recommended = half, action needed = 0, n/a excluded."""
    s = summarize(results)
    n = s[OK] + s[WARN] + s[BAD]
    return 100 if n == 0 else int(round(100.0 * (s[OK] + 0.5 * s[WARN]) / n))


def summarize(results):
    s = {OK: 0, WARN: 0, BAD: 0, NA: 0}
    for r in results:
        s[r.status] += 1
    return s


def print_audit(ctx, results, quiet=False):
    vis = "private" if ctx.private else "public"
    say("github-solo audit: %s (%s, default branch: %s)" % (ctx.slug, vis, ctx.branch))
    width = max(len(r.id) for r in results)
    for cat in CATEGORIES:
        rows = [r for r in results if r.cat == cat and not (quiet and r.status in (OK, NA))]
        if not rows:
            continue
        say("\n%s" % cat)
        for r in rows:
            tail = ("  -> apply: %s" % r.apply) if r.apply and r.status in (WARN, BAD) and r.actionable else ""
            say("  %s %-*s  %s%s" % (ICON[r.status], width, r.id, r.msg, tail))
            for d in r.details:
                say("       %s" % d)
    s = summarize(results)
    say("\nSummary: %d ok, %d recommended, %d action needed, %d n/a   Score: %d/100" % (
        s[OK], s[WARN], s[BAD], s[NA], score(results)))
    if s[BAD]:
        say("Action needed items are never changed automatically; follow the fix lines above.")
    elif any(r.actionable for r in results):
        say("Next: solo.py apply %s   (dry run; add --yes to execute)" % ctx.slug)


# --------------------------------------------------------------------------
# Apply planning
# --------------------------------------------------------------------------

def _undo(method, path, body=None):
    return {"method": method, "path": path, "body": body}


def _undo_ruleset(ctx):
    def undo(resp):
        rid = (resp.data or {}).get("id") if isinstance(resp.data, dict) else None
        return _undo("DELETE", ctx.p("/rulesets/%s" % rid)) if rid is not None else None
    return undo


def validate_topics(raw):
    names = [t.strip().lower() for t in (raw or "").split(",") if t.strip()]
    if not names:
        raise SoloError("--only topics needs --topics a,b,c")
    if len(names) > 20:
        raise SoloError("GitHub allows at most 20 topics")
    for t in names:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", t):
            raise SoloError("invalid topic %r (lowercase letters, digits and hyphens, max 50 chars)" % t)
    return names


def file_action(ctx, id, path, content, desc):
    return Action(id, "file", desc, file_path=path, content=content)


def plan_for(ctx, res, opts):
    """Actions for one actionable check result."""
    id = res.apply
    o = ctx
    if id == "dependabot-alerts":
        return [Action(id, "api", "enable Dependabot alerts", "PUT", o.p("/vulnerability-alerts"),
                       undo=_undo("DELETE", o.p("/vulnerability-alerts")))]
    if id == "dependabot-security-updates":
        return [Action(id, "api", "enable Dependabot security updates", "PUT", o.p("/automated-security-fixes"),
                       undo=_undo("DELETE", o.p("/automated-security-fixes")))]
    if id == "secret-scanning":
        return [Action(id, "api", "enable secret scanning", "PATCH", o.p(),
                       {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}},
                       undo=_undo("PATCH", o.p(), {"security_and_analysis": {"secret_scanning": {"status": "disabled"}}}))]
    if id == "push-protection":
        return [Action(id, "api", "enable push protection", "PATCH", o.p(),
                       {"security_and_analysis": {"secret_scanning_push_protection": {"status": "enabled"}}},
                       undo=_undo("PATCH", o.p(), {"security_and_analysis": {"secret_scanning_push_protection": {"status": "disabled"}}}))]
    if id == "private-vuln-reporting":
        return [Action(id, "api", "enable private vulnerability reporting", "PUT",
                       o.p("/private-vulnerability-reporting"),
                       undo=_undo("DELETE", o.p("/private-vulnerability-reporting")))]
    if id == "codeql":
        return [Action(id, "api", "enable CodeQL default setup (languages auto-detected)", "PATCH",
                       o.p("/code-scanning/default-setup"), {"state": "configured"},
                       undo=_undo("PATCH", o.p("/code-scanning/default-setup"), {"state": "not-configured"}))]
    if id == "dependabot-config":
        ecos = res.data["ecosystems"]
        if res.data.get("missing") is not None:
            parts = []
            if res.data["missing"]:
                parts.append(dependabot_entries(res.data["missing"]))
            for e, gap in sorted(res.data.get("missing_dirs", {}).items()):
                parts.append("# in your existing '%s' entry, also cover: %s\n" % (e, ", ".join(gap)))
            return [Action(id, "note", "dependabot.yml already exists - add these entries yourself (not modified):\n"
                           + "\n".join("      " + l for l in "".join(parts).splitlines()))]
        return [file_action(o, id, ".github/dependabot.yml", dependabot_yaml(ecos),
                            "create .github/dependabot.yml (%s)" % ", ".join(ecos))]
    if id == "guardrail":
        body = {"name": "solo-guard", "target": "branch", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}

        def after(resp, state):
            rid = (resp.data or {}).get("id")
            if rid is not None:
                say("      to lift temporarily: gh api -X PUT repos/%s/rulesets/%s -f enforcement=disabled "
                      "(and 'active' to restore)" % (ctx.slug, rid))
        return [Action(id, "api", "create ruleset solo-guard: block deleting / force-pushing the default branch "
                       "(no PR requirement)", "POST", o.p("/rulesets"), body, after=after, undo=_undo_ruleset(o))]
    if id == "delete-branch-on-merge":
        return [Action(id, "api", "delete head branches after merge", "PATCH", o.p(),
                       {"delete_branch_on_merge": True}, undo=_undo("PATCH", o.p(), {"delete_branch_on_merge": False}))]
    if id == "release-notes-config":
        return [file_action(o, id, ".github/release.yml", RELEASE_YML,
                            "create .github/release.yml (release-notes categories, dependabot excluded)")]
    if id == "security-policy":
        return [file_action(o, id, "SECURITY.md", security_md(o.owner, o.repo),
                            "create SECURITY.md (points to private vulnerability reporting)")]
    if id == "workflow-permissions":
        return [Action(id, "api", "set default GITHUB_TOKEN permission to read (existing workflows that need write "
                       "must declare permissions: explicitly)", "PUT", o.p("/actions/permissions/workflow"),
                       {"default_workflow_permissions": "read"},
                       undo=_undo("PUT", o.p("/actions/permissions/workflow"),
                                  {"default_workflow_permissions": "write"}))]
    if id == "discussions":
        return [Action(id, "api", "enable Discussions", "PATCH", o.p(), {"has_discussions": True},
                       undo=_undo("PATCH", o.p(), {"has_discussions": False}))]
    if id == "pages":
        path, note = pages_source(ctx, opts.pages_path)
        acts = []

        def after(resp, state):
            state["pages_url"] = (resp.data or {}).get("html_url")
        acts.append(Action(id, "api", "enable Pages from %s of %s (%s)" % (path, ctx.branch, note), "POST",
                           o.p("/pages"), {"build_type": "legacy", "source": {"branch": ctx.branch, "path": path}},
                           after=after, undo=_undo("DELETE", o.p("/pages"))))
        if not ctx.info.get("homepage"):
            predicted = pages_url(ctx.owner, ctx.repo)
            acts.append(Action(id, "api", "set homepage to the Pages URL (currently empty)", "PATCH", o.p(),
                               lambda st: {"homepage": st.get("pages_url") or predicted},
                               undo=_undo("PATCH", o.p(), {"homepage": ""})))
        return acts
    if id == "tag-guard":
        body = {"name": "solo-tag-guard", "target": "tag", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}
        return [Action(id, "api", "create ruleset solo-tag-guard: block deleting / force-moving v* tags", "POST",
                       o.p("/rulesets"), body, undo=_undo_ruleset(o))]
    if id == "labels":
        acts = []
        for name, color, desc in res.data["missing"]:
            acts.append(Action(id, "api", "create label %s" % name, "POST", o.p("/labels"),
                               {"name": name, "color": color, "description": desc},
                               undo=_undo("DELETE", o.p("/labels/%s" % urllib.parse.quote(name)))))
        return acts
    if id == "community-files":
        contents = {"pr-template": PR_TEMPLATE, "bug-template": BUG_TEMPLATE, "feature-template": FEATURE_TEMPLATE,
                    "contributing": contributing_md(o.repo)}
        return [file_action(o, id, target, contents[key], "create %s" % target) for key, target in res.data["missing"]]
    if id == "topics":
        names = validate_topics(opts.topics)
        return [Action(id, "api", "set topics: %s" % ", ".join(names), "PUT", o.p("/topics"), {"names": names},
                       undo=_undo("PUT", o.p("/topics"), {"names": list(ctx.info.get("topics") or [])}))]
    return []


def select_results(results, only, skip):
    sel = []
    for r in results:
        if not (r.apply and r.actionable and r.status in (WARN, BAD)):
            continue
        if only is not None:
            if r.apply not in only:
                continue
        elif r.apply not in DEFAULT_APPLY:
            continue
        if r.apply in skip:
            continue
        sel.append(r)
    sel.sort(key=lambda r: ALL_APPLY.index(r.apply))
    return sel


def split_csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def split_ids(s, what):
    ids = [x.strip() for x in (s or "").split(",") if x.strip()]
    bad = [x for x in ids if x not in ALL_APPLY]
    if bad:
        raise SoloError("unknown %s id(s): %s (valid: %s)" % (what, ", ".join(bad), ", ".join(ALL_APPLY)))
    return ids


def file_mode(ctx, action, opts):
    """-> (mode, text) mode in local|exists|commit|skip"""
    if ctx.local_root:
        full = os.path.join(ctx.local_root, action.file_path)
        if os.path.exists(full):
            return "exists", "already exists locally - left untouched"
        return "local", "write locally (you commit it)"
    if opts.commit_files:
        return "commit", "commit to %s via the Contents API" % ctx.branch
    return "skip", "not a clone of this repo: run inside a clone, or pass --commit-files"


DIFF_TEXT = {
    "dependabot-alerts": "Dependabot alerts: off -> on",
    "dependabot-security-updates": "Dependabot security updates: off -> on",
    "secret-scanning": "secret scanning: off -> on", "push-protection": "push protection: off -> on",
    "private-vuln-reporting": "private vulnerability reporting: off -> on",
    "codeql": "code scanning: not configured -> default setup",
    "guardrail": "default branch: deletable / force-pushable -> protected (no PR required)",
    "tag-guard": "v* tags: deletable / movable -> protected",
    "delete-branch-on-merge": "delete branch on merge: off -> on",
    "workflow-permissions": "default GITHUB_TOKEN: write -> read", "discussions": "Discussions: off -> on",
}


def describe(action, ctx, opts):
    if action.kind == "api":
        b = action.body(ctx.state) if callable(action.body) else action.body
        body = (" " + json.dumps(b, separators=(",", ":"))) if b is not None else ""
        if action.id == "pages" and callable(action.body):
            b = action.body({})
            body = " " + json.dumps(b, separators=(",", ":")) + " (URL from the Pages response)"
        diff = DIFF_TEXT.get(action.id)
        return "%s %s%s\n      %s%s" % (action.method, action.path, body, action.desc,
                                       ("\n      change: " + diff) if diff else "")
    if action.kind == "file":
        mode, text = file_mode(ctx, action, opts)
        return "%s\n      %s%s" % (action.desc, "will skip: " if mode == "skip" else "", text)
    return action.desc


def counts_as_change(action, ctx, opts):
    if action.kind == "api":
        return True
    if action.kind == "file":
        return file_mode(ctx, action, opts)[0] in ("local", "commit")
    return False


def print_release_warning(ctx):
    say("\n  WARNING: pushing to %s may start a release workflow:" % ctx.branch)
    for path, ind, strong in ctx.release_risk:
        say("    - %s (%s)%s" % (path, ", ".join(ind), "" if strong else " [weak signal]"))
    say("    Committing the generated files (or pushing your local commit) can create a release.")


def _log(ctx, status, target, detail=""):
    ctx.log.append({"status": status, "target": target, "detail": detail})


def execute(ctx, actions, opts):
    failures = 0
    for a in actions:
        if a.kind == "note":
            continue
        if a.kind == "api":
            body = a.resolved_body(ctx.state)
            r = ctx.api.request(a.method, a.path, body)
            tgt = "%s %s" % (a.method, a.path)
            if r.ok:
                say("  done    %s" % tgt)
                _log(ctx, "done", tgt)
                if a.undo:
                    u = a.undo(r) if callable(a.undo) else a.undo
                    if u:
                        ctx.undo.append(dict(u, id=a.id))
                if a.after:
                    a.after(r, ctx.state)
            else:
                failures += 1
                say("  FAILED  %s -> %s" % (tgt, r.describe()))
                say("          hint: %s" % hint_for(r))
                _log(ctx, "failed", tgt, r.describe())
            continue
        mode, text = file_mode(ctx, a, opts)
        if mode == "exists" or mode == "skip":
            say("  skip    %s (%s)" % (a.file_path, text))
            _log(ctx, "skipped", a.file_path, text)
        elif mode == "local":
            full = os.path.join(ctx.local_root, a.file_path)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "x", encoding="utf-8", newline="\n") as f:
                f.write(a.content)
            say("  written %s (local only; review and commit it yourself)" % a.file_path)
            _log(ctx, "written", a.file_path, "local only")
        elif mode == "commit":
            if ctx.release_risk and not opts.accept_release_risk:
                failures += 1
                say("  BLOCKED %s: committing to %s may trigger a release workflow; re-run with "
                    "--accept-release-risk if that is what you want" % (a.file_path, ctx.branch))
                _log(ctx, "blocked", a.file_path, "release workflow may fire")
                continue
            body = {"message": "chore: add %s (github-solo)" % a.file_path,
                    "content": base64.b64encode(a.content.encode("utf-8")).decode("ascii"),
                    "branch": ctx.branch}
            r = ctx.api.request("PUT", ctx.p("/contents/" + urllib.parse.quote(a.file_path)), body)
            if r.ok:
                say("  done    committed %s to %s" % (a.file_path, ctx.branch))
                _log(ctx, "done", "commit " + a.file_path)
            else:
                failures += 1
                say("  FAILED  PUT contents/%s -> %s" % (a.file_path, r.describe()))
                say("          hint: %s" % hint_for(r))
                _log(ctx, "failed", "commit " + a.file_path, r.describe())
    return failures


def state_dir():
    d = os.environ.get("SOLO_STATE_DIR")
    if d:
        return d
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "github-solo")


def save_snapshot(ctx):
    d = state_dir()
    os.makedirs(d, mode=0o700, exist_ok=True)
    stamp = "%s%03d" % (time.strftime("%Y%m%dT%H%M%S"), int(time.time() * 1000) % 1000)
    path = os.path.join(d, "%s__%s__%s.json" % (ctx.owner, ctx.repo, stamp))
    doc = {"repo": ctx.slug, "created": stamp, "undo": ctx.undo}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def latest_snapshot(owner, repo):
    d = state_dir()
    prefix = "%s__%s__" % (owner, repo)
    try:
        names = sorted(n for n in os.listdir(d) if n.startswith(prefix) and n.endswith(".json"))
    except OSError:
        return None
    return os.path.join(d, names[-1]) if names else None


def hint_for(r):
    if "proxy" in r.message.lower():
        return ("a proxy/sandbox in front of the API blocks this path (this is not your PC); run solo.py in a terminal on your PC, "
                "or in Claude Code running on your PC")
    if r.status == 403:
        return "token lacks permission or the feature is not available on this plan (references/troubleshooting.md)"
    if r.status == 404:
        return "token cannot administer this repo, or the feature is unavailable (references/troubleshooting.md)"
    if r.status == 422:
        return "GitHub rejected the request; the setting may already exist or be unavailable for this repo"
    return "see references/troubleshooting.md"


def cmd_restore(args):
    owner, repo, _ = resolve_target(args.repo)
    token = get_token()
    if not token:
        raise SoloError("no token: set GH_TOKEN / GITHUB_TOKEN or run `gh auth login`")
    path = args.snapshot or latest_snapshot(owner, repo)
    if not path or not os.path.exists(path):
        say("Nothing to restore for %s/%s (no snapshot in %s)." % (owner, repo, state_dir()))
        return 0
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    ops = list(reversed(doc.get("undo", [])))
    say("github-solo restore: %s (%s)" % (doc.get("repo", "%s/%s" % (owner, repo)), "executing" if args.yes else "dry run"))
    say("snapshot: %s" % path)
    for i, op in enumerate(ops, 1):
        body = (" " + json.dumps(op["body"], separators=(",", ":"))) if op.get("body") is not None else ""
        say("  [%d] %s: %s %s%s" % (i, op.get("id"), op["method"], op["path"], body))
    say("Files written or committed by apply are not touched; remove them yourself if you do not want them.")
    if not args.yes:
        say("\nDry run: nothing was changed. Re-run with --yes to revert.")
        return 0
    api = Api(token)
    failures = 0
    say("\nExecuting:")
    for op in ops:
        r = api.request(op["method"], op["path"], op.get("body"))
        tgt = "%s %s" % (op["method"], op["path"])
        if r.ok or r.status == 404:
            say("  done    %s%s" % (tgt, "" if r.ok else " (already gone)"))
        else:
            failures += 1
            say("  FAILED  %s -> %s" % (tgt, r.describe()))
            say("          hint: %s" % hint_for(r))
    if failures:
        say("\nFinished with %d failure(s); the snapshot is kept so you can run restore again." % failures)
        return 1
    os.replace(path, path + ".restored")
    say("\nDone. Run `solo.py audit %s/%s` to verify." % (owner, repo))
    return 0


def cmd_apply(args):
    if getattr(args, "json", False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code, report = _apply(args)
        builtins.print(json.dumps(report, indent=2, ensure_ascii=False))
        return code
    return _apply(args)[0]


def _apply(args):
    owner, repo, local = resolve_target(args.repo)
    token = get_token()
    if not token:
        raise SoloError("no token: set GH_TOKEN / GITHUB_TOKEN or run `gh auth login`")
    only = split_ids(args.only, "--only") if args.only else None
    skip = split_ids(args.skip, "--skip") if args.skip else []
    ctx = Ctx(Api(token), owner, repo, local)
    ctx.profile = getattr(args, "profile", None) or "app"
    results = run_checks(ctx)
    selected = select_results(results, only, skip)

    mode = "executing" if args.yes else "dry run"
    say("github-solo apply: %s (%s)" % (ctx.slug, mode))
    actions = []
    for res in selected:
        actions.extend(plan_for(ctx, res, args))
    if only:
        for oid in only:
            if oid not in [r.apply for r in selected]:
                st = [r for r in results if r.apply == oid]
                why = "already OK / not applicable" if st and not st[0].actionable else "nothing to do"
                if st:
                    say("  note: %s - %s (%s)" % (oid, why, st[0].msg))
    if actions:
        say("")
        for i, a in enumerate(actions, 1):
            say("  [%d] %s: %s" % (i, a.id, describe(a, ctx, args)))
        if ctx.release_risk and any(a.kind == "file" and file_mode(ctx, a, args)[0] in ("local", "commit")
                                    for a in actions):
            print_release_warning(ctx)
    pending_opt = [r for r in results if r.apply in OPT_IN_APPLY and r.actionable
                   and r.status == WARN and (only is None or r.apply not in only)]
    if pending_opt:
        say("\nNot applied by default (opt-in, use --only <id>):")
        for r in pending_opt:
            say("  - %s: %s" % (r.apply, OPT_IN_WHY[r.apply]))
    blocked = [r for r in results if r.status == BAD]
    for r in blocked:
        say("\n%s %s is never changed by apply: %s" % (ICON[BAD], r.id, r.msg))
        for d in r.details:
            say("     %s" % d)
    changes = [a for a in actions if counts_as_change(a, ctx, args)]
    if not changes:
        say("\nNo changes needed.")
    failures = 0
    if args.yes and changes:
        say("\nExecuting:")
        failures = execute(ctx, actions, args)
        say("\n%s. Run `solo.py audit %s` to verify." % (
            "Finished with %d failure(s)" % failures if failures else "Done", ctx.slug))
    elif changes:
        say("\nDry run: nothing was changed. Re-run with --yes to execute.")
    snapshot = None
    if ctx.undo:
        snapshot = save_snapshot(ctx)
        say("Undo information saved: %s" % snapshot)
        say("To revert what was just applied: solo.py restore %s --yes" % ctx.slug)
    report = {
        "repo": ctx.slug, "dry_run": not args.yes, "snapshot": snapshot,
        "plan": [{"id": a.id, "kind": a.kind, "method": a.method, "path": a.path or a.file_path,
                  "body": None if callable(a.body) else (a.body if a.kind == "api" else None),
                  "description": a.desc, "change": counts_as_change(a, ctx, args),
                  "file_mode": file_mode(ctx, a, args)[0] if a.kind == "file" else None}
                 for a in actions],
        "opt_in_available": [r.apply for r in pending_opt],
        "never_changed": [r.id for r in blocked],
        "log": ctx.log, "failures": failures,
    }
    return (1 if failures else 0), report


# --------------------------------------------------------------------------
# audit / links / dependabot commands
# --------------------------------------------------------------------------

def make_ctx(args):
    owner, repo, local = resolve_target(args.repo)
    token = get_token()
    if not token:
        raise SoloError("no token: set GH_TOKEN / GITHUB_TOKEN or run `gh auth login`")
    ctx = Ctx(Api(token), owner, repo, local)
    ctx.profile = getattr(args, "profile", None) or "app"
    return ctx


def _gh_escape(t):
    return t.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def print_annotations(results):
    """GitHub Actions workflow commands, so findings show up as annotations in a CI run."""
    for r in results:
        if r.status in (WARN, BAD):
            say("::%s title=github-solo %s::%s" % ("error" if r.status == BAD else "warning", r.id,
                                                   _gh_escape(r.msg)))


def cmd_audit(args):
    if args.all_repos:
        if args.repo:
            raise SoloError("give either OWNER/REPO or --all-repos OWNER, not both")
        return cmd_audit_all(args)
    ctx = make_ctx(args)
    results = run_checks(ctx)
    ignore = set(split_csv(args.ignore))
    if ignore:
        known = {r.id for r in results}
        unknown = sorted(ignore - known)
        if unknown:
            raise SoloError("unknown check id(s) in --ignore: %s (valid: %s)" % (", ".join(unknown), ", ".join(sorted(known))))
        results = [r for r in results if r.id not in ignore]
    s = summarize(results)
    code = 1 if s[BAD] or (args.fail_on == "warn" and s[WARN]) else 0
    if args.json:
        builtins.print(json.dumps({"repo": ctx.slug, "private": ctx.private, "default_branch": ctx.branch,
                                   "results": [r.to_json() for r in results], "summary": s,
                                   "score": score(results), "profile": ctx.profile, "exit_code": code}, indent=2, ensure_ascii=False))
    else:
        print_audit(ctx, results, quiet=args.quiet)
        if args.github_annotations:
            print_annotations(results)
    return code


def list_owner_repos(api, owner):
    me = api.request("GET", "/user")
    login = me.data.get("login") if me.ok and isinstance(me.data, dict) else None
    if login and login.lower() == owner.lower():
        path, params = "/user/repos", {"affiliation": "owner"}
    else:
        path, params = "/orgs/%s/repos" % owner, {"type": "all"}
    repos, page = [], 1
    while page <= 10:
        r = api.request("GET", path, params=dict(params, per_page=100, page=page))
        if r.status == 404 and path.startswith("/orgs/"):
            path, params, page = "/users/%s/repos" % owner, {"type": "owner"}, 1
            continue
        if not r.ok or not isinstance(r.data, list):
            raise SoloError("cannot list repos of %s: %s" % (owner, r.describe()))
        repos.extend(r.data)
        if len(r.data) < 100:
            break
        page += 1
    return repos


def cmd_audit_all(args):
    token = get_token()
    if not token:
        raise SoloError("no token: set GH_TOKEN / GITHUB_TOKEN or run `gh auth login`")
    api = Api(token)
    owner = args.all_repos
    rows, skipped = [], []
    for item in list_owner_repos(api, owner):
        name = item.get("name")
        if item.get("archived") or item.get("fork"):
            skipped.append("%s (%s)" % (name, "archived" if item.get("archived") else "fork"))
            continue
        try:
            ctx = Ctx(api, item.get("owner", {}).get("login", owner), name)
            ctx.profile = getattr(args, "profile", None) or "app"
            res = run_checks(ctx)
            rows.append({"repo": ctx.slug, "private": ctx.private, "summary": summarize(res), "score": score(res),
                         "bad": [r.id for r in res if r.status == BAD],
                         "warn": [r.id for r in res if r.status == WARN]})
        except SoloError as e:
            rows.append({"repo": "%s/%s" % (owner, name), "error": str(e), "bad": [], "warn": [],
                         "summary": {OK: 0, WARN: 0, BAD: 0, NA: 0}})
    code = 1 if any(r["bad"] for r in rows) else 0
    if args.json:
        builtins.print(json.dumps({"owner": owner, "repos": rows, "skipped": skipped, "exit_code": code},
                                  indent=2, ensure_ascii=False))
        return code
    say("github-solo audit --all-repos %s (%d repos)" % (owner, len(rows)))
    width = max([len(r["repo"]) for r in rows] or [0])
    for r in rows:
        if "error" in r:
            say("  %s %-*s  error: %s" % (ICON[WARN], width, r["repo"], r["error"]))
            continue
        st = BAD if r["bad"] else (WARN if r["warn"] else OK)
        sm = r["summary"]
        extra = ("  action needed: " + ", ".join(r["bad"])) if r["bad"] else ""
        say("  %s %-*s  %-7s %3d/100  %d ok, %d recommended, %d action needed, %d n/a%s" % (
            ICON[st], width, r["repo"], "private" if r["private"] else "public", r.get("score", 0),
            sm[OK], sm[WARN], sm[BAD], sm[NA], extra))
    if skipped:
        say("\nSkipped: %s" % ", ".join(skipped))
    say("\nRun `solo.py audit OWNER/REPO` for the details of one repo.")
    return code


def detect_environment(env=None):
    """Where is this running? Only signals that are actually present are used; nothing is guessed.
    kind: "cloud" (Claude Code in a managed cloud container, e.g. started from the web/mobile app),
          "local-claude-code" (Claude Code on this machine), "shell" (no Claude Code signal)."""
    env = os.environ if env is None else env
    entry = env.get("CLAUDE_CODE_ENTRYPOINT") or ""
    sig = []
    cloud = [k for k in ("CLAUDE_CODE_REMOTE", "CCR_AGENT_PROXY_ENABLED", "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE")
             if env.get(k) and env.get(k).lower() not in ("0", "false")]
    if env.get("CLAUDE_CODE_REMOTE", "").lower() == "true" or env.get("CCR_AGENT_PROXY_ENABLED"):
        sig = cloud + (["IS_SANDBOX"] if env.get("IS_SANDBOX") else [])
        kind = "cloud"
    elif env.get("CLAUDECODE"):
        kind, sig = "local-claude-code", ["CLAUDECODE"]
    else:
        kind = "shell"
    text = {"cloud": "Claude Code in a managed cloud container (this session is not your PC)",
            "local-claude-code": "Claude Code running on this PC (CLI)",
            "shell": "no Claude Code signal (another agent, a plain shell or CI)"}[kind]
    return {"kind": kind, "entrypoint": entry or None, "signals": sig, "text": text}


def token_kind(token):
    for prefix, kind in (("github_pat_", "fine-grained personal access token"), ("ghp_", "classic personal access token"),
                         ("gho_", "OAuth token (for example from `gh auth login`)"),
                         ("ghu_", "GitHub App user token"), ("ghs_", "GitHub App / Actions installation token")):
        if token.startswith(prefix):
            return kind
    return "unrecognised token format"


def cmd_doctor(args):
    rows = []  # (status, name, text)

    def add(status, name, text):
        rows.append((status, name, text))

    envinfo = detect_environment()
    add(OK, "environment", "%s%s" % (envinfo["text"], (" [entrypoint=%s]" % envinfo["entrypoint"]) if envinfo["entrypoint"] else ""))
    if envinfo["kind"] == "cloud":
        add(WARN, "cloud note", "this environment's network proxy may refuse admin API calls (settings writes); if you see "
            "'not permitted through this proxy', run solo.py in a terminal on your PC (or in Claude Code running on your PC), not in this session")
    v = sys.version_info
    add(OK if v >= (3, 9) else BAD, "python", "%d.%d.%d%s" % (v[0], v[1], v[2], "" if v >= (3, 9) else " (3.9+ required)"))
    for tool, required in (("git", False), ("gh", False)):
        try:
            out = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
            add(OK, tool, (out.stdout.splitlines() or ["found"])[0])
        except (OSError, subprocess.SubprocessError):
            add(NA, tool, "not found (optional: git infers OWNER/REPO, gh is only a token source)")
    token, source = None, None
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(key, "").strip():
            token, source = os.environ[key].strip(), key
            break
    if not token:
        token = get_token()
        source = "gh auth token" if token else None
    api = None
    if not token:
        add(BAD, "token", "none found. Set GH_TOKEN / GITHUB_TOKEN or run `gh auth login`")
    else:
        add(OK, "token", "from %s: %s" % (source, token_kind(token)))
        api = Api(token)
        add(OK if api.base == "https://api.github.com" else WARN, "api base", api.base)
    if api:
        try:
            rl = api.request("GET", "/rate_limit")
            if rl.ok:
                core = ((rl.data or {}).get("resources") or {}).get("core") or {}
                add(OK, "api", "reachable (rate limit %s/%s left)" % (core.get("remaining", "?"), core.get("limit", "?")))
            elif rl.status == 401:
                add(BAD, "api", "reachable but the token was rejected (HTTP 401): expired, revoked or mistyped")
            else:
                add(WARN, "api", "reachable, /rate_limit answered %s" % rl.describe())
            me = api.request("GET", "/user")
            scopes = rl.headers.get("x-oauth-scopes")
            if me.ok and isinstance(me.data, dict):
                add(OK, "user", "%s%s" % (me.data.get("login"), (" (classic scopes: %s)" % (scopes or "none")) if scopes is not None else ""))
            else:
                add(WARN, "user", "cannot read /user (%s); normal for some app / fine-grained tokens" % me.describe())
        except SoloError as e:
            add(BAD, "api", str(e))
            api = None
    slug = None
    if api and (args.repo or git_origin()):
        try:
            owner, repo, _ = resolve_target(args.repo)
            slug = "%s/%s" % (owner, repo)
            ctx = Ctx(api, owner, repo)
            info = ctx.info
            perms = info.get("permissions") or {}
            level = "admin" if perms.get("admin") else ("push (not admin: most settings cannot be changed)" if perms.get("push") else "read only")
            add(OK if perms.get("admin") else WARN, "repo", "%s (%s), your access: %s" % (
                slug, "private" if info.get("private") else "public", level))
            probes = [("vulnerability-alerts", "/vulnerability-alerts", (204, 404)), ("rulesets", "/rulesets", (200,)),
                      ("code-scanning", "/code-scanning/default-setup", (200,)),
                      ("workflow permissions", "/actions/permissions/workflow", (200,)),
                      ("collaborators", "/collaborators", (200,)), ("pages", "/pages", (200, 404))]
            for name, suffix, okay in probes:
                r = api.request("GET", ctx.p(suffix))
                if r.status in okay:
                    add(OK, "read " + name, "ok")
                elif r.status in (401, 403):
                    add(WARN, "read " + name, "%s - token or plan lacks access (references/troubleshooting.md)" % r.describe())
                else:
                    add(WARN, "read " + name, r.describe())
        except SoloError as e:
            add(BAD, "repo", str(e))
    code = 1 if any(r[0] == BAD for r in rows) else 0
    if args.json:
        builtins.print(json.dumps({"environment": envinfo,
                                   "checks": [{"name": n, "status": st, "message": t} for st, n, t in rows],
                                   "exit_code": code}, indent=2, ensure_ascii=False))
        return code
    say("github-solo doctor")
    width = max(len(n) for _, n, _ in rows)
    for st, n, t in rows:
        say("  %s %-*s  %s" % (ICON[st], width, n, t))
    if not slug:
        say("\nTip: pass OWNER/REPO (or run inside a clone) to also check access to that repo.")
    say("\n%s" % ("Problems found: fix the lines marked ❌ first." if code else "Ready: run `solo.py audit OWNER/REPO`."))
    return code


def cmd_explain(args):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "checks.md")
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        raise SoloError("references/checks.md not found next to the script (%s)" % os.path.normpath(path))
    wanted = args.check_id
    start = None
    heads = []
    for i, line in enumerate(lines):
        if line.startswith("### "):
            ids = [x.strip() for x in line[4:].split("(")[0].split(",")]
            heads.append((i, ids))
            if wanted in ids and start is None:
                start = i
    if start is None:
        known = sorted({x for _, ids in heads for x in ids})
        raise SoloError("no such check: %s (known: %s)" % (wanted, ", ".join(known)))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("### "):
            end = i
            break
    say("\n".join(lines[start:end]).rstrip())
    return 0


CI_TEMPLATE = """# Weekly settings check for this repo. Fails (and annotates the run) when something needs action.
# Needs a secret SOLO_AUDIT_TOKEN: a fine-grained token for THIS repo with Administration: read, Contents: read, Metadata: read
# (the built-in GITHUB_TOKEN cannot read most security settings). Pin the download to a commit SHA you reviewed.
name: github-solo audit
on:
  schedule:
    - cron: "17 3 * * 1"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@<full-commit-sha>   # vX.Y.Z
        with:
          python-version: "3.13"
      - name: Fetch github-solo (pinned)
        run: curl -fsSL https://raw.githubusercontent.com/kajisho5/github-solo-skill/<full-commit-sha>/scripts/solo.py -o solo.py
      - name: Audit
        env:
          GH_TOKEN: ${{ secrets.SOLO_AUDIT_TOKEN }}
        run: python3 solo.py audit ${{ github.repository }} --github-annotations --quiet
"""


def cmd_ci_template(args):
    say(CI_TEMPLATE.rstrip())
    return 0


def cmd_badges(args):
    ctx = make_ctx(args)
    base = "https://github.com/%s" % ctx.slug
    for wf in ctx.workflow_paths:
        fn = os.path.basename(wf)
        stem = os.path.splitext(fn)[0]
        say("[![%s](%s/actions/workflows/%s/badge.svg)](%s/actions/workflows/%s)" % (stem, base, fn, base, fn))
    if ctx.info.get("license"):
        say("[![license](https://img.shields.io/github/license/%s)](%s)" % (ctx.slug, base + "/blob/%s/LICENSE" % ctx.branch))
    say("[![release](https://img.shields.io/github/v/release/%s)](%s/releases/latest)" % (ctx.slug, base))
    say("[![last commit](https://img.shields.io/github/last-commit/%s)](%s/commits/%s)" % (ctx.slug, base, ctx.branch))
    say("[![stars](https://img.shields.io/github/stars/%s)](%s/stargazers)" % (ctx.slug, base))
    return 0


def cmd_links(args):
    if args.workflow:
        say(RELEASE_WORKFLOW_TEMPLATE.rstrip())
        return 0
    ctx = make_ctx(args)
    rels, r = fetch_releases(ctx)
    if rels is None:
        raise SoloError("cannot list releases: %s" % r.describe())
    if not rels:
        say("No releases in %s yet, so there is no download URL. See references/release-latest.md." % ctx.slug)
        return 1
    stable = [x for x in rels if not x.get("prerelease")]
    if not stable:
        say("%s has %d release(s) but all are pre-releases." % (ctx.slug, len(rels)))
        say("/releases/latest ignores pre-releases (it answers 404), so no fixed URL exists yet.")
        say("Fix: publish one release as a normal release, e.g.")
        say("  gh release edit %s --prerelease=false --latest -R %s" % (rels[0].get("tag_name"), ctx.slug))
        say("Then use asset names without a version in them (see references/release-latest.md).")
        return 1
    top = stable[0]
    assets = [a.get("name", "") for a in top.get("assets", [])]
    say("Latest release: %s" % top.get("tag_name"))
    say("Page: https://github.com/%s/releases/latest" % ctx.slug)
    if not assets:
        say("The latest release has no assets, so there is nothing to download directly.")
        return 1
    usable, blocked = [], []
    for a in assets:
        (blocked if versioned_asset(a, top.get("tag_name", "")) else usable).append(a)
    for a in usable:
        url = "https://github.com/%s/releases/latest/download/%s" % (ctx.slug, urllib.parse.quote(a))
        say("- [%s](%s)" % (a, url) if args.markdown else url)
    if blocked:
        say("\nNot usable as a fixed URL (the asset name contains the version, so the URL changes every release):")
        for a in blocked:
            say("  - %s" % a)
        say("Fix: also upload a copy with a version-less name in your release workflow, e.g.")
        say("  cp app-1.2.0-win.zip app-win.zip && gh release upload %s app-win.zip --clobber" % top.get("tag_name"))
        say("See references/release-latest.md for a workflow example.")
    return 0 if usable else 1


def cmd_dependabot(args):
    ctx = make_ctx(args)
    ecos, vendored = detect_ecosystems(ctx.paths)
    if not ecos:
        say("No Dependabot-supported manifests detected in %s." % ctx.slug, file=sys.stderr)
        return 1
    sys.stdout.write(dependabot_yaml(ecos))
    if vendored:
        say("# note: bundled code under %s/ is not tracked" % "/, ".join(vendored), file=sys.stderr)
    existing = [p for p in (".github/dependabot.yml", ".github/dependabot.yaml") if p in ctx.paths]
    if existing:
        say("# note: %s already exists in the repo; merge by hand, do not overwrite" % existing[0],
              file=sys.stderr)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="solo.py", description="GitHub settings audit/apply for solo developers")
    p.add_argument("--version", action="version", version="github-solo " + VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="diagnose the repo")
    a.add_argument("repo", nargs="?", help="OWNER/REPO (default: git remote origin)")
    a.add_argument("--json", action="store_true", help="machine-readable output")
    a.add_argument("--profile", choices=PROFILES,
                   help="kind of repo: app (default), library, site, docs; hides checks that do not apply")
    a.add_argument("--quiet", action="store_true", help="hide ✅ and ➖ rows")
    a.add_argument("--ignore", help="comma-separated check ids to leave out (also from the exit code)")
    a.add_argument("--fail-on", choices=["bad", "warn"], default="bad",
                   help="exit 1 on ❌ only (default) or also on ⚠️")
    a.add_argument("--all-repos", metavar="OWNER", help="audit every non-archived, non-fork repo of OWNER")
    a.add_argument("--github-annotations", action="store_true",
                   help="also print ::warning/::error workflow commands (for GitHub Actions)")
    ap = sub.add_parser("apply", help="apply missing settings (dry run unless --yes)")
    ap.add_argument("repo", nargs="?")
    ap.add_argument("--yes", action="store_true", help="execute (default is a dry run)")
    ap.add_argument("--only", help="comma-separated apply ids (needed for opt-in items)")
    ap.add_argument("--skip", help="comma-separated apply ids to skip")
    ap.add_argument("--pages-path", choices=["/", "/docs"], help="Pages publishing folder")
    ap.add_argument("--topics", help="comma-separated topics for --only topics")
    ap.add_argument("--commit-files", action="store_true",
                    help="commit generated files via the Contents API when not in a clone")
    ap.add_argument("--json", action="store_true", help="machine-readable plan and execution log")
    ap.add_argument("--profile", choices=PROFILES, help="kind of repo: app (default), library, site, docs")
    ap.add_argument("--accept-release-risk", action="store_true",
                    help="allow --commit-files even if a workflow may create a release on push")
    li = sub.add_parser("links", help="print fixed latest-release download URLs")
    li.add_argument("repo", nargs="?")
    li.add_argument("--workflow", action="store_true",
                    help="print a release workflow template that uploads version-less asset copies (no API call)")
    li.add_argument("--markdown", action="store_true", help="print Markdown list items instead of bare URLs")
    d = sub.add_parser("dependabot", help="print a generated dependabot.yml")
    d.add_argument("repo", nargs="?")
    ex = sub.add_parser("explain", help="print the reference entry (why, API, undo) of one check")
    ex.add_argument("check_id")
    ci = sub.add_parser("ci-template", help="print a weekly audit GitHub Actions workflow (no API call)")
    bd = sub.add_parser("badges", help="print README badge Markdown for the repo")
    bd.add_argument("repo", nargs="?")
    dr = sub.add_parser("doctor", help="check token, permissions and connectivity before you start")
    dr.add_argument("repo", nargs="?")
    dr.add_argument("--json", action="store_true", help="machine-readable output")
    rs = sub.add_parser("restore", help="revert what the last `apply --yes` changed (dry run unless --yes)")
    rs.add_argument("repo", nargs="?")
    rs.add_argument("--yes", action="store_true", help="execute (default is a dry run)")
    rs.add_argument("--snapshot", help="snapshot file to use (default: the newest for this repo)")
    for sp in (a, ap, li, d, dr, rs, ex, bd, ci):
        sp.add_argument("--lang", choices=["en", "ja"], help="output language of the text output (default: SOLO_LANG or $LANG)")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if getattr(args, "lang", None):
        LANG[0] = args.lang
    try:
        return {"audit": cmd_audit, "apply": cmd_apply, "links": cmd_links,
                "dependabot": cmd_dependabot, "doctor": cmd_doctor,
                "explain": cmd_explain, "badges": cmd_badges, "ci-template": cmd_ci_template,
                "restore": cmd_restore}[args.cmd](args)
    except SoloError as e:
        say("error: %s" % e, file=sys.stderr)
        return 2
    except BrokenPipeError:  # e.g. `solo.py audit | head`
        try:
            sys.stdout.close()
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""A tiny stateful GitHub API mock (stdlib http.server) for the solo.py tests.

State layout: see tests/fixtures.py. Every non-GET request (except the GraphQL
POST, which is a read) is appended to `server.writes` as (method, path, body).
"""
import base64
import copy
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockGitHub(object):
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.writes = []
        self.requests = []
        self._next_id = 100
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, data=None):
                raw = b"" if data is None else json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-OAuth-Scopes", "repo, read:org")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _handle(self, method):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n)) if n else None
                path = self.path.split("?")[0]
                if not (self.headers.get("Authorization") or "").startswith("Bearer "):
                    return self._send(401, {"message": "Requires authentication"})
                mock.requests.append((method, path))
                if method != "GET" and path != "/graphql":
                    mock.writes.append((method, path, body))
                status, data = mock.route(method, path, body)
                self._send(status, data)

            def do_GET(self):
                self._handle("GET")

            def do_PUT(self):
                self._handle("PUT")

            def do_POST(self):
                self._handle("POST")

            def do_PATCH(self):
                self._handle("PATCH")

            def do_DELETE(self):
                self._handle("DELETE")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def clear_writes(self):
        del self.writes[:]

    # ------------------------------------------------------------------
    def route(self, method, path, body):
        s = self.state
        repo = s["repo"]
        base = "/repos/%s" % repo["full_name"]
        if path == "/rate_limit" and method == "GET":
            return 200, {"resources": {"core": {"limit": 5000, "remaining": 4999}}}
        if path == "/user" and method == "GET":
            return 200, {"login": repo["owner"]["login"]}
        if path in ("/user/repos", "/orgs/%s/repos" % repo["owner"]["login"],
                    "/users/%s/repos" % repo["owner"]["login"]) and method == "GET":
            return 200, [repo] + list(s.get("extra_repos", []))
        if path == "/graphql":
            return 200, {"data": {"repository": {"usesCustomOpenGraphImage": s["uses_custom_og"]}}}
        if not path.startswith(base):
            return 404, {"message": "Not Found"}
        sub = path[len(base):]
        if sub == "":
            if method == "GET":
                out = copy.deepcopy(repo)
                if repo.get("private"):
                    out.pop("security_and_analysis", None)
                return 200, out
            if method == "PATCH":
                for k, v in body.items():
                    if k == "security_and_analysis":
                        for kk, vv in v.items():
                            repo.setdefault("security_and_analysis", {})[kk] = vv
                    else:
                        repo[k] = v
                return 200, repo
        if sub == "/vulnerability-alerts":
            if method == "GET":
                return (204, None) if s["alerts"] else (404, {"message": "Vulnerability alerts are disabled."})
            if method == "PUT":
                s["alerts"] = True
                return 204, None
            if method == "DELETE":
                s["alerts"] = False
                return 204, None
        if sub == "/automated-security-fixes":
            if method == "GET":
                return 200, s["security_fixes"]
            if method == "PUT":
                s["security_fixes"] = {"enabled": True, "paused": False}
                return 204, None
            if method == "DELETE":
                s["security_fixes"] = {"enabled": False, "paused": False}
                return 204, None
        if sub == "/private-vulnerability-reporting":
            if method == "GET":
                return 200, {"enabled": s["pvr"]}
            if method == "PUT":
                s["pvr"] = True
                return 204, None
            if method == "DELETE":
                s["pvr"] = False
                return 204, None
        if sub == "/code-scanning/default-setup":
            if method == "GET":
                return 200, s["codeql"]
            if method == "PATCH":
                if body.get("state") == "not-configured":
                    s["codeql"] = {"state": "not-configured", "languages": []}
                    return 202, {}
                s["codeql"] = {"state": "configured", "languages": ["c-cpp"]}
                return 202, {"run_id": 1, "run_url": "x"}
        if sub == "/languages" and method == "GET":
            return 200, s["languages"]
        if sub.startswith("/git/trees/") and method == "GET":
            return 200, {"truncated": False,
                         "tree": [{"path": p, "type": "blob"} for p in sorted(s["tree"])]}
        if sub.startswith("/contents/"):
            fpath = sub[len("/contents/"):]
            if method == "GET":
                if fpath in s["files"]:
                    return 200, {"path": fpath, "encoding": "base64",
                                 "content": base64.b64encode(s["files"][fpath].encode()).decode()}
                return 404, {"message": "Not Found"}
            if method == "PUT":
                s["files"][fpath] = base64.b64decode(body["content"]).decode()
                if fpath not in s["tree"]:
                    s["tree"].append(fpath)
                return 201, {"content": {"path": fpath}}
        m = re.match(r"^/branches/([^/]+)/protection$", sub)
        if m and method == "GET":
            if s.get("free_private"):
                return 403, {"message": "Upgrade to GitHub Pro or make this repository public to enable this feature."}
            if s["protection"] is None:
                return 404, {"message": "Branch not protected"}
            return 200, s["protection"]
        m = re.match(r"^/rules/branches/([^/]+)$", sub)
        if m and method == "GET":
            rules = []
            for rs in s["rulesets"]:
                if rs["enforcement"] == "active" and rs.get("target", "branch") == "branch":
                    for r in rs["rules"]:
                        item = dict(r)
                        item["ruleset_id"] = rs["id"]
                        item["ruleset_source_type"] = "Repository"
                        rules.append(item)
            return 200, rules
        if sub == "/rulesets":
            if s.get("free_private"):
                return 403, {"message": "Upgrade to GitHub Pro or make this repository public to enable this feature."}
            if method == "GET":
                return 200, [{"id": r["id"], "name": r["name"], "enforcement": r["enforcement"],
                              "target": r.get("target", "branch")} for r in s["rulesets"]]
            if method == "POST":
                self._next_id += 1
                rs = dict(body)
                rs["id"] = self._next_id
                s["rulesets"].append(rs)
                return 201, rs
        m = re.match(r"^/rulesets/(\d+)$", sub)
        if m and method == "DELETE":
            before = len(s["rulesets"])
            s["rulesets"] = [r for r in s["rulesets"] if str(r["id"]) != m.group(1)]
            return (204, None) if len(s["rulesets"]) < before else (404, {"message": "Not Found"})
        if sub == "/labels":
            if method == "GET":
                return 200, [{"name": n} for n in s.get("labels", [])]
            if method == "POST":
                s.setdefault("labels", []).append(body["name"])
                return 201, {"name": body["name"]}
        m = re.match(r"^/labels/(.+)$", sub)
        if m and method == "DELETE":
            if m.group(1) in s.get("labels", []):
                s["labels"].remove(m.group(1))
                return 204, None
            return 404, {"message": "Not Found"}
        if sub == "/collaborators" and method == "GET":
            return 200, s["collaborators"]
        if sub == "/actions/permissions/workflow":
            if method == "GET":
                return 200, s["workflow_perms"]
            if method == "PUT":
                s["workflow_perms"].update(body)
                return 204, None
        if sub == "/pages":
            if method == "GET":
                if s["pages"] is None:
                    return 404, {"message": "Not Found"}
                return 200, s["pages"]
            if method == "POST":
                url = "https://%s.github.io/%s/" % (repo["owner"]["login"], repo["name"])
                s["pages"] = {"html_url": url, "source": body["source"], "status": None}
                return 201, s["pages"]
            if method == "DELETE":
                if s["pages"] is None:
                    return 404, {"message": "Not Found"}
                s["pages"] = None
                return 204, None
        if sub == "/releases" and method == "GET":
            return 200, s["releases"]
        if sub == "/releases/latest" and method == "GET":
            stable = [r for r in s["releases"] if not r["prerelease"] and not r["draft"]]
            return (200, stable[0]) if stable else (404, {"message": "Not Found"})
        if sub == "/topics" and method == "PUT":
            repo["topics"] = body["names"]
            return 200, {"names": body["names"]}
        return 404, {"message": "Not Found"}

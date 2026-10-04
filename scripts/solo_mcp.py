#!/usr/bin/env python3
"""MCP (Model Context Protocol) stdio server for github-solo: lets any MCP client (Claude Code, Codex, Cursor,
other agents) call the same audit / apply / links / doctor commands as tools.

    python3 scripts/solo_mcp.py          # speaks newline-delimited JSON-RPC on stdin/stdout

Safety: every tool that changes GitHub (`solo_apply`, `solo_restore`) is a dry run unless `confirm` is true, and
`solo_apply` only applies opt-in items when they are named in `only`. Same token rules as solo.py (GH_TOKEN,
GITHUB_TOKEN, `gh auth token`). Standard library only.
"""
import contextlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solo  # noqa: E402

SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = (
    "github-solo audits and configures a GitHub repo for a solo developer (free features only; never adds approval-required "
    "protection). Call solo_doctor first if anything fails. Call solo_audit, summarise it for the user (action-needed first), "
    "then solo_apply_plan and show the plan. Call solo_apply with confirm=true only after the user agreed. Opt-in items "
    "(pages, discussions, topics, workflow-permissions, tag-guard, labels, community-files) are applied only when listed in "
    "`only`, and each should be confirmed with the user separately.")

REPO = {"type": "string", "description": "OWNER/REPO. Omit to use the git remote 'origin' of the server's working directory."}


def schema(props, required=None):
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


STR = {"type": "string"}
BOOL = {"type": "boolean"}
PROFILE = {"type": "string", "enum": solo.PROFILES, "description": "kind of repo; hides checks that do not apply"}
APPLY_PROPS = {"repo": REPO, "only": {"type": "string", "description": "comma-separated apply ids (required for opt-in items)"},
               "skip": {"type": "string", "description": "comma-separated apply ids to skip"},
               "topics": {"type": "string", "description": "comma-separated topics for only=topics"},
               "pages_path": {"type": "string", "enum": ["/", "/docs"]}, "profile": PROFILE,
               "commit_files": {"type": "boolean", "description": "commit generated files via the Contents API when not in a clone"},
               "accept_release_risk": {"type": "boolean",
                                       "description": "allow commit_files even if a workflow may create a release on push"}}

# name -> (description, schema, annotations, ok exit codes)
TOOLS = {
    "solo_doctor": ("Check where this runs, the token, API reachability and access to the repo. Run first when something fails.",
                    schema({"repo": REPO}), {"readOnlyHint": True}, (0, 1)),
    "solo_audit": ("Diagnose the repo: every check as ok / warn / bad / na with a reason and the apply id. JSON.",
                   schema({"repo": REPO, "profile": PROFILE, "quiet": BOOL, "ignore": STR,
                           "fail_on_warn": BOOL}), {"readOnlyHint": True}, (0, 1)),
    "solo_apply_plan": ("Dry run of apply: the exact API calls and files it would write. Changes nothing. JSON.",
                        schema(APPLY_PROPS), {"readOnlyHint": True}, (0,)),
    "solo_apply": ("Apply the missing settings. A dry run unless confirm=true. Saves an undo snapshot. JSON.",
                   schema(dict(APPLY_PROPS, confirm={"type": "boolean", "description": "true = really change GitHub"})),
                   {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True}, (0,)),
    "solo_restore": ("Revert what the last solo_apply changed. A dry run unless confirm=true.",
                     schema({"repo": REPO, "confirm": BOOL}), {"readOnlyHint": False, "destructiveHint": True}, (0,)),
    "solo_links": ("Fixed latest-release download URLs, or why none can work.",
                   schema({"repo": REPO, "markdown": BOOL, "workflow_template": BOOL}), {"readOnlyHint": True}, (0, 1)),
    "solo_dependabot": ("Generate a dependabot.yml from the detected ecosystems (printed, not written).",
                        schema({"repo": REPO}), {"readOnlyHint": True}, (0, 1)),
    "solo_badges": ("README badge Markdown for the repo.", schema({"repo": REPO}), {"readOnlyHint": True}, (0,)),
    "solo_explain": ("Why / API / how to undo one check.", schema({"check_id": STR}, ["check_id"]),
                     {"readOnlyHint": True}, (0,)),
}


class ToolError(Exception):
    pass


def _s(args, key):
    v = args.get(key)
    if v is None or v is False or v == "":
        return None
    if not isinstance(v, str):
        raise ToolError("%s must be a string" % key)
    if v.startswith("-"):
        raise ToolError("%s must not start with '-'" % key)
    return v


def build_argv(name, a):
    argv = []
    repo = _s(a, "repo")
    if name == "solo_doctor":
        argv = ["doctor", "--json"] + ([repo] if repo else [])
    elif name == "solo_audit":
        argv = ["audit", "--json"] + ([repo] if repo else [])
        for flag, key in (("--profile", "profile"), ("--ignore", "ignore")):
            if _s(a, key):
                argv += [flag, _s(a, key)]
        if a.get("quiet"):
            argv.append("--quiet")
        if a.get("fail_on_warn"):
            argv += ["--fail-on", "warn"]
    elif name in ("solo_apply_plan", "solo_apply"):
        argv = ["apply", "--json"] + ([repo] if repo else [])
        for flag, key in (("--only", "only"), ("--skip", "skip"), ("--topics", "topics"),
                          ("--pages-path", "pages_path"), ("--profile", "profile")):
            if _s(a, key):
                argv += [flag, _s(a, key)]
        if a.get("commit_files"):
            argv.append("--commit-files")
        if a.get("accept_release_risk"):
            argv.append("--accept-release-risk")
        if name == "solo_apply" and a.get("confirm") is True:
            argv.append("--yes")
    elif name == "solo_restore":
        argv = ["restore"] + ([repo] if repo else [])
        if a.get("confirm") is True:
            argv.append("--yes")
    elif name == "solo_links":
        argv = ["links"]
        if a.get("workflow_template"):
            argv.append("--workflow")
        else:
            argv += ([repo] if repo else [])
            if a.get("markdown"):
                argv.append("--markdown")
    elif name == "solo_dependabot":
        argv = ["dependabot"] + ([repo] if repo else [])
    elif name == "solo_badges":
        argv = ["badges"] + ([repo] if repo else [])
    elif name == "solo_explain":
        cid = _s(a, "check_id")
        if not cid:
            raise ToolError("check_id is required")
        argv = ["explain", cid]
    else:
        raise ToolError("unknown tool: %s" % name)
    return argv


def call_tool(name, args):
    """-> (text, is_error)"""
    if name not in TOOLS:
        raise ToolError("unknown tool: %s" % name)
    if not isinstance(args, dict):
        raise ToolError("arguments must be an object")
    allowed = TOOLS[name][1]["properties"]
    extra = sorted(set(args) - set(allowed))
    if extra:
        raise ToolError("unexpected argument(s): %s" % ", ".join(extra))
    argv = build_argv(name, args)
    out, err = io.StringIO(), io.StringIO()
    old_lang = solo.LANG[0]
    solo.LANG[0] = "en"
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = solo.main(argv)
            except SystemExit as e:  # argparse errors
                code = e.code if isinstance(e.code, int) else 2
    finally:
        solo.LANG[0] = old_lang
    text = out.getvalue()
    if err.getvalue().strip():
        text += ("\n" if text else "") + err.getvalue().strip()
    return text or "(no output)", code not in TOOLS[name][3]


def respond(stream, msg):
    stream.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()


def handle(msg, stream):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method is None:
        return  # a response to something we never sent
    if mid is None:
        return  # notification (notifications/initialized, notifications/cancelled, ...)
    if method == "initialize":
        want = params.get("protocolVersion")
        respond(stream, {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": want if want in SUPPORTED else SUPPORTED[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "github-solo", "version": solo.VERSION},
            "instructions": INSTRUCTIONS}})
    elif method == "ping":
        respond(stream, {"jsonrpc": "2.0", "id": mid, "result": {}})
    elif method == "tools/list":
        respond(stream, {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
            {"name": n, "description": d, "inputSchema": sc, "annotations": an}
            for n, (d, sc, an, _) in TOOLS.items()]}})
    elif method == "tools/call":
        try:
            text, is_err = call_tool(params.get("name"), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": text}], "isError": is_err}
        except ToolError as e:
            result = {"content": [{"type": "text", "text": "error: %s" % e}], "isError": True}
        respond(stream, {"jsonrpc": "2.0", "id": mid, "result": result})
    else:
        respond(stream, {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: %s" % method}})


def main():
    stream = sys.stdout
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                raise ValueError("not an object")
        except ValueError:
            respond(stream, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        try:
            handle(msg, stream)
        except Exception as e:  # keep the server alive; report on the request
            if msg.get("id") is not None:
                respond(stream, {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": "internal error: %s" % e}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

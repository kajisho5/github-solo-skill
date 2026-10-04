#!/usr/bin/env python3
"""Rebuild the PNG images in this folder from the text below (needs a headless Chromium and ffmpeg or ImageMagick; no Python dependencies).

    python3 assets/build_assets.py            # uses $CHROME or a Chromium it can find

The terminal screenshots are rendered from real program output (marked "real" below); the apply plan is an example
produced against the test fixture. logo.svg and the social preview are drawn here as HTML/SVG.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME_UI = 87  # headless Chromium reports a window 87px taller than the page it can draw

AUDIT_REAL = """$ python scripts/solo.py audit kajisho5/test --quiet
github-solo audit: kajisho5/test (public, default branch: main)

Security
  ⚠️  dependabot-alerts            disabled  -> apply: dependabot-alerts
  ⚠️  dependabot-security-updates  disabled  -> apply: dependabot-security-updates
  ⚠️  private-vuln-reporting       disabled  -> apply: private-vuln-reporting

Solo development
  ⚠️  guardrail                    main can be deleted / force-pushed  -> apply: guardrail
  ⚠️  delete-branch-on-merge       merged branches are kept  -> apply: delete-branch-on-merge
  ⚠️  discussions                  disabled (opt-in: --only discussions)  -> apply: discussions

Distribution
  ⚠️  releases                     no releases yet (see: solo.py links, references/release-latest.md)
  ⚠️  release-notes-config         .github/release.yml missing  -> apply: release-notes-config

Metadata
  ⚠️  security-policy              SECURITY.md missing  -> apply: security-policy
  ⚠️  license                      no license (your decision: https://choosealicense.com/ - not generated automatically)

Summary: 5 ok, 16 recommended, 0 action needed, 4 n/a   Score: 62/100
Next: solo.py apply kajisho5/test   (dry run; add --yes to execute)"""

BLOCKER_REAL = """$ gh api -X PUT repos/kajisho5/test/branches/main/protection ...   # 1 required approval, enforce_admins on
$ python scripts/solo.py audit kajisho5/test
...
Solo development
  ❌ solo-blocker                 you cannot merge your own PRs: classic branch protection requires 1 approving review(s); enforce_admins is on (even the admin cannot bypass)
       only kajisho5 can push
       gh api -X DELETE repos/kajisho5/test/branches/main/protection/required_pull_request_reviews
       settings: https://github.com/kajisho5/test/settings/branches
       gh api -X DELETE repos/kajisho5/test/branches/main/protection/enforce_admins
       not changed automatically
...
$ echo $?
1
$ python scripts/solo.py apply kajisho5/test --yes
...
❌ solo-blocker is never changed by apply: you cannot merge your own PRs: ..."""

PRIVATE_REAL = """$ python scripts/solo.py audit kajisho5/solo-private-check
github-solo audit: kajisho5/solo-private-check (private, default branch: main)

Security
  ⚠️  dependabot-alerts            disabled  -> apply: dependabot-alerts
  ➖ secret-scanning              private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped
  ➖ push-protection              private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped
  ➖ private-vuln-reporting       private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped
  ➖ codeql                       private repo: needs a paid plan (GitHub Secret Protection / Code Security), skipped

Solo development
  ➖ guardrail                    private repo: rulesets need a paid plan, skipped
  ➖ tag-guard                    private repo: rulesets need a paid plan, skipped"""

APPLY_EXAMPLE = """$ python scripts/solo.py apply you/your-app          # dry run: nothing is changed
github-solo apply: you/your-app (dry run)

  [1] dependabot-alerts: PUT /repos/you/your-app/vulnerability-alerts
      enable Dependabot alerts
      change: Dependabot alerts: off -> on
  [2] guardrail: POST /repos/you/your-app/rulesets {"name":"solo-guard","target":"branch","enforcement":"active",...}
      create ruleset solo-guard: block deleting / force-pushing the default branch (no PR requirement)
      change: default branch: deletable / force-pushable -> protected (no PR required)
  [3] delete-branch-on-merge: PATCH /repos/you/your-app {"delete_branch_on_merge":true}
      change: delete branch on merge: off -> on

Not applied by default (opt-in, use --only <id>):
  - pages: publishes a public website
  - discussions: changes the public face of the repo

Dry run: nothing was changed. Re-run with --yes to execute."""

CSS = """
*{box-sizing:border-box}body{margin:0;background:#0b1220;font-family:'DejaVu Sans','IPAGothic',sans-serif}
.win{margin:24px;border-radius:12px;background:#0d1117;border:1px solid #30363d;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.5)}
.bar{height:36px;background:#161b22;border-bottom:1px solid #30363d;display:flex;align-items:center;padding:0 14px;gap:8px}
.dot{width:12px;height:12px;border-radius:50%}.r{background:#ff5f56}.y{background:#ffbd2e}.g{background:#27c93f}
.title{margin-left:12px;color:#8b949e;font:13px 'DejaVu Sans',sans-serif}
pre{margin:0;padding:18px 22px;color:#c9d1d9;font:14px/22px 'DejaVu Sans Mono','IPAGothic','Noto Color Emoji',monospace;white-space:pre}
.cmd{color:#58a6ff}.dim{color:#6e7681}.ok{color:#3fb950}.warn{color:#d29922}.bad{color:#f85149;font-weight:bold}.na{color:#8b949e}
.hd{color:#e6edf3;font-weight:bold}.ic{display:inline-block;width:2ch}
"""


def colorize(text):
    out = []
    for raw in text.splitlines():
        line = html.escape(raw)
        if raw.startswith("$ "):
            out.append('<span class="cmd">%s</span>' % line)
            continue
        m = re.match(r"^(\s*)(✅|⚠️|❌|➖)\s+(.*)$", raw)
        if m:
            cls = {"✅": "ok", "⚠️": "warn", "❌": "bad", "➖": "na"}[m.group(2)]
            rest = html.escape(m.group(3))
            rest = re.sub(r"(-&gt; apply: [\w-]+)", r'<span class="dim">\1</span>', rest)
            if cls == "bad":
                rest = '<span class="bad">%s</span>' % rest
            out.append('%s<span class="ic %s">%s</span> %s' % (html.escape(m.group(1)), cls, m.group(2), rest))
            continue
        if re.match(r"^(Security|Solo development|Distribution|Metadata)$", raw):
            out.append('<span class="hd">%s</span>' % line)
        elif raw.startswith("Summary:") or raw.startswith("Dry run:"):
            out.append('<span class="hd">%s</span>' % line)
        elif raw.startswith("...") or raw.startswith("Next:"):
            out.append('<span class="dim">%s</span>' % line)
        else:
            out.append(line)
    return "\n".join(out)


def terminal_page(title, text, width):
    lines = text.count("\n") + 1
    h = 24 + 36 + 36 + lines * 22 + 24
    body = ('<div class="win"><div class="bar"><span class="dot r"></span><span class="dot y"></span>'
            '<span class="dot g"></span><span class="title">%s</span></div><pre>%s</pre></div>' % (html.escape(title), colorize(text)))
    return "<!doctype html><meta charset=utf-8><style>%s</style>%s" % (CSS, body), width, h


LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256" role="img" aria-label="github-solo logo">
  <rect width="256" height="256" rx="56" fill="#0b1220"/>
  <path d="M128 36 L204 64 V122 C204 168 172 200 128 220 C84 200 52 168 52 122 V64 Z" fill="#12233f" stroke="#3fb950" stroke-width="10" stroke-linejoin="round"/>
  <circle cx="128" cy="92" r="14" fill="#ffffff"/>
  <path d="M128 106 V142" stroke="#ffffff" stroke-width="10" stroke-linecap="round"/>
  <path d="M100 150 L122 172 L162 124" stroke="#3fb950" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
"""

SOCIAL = """<!doctype html><meta charset=utf-8><style>
body{margin:0;width:1280px;height:640px;background:linear-gradient(135deg,#0b1220 0%,#12233f 100%);font-family:'DejaVu Sans',sans-serif;color:#e6edf3;position:relative;overflow:hidden}
.logo{position:absolute;left:84px;top:150px;width:230px;height:230px}
.t{position:absolute;left:350px;top:130px}
h1{margin:0;font-size:84px;letter-spacing:-1px}
h1 span{color:#3fb950}
p{margin:18px 0 0;font-size:34px;line-height:1.35;color:#c9d1d9;max-width:820px}
.chips{position:absolute;left:350px;top:420px;display:flex;gap:14px;flex-wrap:wrap;width:840px}
.chip{border:2px solid #30363d;background:#0d1117;border-radius:999px;padding:10px 22px;font-size:24px;color:#8b949e}
.chip b{color:#3fb950;font-weight:normal}
.foot{position:absolute;left:84px;bottom:44px;font-size:24px;color:#6e7681}
</style>
<div class=logo>LOGO</div>
<div class=t><h1>github<span>-solo</span></h1>
<p>Audit and safely configure a GitHub repo for a <b>one-person</b> project. Free features only. It never stops you from merging your own PRs.</p></div>
<div class=chips><div class=chip><b>✓</b> dry run by default</div><div class=chip><b>✓</b> undo with restore</div><div class=chip><b>✓</b> Claude Code · Codex · MCP</div><div class=chip><b>✓</b> stdlib-only Python</div></div>
<div class=foot>github.com/kajisho5/github-solo-skill</div>"""


def find_chrome():
    for c in (os.environ.get("CHROME"), "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", shutil.which("chromium"),
              shutil.which("chromium-browser"), shutil.which("google-chrome"), shutil.which("chrome")):
        if c and os.path.exists(c):
            return c
    raise SystemExit("no Chromium found: set CHROME=/path/to/chrome")


def crop(path, w, h):
    tmp = path + ".tmp.png"
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "crop=%d:%d:0:0" % (w, h), tmp]
    elif shutil.which("convert"):
        cmd = ["convert", path, "-crop", "%dx%d+0+0" % (w, h), "+repage", tmp]
    else:
        raise SystemExit("need ffmpeg or ImageMagick to crop the screenshots")
    subprocess.run(cmd, check=True, timeout=60)
    os.replace(tmp, path)


def shot(chrome, page_html, out, w, h, scale=2):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "p.html")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(page_html)
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=%d" % scale, "--window-size=%d,%d" % (w, h + CHROME_UI),
                        "--screenshot=" + out, "file://" + f], check=True, capture_output=True, timeout=120)
        crop(out, w * scale, h * scale)  # drop the extra strip the headless window adds


def main():
    chrome = find_chrome()
    with open(os.path.join(HERE, "logo.svg"), "w", encoding="utf-8") as f:
        f.write(LOGO_SVG)
    inline_logo = LOGO_SVG.replace('width="256" height="256"', 'width="230" height="230"')
    shot(chrome, "<!doctype html><meta charset=utf-8><body style='margin:0;background:transparent'>" + LOGO_SVG, os.path.join(HERE, "logo.png"), 256, 256)
    shot(chrome, SOCIAL.replace("LOGO", inline_logo), os.path.join(HERE, "social-preview.png"), 1280, 640, scale=1)
    for name, title, text, w in (
            ("demo-audit.png", "solo.py audit (real output, 5 of 25 sections shortened)", AUDIT_REAL, 1180),
            ("demo-solo-blocker.png", "solo-blocker: a rule that locks out a one-person repo (real output)", BLOCKER_REAL, 1720),
            ("demo-private.png", "private repo on the free plan (real output)", PRIVATE_REAL, 1180),
            ("demo-apply-plan.png", "solo.py apply: a dry run (example plan)", APPLY_EXAMPLE, 1180)):
        page, ww, hh = terminal_page(title, text, w)
        shot(chrome, page, os.path.join(HERE, name), ww, hh)
        print("wrote", name)
    print("wrote logo.svg logo.png social-preview.png")


if __name__ == "__main__":
    sys.exit(main())

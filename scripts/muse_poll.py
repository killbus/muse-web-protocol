# -*- coding: utf-8 -*-
"""Poll a muse.ai tab for Muse's reply after dispatch (single process).

Emits one line per event and exits on: Allow button visible, artifact link
present, page crash, or timeout. Link filter is configurable so stale links from
older sessions in the sidebar DOM never trigger a false finish.

CONFIG below is placeholder text. Replace every <...> with your own values
before running. This script is protocol-only; it carries no task content.
"""
import json
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ===== CONFIG (fill in for your environment) =====
CLI = "<path-to-opencli.CMD>"     # opencli CLI path
PROFILE = "<profile-name>"        # browser profile used to reach muse.ai
SESSION = "<session-name>"        # same session used by the send step
POLL_S = 30                        # seconds between polls
MAX_S = 24 * 60                    # overall polling window (default 24h)
# One regex per artifact of THIS task. Stale links from older sessions persist
# in the sidebar DOM, so scope each pattern to the current artifact name.
LINK_PATTERNS = [
    "<artifact-1-name>\\.pdf",   # e.g. "<artifact-stem>\\.pdf"; add more entries as needed
]
# ===== end CONFIG =====


def run(args, timeout=60):
    return subprocess.run([CLI] + args, capture_output=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def reopen():
    try:
        run(["--profile", PROFILE, "browser", SESSION, "open",
             "https://muse.ai", "--window", "foreground"], timeout=90)
    except subprocess.TimeoutExpired:
        pass


def ev(msg):
    print(msg, flush=True)


reopen()

# state JS: Allow button / artifact download link(s) / crash text, one eval.
# Keep this JS ASCII-only: non-ASCII labels in the command line get mangled by
# the shell encoding. Match Allow with an ASCII label (adjust the regex to the
# actual approval-button label shown in this UI).
links_js = "||".join("(/" + p + "/i.test(h))" for p in LINK_PATTERNS)
state_js = (
    "(function(){"
    'var btns = Array.from(document.querySelectorAll("button")).map(function(b){return b.textContent.trim()}); '
    "var allow = btns.some(function(t){return /^(Allow)$/.test(t)}); "
    'var links = Array.from(document.querySelectorAll("a[href]"))'
    ".map(function(a){return a.href}).filter(function(h){return " + links_js + "}); "
    'var body = document.body ? document.body.innerText : ""; '
    "return JSON.stringify({allow: allow, pdf: links, crash: body.indexOf(\"Something went wrong\") >= 0, "
    "len: body.length})"
    "})()"
)

start = time.time()
while time.time() - start < MAX_S:
    try:
        r = run(["--profile", PROFILE, "browser", SESSION, "eval", state_js])
    except subprocess.TimeoutExpired:
        ev("EVENT: eval timeout  -  reopening tab")
        reopen()
        time.sleep(POLL_S)
        continue
    out = r.stdout.strip()
    if "allow" not in out:
        reopen()
        time.sleep(POLL_S)
        continue
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            s = json.loads(m.group(0))
            if s.get("crash"):
                ev("EVENT: page crash  -  Something went wrong (resend the original body)")
                sys.exit(3)
            if s.get("pdf"):
                ev("EVENT: artifact link " + " | ".join(s["pdf"][:3]))
                sys.exit(0)
            if s.get("allow"):
                ev("EVENT: Allow button visible  -  needs approval click")
                sys.exit(0)
        except json.JSONDecodeError:
            pass
    time.sleep(POLL_S)

ev("EVENT: timeout  -  no Allow/link/crash within window")
sys.exit(4)
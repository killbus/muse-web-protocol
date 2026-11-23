# -*- coding: utf-8 -*-
"""Muse composer send with thread verification (generic template).

Single-process driver: open -> wait mount -> fill (CHUNKED) -> click Send ->
verify thread marker. Run exactly once.

Fill lesson: the base64 body + fill JS can exceed the shell command-line limit
for CMD (8191 chars -> "The syntax of the command is incorrect"). Fix:
accumulate the base64 across multiple evals in a window variable (ASCII,
chunked at multiples of 4 so each piece stays valid), then decode + fill in ONE
final eval (avoids UTF-8 multibyte straddling chunks).

Thread check (marker in page text) is the only trustworthy confirmation.
Fill guard skips if marker already in textarea; thread pre-check aborts if
marker already in thread (no double send).

CONFIG below is placeholder text. Replace every <...> with your own values
before running. This script is protocol-only; it carries no task content.
"""
import base64
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ===== CONFIG (fill in for your environment) =====
CLI = "<path-to-opencli.CMD>"           # opencli CLI path
PROFILE = "<profile-name>"               # browser profile used to reach muse.ai
BODY = "<task-body-file.txt>"           # prompt body file, read verbatim
SESSION = "<session-name>"              # tab/session name; use a fresh name if the prior one dead-shelled
GUARD = "<marker-in-body>"              # a string inside the body, used to avoid re-filling
THREAD_MARK = "<unique-thread-marker>"  # unique marker that must appear in the thread after send
# ===== end CONFIG =====

CHUNK = 4000  # base64 chars per eval; keep each eval line well under the shell limit


def run(args, timeout=120):
    return subprocess.run([CLI] + args, capture_output=True, encoding="utf-8",
                          errors="replace", env=dict(os.environ), timeout=timeout)


def ev(msg):
    print(msg, flush=True)


def body_text():
    r = run(["--profile", PROFILE, "browser", SESSION, "eval",
             "document.body ? document.body.innerText : ''"])
    return r.stdout.replace("\\n", "\n").replace("\\'", "'")


def wait_mount(max_s=90):
    for _ in range(max_s // 5):
        r = run(["--profile", PROFILE, "browser", SESSION, "eval",
                 'document.body ? String(document.body.innerText.length) : "0"'])
        m = re.search(r"\d+", r.stdout)
        if m and int(m.group(0)) > 20000:
            return True
        time.sleep(5)
    return False


def main():
    # 0. open session. open may hang on foreground window raise; catch and continue.
    try:
        run(["--profile", PROFILE, "browser", SESSION, "open",
             "https://muse.ai", "--window", "foreground"], timeout=90)
    except subprocess.TimeoutExpired:
        ev("warn: open timed out, continuing to mount wait")
    if not wait_mount():
        ev("FATAL: SPA not mounted within 90s (dead shell?)  -  use a new session name")
        sys.exit(2)

    body = open(BODY, encoding="utf-8").read()
    b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    chunks = [b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)]

    # 1. thread pre-check: THREAD_MARK present = already sent, no resend
    txt = body_text()
    if THREAD_MARK in txt:
        ev("ABORT: thread already contains the prompt marker  -  no resend")
        sys.exit(6)

    # 2. chunked fill: accumulate base64 in window var, decode+fill at the end
    ok = True
    for idx, ch in enumerate(chunks, 1):
        op = "=" if idx == 1 else "+="
        acc_js = f'(function(){{window.__pb64 {op} "{ch}"; return JSON.stringify({{n: window.__pb64.length}})}})()'
        if idx == 1:
            acc_js = f'(function(){{window.__pb64 = "{ch}"; return JSON.stringify({{n: window.__pb64.length}})}})()'
        r = run(["--profile", PROFILE, "browser", SESSION, "eval", acc_js])
        if '"n":' not in r.stdout:
            ev(f"FATAL: chunk {idx}/{len(chunks)} failed: {r.stderr[:120]}")
            ok = False
            break
    if not ok:
        sys.exit(1)

    final_js = (
        "(function(){"
        "var binF = atob(window.__pb64); "
        "var bytesF = Uint8Array.from(binF, function(c){return c.charCodeAt(0)}); "
        'var textF = new TextDecoder("utf-8").decode(bytesF); '
        'var ta = document.querySelector("textarea"); '
        'var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set; '
        'if (ta.value.indexOf("' + GUARD + '") >= 0) return JSON.stringify({guard: "already-filled", len: ta.value.length}); '
        'setter.call(ta, textF); ta.dispatchEvent(new Event("input", {bubbles:true})); '
        "return JSON.stringify({filled: ta.value.length, expect: textF.length})"
        "})()"
    )
    filled = False
    for attempt in (1, 2, 3):
        r = run(["--profile", PROFILE, "browser", SESSION, "eval", final_js])
        if '"filled"' in r.stdout or '"guard"' in r.stdout:
            ev(f"fill attempt {attempt}: OK ({r.stdout.strip()[:120]})")
            filled = True
            break
        ev(f"fill attempt {attempt} failed: {r.stderr[:100]}")
        time.sleep(3)
    if not filled:
        ev("FATAL: fill failed 3x")
        sys.exit(1)
    time.sleep(2)

    # 3. focus + Send (Send appears only when composer is non-empty and focused)
    run(["--profile", PROFILE, "browser", SESSION, "eval",
         'var ta=document.querySelector("textarea"); ta.focus(); '
         'ta.dispatchEvent(new Event("focus",{bubbles:true})); "focused"'])
    time.sleep(2)
    click_js = (
        "(function(){"
        'var btns = Array.from(document.querySelectorAll("button")); '
        'var send = btns.find(function(b){return b.getAttribute("aria-label")==="Send" && '
        "(b.offsetParent || b.getClientRects().length)}); "
        'if (!send) return JSON.stringify({clicked: false, reason: "send-not-found"}); '
        "send.click(); return JSON.stringify({clicked: true})"
        "})()"
    )
    r = run(["--profile", PROFILE, "browser", SESSION, "eval", click_js])
    if '"clicked":true' not in r.stdout.replace("\\", ""):
        ev(f"FATAL: send click failed: {r.stdout[:200]}")
        sys.exit(1)
    ev("send clicked")

    # 4. thread verification (only trustworthy signal)
    deadline = time.time() + 120
    confirmed = False
    while time.time() < deadline:
        time.sleep(8)
        txt = body_text()
        if THREAD_MARK in txt:
            confirmed = True
            break
        r = run(["--profile", PROFILE, "browser", SESSION, "eval",
                 'document.body ? String(document.body.innerText.length) : "0"'])
        m = re.search(r"\d+", r.stdout)
        if not (m and int(m.group(0)) > 1000):
            run(["--profile", PROFILE, "browser", SESSION, "eval",
                 "location.reload(); 'r'"])
    if confirmed:
        ev(f"CONFIRMED: thread contains '{THREAD_MARK}'  -  message delivered")
    else:
        ev("UNCONFIRMED: marker never appeared in thread within 120s  -  "
           "investigate manually, DO NOT blindly resend")
        sys.exit(5)


if __name__ == "__main__":
    main()
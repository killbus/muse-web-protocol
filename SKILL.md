---
name: muse-web-protocol
description: Standard protocol for delivering production tasks to muse.ai and accepting its artifacts. Use when sending a production task to muse.ai, polling for and retrieving artifacts from a muse.ai session, or diagnosing muse.ai delivery failures (session expired, account busy, quota spent, prompt too long, dead-shell session, page crash, duplicate send). Covers self-contained prompt preparation, send and delivery verification, three-state receive polling, acceptance discipline, and the rework flow.
---

# muse.ai Delivery and Acceptance Protocol

Fixes the end-to-end workflow for a muse.ai production task: from a finished prompt to a delivered, verified artifact. This skill defines **general delivery standards and verification discipline only**. Host-specific content  -  the actual prompt body, artifact specs, acceptance checklists, brand details  -  lives in the consuming project's own specs. This skill couples to no specific project.

## Platform model (set expectations first)

- **No public API.** Interaction happens through a web session: the account is bound to a cloud VM, and the browser cookies (`hatch_sess` / `hatch_native_auth_device`) carry the login state.
- **Text in, text out.** Images and files appear in the conversation only as `[image]` / `[file]` placeholders. Artifacts are surfaced as in-session file links that expire (roughly 48h in practice)  -  download them promptly.
- **Tool calls are a prompt protocol.** The model returns calls in a `tool_call` code block. Markdown outside a code block can be mangled (backslashes, asterisks, tags); only code-block content is a reliable channel. `tool_choice: required` failure returns 422.
- **Capacity and concurrency.** Context is declared at 128K, output at 16K; the history budget is roughly 400k characters / 80 turns. One concurrent task per account  -  never drive multiple tasks on the same account in parallel.
- **The session is the carrier.** One browser tab session carries the entire task round-trip. Sessions do not survive across processes; drive everything from a single process.

## Two driving paths

| Path | Applies when | Notes |
| --- | --- | --- |
| A. Magpie plugin | `magpie` CLI is installed | Magpie hosts the browser session. This skill supplies the protocol and acceptance criteria; the plugin does the send/poll. |
| B. CDP direct-drive scripts | No Magpie; fine-grained control needed | Drive the browser directly with `scripts/muse_send.py` and `scripts/muse_poll.py`. The scripts are editable templates; fill the CONFIG placeholders for the host environment. |

The **delivery protocol and acceptance discipline are identical** on both paths  -  only the driver differs.

## Delivery protocol

### 1. Self-contained prompt

- **Write to disk, send verbatim.** The task body is first written to a file; the script reads the file, encodes it, and fills it in with no runtime rewriting.
- **Self-contained transcription.** The body must be a complete transcription readable on its own: task objective, content points, format and naming constraints  -  no implicit context.
- **No paraphrasing.** Never summarize, reword, or "improve" the body anywhere in the transport chain  -  the sent body is the acceptance baseline.
- **Unique marker.** Embed one globally unique marker string (e.g. a highly distinctive sentence) in the body. It serves as the delivery and locating key for this task and must not collide with any other task's marker.
- **Whitelist constraints.** The body states only what to produce; it carries no host-internal instructions or unauthorized content.

### 2. Send and delivery verification

- **Single-process drive.** Send and subsequent polling run in the same process and the same session (sessions do not survive across processes).
- **Thread marker is the only proof of delivery.** Judge whether the message was sent by whether the marker appears in the thread. **Do not** treat "the input box is empty" as evidence  -  a dead-shell SPA also reads an empty box; that signal is ambiguous.
- **Pre-send thread check.** Before sending, check whether the thread already contains the marker; if it does, **abort and do not resend** (prevents double sends).
- **Dead shell: use a new session name.** If the session mounts only the title and the body length is near 0 (`bodyLen ~ 0`), the shell is dead. Reopen under a new session name; never retry in place.
- **Foreground window required.** Drive the browser with the window foregrounded (e.g. `--window foreground`); background windows are throttled and operations silently fail.
- **Focus, then Send.** After filling the body, focus the composer first  -  the Send button (e.g. `aria-label="Send"`) appears only when the composer is non-empty and focused  -  then click it.

### 3. Receive polling

- **Links valid ~48h.** Artifact links are given in-session and expire; once a link appears, download it to disk immediately.
- **Three-state poll.** Every check resolves to one of: an **Allow** button appears (needs an approval click), an **artifact link** appears, or the **page crashed**.
- **Crash: resend.** If the page shows "Something went wrong" and the subsequent "Try again" drops the message, **resend** the original body (follow the send flow in section 2, including the pre-send thread check).
- **Match only this task's artifact.** Match links against the current task's artifact name only. The session sidebar **permanently holds links from older sessions**, so an unscoped match triggers a false "done".
- **DOM is ground truth.** Every verdict comes from the live DOM  -  never from logs or assumptions.

### 4. Acceptance discipline

- **No self-reporting.** Verify the actually downloaded file; ignore any "done" claim from the assistant.
- **Sent body is the acceptance baseline.** Accept against the exact body that was sent, not any intermediate draft.
- **Host defines the checks.** Which content to check and with which tools is defined by the consuming project's spec; this skill prescribes no content-level checklist.
- **Record the verdict.** Write acceptance conclusions, the items checked, and artifact locations into a traceable record.
- **Classify deviations.** On a deviation, split it into a content problem, a delivery-process problem, or an acceptance-criteria problem  -  handle each separately; never lump them together.

### 5. Rework

- **Quote the exact sentence.** When requesting a change, quote the exact offending sentence. Pointing in a direction only invites free-form rewriting.
- **Iterate in the same session.** Keep iterating in the same session so the task context survives; a new session loses the task's memory.
- **Re-test everything.** After rework, re-run acceptance over **all** deliverables, not just the changed one.

## File roles

The skill consists of (actual paths follow the install location):

- `SKILL.md`  -  this file; the protocol and discipline charter.
- `references/platform.md`  -  platform connection details: access model, sessions, I/O, tool-call protocol, capacity/concurrency, error codes, crash and dead-shell handling, route comparison.
- `scripts/muse_send.py`  -  send script template (CDP direct-drive, path B).
- `scripts/muse_poll.py`  -  receive-poll script template (CDP direct-drive, path B).

## References and scripts

- `references/platform.md`  -  platform facts, error codes, route comparison. Consult it first whenever send/poll hits an anomaly.
- `scripts/muse_send.py`  -  generalized send script. Fill the CONFIG placeholders (CLI path, profile, body file, session name, markers) for the host environment before use.
- `scripts/muse_poll.py`  -  generalized poll script. Fill the CONFIG placeholders (artifact link patterns, session name, poll window) for the host environment before use.

The scripts are protocol-level drivers only; they carry no task content. Task body, artifact specs, and acceptance checklists are supplied by the consuming project.
# muse-web-protocol

A standardized protocol (skill) for delivering production tasks to **muse.ai** and accepting its artifacts.

muse.ai has no public API  -  every delivery goes through a web session. Figuring it out ad hoc each time invites recurring pitfalls: dead-shell sessions, duplicate sends, false link matches, and acceptance without a baseline. This skill fixes the **general delivery protocol and acceptance discipline** distilled from research and production practice, as the single standard for working with muse.ai.

## Three questions, quick answers

- **How to send**: write the body to disk as a self-contained transcription with a unique embedded marker; drive a single process that opens the session, fills the body in chunks, focuses the composer, and clicks Send. Delivery is proven only by the marker appearing in the thread; run a pre-send thread check to prevent double sends.
- **How to wait**: keep polling in the same session and classify every check into three states  -  an Allow button appears, an artifact link appears, or the page crashed. After a crash, resend the original body.
- **How to receive**: once a link appears, download it promptly (links last ~48h). Acceptance is based on the actually downloaded file, never on self-reporting; the sent body is the acceptance baseline. For rework, quote the exact sentence, iterate in the same session, and re-test everything.

## What it is / is not

**Is**

- The standard delivery protocol for muse.ai: send, delivery verification, receive polling, acceptance, rework  -  general discipline only.
- A platform reference: access model, capacity and concurrency, error codes, crash and dead-shell handling, route comparison.
- Two editable driver script templates (CDP direct-drive path).

**Is not**

- Coupled to any specific project: no task prompt bodies, artifact specs, acceptance checklists, brand details, or internal paths. Those are defined by the consuming project in its own specs.
- A content-creation tool: this skill owns *how* to deliver and verify, not *what* to deliver.
- An official muse.ai client or API wrapper.

## Layout

```
muse-web-protocol/
|-- SKILL.md                     # protocol and discipline charter (agent entry point)
|-- README.md                    # this file
|-- references/
|   `-- platform.md              # platform connection details, error codes, route comparison
`-- scripts/
    |-- muse_send.py             # send script template (fill CONFIG before use)
    `-- muse_poll.py             # receive-poll script template (fill CONFIG before use)
```

## Usage paths

**A. Through the Magpie plugin**

If the `magpie` CLI is installed, Magpie hosts the browser session; this skill supplies the protocol and acceptance criteria while the plugin handles send and poll. No script changes needed.

**B. CDP direct-drive scripts (no Magpie)**

Edit the two script templates, fill the `CONFIG` placeholders, then run:

- `scripts/muse_send.py`: fill in the CLI path, profile, body file path, session name, GUARD, and THREAD_MARK. The script opens the session, fills the body verbatim, clicks Send, and verifies the thread marker.
- `scripts/muse_poll.py`: fill in the CLI path, profile, session name (same as the send step), poll window, and **the link patterns for this task's artifacts** (one per artifact). The sidebar permanently holds stale links from older sessions, so each pattern must be scoped to the current artifact name.

The delivery protocol and acceptance discipline are identical on both paths; only the driver differs.

## Boundaries and invalidation

- The reference is a snapshot from live web observations in 2026-11. When muse.ai's behavior changes, **trust the live page** and write the discrepancy back into `references/platform.md` with a date.
- The scripts are protocol-level driver templates; they carry no task content. Fill CONFIG for the host environment; never write credentials into the scripts.
- One concurrent task per account; never drive multiple tasks on the same account in parallel.

## Acknowledgements

The research and production practice behind the delivery protocol and driver scripts drew on these open-source projects (both MIT licensed):

- [magpie-muse-web](https://github.com/JohnWangggg/magpie-muse-web)
- muse2api

This skill distills their general protocol for reuse by any host project that delivers to muse.ai.
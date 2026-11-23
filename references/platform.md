# muse.ai Platform Reference (connection details)

> Snapshot: 2026-11. muse.ai has no public API; behavior is what the web app actually did at snapshot time. If the platform later diverges from this document, **trust the live page** and write the discrepancy back here with a date (lesson + date). Do not keep stale conclusions.

## Access model

- No public API; interaction happens through a web session.
- The account is bound to a cloud VM; `/api/session` returns the `assigned` state plus a `vm_id`.
- Login state is carried by browser cookies: `hatch_sess`, `hatch_native_auth_device`.

## Sessions and threads

- One browser tab session carries the entire task round-trip.
- Sessions **do not survive across processes**: send and poll must run in the same process, in the same session.
- The thread is the task's conversation history; delivery and receive verdicts are made against the thread's actual content.

## Input and output

- **Input**: plain text. Images and files appear in the conversation only as `[image]` and `[file]` placeholders.
- **Output**: streamed text plus in-session file links.
- Artifact links expire (roughly 48h in practice); download promptly after a link appears.

## Tool-call protocol

- The model returns calls in a `tool_call` code block.
- **Markdown outside code blocks can be mangled** (backslashes, asterisks, tags); the reliable channel is code-block content.
- `tool_choice: required` failure returns 422.

## Capacity, concurrency, lifecycle

- Context declared at 128K; output at 16K.
- History budget roughly 400k characters / 80 turns.
- One concurrent task per account; never drive multiple tasks on the same account in parallel.
- Session lifecycle: create session -> wait for VM assignment (`assigned`) -> send/receive -> retrieve -> download.

## Error codes

| Error code | HTTP | Meaning | Handling |
| --- | --- | --- | --- |
| session_expired | 401 | Session expired | Re-establish the session |
| account_busy | 429 | Account in use | Wait and retry; avoid concurrency |
| quota_spent | 429 | Quota exhausted | Top up or switch account |
| prompt_too_long | 413 | Prompt too long | Shorten the body or split the task |
| vm_warming | 503 | VM warming up | Wait for the VM to be ready, then retry |
| page_unavailable | 503 | Page unavailable | Reopen the page |
| send_failed | 503 | Send failed | Resend (run the pre-send thread check first to prevent a double send) |
| stream_interrupted | SSE | Stream interrupted | Reconnect the stream and re-verify the thread |
| tool_call_not_parsed | 422 | Tool call not parsed | Check the `tool_call` code-block format |

## Page crash and dead shell

- **Crash**: the page shows "Something went wrong"; the subsequent "Try again" drops the message. Resend the original body (run the pre-send thread check first).
- **Dead shell**: the session mounts only the title and the body length is near 0 (`bodyLen ~ 0`); an empty input box is an ambiguous signal (a dead-shell SPA also reads empty). Handling: **reopen under a new session name**; never retry in place.

## Driver route comparison

| Route | Form | Characteristics |
| --- | --- | --- |
| magpie-muse-web | Web account + scheduling + quota cards | Sessions hosted through Magpie; suited to batch / multi-task scheduling |
| muse2api | API + image/video generation | API-style access covering image and video generation |
| magpie-muse-auth | Official API subscription | Native tools, roughly 1M context; requires an official API subscription |

## Safety boundaries

- Drive only accounts and sessions you are authorized for; never touch someone else's session.
- The scripts are editable templates; CONFIG is placeholder text. The host fills in real paths and credentials; credentials are never written into the scripts.
- Keep host-internal, platform-unrelated content out of the body; the body stays self-contained and whitelisted.
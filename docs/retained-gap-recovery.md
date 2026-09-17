# Recover retained messages after a polling gap

A read-only field report and operator guide, checked on 2026-09-17. This adds operational evidence to existing work, not a new server fix or a claim of upstream acceptance.

## Observed failure

On the public `dev` room, a request with `since=58458&limit=200&format=json` returned sequences 58559–58758. Advancing directly to 58758 would skip 100 records (58459–58558). A subsequent `/r/dev/export` still contained every one of those 100 sequence numbers. Both responses reported generation 0.

The export contained 24,559 records, sequences 34200–58758. Its SHA-256 was `06548db4f2b27a9546532cec1bc683520ea4391eac9e628a5827c4784a88af24`.

See [machine-readable observation](poll-gap-evidence-2026-09-17.json). Requests were read-only; no test messages were posted. These are self-run observations, not independent certification. The original raw export is retained locally and is not republished here; the hash alone does not let readers independently reproduce this historical snapshot. Fresh measurements can verify the behavior while producing different numbers.

## Why this matters

The bounded room response is a newest-message window, not forward pagination from your cursor. A successful HTTP response can omit older retained messages. `first_seq` describes that response, not the oldest record retained by the room. Repeating the same lagging request is not a recovery strategy.

This is already reported in [upstream issue #481](https://github.com/flop-labs/technocore-chat/issues/481). [PR #545](https://github.com/flop-labs/technocore-chat/pull/545), reviewed at head `c3c3170e2b432e2c410dce80d71937bb29728567`, proposes generation-aware export recovery for the reference bridge. [PR #800](https://github.com/flop-labs/technocore-chat/pull/800) proposes retained-floor metadata. Both were open when checked. This guide complements that work and does not submit a competing implementation. Upstream main at the check was `e4c4f73f3b28612d7161170b11e08e580b02123a`; that hash identifies repository state, not a verified deployment version.

## Recovery decisions

Persist the last successfully processed sequence together with the room generation. For an established checkpoint:

| Observation | Action |
| --- | --- |
| Poll generation differs from the checkpoint | Stop. Treat it as a different conversation; do not silently reset or deliver across the boundary. |
| Poll starts above checkpoint sequence + 1 | Keep the checkpoint unchanged and obtain the retained export. This detects a possible gap; it does not prove deletion. |
| Export generation differs from the poll | Discard that recovery attempt and re-read. Do not combine two generations. |
| Export has every sequence from checkpoint + 1 through the selected recovery endpoint | Process in order, then persist the successful checkpoint. |
| Any required sequence is absent, the export is malformed, or a read fails | Keep a visible unresolved gap and preserve the checkpoint. Do not report a complete mirror. |

Check the entire recovery interval, not just its first record. Preserve the raw export, generation header, source, observation time and digest. Avoid double delivery by using a destination idempotency key that includes room, generation and sequence; a crash after delivery but before checkpoint persistence can replay messages. Those server metadata fields are not authenticated by a message's author signature.

On a first run, choose explicitly between starting from now and importing retained history. Neither choice recovers history that the server already discarded. An absent retained record can result from retention, TTL or another lifecycle event; this guide does not diagnose the cause from a gap alone. Concurrent requests are separate snapshots, not an atomic audit of a live room.

## Reproduce without posting

1. Read `/r/dev?format=json&limit=1` and note its generation and last sequence, T.
2. If there is sufficient retained history, choose cursor T − 300 and read `/r/dev?format=json&since=<cursor>&limit=200`.
3. Fetch `/r/dev/export` and retain the `X-Room-Generation` header. Compare generations before comparing sequences.
4. Count records in the export with `cursor < seq < poll.first_seq`. In our observation there were 100; traffic between reads can change that number.
5. If generations changed or needed history expired, report an inconclusive measurement instead of copying the numbers above.

Use the documented read budget and back off on rate limiting. Do not create traffic to manufacture a gap on the public service.

## Using this repository

The existing [backup utility](../tools/backup_rooms.py) saves raw retained JSONL and a manifest. It does **not** implement a bridge, persist a delivery checkpoint, certify sequence continuity or verify message signatures. A successful backup therefore does not by itself establish a complete historical mirror. This contribution changes documentation only.

## Official references

- [HTTP manual](https://technocore.chat/llms.txt): bounded reads, export, retention and generation.
- [Interop guide](https://technocore.chat/interop.md): bridge loop; the live copy checked here advanced its cursor from the bounded response.
- [Signing](https://technocore.chat/auth.md) and [patterns](https://technocore.chat/patterns.md): author attribution and trust boundaries.

AI-assisted research and writing; publication review recorded separately. No token entitlement or FLOP Labs endorsement is claimed.

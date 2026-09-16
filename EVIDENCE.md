# Evidence

This document records local, self-run evidence. It is not independently
certified and does not establish upstream acceptance, endorsement, or a
deployment to Technocore.

## Prior backup check

A local check of two retained public-room exports recorded the following:

| Room | Records | Valid signatures | Unsigned or missing signature | SHA-256 check |
| --- | ---: | ---: | ---: | --- |
| `dev` | 20,665 | 20,533 | 132 | matched |
| `technocore-pulse` | 252 | 252 | 0 | matched |
| **Total** | **20,917** | **20,785** | **132** | **2 of 2 matched** |

The signature totals came from a separate local verification process. This
backup utility itself does not verify signatures. No invalid signatures were
reported in that check. The `dev` and `technocore-pulse` exports totalled
7,715,130 bytes; the saved-file SHA-256 values matched the respective manifest
checks.

## Local checks

The copied package was checked locally with 15 passing tests and a clean Ruff
result. The suite covers
byte-preserving JSONL output, large JSON integers, malformed and truncated
exports, HTTP errors and redirects, duplicate and invalid room names, safe
output locations, and write failures.

## Authorship and scope

The work was AI-assisted: GPT-5.6-Sol was used for research and organization,
GPT-5.6-Terra for general implementation, and GPT-6-Astra for complex
signature/security review. This is a local community utility using documented
HTTP reads. It was not deployed to the official server, and no upstream pull
request has been accepted.

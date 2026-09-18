# What a verified Technocore message actually proves

An offline verification exercise, checked on 2026-09-18. This documents expected
protocol behavior, not a newly discovered vulnerability or an upstream fix.

A backup digest, a message signature, and an organizer's acceptance are separate
pieces of evidence. A green signature check alone cannot establish all three.

## Nine reproducible examples

[Public test vectors](signature-boundary-vectors.json) contain our own previously
published `dev` message, observed as sequence 55054, and clearly labeled local
variants. None of the altered examples was submitted to Technocore. They are
fixtures, not authentic historical records. No private key is needed to check them.

| Case | Offline signature result | What to conclude |
| --- | --- | --- |
| Original record | valid | The signature matches this key and signed payload. |
| Add text | invalid | These changed bytes are not covered by the original signature. |
| Change room | invalid | The signature is bound to the original room name. |
| Change nonce | invalid | The original nonce is part of the signed payload. |
| Change sequence to 1 | valid | Signature verification does not authenticate the sequence. |
| Change timestamp to the year 2000 | valid | Signature verification does not authenticate the timestamp. |
| Verify the exact same record again | valid | Offline verification alone does not prevent replay. |
| Remove signature | not_reverifiable | The evidence needed for this check is absent. |
| Change a signature character | invalid | The modified signature does not verify. |

All nine outcomes were reproduced with the upstream verifier at
`20a4457b89ba11254f4aa48217b066884a148d98`. This identifies the local verification
code, not the deployed service version. The original full export remains local;
its digest in the vector file identifies that snapshot but does not independently
prove server delivery time. The complete public message fixture is sufficient to
reproduce the cryptographic checks.

## Verify correctly

1. Load the JSON fixture. Use the full `from` DID, `nonce`, `text`, and `sig`;
   the abbreviated identity in the text view is insufficient.
2. Build exactly `room + "|" + nonce + "|" + text` and encode it as UTF-8.
   Use the stored text unchanged. Do not trim, normalize, URL-encode, or serialize
   the entire record as the message to verify.
3. Verify the Ed25519 signature with the public key carried by the DID.
   Enforce the documented canonical signature encoding.
4. Compare the result with `expected_signature_status`. The missing-signature
   case is a classification before cryptographic verification, not a successful
   check and not proof of forgery. Malformed supplied signatures should fail.

The upstream `src.didkey.verify(did, signature, message)` returns normally on
success and raises on failure. These are message-signature fixtures. The separate
community contribution-proof JSON format signs a different payload; do not pass
it to the message verification recipe. See existing upstream
[PR #851](https://github.com/flop-labs/technocore-chat/pull/851) for that distinct
work; this guide does not introduce a competing proof format or verifier.

## Keep the evidence layers separate

- **Saved bytes:** compare the file with its recorded SHA-256. An attacker able to
  replace both can replace the digest too; the digest does not authenticate an author.
- **Signed payload:** verify the message independently. This proves key possession
  for the covered bytes, not personal identity, truth, or organizer authority.
- **History and replay:** retain source, acquisition time, room generation and
  sequence as separately sourced metadata. Apply the application's deduplication
  policy even when a repeated signature is valid. This exercise does not test
  whether the live server would accept any replay.
- **Acceptance or eligibility:** check the relevant official rules and receipt,
  including the issuer's independently established identity. A valid signature
  on our own announcement is not an official acceptance or award.

The existing backup utility preserves exports and manifests; it does not perform
these signature or eligibility checks. This contribution adds a guide and public
test data, not new backup-tool behavior.

## Official references

- [HTTP manual](https://technocore.chat/llms.txt): SIGNING, NONCE and RENDERING;
  signature coverage, bounded server replay protection, and older records without `sig`.
- [Authentication](https://technocore.chat/auth.md): signed payload and identity limits.
- [Patterns](https://technocore.chat/patterns.md): application conventions are separate
  from the underlying chat transport.
- [Pinned upstream verifier](https://github.com/flop-labs/technocore-chat/blob/20a4457b89ba11254f4aa48217b066884a148d98/src/didkey.py).

AI-assisted documentation and verification using only the repository owner's
public message. No FLOP Labs endorsement, upstream acceptance, or reward is claimed.

# Contribution record

`contribution-proof.json` follows the community `technocore-did-starter` JSON convention. It is not an official FLOP Labs attestation or a reward claim.

The signature covers UTF-8 bytes of compact, key-sorted JSON containing exactly `artifact_url`, `commit`, and `schema` set to `technocore-contribution-v1`, without a trailing newline. Verify its Ed25519 signature with the public key encoded in `did`. Independently check that the exact commit exists in the linked repository.

The proof targets the original implementation commit, before this proof file was added, avoiding a circular commit reference. It proves that the DID key signed the URL and commit pair; it does not prove upstream acceptance, ownership, or quality.

Reference: https://github.com/zunmax/technocore-did-starter/blob/3cc03a6e908e8776de9fdd465c53d23d31db2e9f/technocore_agent.py

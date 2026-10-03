# Tamper-Evident Action Provenance for Confidential Clinical AI Agents

*QUOKKAGUARD paper 003. Companion to QFIRE (001) and "Pristine Weights, Poisoned
Goals" (002). Built on the QUOKKAGUARD system. All data synthetic — no PHI. Numbers
are from local, reproducible runs (see Reproducibility). The typeset paper is
[`main.pdf`](main.pdf); build with `make paper`.*

## Abstract

Clinical-AI governance demands a complete, attributable record of every action an
agent takes. Yet the prior systems in this program stored that record as a plain
JSONL file (QFIRE) and an in-memory hash chain (QUOKKAGUARD): an adversarial agent, a
compromised host process, or a privileged operator can silently rewrite, drop, or
reorder entries, defeating the very traceability the framework requires (HAARF C2).
We close this third zero-trust gap — after attested weights and an attested harness —
with a single tamper-evident log that unifies the gateway decision stream and the
harness mutation stream into one **blake3-chained, ed25519-signed,
externally-anchored, append-only** record, plus a streaming verifier that localizes
the first tampered entry. We introduce **TamperBench**, a labeled corpus of six
audit-tampering attack classes (TA1–TA6), and show the verifier detects **100% of
tampering (26/26)** and localizes point tampers at **100%**. The cryptographic cost
is small — **14.0 µs/entry (~71,400 entries/s/core)** — so the observed chained write
latency is dominated by per-entry `fsync`, the correct fail-closed durability
semantic; verification is linear at **~440,000 entries/s**.

## Threat model

Three adversary tiers, host untrusted (confidential-enclave model): (i) the agent,
(ii) a co-located process, (iii) a privileged operator with store access. Six attack
classes: **TA1** entry mutation · **TA2** deletion/truncation · **TA3** reordering ·
**TA4** forgery/backdating · **TA5** repudiation · **TA6** host-level rollback.

## System (`src/audit/`)

One append-only JSONL chain, four entry kinds (`header`/`decision`/`mutation`/`checkpoint`):

- **chain** — `this_hash = blake3(prefix bytes)` over the exact written bytes; body
  re-serialized before hashing (kills field-injection); fixed-length tail parsed from
  the end.
- **sign** — ed25519 per entry (`chained_signed`) or per-batch Merkle root
  (`chained_signed_batched`); key attestation-released in prod.
- **anchor** — every *k* entries a Merkle root is published to an external append-only
  sink (defeats TA6 rollback).
- **store** — single writer thread, **write-ahead fail-closed** (entry durable before
  the gateway call returns).
- **verify** — chain → signature → anchor walk; reports first-broken seq + tamper
  class; incremental Merkle keeps anchor checking *O(n log n)*; a pinned `--pubkey`
  forces signature checking.

CLI: `qfire audit verify | prove | head`. Unifies QFIRE's decision log and
QUOKKAGUARD's provenance ledger; prior `ProvenanceLog` API preserved.

## Results

| Experiment | Result | Hypothesis |
|---|---|---|
| **E1/E5** detection + localization | TDR **100% (26/26)**, localization **100% (20/20)**, integration test passes | H1 ✓ |
| **E2** write cost | compute-only **14.0 µs/entry (~71.4k/s)** meets ≥50k target; chained ~4.71 ms = per-entry-fsync durability tax (NVMe-class → 64–214 µs, meets <1 ms); signing within noise | H2 ✓ (dual-number), H4 ✓ |
| **E3** anchor cadence | window ≤ k at every cadence; storage **0.058% at k=1000** (5.84% → 0.006% across sweep) | H3 ✓ |
| **E4** verify scaling | linear **~440k entries/s** across 1e3–1e6 (no quadratic blowup); 1e6 verifies in **2.24 s** | scaling ✓ |

Detection diagnoses match the attacked mechanism: HashMismatch (TA1/TA4),
SequenceBreak (TA2-delete/TA3), RollbackVsAnchor (TA2-truncate/TA6).

## Security argument

Integrity reduces to blake3 collision-resistance; non-repudiation to ed25519
EUF-CMA (a property a shared MAC cannot give). Tiers (i)/(ii) cannot forge a
self-consistent chain without the key; tier (iii) with the key is still caught by
external anchors (TA6) and a pinned verifier key (re-key/downgrade). Sequence number,
not wall-clock, defines order.

## Honest limitations

- Full-file rewrite **with** the signing key is defended only by anchoring + a pinned
  verifier key, not the chain alone.
- Per-entry `fsync` makes chained writes ~4.7 ms on dev/APFS (the correct fail-closed
  semantic; <1 ms is NVMe-class) — reported as a dual number, never claimed as <1 ms
  on dev HW.
- 1e6-entry verify is 2.24 s single-core (linear, parallelizable).
- Signed external timestamps and HSM/KMS key management are future work.

## HAARF mapping

Primary owner of **C2** (end-to-end traceability, non-repudiable audit); supports C8
authorization-evidence by making every decision a signed, ordered, anchored record.

## Reproducibility

```bash
cargo build --release
python3 scripts/003-tamper-audit/e1_detection.py          # E1/E5
cargo bench --bench audit_write                            # E2
cargo bench --bench audit_verify                           # E4
python3 scripts/003-tamper-audit/e3_anchor_sweep.py \
    > results/003-tamper-audit/e3_anchor/e3_anchor_sweep.csv  # E3
python3 scripts/003-tamper-audit/make_figs.py              # figures
cd papers/003-tamper-audit && make paper                   # main.pdf
```

Seed 42 throughout; result artifacts under `results/003-tamper-audit/`. Design spec:
[`docs/superpowers/specs/2026-06-07-003-tamper-audit-design.md`](../../docs/superpowers/specs/2026-06-07-003-tamper-audit-design.md);
paper spec + per-experiment results docs: `docs/superpowers/specs/2026-06-08-003-*`.
License: Apache-2.0.

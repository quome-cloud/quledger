> **Paper 003 proposal — Tamper-evident audit & action provenance.** Imported 2026-06-07 from the local
> outline `P2` (`ongoing-papers/papers/02-tamper-evident-audit/`). Read with the
> [`ROADMAP.md`](../ROADMAP.md) deltas in mind: **monorepo** — features are `qfire`
> modules, not `haarf-*` crates or spin-out repos — and **confidential-enclave**
> production deployment, validated locally on Ollama via the OpenAI-compatible
> bridge. The threat model, hypotheses, experiments, datasets, and figures below
> are the pre-registered working plan; they are reconciled against the gateway as
> built at the feature-spec (stage 2) and paper-spec (stage 4) gates.

---

# Paper 2 — Tamper-Evident Action Provenance for Clinical AI Agents

**Crate:** `haarf-audit` · **New dataset:** HAARF-Audit-Adv · **Status:** outline

## Abstract

HAARF requires complete, structured audit of every agent action (C8.1.5, C8.4.3) and
end-to-end traceability (C2). But the published harness stores the audit log as an
in-memory Python list — an adversarial agent, a compromised host process, or a
malicious operator could silently rewrite or drop entries, defeating the very
traceability HAARF claims. We design and implement a **hash-chained, signed,
append-only audit log** (`haarf-audit`) that makes tampering *detectable* and actions
*non-repudiable*, with optional external anchoring for tamper-*evidence* against a
host-level adversary. We introduce **HAARF-Audit-Adv**, a benchmark of audit-tampering
attacks, and show the chained log detects 100% of post-hoc mutations at production
write latency, with a quantified storage/throughput cost.

## Stakeholders & expert-in-the-loop

To keep this work clinically grounded, safe, and credible, the following experts should
guide its design and co-author/review as experts-in-the-loop:

- **Applied cryptographer / security engineer** — to vet the hash-chain, signing, and
  anchoring constructions and the reductions to blake3 collision-resistance / ed25519
  EUF-CMA so the integrity claims hold under real adversaries.
- **Health-information-management (HIM) officer** — to confirm the audit schema captures
  what a clinical record-of-action must retain and aligns with retention/disclosure
  obligations for the medical record.
- **Medico-legal counsel** — to assess whether per-action signing and anchoring meet
  the evidentiary bar for non-repudiation (TA5) and admissibility in malpractice or
  regulatory proceedings.
- **Clinical quality & safety auditor** — to ensure the tamper-evident log supports the
  root-cause and incident reviews that quality teams actually run after an adverse event.
- **Frontline clinician (logged user)** — to surface how being non-repudiably logged
  affects trust, workflow, and willingness to use the agent, since their actions are the
  ones recorded.
- **Health-IT / EHR integration engineer** — to ground the write-ahead, fail-closed
  gateway path and attestation API in real EHR latency budgets and deployment constraints.
- **Regulatory / compliance lead** — to map the design to HIPAA audit-control, ONC, and
  FDA/SaMD expectations so the chain is defensible to a regulator, not just a researcher.

## Threat model

- **TA1 Entry mutation** — alter fields of a recorded action (e.g. change ordered drug
  or dose after the fact).
- **TA2 Entry deletion / truncation** — drop incriminating actions; truncate the tail.
- **TA3 Reordering** — change apparent sequence to fabricate a benign causal story.
- **TA4 Forgery / backdating** — insert fabricated entries with false timestamps.
- **TA5 Repudiation** — agent/operator denies having performed a recorded action.
- **TA6 Host-level rollback** — privileged attacker replaces the entire store with an
  earlier consistent snapshot (defeated only by *external anchoring*).

Adversary tiers: (i) the agent, (ii) a co-located process, (iii) a privileged operator
with DB access. We state which mechanism covers which tier (rollback ⇒ anchoring).

## Research questions

- **RQ1** Can a hash-chained signed log detect TA1–TA4 with zero missed detections?
- **RQ2** What is the marginal write latency / storage / throughput cost vs. a plain
  log, and is it within the gateway's p99 budget?
- **RQ3** What external-anchoring cadence defeats TA6 rollback at acceptable cost?
- **RQ4** Does per-action signing meaningfully raise non-repudiation (TA5) over a
  single chain MAC, and at what CPU cost?

## Hypotheses

- **H1** A blake3 hash chain detects 100% of TA1–TA4 mutations (tamper localizes to the
  first broken link). *(near-deterministic; the paper quantifies cost, not whether.)*
- **H2** Added write latency p99 < 1 ms (chain) / < 200 µs amortized batched signing;
  throughput ≥ 50k entries/s/core.
- **H3** Periodic Merkle-root anchoring every k entries detects TA6 with detection
  window ≤ k actions; storage overhead < 1% at k = 1000.
- **H4** Ed25519 per-action signatures add < X µs/entry (measured) and provide
  cryptographic non-repudiation that a shared MAC cannot.

## Experiments → figures

- **E1 Detection completeness (→ Fig 1):** generate logs, apply each tamper class from
  HAARF-Audit-Adv, run the verifier; confusion matrix / detection rate per TA class.
- **E2 Write cost (→ Fig 2):** `criterion` latency + throughput for {plain, chained,
  chained+signed, chained+signed+batched} vs. entry rate.
- **E3 Anchoring trade-off (→ Fig 3):** detection window vs. anchor cadence k vs. cost
  (storage + anchor-write latency); sweep k ∈ {10,100,1k,10k}.
- **E4 Scale (→ Fig 4):** verification time vs. log size (1e3…1e8 entries); show
  sub-linear with Merkle range proofs.
- **E5 Recovery/forensics (→ Fig 5):** given a tampered log, time + accuracy to
  localize the first compromised entry.
- **E6 Gateway overhead (→ shared Fig).**

## Datasets

**Public:**
- **MIMIC-IV** structure (schema/field realism for what an action record contains;
  credentialed) — or **Synthea** events as the open substitute for action streams.
- General append-only/transparency-log references (Certificate Transparency, Trillian)
  as *design* baselines, not data.

**New — HAARF-Audit-Adv (the contribution):**
- A generator that emits realistic clinical action streams (from Synthea encounters)
  in the HAARF audit schema, at configurable rates/durations.
- A labeled **tampering corpus**: for each base log, a family of mutated copies
  spanning TA1–TA6 with ground-truth (what changed, where), enabling precision/recall
  of *any* audit-integrity scheme — not just ours.
- Reference verifier + format spec so other audit designs can be benchmarked head-to-
  head. Apache-2.0, synthetic.

## Validation & statistics

- Detection completeness reported as exact rates (expected 100%) with the *one* failure
  mode analyzed (collision resistance assumption stated).
- Performance: `criterion` with CIs; report p50/p99/p999.
- Security argument: reduction to collision-resistance of blake3 + EUF-CMA of ed25519;
  explicitly bound what each adversary tier can/can't do.
- **Threats to validity:** clock trust (use monotonic + signed external timestamps),
  key management (HSM/KMS out of scope but discussed), sim action realism.

## Rust components (`haarf-audit`)

- **Chained record:** `entry_hash = blake3(prev_hash ‖ canonical(entry))`; entries are
  canonicalized (deterministic JSON/CBOR) before hashing.
- **Signing:** ed25519 per-entry (or batched Merkle-root signing for throughput);
  signer key per gateway instance, rotation supported.
- **Anchoring:** every k entries, publish the Merkle root to an external sink
  (append-only file on separate host, S3 object-lock, or a transparency log) → TA6.
- **Verifier:** `haarf-audit verify` walks the chain, checks signatures, validates
  anchors, and on failure reports the first broken index + diff.
- **Storage:** `sqlx` (SQLite/Postgres); write path is append-only with a UNIQUE
  monotonic sequence; reads via Merkle range proofs.

```rust
struct AuditEntry { seq: u64, ts: SignedTime, call: ToolCall, decision: Decision,
                    prev_hash: Hash, this_hash: Hash, sig: Signature }
```

## Server / proxy design

- Terminal layer in the gateway: **every** decision (Allow/Deny/Transform/Escalate) is
  recorded *before* the result returns to the agent (write-ahead, fail-closed for
  safety-critical tools).
- Async batched writer keeps the hot path fast; chain integrity maintained by a single
  writer task (no concurrent append races).
- Exposes a read-only attestation API: "prove action X at seq N occurred and is
  unaltered" (Merkle inclusion proof).

## Metrics

| Metric | Definition | Target |
|---|---|---|
| TDR | Tamper detection rate (TA1–TA4) | 100% |
| RAW | Rollback detection window | ≤ k actions |
| WLp99 | Added write latency p99 | < 1 ms |
| VTS | Verification time @ 1e6 entries | < 1 s |
| LOC | Localization accuracy (first bad entry) | 100% |

## Repo scaffold

```
haarf-audit/
├── crates/haarf-audit/             # chain + sign + anchor + verifier
├── dataset/haarf-audit-adv/        # stream generator + tamper corpus + labels
├── benches/                        # criterion suites for E2/E4
├── figures/
└── paper/
```

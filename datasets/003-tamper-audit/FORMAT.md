# TamperBench (datasets/003-tamper-audit) — format spec

Paper 003's labeled audit-tampering corpus. Apache-2.0, fully synthetic.

## Layout
- `streams/stream-<i>.jsonl` — generated clinical action streams (gen.py,
  seed 42). One JSON object per line; schema below. **Generated, gitignored.**
- `tampered/<class>-<j>.jsonl` — mutated chained logs (tamper.py). Gitignored.
- `labels.json` — ground truth: `{file, class, where}` per mutated log.
- This file + the two scripts in `scripts/003-tamper-audit/` are the committed
  artifacts; corpora are regenerated deterministically.

## Stream event schema
`{stream, event_id, ts_epoch, actor, patient_ref, action, detail, unit, decision}`
— `patient_ref` is always `synthetic-NNNN`; no real identifiers exist anywhere.

## Chained-log line format (the object under test)
`{"seq":N,"ts":"<rfc3339>","kind":"header|decision|mutation|checkpoint",
"body":{...},"prev_hash":"<64hex|GENESIS>","this_hash":"<64hex>","sig":"<128hex|>"}`
with `this_hash = blake3(line bytes from '{' through the prev_hash closing quote)`
and `sig = ed25519(this_hash hex bytes)`. Verifier reference:
`qfire audit verify`. See docs/superpowers/specs/2026-06-07-003-tamper-audit-design.md.

## Tamper classes
| class | mutation | expected detection |
|---|---|---|
| ta1_field_edit | edit one body field in place | HashMismatch at that seq |
| ta2_delete | remove one line | SequenceBreak |
| ta2_truncate | drop the tail | clean without anchors; RollbackVsAnchor with |
| ta3_reorder | swap adjacent lines | SequenceBreak |
| ta4_forge | insert edited duplicate (stale hash) | HashMismatch / ChainBreak |
| ta6_rollback | truncate + stale anchors | RollbackVsAnchor |

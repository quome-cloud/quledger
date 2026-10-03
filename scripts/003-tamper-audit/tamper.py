#!/usr/bin/env python3
"""TamperBench corpus builder (paper 003). Operates on any chained qfire audit log (e.g. produced by the E1 fixture exporter in tests/audit_tamper.rs or a live gateway run). Mutations (labels.json records ground truth): TA1 field-edit, TA2 delete/truncate, TA3 reorder, TA4 forge, TA6 rollback."""
import argparse
import json
import random
import shutil
from pathlib import Path

def mutate(lines, kind, rng):
    lines = list(lines)
    n = len(lines)
    if kind == "ta1_field_edit":
        i = rng.randrange(1, n)
        lines[i] = lines[i].replace('"allow"', '"block"', 1) if '"allow"' in lines[i] \
            else lines[i].replace("5", "9", 1)
        return lines, {"line": i}
    if kind == "ta2_delete":
        i = rng.randrange(1, n)
        del lines[i]
        return lines, {"line": i}
    if kind == "ta2_truncate":
        keep = rng.randrange(2, n)
        return lines[:keep], {"kept": keep}
    if kind == "ta3_reorder":
        i = rng.randrange(1, n - 1)
        lines[i], lines[i + 1] = lines[i + 1], lines[i]
        return lines, {"lines": [i, i + 1]}
    if kind == "ta4_forge":
        i = rng.randrange(1, n)
        lines.insert(i, lines[i].replace('"seq":', '"forged":true,"seq":', 1))
        return lines, {"line": i}
    raise ValueError(kind)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="a clean chained log (audit.jsonl)")
    ap.add_argument("--anchors", help="matching anchors file (enables ta6_rollback)")
    ap.add_argument("--out", default="datasets/003-tamper-audit/tampered")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--per-class", type=int, default=5)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = Path(args.log).read_text().splitlines()
    labels = []
    classes = ["ta1_field_edit", "ta2_delete", "ta2_truncate", "ta3_reorder", "ta4_forge"]
    for cls in classes:
        for j in range(args.per_class):
            mutated, where = mutate(base, cls, rng)
            name = f"{cls}-{j}.jsonl"
            (out / name).write_text("\n".join(mutated) + "\n")
            labels.append({"file": name, "class": cls, "where": where})
    if args.anchors:
        keep = max(2, len(base) // 2)
        name = "ta6_rollback-0.jsonl"
        (out / name).write_text("\n".join(base[:keep]) + "\n")
        shutil.copy(args.anchors, out / "ta6_rollback-0.anchors.jsonl")
        labels.append({"file": name, "class": "ta6_rollback",
                       "where": {"kept": keep}, "anchors": "ta6_rollback-0.anchors.jsonl"})
    (out.parent / "labels.json").write_text(json.dumps(labels, indent=2) + "\n")
    print(f"wrote {len(labels)} tampered logs + labels.json")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""TamperBench stream generator (paper 003). Deterministic (seed 42).

Emits synthetic clinical action streams — Synthea-shaped encounter/order/
dispense/administer events, NO PHI — as JSONL bodies, one per line, to be fed
through the Rust writer (`qfire`-side) or consumed directly by tamper.py's
chain builder. Output: datasets/003-tamper-audit/streams/stream-<i>.jsonl
"""
import argparse
import json
import random
from pathlib import Path

ACTIONS = ["order_medication", "dispense", "administer", "order_lab", "review_result", "triage"]
DRUGS = ["metformin 500mg", "lisinopril 10mg", "insulin glargine 10u", "amoxicillin 250mg",
         "heparin 5000u", "warfarin 2mg"]
UNITS = ["icu", "ed", "med-surg", "outpatient"]

def gen_stream(rng: random.Random, n: int, stream_id: int):
    t = 1_700_000_000
    for seq in range(n):
        t += rng.randint(1, 300)
        yield {
            "stream": stream_id,
            "event_id": f"s{stream_id}-e{seq}",
            "ts_epoch": t,
            "actor": f"agent-{rng.randint(1, 3)}",
            "patient_ref": f"synthetic-{rng.randint(1000, 9999)}",
            "action": rng.choice(ACTIONS),
            "detail": rng.choice(DRUGS),
            "unit": rng.choice(UNITS),
            "decision": rng.choices(["allow", "block", "escalate"], weights=[88, 8, 4])[0],
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="datasets/003-tamper-audit/streams")
    ap.add_argument("--streams", type=int, default=10)
    ap.add_argument("--events", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    for i in range(args.streams):
        p = out / f"stream-{i}.jsonl"
        with p.open("w") as f:
            for ev in gen_stream(rng, args.events, i):
                f.write(json.dumps(ev, sort_keys=True) + "\n")
        print(f"wrote {p}")

if __name__ == "__main__":
    main()

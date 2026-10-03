#!/usr/bin/env python3
"""E3 (paper 003): anchor cadence k vs detection window vs storage cost.

Operates on any chained qfire audit log (e.g. produced by the E1 fixture
exporter in tests/audit_tamper.rs or a live gateway run).

For each k in {10, 100, 1000, 10000}: builds a clean chained log of N entries
with anchoring every k (via the Rust fixture exporter), truncates it at a
random point past the first anchor, and records (k, anchors_emitted,
anchor_file_bytes, detection_window = entries_since_last_anchor, detected).
Output: CSV on stdout -> results/003-tamper-audit/e3_anchor_sweep.csv
"""
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

N = 20_000
KS = [10, 100, 1000, 10000]

# Resolve the repo root (two levels up from scripts/003-tamper-audit/)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def main():
    rng = random.Random(42)
    rows = []
    header = ["k", "entries", "anchors", "anchor_bytes", "cut_at", "window", "detected"]

    for k in KS:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {**os.environ, "TB_OUT": str(d), "TB_N": str(N), "TB_K": str(k)}
            result = subprocess.run(
                [
                    "cargo", "test", "--quiet", "--release",
                    "--test", "audit_tamper",
                    "--", "--ignored", "--exact", "export_fixture_param",
                ],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            if result.returncode != 0:
                print(
                    f"[E3] cargo test failed for k={k}:\n"
                    f"  stdout: {result.stdout.strip()}\n"
                    f"  stderr: {result.stderr.strip()}",
                    file=sys.stderr,
                )
                rows.append([k, N, "ERR", "ERR", "ERR", "ERR", False])
                continue

            log = d / "audit.jsonl"
            anchors_path = d / "anchors.jsonl"

            if not log.exists() or not anchors_path.exists():
                print(f"[E3] missing output files for k={k}", file=sys.stderr)
                rows.append([k, N, "ERR", "ERR", "ERR", "ERR", False])
                continue

            lines = log.read_text().splitlines()
            raw_anchors = anchors_path.read_text().splitlines()
            anchors = [json.loads(l) for l in raw_anchors if l.strip()]

            if len(anchors) == 0:
                print(f"[E3] no anchors emitted for k={k}", file=sys.stderr)
                rows.append([k, N, 0, 0, "ERR", "ERR", False])
                continue

            # Truncate past the first anchor so that at least one anchor is
            # violated when we pass the stale anchors file.
            min_cut = k + 1  # at least one full anchor window written
            if min_cut >= len(lines):
                min_cut = len(lines) // 2 + 1
            cut = rng.randrange(min_cut, len(lines))

            log.write_text("\n".join(lines[:cut]) + "\n")

            eligible = [a["seq"] for a in anchors if a["seq"] < cut - 1]
            last_anchor_seq = max(eligible) if eligible else -1
            window = (cut - 1) - last_anchor_seq if last_anchor_seq >= 0 else cut

            anchor_bytes = anchors_path.stat().st_size

            r = subprocess.run(
                [
                    str(REPO_ROOT / "target" / "release" / "qfire"),
                    "audit", "verify",
                    "--log", str(log),
                    "--anchors", str(anchors_path),
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            if r.returncode not in (0, 2):
                print(
                    f"[E3] verify subprocess failed for k={k} (returncode {r.returncode}):\n"
                    f"  stderr: {r.stderr.strip()}",
                    file=sys.stderr,
                )
                rows.append([k, N, len(anchors), anchor_bytes, cut, window, "ERR"])
                continue
            detected = r.returncode == 2
            rows.append([k, N, len(anchors), anchor_bytes, cut, window, detected])

    # Write CSV to stdout
    w = csv.writer(sys.stdout)
    w.writerow(header)
    for row in rows:
        w.writerow(row)

    # Also persist to results/
    out_dir = REPO_ROOT / "results" / "003-tamper-audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "e3_anchor_sweep.csv"
    with out_csv.open("w", newline="") as f:
        w2 = csv.writer(f)
        w2.writerow(header)
        for row in rows:
            w2.writerow(row)
    print(f"[E3] results written to {out_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()

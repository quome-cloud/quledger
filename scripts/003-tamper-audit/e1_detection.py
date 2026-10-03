#!/usr/bin/env python3
"""E1/E5 (paper 003) detection-completeness driver.

Builds a clean signed+anchored chained log (via the #[ignore] Rust fixture
exporter), applies every TamperBench mutation class (tamper.py), runs the real
`qfire audit verify` CLI over each tampered copy, and records the detection
matrix to results/003-tamper-audit/e1_detection/summary.json.

Detection = verify exits 2 (tampered) with report.ok == False. Localization is
recorded as report.first_bad_seq; for the point-tamper class ta1_field_edit the
expected seq is the mutated line index, so localization is scored there. The
authoritative 100%-detection + exact-localization proof across ALL classes is
the Rust integration test (tests/audit_tamper.rs); this driver produces the
per-class figure data through the end-to-end CLI path.

Deterministic (seed 42). No LLM / no network / no paid keys.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QFIRE = REPO_ROOT / "target" / "release" / "qfire"
OUT_DIR = REPO_ROOT / "results" / "003-tamper-audit" / "e1_detection"
N = 200          # entries in the clean fixture
K = 50           # anchor cadence
PER_CLASS = 5    # mutated copies per tamper class


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, **kw)


def expected_seq(cls, where):
    """Ground-truth first tampered seq for point-tamper classes, else None.
    File line index == seq (header is line 0 / seq 0)."""
    if cls in ("ta1_field_edit", "ta2_delete", "ta4_forge"):
        return where.get("line")
    if cls == "ta3_reorder":
        return (where.get("lines") or [None])[0]
    return None  # truncation / rollback have no single tamper point


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fixture = OUT_DIR / "fixture"
    tampered = OUT_DIR / "tampered"

    # 1. Build a clean signed+anchored log via the Rust fixture exporter.
    #    QFIRE_AUDIT_FIXED_TS pins entry timestamps so the fixture is byte-identical across runs;
    #    without it the log uses the wall clock and tamper *localization* is non-deterministic even
    #    under the fixed tamper seed below.
    env = {**os.environ, "TB_OUT": str(fixture), "TB_N": str(N), "TB_K": str(K),
           "QFIRE_AUDIT_FIXED_TS": "2026-01-01T00:00:00+00:00",
           "QFIRE_AUDIT_FIXED_KEY": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"}
    r = run(
        ["cargo", "test", "--release", "--quiet", "--test", "audit_tamper",
         "--", "--ignored", "--exact", "export_fixture_param"],
        env=env,
    )
    if r.returncode != 0:
        print(f"[E1] fixture export failed:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    log = fixture / "audit.jsonl"
    anchors = fixture / "anchors.jsonl"
    if not log.exists() or not anchors.exists():
        print(f"[E1] fixture missing log/anchors in {fixture}", file=sys.stderr)
        sys.exit(1)

    # 2. Apply the labeled tamper corpus.
    r = run(
        ["python3", "scripts/003-tamper-audit/tamper.py",
         "--log", str(log), "--anchors", str(anchors),
         "--out", str(tampered), "--per-class", str(PER_CLASS), "--seed", "42"],
    )
    if r.returncode != 0:
        print(f"[E1] tamper.py failed:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    labels = json.loads((tampered.parent / "labels.json").read_text())

    # 3. Verify each tampered log via the real CLI (always pass anchors so the
    #    truncation/rollback classes are detectable; chain breaks fire first for
    #    the point-tamper classes, so anchors are harmless there).
    per_class = {}
    rows = []
    loc_total = loc_ok = 0
    for item in labels:
        cls, where = item["class"], item["where"]
        f = tampered / item["file"]
        cmd = [str(QFIRE), "audit", "verify", "--log", str(f), "--anchors", str(anchors)]
        vr = run(cmd)
        if vr.returncode not in (0, 2):
            print(f"[E1] verify error rc={vr.returncode} on {f.name}:\n{vr.stderr}", file=sys.stderr)
            sys.exit(1)
        try:
            report = json.loads(vr.stdout)
        except json.JSONDecodeError:
            print(f"[E1] verify produced non-JSON on {f.name}:\n{vr.stdout}", file=sys.stderr)
            sys.exit(1)
        detected = (vr.returncode == 2) and (report.get("ok") is False)
        fbs = report.get("first_bad_seq")
        exp = expected_seq(cls, where)
        localized = None
        if exp is not None and detected:
            localized = (fbs == exp)
            loc_total += 1
            loc_ok += int(localized)

        agg = per_class.setdefault(cls, {"n": 0, "detected": 0, "classes": {}})
        agg["n"] += 1
        agg["detected"] += int(detected)
        rc = report.get("class")
        agg["classes"][rc] = agg["classes"].get(rc, 0) + 1
        rows.append({
            "file": item["file"], "tamper_class": cls, "detected": detected,
            "verifier_class": rc, "first_bad_seq": fbs, "expected_seq": exp,
            "localized": localized,
        })

    total = sum(c["n"] for c in per_class.values())
    detected_total = sum(c["detected"] for c in per_class.values())
    tdr = detected_total / total if total else 0.0
    loc = loc_ok / loc_total if loc_total else None

    # 4. Cross-check against the authoritative Rust integration test.
    rt = run(["cargo", "test", "--release", "--quiet", "--test", "audit_tamper",
              "--", "--exact", "e1_e5_all_tamper_classes_detected_and_localized"])
    rust_test_passed = rt.returncode == 0

    summary = {
        "experiment": "E1/E5 detection completeness + localization",
        "fixture": {"entries": N, "anchor_every": K, "per_class": PER_CLASS},
        "TDR": tdr,
        "detected": detected_total,
        "total": total,
        "LOC_point_classes": loc,
        "LOC_scored": loc_total,
        "per_class": {
            k: {"TDR": v["detected"] / v["n"], "n": v["n"],
                "verifier_classes": v["classes"]}
            for k, v in sorted(per_class.items())
        },
        "rust_integration_test": {
            "name": "e1_e5_all_tamper_classes_detected_and_localized",
            "passed": rust_test_passed,
            "note": "authoritative 100% detection + exact localization across all classes",
        },
        "rows": rows,
        "seed": 42,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[E1] TDR={tdr:.3f} ({detected_total}/{total}); "
          f"LOC(point)={loc} ({loc_ok}/{loc_total}); "
          f"rust_test_passed={rust_test_passed}")
    print(f"[E1] -> {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()

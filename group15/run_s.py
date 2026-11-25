"""Run S on paired targets (Categories by default), without reading answer labels."""

import argparse
import json
import subprocess
import sys
from collections import Counter

from analysis_common import load_inputs, report_metadata
from structural import analyse
from pair_dataset import add_dataset_argument
from validate import BUILD, ROOT, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_dataset_argument(parser)
    args = parser.parse_args(argv)
    build = BUILD / args.dataset
    output = build / "s-results.json"
    # A failed rerun must not leave an earlier success looking current.
    output.unlink(missing_ok=True)
    inputs, disassembly = load_inputs(build)
    results = analyse(inputs, disassembly)
    summary = {value: 0 for value in ("unreachable", "unknown")}
    summary.update(Counter(result["verdict"] for result in results))
    report = {
        **report_metadata(inputs, build),
        "analysis": "S",
        "backend": "javap paired control-flow graph" if inputs["schema_version"] == 2
                   else "javap via group15.validate.parse_disassembly",
        "runner_sha256": digest(ROOT / "group15" / "run_s.py"),
        "structural_sha256": digest(ROOT / "solutions" / "syntactic" / "src" / "structural.py"),
        "summary": summary,
        "queries": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        reason = f";reason={result['reason']}" if "reason" in result else ""
        print(f"{result['id']};{result['verdict']}{reason}")
    print(f"S: {len(results)} queries; {summary['unreachable']} unreachable; "
          f"{summary['unknown']} unknown; {summary.get('unsupported', 0)} unsupported")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)

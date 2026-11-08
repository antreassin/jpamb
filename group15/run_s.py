"""Run S on the validated Group 15 queries, without reading their answer labels."""

import json
import subprocess
import sys
from collections import Counter

from analysis_common import (
    load_inputs,
    prepare_queries,
    query_metadata,
    report_metadata,
)
from structural import verdict
from validate import BUILD, ROOT, digest


def analyse(inputs: dict, disassembly: str) -> list[dict]:
    return [
        {
            **query_metadata(query, method),
            "verdict": verdict(instructions, method["target_instruction_index"]),
        }
        for query, method, instructions in prepare_queries(inputs, disassembly)
    ]


def main():
    output = BUILD / "s-results.json"
    # A failed rerun must not leave an earlier success looking current.
    output.unlink(missing_ok=True)
    inputs, disassembly = load_inputs(BUILD)
    results = analyse(inputs, disassembly)
    summary = {value: 0 for value in ("unreachable", "unknown")}
    summary.update(Counter(result["verdict"] for result in results))
    report = {
        **report_metadata(inputs, BUILD),
        "analysis": "S",
        "backend": "javap via group15.validate.parse_disassembly",
        "runner_sha256": digest(ROOT / "group15" / "run_s.py"),
        "structural_sha256": digest(ROOT / "solutions" / "syntactic" / "src" / "structural.py"),
        "summary": summary,
        "queries": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['id']};{result['verdict']}")
    print(f"S: {len(results)} queries; {summary['unreachable']} unreachable; {summary['unknown']} unknown")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)

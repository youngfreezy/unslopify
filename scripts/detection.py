#!/usr/bin/env python3
"""Detection eval: does the audit separate LLM output from human prose?

Calibration (calibrate.py) measures false positives only. This script
measures both sides at once:

- true-positive rate: share of the LLM-written fixtures in
  fixtures/llm/ that the audit fails (they are genuine model output,
  written by an LLM for this repo and labeled as such in each file)
- false-positive rate: share of pre-LLM human sources (same five as
  calibrate.py) that the audit fails on NAMED types alone

  python scripts/detection.py
  python scripts/detection.py --add path/to/your-llm-sample.md

Add your own labeled samples to fixtures/llm/ (model output) and
fixtures/human/ (text you wrote yourself) to eval on your material;
the built-in human side uses the public-domain calibration sources.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibrate import SOURCES, excerpt, fetch  # noqa: E402
from unslopify.audit import audit_text  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


MECHANICS = {"dash", "curly-quotes", "sentence-length", "semicolon-density", "repeated-ngram"}


def named_fail(text: str, source: str) -> tuple[bool, int]:
    """Verdict on named types alone (mechanics disabled): hard findings
    fail, soft types fail past their length-scaled thresholds. This is
    the claim under eval: 'reads as generated', not 'breaks the style
    gates'."""
    report = audit_text(text, source=source, disable=MECHANICS)
    return report.verdict == "fail", len(report.findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--add", action="append", default=[], help="extra LLM sample file(s)")
    parser.add_argument("--words", type=int, default=5000)
    args = parser.parse_args()

    llm_files = sorted((FIXTURES / "llm").glob("*.md")) + [Path(p) for p in args.add]
    human_files = sorted((FIXTURES / "human").glob("*.md"))

    print("LLM-written samples (should fail):")
    tp = 0
    for f in llm_files:
        failed, n = named_fail(f.read_text(encoding="utf-8"), f.name)
        tp += failed
        print(f"  {'FAIL' if failed else 'pass'}  {f.name}  ({n} named findings)")

    print()
    print("Human prose (should pass on named types):")
    fp = 0
    total_human = 0
    for name, url in SOURCES:
        try:
            sample = excerpt(fetch(url), args.words)
        except OSError as exc:
            print(f"  skip {name}: {exc}", file=sys.stderr)
            continue
        total_human += 1
        failed, n = named_fail(sample, name)
        fp += failed
        print(f"  {'FAIL' if failed else 'pass'}  {name}  ({n} named findings)")
    for f in human_files:
        total_human += 1
        failed, n = named_fail(f.read_text(encoding="utf-8"), f.name)
        fp += failed
        print(f"  {'FAIL' if failed else 'pass'}  {f.name}  ({n} named findings)")

    print()
    if llm_files:
        print(f"detection rate: {tp}/{len(llm_files)} LLM samples flagged")
    if total_human:
        print(f"false-positive rate: {fp}/{total_human} human sources flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())

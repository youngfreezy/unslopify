#!/usr/bin/env python3
"""Generate RULES.md from the rubric, one entry per named type.

The catalog is the shareable artifact: every rule with its id, category,
severity, one-line definition, and an invented before/after pair.

  python scripts/rules_md.py > RULES.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unslopify.rubric import CATEGORIES, TYPES  # noqa: E402


def main() -> int:
    out = []
    out.append("# unslopify rule catalog")
    out.append("")
    out.append(
        "<!-- unslopify:disable=repeated-ngram : a catalog repeats its own"
        " severity labels; that is structure, not prose stamps -->"
    )
    out.append("")
    out.append(
        "Generated from `src/unslopify/rubric.py` by `scripts/rules_md.py`; "
        "edit the rubric, not this file. Every definition and example is "
        "original to this project. Hard rules fail an audit on one hit. "
        "Soft rules fail past a threshold that scales with document length. "
        "Rules marked judgment have no regex and belong to the agent pass."
    )
    out.append("")
    for cat_id, cat_name in CATEGORIES.items():
        out.append(f"## {cat_name}")
        out.append("")
        for t in TYPES:
            if t.category != cat_id:
                continue
            if not t.patterns:
                sev = "judgment"
            elif t.severity == "hard":
                sev = "hard"
            else:
                sev = f"soft, threshold {t.threshold} per 1,000 words"
            out.append(f"### `{t.id}` ({sev})")
            out.append("")
            out.append(t.definition)
            out.append("")
            out.append(f'Before: "{t.example_bad}"')
            out.append("")
            out.append(f'After: "{t.example_fix}"')
            out.append("")
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

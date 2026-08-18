"""unslopify CLI.

  unslopify DRAFT.md              audit, print findings, exit 1 on fail
  unslopify - < draft.txt         audit stdin
  unslopify DRAFT.md --json      full Audit report as JSON
  unslopify DRAFT.md --fix       safe mechanical fixes to stdout
  unslopify DRAFT.md --brief     rewrite instructions for a model or human
  unslopify DRAFT.md --bank      also check the cross-document phrase bank
  unslopify commit DRAFT.md --id blog-2026-08   bank a finished document
  unslopify types                list the rubric

Exit codes: 0 pass, 1 findings, 2 usage or IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import audit_text
from .models import Draft
from .phrasebank import bank_path, commit, cross_check
from .rewrite import build_brief, mechanical_rewrite
from .rubric import CATEGORIES, TYPES


def _read_input(target: str) -> tuple[str, str]:
    if target == "-":
        return sys.stdin.read(), "stdin"
    path = Path(target)
    if not path.is_file():
        print(f"error: no such file: {target}", file=sys.stderr)
        raise SystemExit(2)
    return path.read_text(encoding="utf-8"), str(path)


def _print_types() -> None:
    for cat_id, cat_name in CATEGORIES.items():
        print(f"{cat_name} ({cat_id})")
        for t in TYPES:
            if t.category != cat_id:
                continue
            sev = "" if t.severity == "hard" else f" [soft, threshold {t.threshold}]"
            print(f"  {t.id}{sev}")
            print(f"      {t.definition}")
        print()


def _print_human(audit, bank_fails: list[str]) -> None:
    if not audit.findings and not audit.mechanics and not bank_fails:
        print(f"PASS {audit.source} ({audit.word_count} words, 0 findings)")
        return
    for f in audit.findings:
        print(f"{audit.source}:{f.line}: [{f.type_id}] {f.span!r}")
        print(f"    {f.why}")
    for m in audit.mechanics:
        loc = f"{audit.source}:{m.line}" if m.line else f"{audit.source}"
        print(f"{loc}: [{m.check}] {m.detail}")
    for msg in bank_fails:
        print(f"{audit.source}: [phrase-bank] {msg}")
    print()
    verdict = audit.verdict.upper()
    if bank_fails:
        verdict = "FAIL"
    print(
        f"{verdict} {audit.source}: {len(audit.findings)} findings, "
        f"{len(audit.mechanics)} mechanics, {len(bank_fails)} bank"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="unslopify",
        description="Audit text for AI-writing patterns. Exit 0 pass, 1 findings.",
    )
    parser.add_argument("target", nargs="?", help="file path, '-' for stdin, or 'types' / 'commit'")
    parser.add_argument("extra", nargs="?", help="file path when target is 'commit'")
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument("--fix", action="store_true", help="apply safe mechanical fixes, print result to stdout")
    parser.add_argument("--brief", action="store_true", help="print rewrite instructions instead of findings")
    parser.add_argument("--bank", action="store_true", help="also check the cross-document phrase bank")
    parser.add_argument("--id", dest="doc_id", help="document id (for commit, or to skip self-overlap with --bank)")
    parser.add_argument("--ignore-quotes", action="store_true", help="skip text inside double quotes")
    parser.add_argument("--max-sentence-words", type=int, default=36)
    parser.add_argument("--version", action="version", version=f"unslopify {__version__}")
    args = parser.parse_args(argv)

    if args.target == "types":
        _print_types()
        return 0

    if args.target == "commit":
        if not args.extra or not args.doc_id:
            print("usage: unslopify commit FILE --id DOC_ID", file=sys.stderr)
            return 2
        text, _ = _read_input(args.extra)
        path = commit(text, args.doc_id)
        print(f"banked {args.doc_id!r} in {path}")
        return 0

    if not args.target:
        parser.print_help()
        return 2

    text, source = _read_input(args.target)
    draft = Draft(text=text, source=source)

    if args.fix:
        rw = mechanical_rewrite(draft)
        sys.stdout.write(rw.rewritten)
        for note in rw.applied_fixes:
            print(f"fixed: {note}", file=sys.stderr)
        after = rw.audit_after
        if after and after.verdict == "fail":
            print(
                f"note: {len(after.fail_reasons)} problem(s) remain that need a "
                "real rewrite; run --brief for instructions",
                file=sys.stderr,
            )
        return 0

    audit = audit_text(
        text,
        source=source,
        ignore_quoted=args.ignore_quotes,
        max_sentence_words=args.max_sentence_words,
    )
    bank_fails = cross_check(text, doc_id=args.doc_id) if args.bank else []
    if bank_fails:
        audit.verdict = "fail"
        audit.fail_reasons.extend(bank_fails)

    if args.brief:
        print(build_brief(audit))
    elif args.json:
        print(audit.model_dump_json(indent=2))
    else:
        _print_human(audit, bank_fails)

    return 0 if audit.verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

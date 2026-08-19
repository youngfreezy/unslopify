"""unslopify CLI.

  unslopify DRAFT.md              audit, print findings, exit 1 on fail
  unslopify a.md b.md docs/       audit many files; directories recurse
  unslopify - < draft.txt         audit stdin ('-' optional when piped)
  unslopify DRAFT.md --json       full Audit report(s) as JSON
  unslopify DRAFT.md --fix        safe mechanical fixes to stdout
  unslopify DRAFT.md --fix -w     apply the fixes in place
  unslopify DRAFT.md --brief      rewrite instructions for a model or human
  unslopify DRAFT.md --bank       also check the cross-document phrase bank
  unslopify commit DRAFT.md --id blog-2026-08   bank a finished document
  unslopify types                 list the rubric

Exit codes: 0 pass, 1 findings in any target, 2 usage or IO error.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # 3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None

from . import __version__
from .audit import audit_text
from .models import Draft
from .phrasebank import commit, cross_check
from .rewrite import build_brief, mechanical_rewrite
from .rubric import CATEGORIES, TYPES

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}


def _load_config() -> dict:
    """[tool.unslopify] from the nearest pyproject.toml at or above cwd.
    Keys: disable (list of type ids / checks), exclude (glob list),
    max-sentence-words (int)."""
    if tomllib is None:  # no TOML parser available; config is inert
        return {}
    d = Path.cwd()
    for parent in [d, *d.parents]:
        pp = parent / "pyproject.toml"
        if pp.is_file():
            try:
                data = tomllib.loads(pp.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                return {}
            return data.get("tool", {}).get("unslopify", {}) or {}
    return {}


def _excluded(path: Path, patterns: list[str]) -> bool:
    s = str(path)
    return any(fnmatch.fnmatch(s, pat) or fnmatch.fnmatch(path.name, pat) for pat in patterns)


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


class _Style:
    def __init__(self, on: bool):
        self.red = "\033[31m" if on else ""
        self.green = "\033[32m" if on else ""
        self.yellow = "\033[33m" if on else ""
        self.dim = "\033[2m" if on else ""
        self.off = "\033[0m" if on else ""


def _expand_targets(targets: list[str], exclude: list[str]) -> tuple[list[Path], list[str]]:
    """Resolve files and directories to a file list. Returns (files, errors)."""
    files: list[Path] = []
    errors: list[str] = []
    for t in targets:
        p = Path(t)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            found = sorted(
                q
                for q in p.rglob("*")
                if q.is_file()
                and q.suffix.lower() in TEXT_SUFFIXES
                and not _excluded(q, exclude)
            )
            if found:
                files.extend(found)
            else:
                errors.append(f"{t}: directory has no text files ({'/'.join(sorted(TEXT_SUFFIXES))})")
        else:
            errors.append(f"{t}: no such file or directory")
    return [f for f in files if not _excluded(f, exclude)], errors


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


def _print_human(audit, bank_fails: list[str], style: _Style) -> None:
    if not audit.findings and not audit.mechanics and not bank_fails:
        print(
            f"{style.green}PASS{style.off} {audit.source} "
            f"({audit.word_count} words, 0 findings)"
        )
        return
    for f in audit.findings:
        print(
            f"{audit.source}:{f.line}: "
            f"{style.yellow}[{f.type_id}]{style.off} {f.span!r}"
        )
        print(f"    {style.dim}{f.why}{style.off}")
    for m in audit.mechanics:
        loc = f"{audit.source}:{m.line}" if m.line else f"{audit.source}"
        print(f"{loc}: {style.yellow}[{m.check}]{style.off} {m.detail}")
    for msg in bank_fails:
        print(f"{audit.source}: {style.yellow}[phrase-bank]{style.off} {msg}")
    verdict = audit.verdict.upper()
    color = style.red if verdict == "FAIL" or bank_fails else style.green
    if bank_fails:
        verdict = "FAIL"
    print(
        f"{color}{verdict}{style.off} {audit.source}: "
        f"{len(audit.findings)} findings, {len(audit.mechanics)} mechanics, "
        f"{len(bank_fails)} bank"
    )


def _run_one(
    path: Path | None,
    text: str,
    source: str,
    args,
    style: _Style,
    disable: set[str],
    json_out: list | None = None,
) -> int:
    """Audit or fix one input. Returns 0 pass, 1 findings."""
    draft = Draft(text=text, source=source)

    if args.fix:
        rw = mechanical_rewrite(draft)
        if args.write and path is not None:
            if rw.rewritten != text:
                path.write_text(rw.rewritten, encoding="utf-8")
                print(f"fixed {source} ({len(rw.events)} edits)", file=sys.stderr)
            else:
                print(f"clean {source}", file=sys.stderr)
        else:
            sys.stdout.write(rw.rewritten)
            for e in rw.events:
                print(f"fixed line {e.line}: {e.rule_id}", file=sys.stderr)
        after = rw.audit_after
        if after and after.verdict == "fail":
            print(
                f"note: {source}: {len(after.fail_reasons)} problem(s) remain that "
                "need a real rewrite; run --brief for instructions",
                file=sys.stderr,
            )
            # a fix that leaves problems is not a pass; gates need to see it
            return 1
        return 0

    audit = audit_text(
        text,
        source=source,
        ignore_quoted=args.ignore_quotes,
        max_sentence_words=args.max_sentence_words,
        disable=disable,
        level=args.level,
    )
    bank_fails = cross_check(text, doc_id=args.doc_id) if args.bank else []
    if bank_fails:
        audit.verdict = "fail"
        audit.fail_reasons.extend(bank_fails)

    if args.brief:
        if path is not None:
            print(f"# {source}")
        print(build_brief(audit))
    elif args.json:
        if json_out is None:
            print(audit.model_dump_json(indent=2))
        else:
            json_out.append(audit)
    else:
        _print_human(audit, bank_fails, style)

    return 0 if audit.verdict == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="unslopify",
        description="Audit text for AI-writing patterns. Exit 0 pass, 1 findings.",
        epilog=(
            "examples:\n"
            "  unslopify draft.md               audit one file\n"
            "  unslopify docs/ README.md        audit a tree plus a file\n"
            "  cat draft.txt | unslopify        audit stdin\n"
            "  unslopify draft.md --fix -w      apply safe fixes in place\n"
            "  unslopify types                  print the rubric\n"
            "  unslopify commit draft.md --id blog-08   bank a finished doc"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="files or directories ('-' or piped stdin also work); or 'types' / 'commit'",
    )
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument("--fix", action="store_true", help="apply safe mechanical fixes (stdout by default)")
    parser.add_argument("-w", "--write", action="store_true", help="with --fix: edit files in place")
    parser.add_argument("--brief", action="store_true", help="print rewrite instructions instead of findings")
    parser.add_argument("--bank", action="store_true", help="also check the cross-document phrase bank")
    parser.add_argument("--id", dest="doc_id", help="document id (for commit, or to skip self-overlap with --bank)")
    parser.add_argument("--ignore-quotes", action="store_true", help="skip text inside double quotes")
    parser.add_argument(
        "--level",
        choices=["strict", "standard", "relaxed"],
        default=None,
        help="sensitivity: strict halves soft-type allowances, relaxed doubles them",
    )
    parser.add_argument("--max-sentence-words", type=int, default=36)
    parser.add_argument("--version", action="version", version=f"unslopify {__version__}")
    args = parser.parse_args(argv)
    style = _Style(_color_enabled() and not args.json and not args.brief)

    config = _load_config()
    disable = set(config.get("disable", []))
    exclude = [str(x) for x in config.get("exclude", [])]
    if args.max_sentence_words == 36 and "max-sentence-words" in config:
        args.max_sentence_words = int(config["max-sentence-words"])
    if args.level is None:
        args.level = str(config.get("level", "standard"))

    targets = list(args.targets)
    if args.write and not args.fix:
        print("error: -w/--write requires --fix", file=sys.stderr)
        return 2

    # subcommands only when no file of that name exists, so a repo
    # containing a file literally named 'types' cannot shadow the audit
    if targets and targets[0] == "types" and not Path("types").exists():
        _print_types()
        return 0

    if targets and targets[0] == "commit" and not Path("commit").exists():
        if len(targets) < 2 or not args.doc_id:
            print("usage: unslopify commit FILE --id DOC_ID", file=sys.stderr)
            return 2
        rc = 0
        for name in targets[1:]:
            p = Path(name)
            if not p.is_file():
                print(f"error: no such file: {name}", file=sys.stderr)
                return 2
            doc_id = args.doc_id if len(targets) == 2 else f"{args.doc_id}/{p.stem}"
            path = commit(p.read_text(encoding="utf-8"), doc_id)
            print(f"banked {doc_id!r} in {path}")
        return rc

    # stdin: explicit '-', or piped input with no targets
    use_stdin = targets == ["-"] or (not targets and not sys.stdin.isatty())
    if use_stdin:
        return _run_one(None, sys.stdin.read(), "stdin", args, style, disable)

    if not targets:
        parser.print_help()
        return 2

    files, errors = _expand_targets(targets, exclude)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 2

    json_out: list | None = [] if args.json and len(files) > 1 else None
    worst = 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"error: {p}: not valid UTF-8", file=sys.stderr)
            return 2
        rc = _run_one(p, text, str(p), args, style, disable, json_out)
        worst = max(worst, rc)
    if json_out is not None:
        print("[" + ",\n".join(a.model_dump_json(indent=2) for a in json_out) + "]")
    if len(files) > 1 and not args.json and not args.brief and not args.fix:
        word = "pass" if worst == 0 else "fail"
        print(f"{len(files)} files checked: {word}")
    return worst


if __name__ == "__main__":
    sys.exit(main())

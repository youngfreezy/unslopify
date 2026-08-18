#!/usr/bin/env python3
"""Calibration: run the audit over pre-LLM human prose and report rates.

AI-pattern linters get tested against old books within an hour of any
launch, so the repo tests itself first and publishes the numbers. Each
source is public domain or freely redistributable, fetched at run time
and cached; no source text is stored in the repo.

  python scripts/calibrate.py            # table to stdout
  python scripts/calibrate.py --words 3000

The named types are the signal to watch: they claim "this reads as
generated", so hits on 19th-century prose are false positives. The
mechanics checks (sentence length, semicolon density) are style gates
for modern professional writing and are expected to fire on Victorian
prose; both are tunable CLI flags, and the table reports the two
families separately.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from unslopify.audit import audit_text  # noqa: E402

CACHE = Path.home() / ".cache" / "unslopify-calibration"

SOURCES = [
    (
        "Twain, Life on the Mississippi (1883)",
        "https://www.gutenberg.org/cache/epub/245/pg245.txt",
    ),
    (
        "Darwin, On the Origin of Species (1859)",
        "https://www.gutenberg.org/cache/epub/1228/pg1228.txt",
    ),
    (
        "Austen, Pride and Prejudice (1813)",
        "https://www.gutenberg.org/cache/epub/1342/pg1342.txt",
    ),
    (
        "Doyle, The Adventures of Sherlock Holmes (1892)",
        "https://www.gutenberg.org/cache/epub/1661/pg1661.txt",
    ),
    (
        "RFC 7231, HTTP/1.1 Semantics (2014)",
        "https://www.rfc-editor.org/rfc/rfc7231.txt",
    ),
]

GUTENBERG_START = re.compile(r"\*\*\* START OF.*\*\*\*", re.I)
GUTENBERG_END = re.compile(r"\*\*\* END OF.*\*\*\*", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9']+")


def fetch(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / re.sub(r"[^\w.]+", "_", url)
    if cached.is_file():
        return cached.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "unslopify-calibration"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    cached.write_text(text, encoding="utf-8")
    return text


def excerpt(text: str, words: int) -> str:
    m = GUTENBERG_START.search(text)
    if m:
        text = text[m.end() :]
        e = GUTENBERG_END.search(text)
        if e:
            text = text[: e.start()]
        # skip front matter: contents pages, headings
        text = text[2000:]
    out: list[str] = []
    count = 0
    for line in text.splitlines():
        out.append(line)
        count += len(WORD_RE.findall(line))
        if count >= words:
            break
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, default=5000, help="excerpt size per source")
    args = parser.parse_args()

    rows: list[tuple[str, int, int, int, str]] = []
    for name, url in SOURCES:
        try:
            sample = excerpt(fetch(url), args.words)
        except OSError as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        report = audit_text(sample, source=name)
        named = [f for f in report.findings]
        rows.append(
            (
                name,
                report.word_count,
                len(named),
                len(report.mechanics),
                ", ".join(
                    sorted({f.type_id for f in named})
                ) or "-",
            )
        )

    print(f"{'source':<50} {'words':>6} {'named':>6} {'mech':>5}  named types hit")
    for name, wc, named, mech, types in rows:
        print(f"{name:<50} {wc:>6} {named:>6} {mech:>5}  {types}")
    print()
    total_words = sum(r[1] for r in rows)
    total_named = sum(r[2] for r in rows)
    if total_words:
        print(
            f"named findings per 1,000 words: "
            f"{total_named * 1000 / total_words:.2f} "
            f"({total_named} in {total_words})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

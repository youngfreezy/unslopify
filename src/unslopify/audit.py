"""Deterministic audit: detect named slop types and mechanical problems.

No model calls. Everything here is regex and counting, so the same input
always produces the same report. The agent skill layers judgment on top;
this module is the floor it stands on.

Suppression:
- ``unslopify:disable`` anywhere in a file skips the whole file,
  except the dash check.
- ``unslopify:disable=id1,id2`` disables those type ids or mechanics
  checks for the file. ``dash`` in that list is ignored.
- ``unslopify:disable-line`` suppresses every finding on its own line
  except em and en dashes.
- Em and en dashes always fail. ``--ignore-quotes``, file skip, and
  config ``disable = ["dash"]`` do not waive them.

Soft-type thresholds and the repeated-phrase allowance scale with
document length (per 1,000 words), so a long report is not failed for
the density that is normal at ten times the size of a memo.
"""

from __future__ import annotations

import math
import re

from .lexicon import ABSTRACT_NOUNS, STOPWORDS, TECH_ANCHORS, is_abstract
from .models import Audit, Draft, Finding, MechanicsFinding
from .rubric import TYPES, SlopType

EM_DASH = "—"
EN_DASH = "–"
# Long dashes cannot be suppressed. A quoted prompt, disable pragma,
# disable-line, file skip, or config disable=dash still fails.
HARD_MECHANICS = frozenset({"dash"})
CURLY = "‘’“”"

FENCE_RE = re.compile(r"^(```|~~~)")
QUOTED_RE = re.compile(r'"[^"\n]*"')
URL_RE = re.compile(r"https?://\S+")
MD_LINK_TARGET_RE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)[^)]*\)")
WORD_RE = re.compile(r"[A-Za-z0-9']+")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s|$)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d{1,3}[.)]\s+|#{1,6}\s+|\|)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")

DISABLE_FILE_RE = re.compile(r"unslopify:disable(?!\S)")
DISABLE_TYPES_RE = re.compile(r"unslopify:disable=([\w,-]+)")
DISABLE_LINE_RE = re.compile(r"unslopify:disable-line")

# Tunables. Callers can override via audit_text kwargs.
MAX_SENTENCE_WORDS = 36
SEMICOLONS_PER_100_WORDS = 1.0
NGRAM_N = 4
NGRAM_MAX_REPEATS = 1

# Sensitivity levels multiply the length-scaled soft thresholds.
LEVELS = {"strict": 0.5, "standard": 1.0, "relaxed": 2.0}


def _scaled(threshold: int, words: int, level: float = 1.0) -> int:
    """A soft threshold is per 1,000 words, floored at its base value and
    multiplied by the sensitivity level."""
    base = max(threshold, math.ceil(threshold * words / 1000))
    return max(1, math.ceil(base * level))


def _ngram_allowance(words: int) -> int:
    """Occurrences of one 4-gram tolerated before it reads as a stamp."""
    return max(NGRAM_MAX_REPEATS, 1 + words // 1500)


def _pragmas(lines: list[str]) -> tuple[bool, set[str], set[int]]:
    """Returns (skip_file, disabled_ids, disabled_lines). Runs on
    structure-stripped lines, so a pragma quoted in a code fence is
    documentation, not an instruction."""
    disabled: set[str] = set()
    disabled_lines: set[int] = set()
    skip = False
    for i, line in enumerate(lines, start=1):
        if DISABLE_LINE_RE.search(line):
            disabled_lines.add(i)
            continue
        m = DISABLE_TYPES_RE.search(line)
        if m:
            disabled.update(x.strip() for x in m.group(1).split(",") if x.strip())
        elif DISABLE_FILE_RE.search(line):
            skip = True
    disabled -= HARD_MECHANICS
    return skip, disabled, disabled_lines


def _dash_findings(lines: list[str]) -> list[MechanicsFinding]:
    """Scan raw lines. Long dashes fail even in quotes, fences, and skipped files."""
    mech: list[MechanicsFinding] = []
    for lineno, line in enumerate(lines, start=1):
        if EM_DASH in line or EN_DASH in line:
            mech.append(
                MechanicsFinding(
                    check="dash",
                    line=lineno,
                    detail="em or en dash; use a comma, colon, or a new sentence",
                )
            )
    return mech


def _strip_structure(lines: list[str]) -> list[str]:
    """Blank out fenced code, YAML frontmatter, and table rows; drop bare
    URLs and markdown link targets (link text stays). Prose only."""
    out: list[str] = []
    in_fence = False
    in_frontmatter = False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            out.append("")
            continue
        if in_frontmatter:
            out.append("")
            if line.strip() in ("---", "..."):
                in_frontmatter = False
            continue
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence or TABLE_ROW_RE.match(line):
            out.append("")
            continue
        line = MD_LINK_TARGET_RE.sub(r"\1", line)
        line = URL_RE.sub(" ", line)
        out.append(line)
    return out


def _normalize(text: str) -> str:
    return " ".join(WORD_RE.findall(text.lower()))


def _ngram_counts(text: str, n: int) -> dict[str, int]:
    words = _normalize(text).split()
    counts: dict[str, int] = {}
    for i in range(len(words) - n + 1):
        g = " ".join(words[i : i + n])
        counts[g] = counts.get(g, 0) + 1
    return counts


def _paragraphs(lines: list[str]) -> list[tuple[int, str]]:
    """Group lines into (start_line, joined_text) paragraphs so patterns
    can match across hard wraps. Headings and list items are their own
    paragraphs, so eight bullets never merge into one fake sentence."""
    paras: list[tuple[int, str]] = []
    start = 0
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            paras.append((start, " ".join(buf)))
            buf = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if LIST_ITEM_RE.match(line):
            flush()
            paras.append((i, stripped))
            continue
        if not buf:
            start = i
        buf.append(stripped)
    flush()
    return paras


def _make_finding(t, lineno: int, span: str, context: str) -> Finding:
    return Finding(
        type_id=t.id,
        type_name=t.name,
        category=t.category,
        severity=t.severity,
        line=lineno,
        span=span,
        context=context.strip()[:200],
        why=t.definition,
        fix_hint=t.example_fix,
    )


def _type_findings(
    lines: list[str],
    ignore_quoted: bool,
    disabled: set[str],
    disabled_lines: set[int],
) -> list[Finding]:
    findings: list[Finding] = []
    line_keys: set[tuple[str, str]] = set()
    types = [t for t in TYPES if t.id not in disabled]

    def clean(haystack: str) -> str:
        return QUOTED_RE.sub(" ", haystack) if ignore_quoted else haystack

    for lineno, line in enumerate(lines, start=1):
        if lineno in disabled_lines:
            continue
        haystack = clean(line)
        if not haystack.strip():
            continue
        for t in types:
            for pat in t.patterns:
                for m in pat.finditer(haystack):
                    line_keys.add((t.id, m.group(0).lower()))
                    findings.append(_make_finding(t, lineno, m.group(0), line))

    # Second pass over joined paragraphs catches matches split across hard
    # wraps. Only spans the line pass never saw are added, so nothing is
    # double-counted.
    for start, para in _paragraphs(lines):
        if start in disabled_lines:
            continue
        haystack = clean(para)
        for t in types:
            for pat in t.patterns:
                for m in pat.finditer(haystack):
                    if (t.id, m.group(0).lower()) in line_keys:
                        continue
                    findings.append(_make_finding(t, start, m.group(0), para))

    findings.sort(key=lambda f: (f.line, f.type_id))
    return findings


def _mechanics(
    lines: list[str],
    text: str,
    max_sentence_words: int,
    disabled: set[str],
    disabled_lines: set[int],
) -> list[MechanicsFinding]:
    mech: list[MechanicsFinding] = []
    words = len(WORD_RE.findall(text))

    for lineno, line in enumerate(lines, start=1):
        if lineno in disabled_lines:
            continue
        if "curly-quotes" not in disabled and any(c in line for c in CURLY):
            mech.append(
                MechanicsFinding(
                    check="curly-quotes",
                    line=lineno,
                    detail="curly quotes; use straight quotes",
                )
            )

    # Long sentences (feeds the "verbosity" soft type). Measured over
    # joined paragraphs, not raw lines, so hard-wrapped prose cannot hide
    # a long sentence across line breaks.
    if "sentence-length" not in disabled:
        for start, para in _paragraphs(lines):
            if start in disabled_lines or LIST_ITEM_RE.match(para):
                continue
            for sent in SENTENCE_SPLIT_RE.split(para):
                n = len(WORD_RE.findall(sent))
                if n > max_sentence_words:
                    mech.append(
                        MechanicsFinding(
                            check="sentence-length",
                            line=start,
                            detail=f"{n} words in one sentence (cap {max_sentence_words})",
                        )
                    )

    # Semicolon density (feeds "staged-punctuation").
    semis = text.count(";")
    if (
        "semicolon-density" not in disabled
        and words
        and semis / words * 100 > SEMICOLONS_PER_100_WORDS
        and semis >= 2
    ):
        mech.append(
            MechanicsFinding(
                check="semicolon-density",
                line=0,
                detail=f"{semis} semicolons in {words} words",
            )
        )

    # Repeated n-grams inside the same document, with a length-scaled
    # allowance so long reports are not failed for normal recurrence.
    if "repeated-ngram" not in disabled:
        allowance = _ngram_allowance(words)
        for gram, count in sorted(_ngram_counts(text, NGRAM_N).items()):
            if count > allowance:
                mech.append(
                    MechanicsFinding(
                        check="repeated-ngram",
                        line=0,
                        detail=(
                            f"{count}x {gram!r} ({NGRAM_N}-word phrase repeats; "
                            f"allowance {allowance} at {words} words)"
                        ),
                    )
                )
    # Abstraction (both feed soft types in the verdict).
    # noun-stack: three or more consecutive abstract nouns with no
    # concrete or technical word breaking the run.
    # abstract-sentence: a sentence dominated by abstract vocabulary with
    # no concrete anchor (number, technical noun, or proper name).
    if "noun-stack" not in disabled or "abstract-sentence" not in disabled:
        for start, para in _paragraphs(lines):
            if start in disabled_lines:
                continue
            for sent in SENTENCE_SPLIT_RE.split(para):
                tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", sent)
                if not tokens:
                    continue
                if "noun-stack" not in disabled:
                    run: list[str] = []
                    for tok in tokens + [""]:
                        low = tok.lower()
                        if tok and low not in STOPWORDS and is_abstract(tok):
                            run.append(tok)
                            continue
                        if len(run) >= 3:
                            mech.append(
                                MechanicsFinding(
                                    check="noun-stack",
                                    line=start,
                                    detail=f"abstract noun stack: {' '.join(run)!r}",
                                )
                            )
                        run = []
                if "abstract-sentence" not in disabled:
                    content = [
                        w for w in tokens if w.lower() not in STOPWORDS and len(w) > 2
                    ]
                    if len(content) < 10:
                        continue
                    abstract = sum(1 for w in content if is_abstract(w))
                    anchored = (
                        any(ch.isdigit() for ch in sent)
                        or '"' in sent
                        or any(w.lower() in TECH_ANCHORS for w in content)
                        or any(w[0].isupper() for w in content[1:])
                    )
                    if not anchored and abstract / len(content) >= 0.5:
                        mech.append(
                            MechanicsFinding(
                                check="abstract-sentence",
                                line=start,
                                detail=(
                                    f"{abstract}/{len(content)} content words are "
                                    f"abstract with no concrete anchor: "
                                    f"{sent.strip()[:90]!r}"
                                ),
                            )
                        )
    return mech


def _verdict(
    findings: list[Finding],
    mech: list[MechanicsFinding],
    words: int,
    level: float = 1.0,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    hard = [f for f in findings if f.severity == "hard"]
    for f in hard:
        reasons.append(f"line {f.line}: {f.type_name} ({f.span!r})")

    soft_counts: dict[str, int] = {}
    for f in findings:
        if f.severity == "soft":
            soft_counts[f.type_id] = soft_counts.get(f.type_id, 0) + 1
    by_id: dict[str, SlopType] = {t.id: t for t in TYPES}
    # structural feeds
    n_long = sum(1 for m in mech if m.check == "sentence-length")
    if n_long:
        soft_counts["verbosity"] = soft_counts.get("verbosity", 0) + n_long
    n_semi = sum(1 for m in mech if m.check == "semicolon-density")
    if n_semi:
        soft_counts["staged-punctuation"] = (
            soft_counts.get("staged-punctuation", 0) + 2 * n_semi
        )
    for check, type_id in (("noun-stack", "noun-stack"), ("abstract-sentence", "abstract-sentence")):
        n = sum(1 for m in mech if m.check == check)
        if n:
            soft_counts[type_id] = soft_counts.get(type_id, 0) + n
    for type_id, count in sorted(soft_counts.items()):
        t = by_id[type_id]
        limit = _scaled(t.threshold, words, level)
        if count >= limit:
            reasons.append(
                f"{t.name}: {count} hits (threshold {limit} at {words} words)"
            )

    for m in mech:
        if m.check in ("dash", "curly-quotes"):
            reasons.append(f"line {m.line}: {m.detail}")
        elif m.check == "repeated-ngram":
            reasons.append(m.detail)

    return ("fail" if reasons else "pass"), reasons


def audit_text(
    text: str,
    source: str | None = None,
    ignore_quoted: bool = False,
    max_sentence_words: int = MAX_SENTENCE_WORDS,
    disable: set[str] | None = None,
    level: str = "standard",
) -> Audit:
    """Audit a draft and return a full report.

    ignore_quoted skips text inside double quotes, for documents that
    quote bad writing on purpose (reviews, style guides). It does not
    skip em or en dashes. ``disable`` turns off type ids or mechanics
    checks; in-file pragmas add to it. ``dash`` cannot be disabled.
    """
    raw_lines = text.splitlines() or [""]
    lines = _strip_structure(raw_lines)
    skip, disabled, disabled_lines = _pragmas(lines)
    if disable:
        disabled |= disable
        disabled -= HARD_MECHANICS
    dash_mech = _dash_findings(raw_lines)
    if skip:
        if dash_mech:
            reasons = [f"line {m.line}: {m.detail}" for m in dash_mech]
            return Audit(
                source=source,
                mechanics=dash_mech,
                word_count=len(WORD_RE.findall(text)),
                verdict="fail",
                fail_reasons=reasons,
            )
        return Audit(
            source=source,
            word_count=len(WORD_RE.findall(text)),
            verdict="pass",
            fail_reasons=[],
        )

    prose = "\n".join(lines)
    words = len(WORD_RE.findall(prose))

    findings = _type_findings(lines, ignore_quoted, disabled, disabled_lines)
    mech = dash_mech + _mechanics(lines, prose, max_sentence_words, disabled, disabled_lines)
    verdict, reasons = _verdict(findings, mech, words, LEVELS.get(level, 1.0))

    counts_by_type: dict[str, int] = {}
    counts_by_category: dict[str, int] = {}
    for f in findings:
        counts_by_type[f.type_id] = counts_by_type.get(f.type_id, 0) + 1
        counts_by_category[f.category] = counts_by_category.get(f.category, 0) + 1

    return Audit(
        source=source,
        findings=findings,
        mechanics=mech,
        counts_by_type=counts_by_type,
        counts_by_category=counts_by_category,
        word_count=words,
        verdict=verdict,
        fail_reasons=reasons,
    )


def audit_draft(draft: Draft, **kwargs) -> Audit:
    return audit_text(draft.text, source=draft.source, **kwargs)

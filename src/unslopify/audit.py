"""Deterministic audit: detect named slop types and mechanical problems.

No model calls. Everything here is regex and counting, so the same input
always produces the same report. The agent skill layers judgment on top;
this module is the floor it stands on.
"""

from __future__ import annotations

import re

from .models import Audit, Draft, Finding, MechanicsFinding
from .rubric import TYPES, SlopType

EM_DASH = "—"
EN_DASH = "–"
CURLY = "‘’“”"

FENCE_RE = re.compile(r"^(```|~~~)")
QUOTED_RE = re.compile(r'"[^"\n]*"')
URL_RE = re.compile(r"https?://\S+")
MD_LINK_TARGET_RE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)[^)]*\)")
WORD_RE = re.compile(r"[A-Za-z0-9']+")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s|$)")

# Tunables. Callers can override via audit_text kwargs.
MAX_SENTENCE_WORDS = 36
SEMICOLONS_PER_100_WORDS = 1.0
NGRAM_N = 4
NGRAM_MAX_REPEATS = 1


def _strip_code_blocks(lines: list[str]) -> list[str]:
    """Blank out fenced code blocks; audit prose, not code. Markdown link
    targets and bare URLs are dropped too (link text stays), so badge
    rows and reference lists do not read as repeated prose."""
    out: list[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
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
    can match across hard-wrapped lines."""
    paras: list[tuple[int, str]] = []
    start = 0
    buf: list[str] = []
    for i, line in enumerate(lines, start=1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line.strip())
        elif buf:
            paras.append((start, " ".join(buf)))
            buf = []
    if buf:
        paras.append((start, " ".join(buf)))
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


def _type_findings(lines: list[str], ignore_quoted: bool) -> list[Finding]:
    findings: list[Finding] = []
    line_keys: set[tuple[str, str]] = set()

    def clean(haystack: str) -> str:
        return QUOTED_RE.sub(" ", haystack) if ignore_quoted else haystack

    for lineno, line in enumerate(lines, start=1):
        haystack = clean(line)
        if not haystack.strip():
            continue
        for t in TYPES:
            for pat in t.patterns:
                for m in pat.finditer(haystack):
                    line_keys.add((t.id, m.group(0).lower()))
                    findings.append(_make_finding(t, lineno, m.group(0), line))

    # Second pass over joined paragraphs catches matches split across hard
    # wraps. Only spans the line pass never saw are added, so nothing is
    # double-counted.
    for start, para in _paragraphs(lines):
        haystack = clean(para)
        for t in TYPES:
            for pat in t.patterns:
                for m in pat.finditer(haystack):
                    if (t.id, m.group(0).lower()) in line_keys:
                        continue
                    findings.append(_make_finding(t, start, m.group(0), para))

    findings.sort(key=lambda f: (f.line, f.type_id))
    return findings


def _mechanics(lines: list[str], text: str, max_sentence_words: int) -> list[MechanicsFinding]:
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
        if any(c in line for c in CURLY):
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
    for start, para in _paragraphs(lines):
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
    words = len(WORD_RE.findall(text))
    semis = text.count(";")
    if words and semis / words * 100 > SEMICOLONS_PER_100_WORDS and semis >= 2:
        mech.append(
            MechanicsFinding(
                check="semicolon-density",
                line=0,
                detail=f"{semis} semicolons in {words} words",
            )
        )

    # Repeated n-grams inside the same document.
    for gram, count in sorted(_ngram_counts(text, NGRAM_N).items()):
        if count > NGRAM_MAX_REPEATS:
            mech.append(
                MechanicsFinding(
                    check="repeated-ngram",
                    line=0,
                    detail=f"{count}x {gram!r} ({NGRAM_N}-word phrase repeats)",
                )
            )
    return mech


def _verdict(
    findings: list[Finding], mech: list[MechanicsFinding]
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
    for type_id, count in sorted(soft_counts.items()):
        t = by_id[type_id]
        if count >= t.threshold:
            reasons.append(f"{t.name}: {count} hits (threshold {t.threshold})")

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
) -> Audit:
    """Audit a draft and return a full report.

    ignore_quoted skips text inside double quotes, for documents that
    quote bad writing on purpose (reviews, style guides).
    """
    raw_lines = text.splitlines() or [""]
    lines = _strip_code_blocks(raw_lines)
    prose = "\n".join(lines)

    findings = _type_findings(lines, ignore_quoted)
    mech = _mechanics(lines, prose, max_sentence_words)
    verdict, reasons = _verdict(findings, mech)

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
        word_count=len(WORD_RE.findall(prose)),
        verdict=verdict,
        fail_reasons=reasons,
    )


def audit_draft(draft: Draft, **kwargs) -> Audit:
    return audit_text(draft.text, source=draft.source, **kwargs)

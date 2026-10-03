"""Mechanical fixes and the rewrite brief.

Two layers:

1. mechanical_rewrite: character and phrase substitutions that never change
   meaning (dashes, curly quotes, deletable filler). Pure Python and
   deterministic. Every edit is recorded as a typed RewriteEvent with a
   rule id and the exact before and after, so the report shows what
   changed, not just the result.
2. build_brief: a structured instruction sheet for whichever model or
   human does the actual rewrite. The heavy lifting is judgment work and
   belongs to the agent skill, not this module.
"""

from __future__ import annotations

import re

from .audit import audit_text
from .models import Audit, Draft, Rewrite, RewriteEvent, StylePolicy

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_QUOTED_RE = re.compile(r'"[^"\n]*"')

# (rule_id, pattern, replacement). Only edits whose meaning is provably
# unchanged belong here.
SAFE_RULES: list[tuple[str, re.Pattern, str]] = [
    ("dash-to-comma", re.compile("—"), ", "),
    ("endash-to-hyphen", re.compile("–"), "-"),
    ("straighten-apostrophe", re.compile("[‘’]"), "'"),
    ("straighten-quote", re.compile("[“”]"), '"'),
    ("in-order-to", re.compile(r"\bin order to\b", re.I), "to"),
    ("due-to-the-fact", re.compile(r"\bdue to the fact that\b", re.I), "because"),
    ("point-in-time", re.compile(r"\bat this point in time\b", re.I), "now"),
    ("for-the-purpose-of", re.compile(r"\bfor the purpose of\b", re.I), "for"),
    ("with-regard-to", re.compile(r"\bwith regard to\b", re.I), "about"),
    ("drop-further-ado", re.compile(r"^\s*without further ado,?\s*", re.I), ""),
    ("drop-dive-in", re.compile(r"^\s*let'?s dive in\.?\s*$", re.I), ""),
    ("drop-hope-helps", re.compile(r"\s*i hope this helps\.?", re.I), ""),
]

_MULTISPACE = re.compile(r"[ \t]{2,}")
_SPACE_PUNCT = re.compile(r" +([,.;:])")


def _mask_quotes(line: str) -> tuple[str, list[str]]:
    """Replace quoted spans with placeholders so rules never edit them."""
    saved: list[str] = []

    def stash(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    return _QUOTED_RE.sub(stash, line), saved


def _unmask_quotes(line: str, saved: list[str]) -> str:
    for i, span in enumerate(saved):
        line = line.replace(f"\x00{i}\x00", span)
    return line


DASH_RULE_IDS = frozenset({"dash-to-comma", "endash-to-hyphen"})


def _apply_rules(
    work: str, fired: list[str], only: frozenset[str] | None = None
) -> str:
    for rule_id, pat, repl in SAFE_RULES:
        if only is not None and rule_id not in only:
            continue
        if only is None and rule_id in DASH_RULE_IDS:
            continue
        new = pat.sub(repl, work)
        if new != work:
            fired.append(rule_id)
            work = new
    return work


def _fix_line(line: str, policy: StylePolicy) -> tuple[str, list[str]]:
    """Apply safe rules to one line. Returns (fixed, rule_ids_fired).

    Dash substitutions run on the full line first. Quoted spans cannot
    keep an em or en dash; that check is not waivable.
    """
    fired: list[str] = []
    work = _apply_rules(line, fired, only=DASH_RULE_IDS)
    work, saved = _mask_quotes(work) if policy.preserve_quotes else (work, [])
    work = _apply_rules(work, fired)
    if fired:
        work = _MULTISPACE.sub(" ", work)
        work = _SPACE_PUNCT.sub(r"\1", work)
    if policy.preserve_quotes:
        work = _unmask_quotes(work, saved)
    return work, fired


def apply_safe_fixes(
    text: str, policy: StylePolicy | None = None
) -> tuple[str, list[RewriteEvent]]:
    """Apply meaning-preserving substitutions line by line.

    Returns the fixed text and one RewriteEvent per changed line per rule,
    so the log carries the exact before and after.
    """
    policy = policy or StylePolicy()
    out_lines: list[str] = []
    events: list[RewriteEvent] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        fixed, fired = _fix_line(line, policy)
        for rule_id in fired:
            events.append(
                RewriteEvent(
                    line=lineno, rule_id=rule_id, before=line, after=fixed
                )
            )
        out_lines.append(fixed)
    result = "\n".join(out_lines)
    if text.endswith("\n"):
        result += "\n"
    return result, events


def build_brief(audit: Audit) -> str:
    """Render an audit as rewrite instructions, grouped by category."""
    if audit.verdict == "pass" and not audit.findings:
        return "No findings. Leave the text as it is."
    lines: list[str] = ["Rewrite instructions, one block per problem:"]
    for f in audit.findings:
        lines.append("")
        lines.append(f"- line {f.line}: {f.type_name}")
        lines.append(f"  span: {f.span!r}")
        lines.append(f"  problem: {f.why}")
        lines.append(f"  direction: {f.fix_hint}")
    for m in audit.mechanics:
        lines.append("")
        lines.append(f"- line {m.line}: {m.check}: {m.detail}")
    lines.append("")
    lines.append(
        "Keep every fact and qualification from the original. Cover everything "
        "the original covers. Do not add new claims. One main point per "
        "sentence, active subject and verb, standard capitalization. Do not "
        "grow the word count to satisfy a gate."
    )
    return "\n".join(lines)


def mechanical_rewrite(draft: Draft, policy: StylePolicy | None = None) -> Rewrite:
    """Safe fixes only, then re-audit. The result usually still needs the
    agent pass; this exists so the CLI has a useful --fix offline."""
    policy = policy or StylePolicy()
    fixed, events = apply_safe_fixes(draft.text, policy)
    return Rewrite(
        original=draft,
        rewritten=fixed,
        policy=policy,
        events=events,
        applied_fixes=sorted({e.rule_id for e in events}),
        words_before=len(_WORD_RE.findall(draft.text)),
        words_after=len(_WORD_RE.findall(fixed)),
        audit_after=audit_text(fixed, source=draft.source),
    )

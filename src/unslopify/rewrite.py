"""Mechanical fixes and the rewrite brief.

Two layers:

1. apply_safe_fixes: character and phrase substitutions that never change
   meaning (dashes, curly quotes, deletable filler). Pure Python.
2. build_brief: a structured instruction sheet for whichever model or
   human does the actual rewrite. The heavy lifting is judgment work and
   belongs to the agent skill, not this module.
"""

from __future__ import annotations

import re

from .audit import audit_text
from .models import Audit, Draft, Rewrite

# (pattern, replacement, note) applied in order. Only edits whose meaning
# is provably unchanged belong here.
SAFE_SUBS: list[tuple[re.Pattern, str, str]] = [
    (re.compile("—"), ", ", "em dash to comma"),
    (re.compile("–"), "-", "en dash to hyphen"),
    (re.compile("[‘’]"), "'", "curly apostrophe to straight"),
    (re.compile("[“”]"), '"', "curly quote to straight"),
    (re.compile(r"\bin order to\b", re.I), "to", "'in order to' to 'to'"),
    (re.compile(r"\bdue to the fact that\b", re.I), "because", "'due to the fact that' to 'because'"),
    (re.compile(r"\bat this point in time\b", re.I), "now", "'at this point in time' to 'now'"),
    (re.compile(r"\bfor the purpose of\b", re.I), "for", "'for the purpose of' to 'for'"),
    (re.compile(r"\bwith regard to\b", re.I), "about", "'with regard to' to 'about'"),
    (re.compile(r"(?m)^\s*without further ado,?\s*", re.I), "", "drop 'without further ado'"),
    (re.compile(r"(?m)^\s*let'?s dive in\.?\s*$", re.I), "", "drop 'let's dive in'"),
    (re.compile(r"\s+i hope this helps\.?", re.I), "", "drop 'I hope this helps'"),
]

_MULTISPACE = re.compile(r"[ \t]{2,}")
_SPACE_PUNCT = re.compile(r" +([,.;:])")


def apply_safe_fixes(text: str) -> tuple[str, list[str]]:
    """Apply meaning-preserving substitutions. Returns (text, notes)."""
    notes: list[str] = []
    for pat, repl, note in SAFE_SUBS:
        new = pat.sub(repl, text)
        if new != text:
            notes.append(note)
            text = new
    text = _MULTISPACE.sub(" ", text)
    text = _SPACE_PUNCT.sub(r"\1", text)
    return text, notes


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
        "the original covers. Do not add new claims."
    )
    return "\n".join(lines)


def mechanical_rewrite(draft: Draft) -> Rewrite:
    """Safe fixes only, then re-audit. The result usually still needs the
    agent pass; this exists so the CLI has a useful --fix offline."""
    fixed, notes = apply_safe_fixes(draft.text)
    return Rewrite(
        original=draft,
        rewritten=fixed,
        applied_fixes=notes,
        audit_after=audit_text(fixed, source=draft.source),
    )

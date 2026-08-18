"""Pydantic models shared by the audit core, the CLI, and the agent skill."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

REPORT_VERSION = "1"

Severity = Literal["hard", "soft"]
Category = Literal["formula", "substance", "wording", "structure"]


class Draft(BaseModel):
    """A piece of text under audit."""

    text: str
    source: Optional[str] = None  # file path, "stdin", or a caller-set id


class Finding(BaseModel):
    """One detected instance of a named slop type."""

    type_id: str
    type_name: str
    category: Category
    severity: Severity
    line: int  # 1-indexed
    span: str  # the matched text
    context: str  # the full line the match sits on
    why: str  # the type's one-line definition
    fix_hint: str  # the type's example fix or revision move


class MechanicsFinding(BaseModel):
    """A structural or character-level problem (not tied to a rubric type)."""

    check: str  # e.g. "em-dash", "curly-quotes", "sentence-length", "repeated-ngram"
    line: int
    detail: str


class Audit(BaseModel):
    """Full result of one audit pass."""

    version: str = REPORT_VERSION
    source: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0)
    )
    findings: list[Finding] = Field(default_factory=list)
    mechanics: list[MechanicsFinding] = Field(default_factory=list)
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    word_count: int = 0
    verdict: Literal["pass", "fail"] = "pass"
    fail_reasons: list[str] = Field(default_factory=list)


class StylePolicy(BaseModel):
    """Typed knobs for the rewrite pass.

    The defaults encode plain-language editing: standard capitalization,
    no injected informality, quotes preserved exactly, and no growth in
    word count to satisfy a gate.
    """

    sentence_word_limit: int = 36
    preserve_quotes: bool = True
    standard_capitalization: bool = True
    allow_word_growth: bool = False
    banned_formulas: list[str] = Field(default_factory=list)


class RewriteEvent(BaseModel):
    """One recorded edit: which rule fired, where, and the exact change."""

    line: int = Field(ge=1)
    rule_id: str
    before: str
    after: str


class Rewrite(BaseModel):
    """A rewrite produced from an audit, plus the audit of the result.

    Every edit is a typed event, so the report shows exactly what changed
    and why, not just the final text.
    """

    original: Draft
    rewritten: str
    policy: StylePolicy = Field(default_factory=StylePolicy)
    events: list[RewriteEvent] = Field(default_factory=list)
    applied_fixes: list[str] = Field(default_factory=list)
    words_before: int = 0
    words_after: int = 0
    audit_after: Optional[Audit] = None


class JudgeVerdict(BaseModel):
    """Verdict from a fresh-context judge that never saw the working notes."""

    approved: bool
    reasons: list[str] = Field(default_factory=list)
    quoted_spans: list[str] = Field(default_factory=list)


class VoiceProfile(BaseModel):
    """Optional stats from a sample of the author's own writing.

    The rewrite pass uses these as targets so the output sounds like the
    author, not like a house style.
    """

    sample_source: Optional[str] = None
    avg_sentence_words: float = 0.0
    max_sentence_words: int = 0
    contraction_rate: float = 0.0  # contractions per 100 words
    first_person_rate: float = 0.0  # I/we per 100 words
    notes: list[str] = Field(default_factory=list)

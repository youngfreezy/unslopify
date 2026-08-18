"""Build a VoiceProfile from a sample of the author's own writing.

The profile is a handful of measurable targets. The rewrite pass aims the
output at these numbers instead of a house style, so the cleaned text still
sounds like the person who wrote it.
"""

from __future__ import annotations

import re

from .models import VoiceProfile

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENT_RE = re.compile(r"[.!?]+(?:\s|$)")
_CONTRACTION_RE = re.compile(
    r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE
)
_FIRST_PERSON_RE = re.compile(r"\b(?:i|we|i'm|i've|i'll|we're|we've)\b", re.IGNORECASE)


def profile_from_sample(sample: str, source: str | None = None) -> VoiceProfile:
    sentences = [s for s in _SENT_RE.split(sample) if _WORD_RE.search(s)]
    lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    words = len(_WORD_RE.findall(sample))
    if not words:
        return VoiceProfile(sample_source=source, notes=["empty sample"])

    contractions = len(_CONTRACTION_RE.findall(sample))
    first_person = len(_FIRST_PERSON_RE.findall(sample))

    notes: list[str] = []
    avg = sum(lengths) / len(lengths) if lengths else 0.0
    if avg and avg < 14:
        notes.append("short sentences; keep rewrites clipped")
    elif avg > 24:
        notes.append("long sentences; do not over-chop the rewrite")
    if contractions / words * 100 > 1.5:
        notes.append("contractions are normal for this author")
    elif contractions == 0 and words > 120:
        notes.append("author avoids contractions; keep the formal register")
    if first_person / words * 100 > 1.0:
        notes.append("first person is part of the voice")

    return VoiceProfile(
        sample_source=source,
        avg_sentence_words=round(avg, 1),
        max_sentence_words=max(lengths) if lengths else 0,
        contraction_rate=round(contractions / words * 100, 2),
        first_person_rate=round(first_person / words * 100, 2),
        notes=notes,
    )

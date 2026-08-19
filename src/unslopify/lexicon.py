"""Small curated lexicons for the abstraction checks.

ABSTRACT_NOUNS is an original curation of management-register nouns that
carry no picture: you cannot point at a governance. The list is meant to
be small and high-precision, not a concreteness corpus; the suffix
heuristic in audit.py extends its reach inside noun stacks.

TECH_ANCHORS are ordinary computing nouns that legitimately stack in
technical prose ("response header field"). A noun run counts as abstract
only when abstract nouns dominate it, so these words defuse the check
rather than trigger it.
"""

from __future__ import annotations

ABSTRACT_NOUNS = frozenset(
    """
    ability agility alignment approach capability capacity commitment
    complexity culture direction effectiveness efficiency effort
    empowerment enablement engagement excellence execution experience
    focus framework functionality governance growth impact initiative
    innovation insight intelligence journey landscape leadership
    leverage maturity methodology mindset mission momentum objective
    opportunity optimization orchestration ownership paradigm
    performance perspective potential priority process productivity
    quality readiness resilience roadmap scalability scale solution
    stakeholder standardization strategy success synergy
    transformation transparency utilization value velocity vision
    """.split()
)

NOMINAL_SUFFIXES = (
    "tion",
    "sion",
    "ment",
    "ness",
    "ance",
    "ence",
    "ity",
    "ization",
    "ability",
    "ship",
)

TECH_ANCHORS = frozenset(
    """
    api array branch buffer build cache client column commit compiler
    config cursor database endpoint error field file function header
    index json key library log method module packet parser password
    path pointer port protocol query queue repo repository request
    response route row schema server socket stack string table test
    thread token url user variable version
    """.split()
)

STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it of on or the to with".split()
)


def is_abstract(word: str) -> bool:
    w = word.lower()
    if w in TECH_ANCHORS:
        return False
    if w in ABSTRACT_NOUNS:
        return True
    return any(w.endswith(s) for s in NOMINAL_SUFFIXES) and len(w) > 6

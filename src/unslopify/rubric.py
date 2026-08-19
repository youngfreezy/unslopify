"""The unslopify rubric: named AI-writing failure types.

Four categories, each holding named types. A type carries a one-line
definition, one invented bad example, one invented fix, and the regex
patterns the deterministic audit uses to spot it.

Types are contextual signals, not banned tokens. Severity "hard" means a
single hit fails the audit. Severity "soft" means hits are counted and the
audit fails only past the per-type threshold, because one isolated instance
of these patterns can be legitimate writing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


CATEGORIES = {
    "formula": "Formula and manufactured rhythm",
    "substance": "Vague or unsupported substance",
    "wording": "Wordy, indirect, or jargon-heavy wording",
    "structure": "Unnecessary framing and structure",
}


@dataclass(frozen=True)
class SlopType:
    id: str
    name: str
    category: str
    definition: str
    example_bad: str
    example_fix: str
    patterns: tuple[re.Pattern, ...] = field(default_factory=tuple)
    severity: str = "hard"  # "hard" | "soft"
    threshold: int = 1  # soft types fail at >= threshold hits


def _p(*sources: str, flags: int = re.IGNORECASE) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(s, flags) for s in sources)


TYPES: tuple[SlopType, ...] = (
    # ------------------------------------------------------------------
    # formula: the claim is fine but it arrives as a jingle
    # ------------------------------------------------------------------
    SlopType(
        id="inflated-contrast",
        name="Inflated contrast",
        category="formula",
        definition="A plain statement dressed up as a reveal by denying a smaller version of itself first.",
        example_bad="This is not just a to-do list. It is a commitment engine.",
        example_fix="The app tracks tasks and nags you until each one is done.",
        patterns=_p(
            r"\b(?:it|this|that|she|he|they)\s+(?:is|are|was|were)?\s*n[o']t\s+just\b",
            r"\bisn't\s+(?:just|merely|simply)\b",
            r"\bnot\s+(?:merely|simply)\s+a\b",
            r"\bit'?s not\b[^.!?]{0,60}\bit'?s\b",
        ),
    ),
    SlopType(
        id="negative-parallelism",
        name="Negative parallelism",
        category="formula",
        definition="The not-X-but-Y frame used as a rhythm device rather than a real correction.",
        example_bad="The launch was not a finish line, but a starting gun.",
        example_fix="The launch shipped the core flow. Billing and admin tools are still open.",
        patterns=_p(
            r"\bnot only\b[^.!?]{0,90}\bbut(?:\s+also)?\b",
            r"\bnot just\b[^.!?]{0,60}\bbut\b",
            r"\bno \w+, no \w+, just\b",
        ),
    ),
    SlopType(
        id="slogan-fragment",
        name="Slogan fragment",
        category="formula",
        definition="A clipped tagline standing in for analysis, often a verbless fragment or drumbeat sentence pair.",
        example_bad="One codebase. Zero excuses. Ship it.",
        example_fix="Merging the two apps into one codebase removes the duplicate release work.",
        patterns=_p(
            r"^\s*(?:[A-Z][\w'-]*(?:\s+[\w'-]+){0,2}\.\s+){2,}[A-Z][\w'-]*(?:\s+[\w'-]+){0,2}\.\s*$",
            flags=0,
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="stock-triad",
        name="Stock triad",
        category="formula",
        definition="Three parallel adjectives or clauses deployed for cadence when one precise word would do.",
        example_bad="The new editor is faster, cleaner, and more delightful.",
        example_fix="The new editor opens files in under 200 ms.",
        patterns=_p(
            r"\b\w+er,\s+\w+er,\s+and\s+(?:more\s+)?\w+\b",
            r"\b(?:faster|smarter|simpler|cleaner|stronger|better),\s+\w+,?\s+and\s+more\s+\w+\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="staged-punctuation",
        name="Staged punctuation",
        category="formula",
        definition="Colons, semicolons, or dashes stacked to fake momentum instead of marking a real relationship.",
        example_bad="The verdict is in: budgets are tight; deadlines are tighter; something has to give.",
        example_fix="The budget covers two of the three features, so one has to wait for next quarter.",
        patterns=(),  # detected structurally in audit.py (semicolon / dash density)
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="canned-empathy",
        name="Canned empathy",
        category="formula",
        definition="A sympathy phrase that could be pasted under any complaint without reading it.",
        example_bad="I completely understand how challenging this must be for you.",
        example_fix="A double charge is a real problem. The refund went out this morning.",
        patterns=_p(
            r"\bi (?:completely|totally|fully) understand\b",
            r"\bhow (?:frustrating|challenging|difficult|overwhelming) (?:this|that|it) (?:must|can) (?:be|feel)\b",
        ),
    ),
    SlopType(
        id="synthetic-balance",
        name="Synthetic balance",
        category="formula",
        definition="A both-sides sentence with no actual tradeoff behind it.",
        example_bad="While automation brings efficiency, it also introduces unique challenges.",
        example_fix="Automation cut ticket volume 40 percent but broke the two workflows that need a human sign-off.",
        patterns=_p(
            r"\bwhile\b[^.!?]{0,70}\b(?:also (?:presents|introduces|brings|poses)|unique challenges)\b",
        ),
    ),
    SlopType(
        id="fake-authority",
        name="Fake authority",
        category="formula",
        definition="An appeal to unnamed experts or unspecified research standing in for a source.",
        example_bad="Experts agree that this approach yields better outcomes.",
        example_fix="The 2025 DORA report links trunk-based development to shorter recovery times.",
        patterns=_p(
            r"\bexperts (?:agree|argue|say|believe|note)\b",
            r"\b(?:observers|analysts|scholars) (?:note|say|argue|suggest)\b",
            r"\bstudies (?:show|suggest|indicate)\b",
            r"\bresearch (?:consistently )?(?:shows|suggests|indicates)\b",
            r"\bseveral sources\b",
            r"\bwidely (?:regarded|considered) as\b",
        ),
    ),
    SlopType(
        id="canned-conclusion",
        name="Canned conclusion",
        category="formula",
        definition="A wrap-up about challenges, legacy, or the future that no part of the text earned.",
        example_bad="Ultimately, only time will tell what the future holds for the project.",
        example_fix="The migration finishes in March. The old API shuts off in June.",
        patterns=_p(
            r"\bonly time will tell\b",
            r"\bwhat the future holds\b",
            r"\bthe road ahead\b",
            r"\bin conclusion\b",
            r"\bin summary\b",
            r"\bfuture outlook\b",
        ),
    ),
    SlopType(
        id="ai-vocab",
        name="AI vocabulary cluster",
        category="formula",
        definition="Words that plain writing rarely needs but generated text reaches for constantly.",
        example_bad="The team will delve into the intricate landscape of vendor contracts.",
        example_fix="The team will read the vendor contracts and list the renewal dates.",
        patterns=_p(
            r"\b(?:delve|delves|delving)\b",
            r"\b(?:tapestry|tapestries)\b",
            r"\bvibrant\b",
            r"\bpivotal\b",
            r"\bintricate\b",
            r"\bfoster(?:s|ing|ed)?\b",
            r"\bshowcas(?:e|es|ing|ed)\b",
            r"\bunderscor(?:e|es|ing|ed)\b",
            r"\btestament\b",
            r"\bcrucial\b",
            r"\bseamless(?:ly)?\b",
            r"\bleverag(?:e|es|ing|ed)\b",
            r"\bboast(?:s|ing|ed)?\b",
            r"\bgame.?chang(?:er|ing)\b",
            r"\belevat(?:e|es|ing|ed)\b",
            r"\bempower(?:s|ing|ed)?\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="significance-inflation",
        name="Significance inflation",
        category="formula",
        definition="An ordinary fact promoted into a milestone, turning point, or statement about broader trends.",
        example_bad="The office move marks a defining chapter in the company's story.",
        example_fix="The company moved to a smaller office in Frisco to cut rent by half.",
        patterns=_p(
            r"\bmarks? a\b[^.!?]{0,40}\b(?:moment|milestone|chapter|shift|turning point|era)\b",
            r"\breflect(?:s|ing) broader\b",
            r"\bevolving landscape\b",
            r"\bprofound (?:shift|change|impact)\b",
            r"\bindelible mark\b",
            r"\bsetting the stage for\b",
            r"\bpav(?:e|es|ing) the way\b",
        ),
    ),
    SlopType(
        id="promo-tone",
        name="Promotional tone",
        category="formula",
        definition="Brochure adjectives and travel-guide praise nobody asked for.",
        example_bad="Guests can savor world-class cuisine in the heart of a bustling downtown.",
        example_fix="The hotel restaurant serves Gulf seafood and stays open until midnight.",
        patterns=_p(
            r"\b(?:world-class|award-winning|breathtaking|stunning|must-(?:visit|see|have)|renowned|bustling)\b",
            r"\bnestled\b",
            r"\bgroundbreaking\b",
            r"\bin the heart of\b",
            r"\brich (?:history|heritage|culture)\b",
            r"\bhidden gem\b",
        ),
        severity="soft",
        threshold=2,
    ),
    # ------------------------------------------------------------------
    # substance: the reader cannot recover what actually happened or why
    # ------------------------------------------------------------------
    SlopType(
        id="empty-abstraction",
        name="Empty abstraction",
        category="substance",
        definition="A claim built from value-words with no observable change underneath.",
        example_bad="The initiative drives alignment and unlocks meaningful impact across teams.",
        example_fix="Support and sales now share one ticket queue, so handoffs stopped losing customer context.",
        patterns=_p(
            r"\bdriv(?:e|es|ing) (?:alignment|impact|value|synergy|innovation)\b",
            r"\bunlock(?:s|ing)? (?:value|potential|impact|growth)\b",
            r"\bmeaningful impact\b",
            r"\bcreate(?:s)? synerg(?:y|ies)\b",
            r"\bmove the needle\b",
        ),
    ),
    SlopType(
        id="tacked-on-benefit",
        name="Tacked-on benefit",
        category="substance",
        definition="An -ing clause bolted to a sentence to assert a benefit the text never demonstrates.",
        example_bad="The dashboard consolidates metrics, ensuring better decision-making at every level.",
        example_fix="The dashboard shows all four regions on one page, so the Monday review no longer needs five tabs.",
        patterns=_p(
            r",\s*ensuring\b",
            r",\s*(?:enhancing|streamlining|elevating|empowering|enabling)\b[^.!?]{0,50}\b(?:experience|efficiency|productivity|outcomes|success)\b",
            r",\s*making it easier than ever\b",
        ),
    ),
    SlopType(
        id="process-not-reason",
        name="Process instead of reason",
        category="substance",
        definition="The meetings that happened offered in place of the reason a decision was made.",
        example_bad="After extensive stakeholder consultation, we have decided to sunset the feature.",
        example_fix="Fewer than 2 percent of accounts used the feature, so we are removing it to simplify billing.",
        patterns=_p(
            r"\bafter (?:extensive|several rounds of|much|careful)\b[^.!?]{0,50}\b(?:consultation|review|deliberation|discussion|consideration)\b",
            r"\baligned? on (?:the )?next (?:phase|steps)\b",
            r"\bcross-functional (?:review|collaboration|alignment)\b",
        ),
    ),
    SlopType(
        id="unsupported-claim",
        name="Unsupported claim",
        category="substance",
        definition="A significance or improvement claim with no number, source, or observable result attached.",
        example_bad="This change dramatically improves performance across the board.",
        example_fix="Page load dropped from 3.1 s to 0.9 s on the checkout flow.",
        patterns=_p(
            r"\bdramatically (?:improv|reduc|increas|boost)\w*\b",
            r"\bsignificantly (?:enhanc|improv|boost)\w*\b",
            r"\bacross the board\b",
            r"\btakes? \w+ to the next level\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="meaning-loss",
        name="Meaning loss",
        category="substance",
        definition="A sentence compressed or abstracted until the specific point can no longer be recovered.",
        example_bad="The proposal addresses where to draw the line.",
        example_fix="The proposal caps overnight shipping subsidies at 4 percent of order value.",
        patterns=(),  # judgment call; surfaced by the agent pass, not regex
    ),
    # ------------------------------------------------------------------
    # wording: the point is clear but buried in packaging
    # ------------------------------------------------------------------
    SlopType(
        id="bureaucratic-phrasing",
        name="Bureaucratic phrasing",
        category="wording",
        definition="Office-memo constructions where a person doing a thing hides behind nouns.",
        example_bad="Stakeholders should be apprised of the operational implications of this transition.",
        example_fix="Tell the support team the phone tree changes on Monday.",
        patterns=_p(
            r"\boperational implications\b",
            r"\bstakeholder(?:s)? (?:should be|will be|alignment)\b",
            r"\boperationaliz(?:e|es|ing|ed)\b",
            r"\bvalue realization\b",
            r"\bgoing forward\b",
            r"\bat this (?:point in time|juncture)\b",
            r"\bin order to\b",
            r"\bdue to the fact that\b",
            r"\bfor the purpose of\b",
            r"\bwith regard to\b",
            r"\bit (?:should|must) be noted that\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="hedge-stack",
        name="Hedge stack",
        category="wording",
        definition="Multiple uncertainty markers piled on one claim until it says nothing.",
        example_bad="It may potentially be worth considering whether a delay could possibly help.",
        example_fix="Delaying two weeks lets QA finish the payment tests. I recommend it.",
        patterns=_p(
            r"\bmay potentially\b",
            r"\bcould possibly\b",
            r"\bmight perhaps\b",
            r"\bit (?:may|might|could) be worth considering\b",
            r"\bit would be advisable\b",
            r"\bperhaps somewhat\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="unexplained-jargon",
        name="Unexplained jargon",
        category="wording",
        definition="Insider or invented terminology dropped on a reader who was never given the decoder.",
        example_bad="The rollout activates our engagement flywheel across acquisition surfaces.",
        example_fix="The rollout adds signup prompts to the blog and the mobile app.",
        patterns=_p(
            r"\b(?:flywheel|force multiplier|paradigm shift|north star metric)\b",
            r"\bsurface(?:s)? (?:the|our) (?:value|insight)s?\b",
            r"\benablement layer\b",
            r"\bdownstream value\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="copula-avoidance",
        name="Copula avoidance",
        category="wording",
        definition="Ornate verbs substituted for is, has, and are, usually to sound weightier.",
        example_bad="The library serves as the backbone of the rendering pipeline.",
        example_fix="The library is the rendering pipeline's core dependency.",
        patterns=_p(
            r"\bserves? as\b",
            r"\bstands? as\b",
            r"\bfunctions? as a\b",
            r"\bacts? as a (?:testament|cornerstone|backbone)\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="verbosity",
        name="Verbosity",
        category="wording",
        definition="A sentence that runs far past the length its content needs.",
        example_bad="(any sentence longer than the configured word cap)",
        example_fix="Split it, or cut the clauses that repeat the point.",
        patterns=(),  # detected structurally in audit.py (sentence word count)
        severity="soft",
        threshold=2,
    ),
    # ------------------------------------------------------------------
    # structure: packaging that delays or dilutes the point
    # ------------------------------------------------------------------
    SlopType(
        id="scene-setting",
        name="Generic scene-setting",
        category="structure",
        definition="A weather-report opener about today's fast-moving world before the actual topic.",
        example_bad="In an era of rapid technological change, documentation matters more than ever.",
        example_fix="The API docs are eight months stale. Here is the update plan.",
        patterns=_p(
            r"\bin today'?s\b[^.!?]{0,40}\b(?:world|landscape|environment|era|economy|market)\b",
            r"\bin an era of\b",
            r"\bfast-paced\b",
            r"\bmore (?:important|critical|essential) than ever\b",
            r"\bever-(?:changing|evolving)\b",
        ),
    ),
    SlopType(
        id="request-restatement",
        name="Request restatement",
        category="structure",
        definition="The question handed back to the reader as filler before the answer starts.",
        example_bad="When it comes to choosing a database, there are several factors to consider.",
        example_fix="Use Postgres. The workload is relational and the team already knows it.",
        patterns=_p(
            r"\bwhen it comes to\b",
            r"\bthere are (?:several|many|a number of) (?:factors|strategies|considerations|options|ways)\b",
        ),
    ),
    SlopType(
        id="meta-announcement",
        name="Meta-announcement",
        category="structure",
        definition="The text narrating itself instead of saying the thing.",
        example_bad="Below is a comprehensive overview tailored to your requirements.",
        example_fix="(delete the line; start with the first point)",
        patterns=_p(
            r"\bbelow is a\b",
            r"\bthe following (?:sections?|overview|guide) (?:provides?|covers?|outlines?)\b",
            r"\btailored to your (?:needs|requirements)\b",
            r"\bi hope this helps\b",
            r"\blet me know if\b",
            r"\bwithout further ado\b",
            r"\blet'?s dive in\b",
        ),
    ),
    SlopType(
        id="redundant-conclusion",
        name="Redundant conclusion",
        category="structure",
        definition="A closing paragraph that re-says the piece in softer words.",
        example_bad="To sum up, the measures above will help the team reach its goals.",
        example_fix="(delete it; the last real point is the ending)",
        patterns=_p(
            r"\bto sum up\b",
            r"\bin closing\b",
            r"\ball in all\b",
            r"\bat the end of the day\b",
            r"\bultimately,\s+(?:the|this|it)\b",
        ),
        severity="soft",
        threshold=2,
    ),
    SlopType(
        id="over-structure",
        name="Over-structure",
        category="structure",
        definition="Headings, bullets, and bold labels multiplying past what the content can fill.",
        example_bad="(a two-paragraph answer split across six headings, or runs of **Label:** bullets)",
        example_fix="Merge into prose; keep structure only where a reader will scan or look things up.",
        patterns=_p(
            r"^\s*[-*+]\s+\*\*[^*\n]{1,40}:?\*\*",
        ),
        severity="soft",
        threshold=4,
    ),
)


TYPES_BY_ID: dict[str, SlopType] = {t.id: t for t in TYPES}


def types_in_category(category: str) -> list[SlopType]:
    return [t for t in TYPES if t.category == category]

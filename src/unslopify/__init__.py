"""unslopify: audit and rewrite text to remove AI-writing patterns."""

__version__ = "0.4.0"

from .audit import audit_draft, audit_text
from .models import (
    Audit,
    Draft,
    Finding,
    JudgeVerdict,
    MechanicsFinding,
    Rewrite,
    RewriteEvent,
    StylePolicy,
    VoiceProfile,
)
from .rewrite import apply_safe_fixes, build_brief, mechanical_rewrite
from .rubric import CATEGORIES, TYPES, TYPES_BY_ID
from .voice import profile_from_sample

__all__ = [
    "__version__",
    "audit_draft",
    "audit_text",
    "Audit",
    "Draft",
    "Finding",
    "JudgeVerdict",
    "MechanicsFinding",
    "Rewrite",
    "RewriteEvent",
    "StylePolicy",
    "VoiceProfile",
    "apply_safe_fixes",
    "build_brief",
    "mechanical_rewrite",
    "CATEGORIES",
    "TYPES",
    "TYPES_BY_ID",
    "profile_from_sample",
]

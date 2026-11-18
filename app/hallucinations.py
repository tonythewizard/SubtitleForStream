"""Conservative, deterministic guard for well-known Whisper subtitle-credit hallucinations.

This is a second line of defence after speech activity detection. It does NOT
try to classify arbitrary words as hallucinations and it does not rewrite speech.
"""
from __future__ import annotations
import re

# Particularly common Whisper training-corpus artefacts; only remove the CREDIT
# phrase, not an unrelated sentence which happens to mention Amara.
_CREDIT = re.compile(
    r'(?i)\b(?:sottotitoli|subtitles|trascrizione|traduzione)\b'
    r'[^.!?\n]{0,115}?\b(?:amara|amra)\s*\.?\s*org\b[.!?]*'
)
_QTSS = re.compile(r'(?i)\b(?:sottotitoli|subtitles)\s+(?:a\s+cura\s+di\s+)?QTSS\b[.!?]*')
_LONE_DOMAIN = re.compile(r'(?i)^[\s\-–—.:,;]*\b(?:amara|amra)\s*\.?\s*org\b[\s.!?]*$')


def clean_asr_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return ''
    cleaned = _CREDIT.sub(' ', text)
    cleaned = _QTSS.sub(' ', cleaned)
    # Entire isolated hallucination, but never scrub normal speech about the website.
    if _LONE_DOMAIN.fullmatch(cleaned):
        return ''
    return ' '.join(cleaned.strip(' \t\r\n,;–—').split())


def accept_segment(segment) -> bool:
    """Reject grossly untrustworthy *segments*; conservative to preserve speech.

    Faster-whisper exposes avg_logprob and no_speech_prob on each segment.
    These are not independent proofs of silence; require both to be poor.
    """
    try:
        no_speech = float(getattr(segment, 'no_speech_prob', 0.0))
        logprob = float(getattr(segment, 'avg_logprob', 0.0))
        return not (no_speech > 0.82 and logprob < -0.65)
    except (TypeError, ValueError, OverflowError):
        return True

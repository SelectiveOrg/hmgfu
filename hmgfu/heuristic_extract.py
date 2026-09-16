"""Deterministic heuristic extraction (Phase 80.2: split from sensitizer.py at the 400-line ceiling — a pure function, no
model). It is the documented fallback when the nano is off or fails, the pre-reply extraction with `nano_in_tail`, and the
extraction of a pre-routed turn with `bypass_skips_nano`. Its summary is the user's own words, never a paraphrase."""
from __future__ import annotations

import re

from .extraction_schema import Extraction, _DEFAULTS, _as_str_list  # noqa: F401

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "i", "you", "he",
    "she", "it", "we", "they", "to", "of", "in", "on", "at", "for", "with", "my", "your",
    "that", "this", "have", "has", "do", "does", "not", "be", "will", "can", "o", "a",
    "os", "as", "um", "uma", "de", "do", "da", "que", "e", "em", "para", "com", "não",
    "eu", "tu", "ele", "ela", "nós", "é", "são", "foi", "ser", "ter",
}

_POSITIVE = {"love", "great", "happy", "excited", "good", "amazing", "adoro", "gosto",
             "feliz", "óptimo", "otimo", "excelente", "bom"}

_NEGATIVE = {"hate", "bad", "sad", "angry", "terrible", "worried", "afraid", "odeio",
             "triste", "mau", "péssimo", "pessimo", "medo", "chato"}


def _is_interrogative(text: str) -> bool:
    from .speech_act import is_interrogative          # lazy: speech_act is a leaf module, sensitizer is not
    return is_interrogative(text)


def heuristic_extract(text: str) -> Extraction:
    """Deterministic fallback — never fails, no model needed."""
    words = re.findall(r"[\wÀ-ÿ'-]+", text)
    lower = [w.lower() for w in words]
    content_words = [w for w in lower if w not in _STOPWORDS and len(w) > 2]
    freq: dict = {}
    for w in content_words:
        freq[w] = freq.get(w, 0) + 1
    keywords = [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:6]]
    # entities: capitalised tokens; sentence-initial ones qualify too when they are
    # clearly not common sentence starters (e.g. "Zorblatt is my project")
    common_starters = {"this", "that", "there", "here", "today", "tomorrow", "yesterday",
                       "when", "what", "how", "why", "please", "also", "then", "now",
                       "hello", "thanks", "maybe", "sometimes"}
    entities, prev_end = [], True
    for w in words:
        if w[0].isupper() and w.lower() not in _STOPWORDS and w not in entities:
            if not prev_end or (len(w) >= 4 and w.lower() not in common_starters):
                entities.append(w)
        prev_end = w.endswith((".", "!", "?"))
    pos = sum(1 for w in lower if w in _POSITIVE)
    neg = sum(1 for w in lower if w in _NEGATIVE)
    valence = 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)
    intensity = min(1.0, (pos + neg) / 4.0)
    is_question = "?" in text
    out = Extraction(_DEFAULTS)
    out.update({
        "title": " ".join(words[:8])[:80],
        "summary": text[:200],
        "type": "message",
        "keywords": keywords,
        "entities": entities[:8],
        "topics": keywords[:3],
        "emotional_valence": valence,
        "emotional_intensity": intensity,
        "importance": min(1.0, 0.35 + len(content_words) / 120.0 + (0.1 if entities else 0.0)),
        "confidence": 0.6,
        "novelty": 0.5,
        "utility": 0.5,
        "intent": "question" if is_question else "statement",
        # 75.4: the fallback leg must CLASSIFY the act too — the echo-free rule (M6) and every question-only gate read
        # `conversation_act`, so a degraded router left them off and assistant/reflection echoes leaked into user-fact
        # answers. Same predicate the harness already trusts (speech_act.is_interrogative), no second phrase list.
        "conversation_act": "question" if _is_interrogative(text) else "statement",
        # P2 fallback leg for the router's freshness class (the constrained nano is the primary):
        # NARROW past-tense/history cues only, so present-value questions never leak to history
        # mode (Plan.txt G2 falsifier). PT+EN, mirroring every other heuristic field.
        "freshness": "historical" if re.search(
            r"\b(before|previously|used to|back then|antes|anteriormente|what was|qual era|como era|"
            r"when did i|quando (?:e que )?(?:mudei|disse|falei)|how long have|h[aá] quanto tempo|"
            r"desde quando|first time|primeira vez|history of|hist[oó]rico) ?", text, re.IGNORECASE,
        ) else "none",
        "extractor": "fallback",
    })
    return out

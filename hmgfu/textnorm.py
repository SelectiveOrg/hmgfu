"""Text normalisation shared by the deterministic detectors (Phase 75): accent-stripped lowercase and the salient
content words of a clause. One implementation — prospective memory (condition words) and the abstention coverage
signal (question words) must agree on what a "word" is."""
from __future__ import annotations

import re
import unicodedata
from typing import List

STOP = {"the", "a", "an", "and", "or", "of", "to", "for", "with", "that", "this", "when", "then", "will", "have", "has",
        "from", "into", "about", "after", "before", "some", "any", "there", "here", "just", "also", "very", "more",
        "para", "com", "que", "uma", "umas", "uns", "dos", "das", "nos", "nas", "pelo", "pela", "isso", "isto", "aqui",
        "quando", "depois", "antes", "assim", "logo", "sempre", "onde", "como", "mais", "muito", "ainda", "sobre",
        "replies", "reply", "responder", "responde", "arrive", "arrives", "chegar", "chega", "send", "sends", "enviar",
        "get", "gets", "back", "again", "me", "you", "your", "meu", "minha", "tell", "dizer", "falar", "talk", "talks",
        "what", "which", "who", "where", "when", "why", "how", "did", "does", "do", "was", "were", "is", "are", "am",
        "first", "last", "many", "much", "long", "ago", "time", "times", "day", "days", "week", "weeks", "month", "year",
        "qual", "quais", "quem", "onde", "quanto", "quantos", "quantas", "foi", "era", "vez", "vezes", "dia", "dias"}


def norm(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(ch) != "Mn")


def salient(text: str, min_len: int = 3) -> List[str]:
    """Content words of a clause, accent-stripped, stop words out, order kept, deduplicated."""
    out: List[str] = []
    for tok in re.findall(r"[a-z0-9]{%d,}" % min_len, norm(text)):
        if tok not in STOP and tok not in out:
            out.append(tok)
    return out

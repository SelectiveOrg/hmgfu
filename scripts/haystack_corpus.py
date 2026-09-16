"""Phase 76.1 — deterministic haystack filler for the scale-quality curve.

`filler(n, seed)` yields n distinct diary lines (PT/EN, dated across two years) whose vocabulary is DISJOINT from the
sealed relational corpus's people, places, projects, tools and preference values, so a filler line can never be a
legitimate answer — it is pure retrieval noise of realistic shape. Same seed → same lines (sha printed by `--check`).
Not sealed as an oracle (it carries no questions); the corpus it surrounds is `scripts/oracles/relational_v1.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import random
from typing import Iterator

_SUBJ_EN = ["the neighbour", "my cousin", "a colleague", "the landlord", "the plumber", "an old friend", "the mechanic",
            "my aunt", "the librarian", "the barber", "a client", "the courier"]
_SUBJ_PT = ["o vizinho", "a minha prima", "um colega", "o senhorio", "o canalizador", "um velho amigo", "o mecânico",
            "a minha tia", "a bibliotecária", "o barbeiro", "um cliente", "o estafeta"]
_ACT_EN = ["called about the fence", "brought soup", "fixed the gate", "asked for the ladder back", "recommended a film",
           "sent a postcard", "complained about the noise", "offered tomatoes", "borrowed the drill", "cancelled lunch",
           "repainted the bench", "lost the spare key", "watered my plants", "found the cat", "moved the bins"]
_ACT_PT = ["ligou por causa da vedação", "trouxe sopa", "arranjou o portão", "pediu a escada de volta", "recomendou um filme",
           "mandou um postal", "queixou-se do barulho", "ofereceu tomates", "pediu o berbequim", "cancelou o almoço",
           "pintou o banco", "perdeu a chave suplente", "regou as minhas plantas", "encontrou o gato", "mudou os caixotes"]
_TAIL_EN = ["", " before dinner", " in the rain", " again", " after work", " on the way home", " early", " late as usual"]
_TAIL_PT = ["", " antes do jantar", " à chuva", " outra vez", " depois do trabalho", " a caminho de casa", " cedo", " tarde como sempre"]
_SOLO_EN = ["Slept badly, too much coffee.", "Long queue at the post office.", "The bus was late by twenty minutes.",
            "Cleaned the oven at last.", "Rain all afternoon; read on the sofa.", "Bought new socks and a lamp.",
            "The printer needs toner.", "Watched the match, a draw.", "Tried the new bakery on the corner.",
            "Sorted the recycling.", "Power cut for an hour.", "Ironed shirts while listening to the radio."]
_SOLO_PT = ["Dormi mal, café a mais.", "Fila enorme nos correios.", "O autocarro atrasou-se vinte minutos.",
            "Limpei o forno finalmente.", "Chuva toda a tarde; li no sofá.", "Comprei meias novas e um candeeiro.",
            "A impressora precisa de toner.", "Vi o jogo, empate.", "Experimentei a padaria nova da esquina.",
            "Separei a reciclagem.", "Faltou a luz uma hora.", "Passei camisas a ouvir rádio."]


def filler(n: int, seed: int = 76) -> Iterator[tuple]:
    """(text, iso_timestamp) pairs; timestamps spread over 2024-09-01 … 2026-08-31, monotonic in generation order."""
    rng = random.Random(seed)
    seen = set()
    made = 0
    day = 0
    while made < n:
        pt = rng.random() < 0.5
        if rng.random() < 0.35:
            text = rng.choice(_SOLO_PT if pt else _SOLO_EN)
        else:
            s = rng.choice(_SUBJ_PT if pt else _SUBJ_EN); a = rng.choice(_ACT_PT if pt else _ACT_EN); t = rng.choice(_TAIL_PT if pt else _TAIL_EN)
            text = f"{s[0].upper()}{s[1:]} {a}{t}."
        text = f"{text} (nota {made})" if text in seen else text
        seen.add(text)
        day += rng.choice([0, 0, 1, 1, 1, 2])
        d = day % 730
        y, rem = 2024 + (8 + d // 30) // 12, (8 + d // 30) % 12
        ts = f"{y:04d}-{rem + 1:02d}-{(d % 28) + 1:02d}T{8 + (made % 12):02d}:{(made * 7) % 60:02d}:00+02:00"
        yield text, ts
        made += 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", type=int, default=1000, help="print the sha of the first N lines")
    args = ap.parse_args()
    h = hashlib.sha256()
    for text, ts in filler(args.check):
        h.update(f"{ts}|{text}\n".encode("utf-8"))
    print(f"haystack seed 76, first {args.check} lines sha {h.hexdigest()[:12]}")

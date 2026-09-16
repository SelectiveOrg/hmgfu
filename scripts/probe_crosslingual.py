"""Experiment 2 (external-reviewer suggestion): is cross-lingual recall actually broken, or only
ASSUMED broken? Measure it — don't defer bge-m3 on a feeling.

The one thing nomic-embed-text (English-centric) should choke on is store-in-Portuguese /
query-in-English EPISODIC recall. We have measured PT tool-routing (fixed by phrase-learning) and
PT directives (fixed by active-directive context) — but NEVER the raw cross-lingual embedding
similarity that all recall bottoms out on.

METHOD (rigorous — absolute cosine is meaningless without a floor and a ceiling for THIS embedder):
  - MATCH      cos(pt_i, en_i)            a PT statement vs its EN translation (should be HIGH)
  - X-FLOOR    cos(pt_i, en_j) i!=j       PT vs an UNRELATED EN statement (the random floor)
  - EN-CEIL    cos(en_i, en_i_paraphrase) EN paraphrase vs EN paraphrase (same-language ceiling)
The VERDICT is the SEPARATION, not the absolute number: if MATCH sits up near EN-CEIL and well
above X-FLOOR, nomic carries cross-lingual meaning → bge-m3 is a single-purpose upgrade (wormhole
surfacing only). If MATCH collapses toward X-FLOOR, nomic cannot tell a PT sentence from its EN
translation apart from noise → the migration is load-bearing and earns its own phase.

NO tuning, NO graph changes — pure embedder measurement. Uses the LIVE production embedder
(config.EMBED_MODEL via engine.embed). Run:
  .venv/Scripts/python scripts/probe_crosslingual.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config, fu_math          # noqa: E402
from hmgfu.chat import HMGFuEngine          # noqa: E402
from _bench_paths import throwaway_db       # noqa: E402

# realistic personal-memory statements (the actual use case: stored PT, later queried EN).
# (pt, en, en_paraphrase) — en_paraphrase is a DIFFERENT English wording of the SAME fact, to
# measure the same-language ceiling for THIS embedder.
PAIRS = [
    ("O meu gato chama-se Nimbus.",
     "My cat is named Nimbus.",
     "The name of my cat is Nimbus."),
    ("Trabalho como engenheiro de backend numa startup fintech.",
     "I work as a backend engineer at a fintech startup.",
     "My job is backend engineering at a fintech company."),
    ("O meu filho Leo começou o 3º ano na escola primária Lincoln.",
     "My son Leo started 3rd grade at Lincoln elementary school.",
     "Leo, my boy, is now in third grade at Lincoln elementary."),
    ("A minha linguagem de programação favorita é Python.",
     "My favorite programming language is Python.",
     "I like Python best out of all programming languages."),
    ("Deixei de beber café e passei a chá verde no mês passado.",
     "I quit coffee and switched to green tea last month.",
     "Last month I stopped drinking coffee and moved to green tea."),
    ("O meu objetivo este ano é correr uma maratona em menos de quatro horas.",
     "My goal this year is to run a marathon under four hours.",
     "This year I want to finish a marathon in less than 4 hours."),
    ("Estou a aprender a tocar guitarra acústica aos fins de semana.",
     "I'm learning to play acoustic guitar on weekends.",
     "On weekends I've been picking up acoustic guitar."),
    ("Mudei de banco para ter melhores taxas de juro na poupança.",
     "I switched banks for better savings interest rates.",
     "I moved to a new bank because its savings rates are higher."),
    ("A professora do Leo disse que ele precisa de ajuda com a leitura.",
     "Leo's teacher said he needs help with reading.",
     "According to his teacher, Leo struggles with reading comprehension."),
    ("Reservei voos para visitar os meus pais em dezembro.",
     "I booked flights to visit my parents in December.",
     "In December I'm flying out to see my parents."),
    ("Já não aguento comida picante como antigamente.",
     "I can't handle spicy food like I used to.",
     "Spicy food doesn't sit well with me anymore."),
    ("O meu colega Daniel emprestou-me um livro de xadrez.",
     "My coworker Daniel lent me a chess book.",
     "Daniel from work gave me a chess book to borrow."),
]


def main() -> int:
    DB = throwaway_db("crosslingual_probe.db")
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1
    print(f"EMBEDDER = {config.EMBED_MODEL}\n")

    pt = [engine.embed(p) for p, _, _ in PAIRS]
    en = [engine.embed(e) for _, e, _ in PAIRS]
    en2 = [engine.embed(e2) for _, _, e2 in PAIRS]

    match = [fu_math.cosine(pt[i], en[i]) for i in range(len(PAIRS))]              # PT_i vs EN_i
    en_ceil = [fu_math.cosine(en[i], en2[i]) for i in range(len(PAIRS))]           # EN_i vs EN_i'
    x_floor = [fu_math.cosine(pt[i], en[j])                                        # PT_i vs EN_j (i≠j)
               for i in range(len(PAIRS)) for j in range(len(PAIRS)) if i != j]

    def summ(xs):
        xs = sorted(xs)
        n = len(xs)
        mean = sum(xs) / n
        return mean, xs[0], xs[-1], xs[n // 2]

    print(f"{'band':<34} {'mean':>6} {'min':>6} {'max':>6} {'median':>7}  n")
    for label, xs in (("MATCH  cos(PT_i, EN_i)  [want HIGH]", match),
                      ("EN-CEIL cos(EN_i, EN_i') [ceiling]", en_ceil),
                      ("X-FLOOR cos(PT_i, EN_j)  [floor]", x_floor)):
        m, lo, hi, med = summ(xs)
        print(f"{label:<34} {m:>6.3f} {lo:>6.3f} {hi:>6.3f} {med:>7.3f}  {len(xs)}")

    m_match = sum(match) / len(match)
    m_ceil = sum(en_ceil) / len(en_ceil)
    m_floor = sum(x_floor) / len(x_floor)
    # separation: how far MATCH sits above the unrelated floor, as a fraction of the ceiling-to-floor
    # span this embedder actually produces (normalizes away the embedder's absolute scale).
    span = m_ceil - m_floor
    retained = (m_match - m_floor) / span if span > 1e-9 else 0.0
    print("\n=== VERDICT ===")
    print(f"  cross-lingual MATCH mean = {m_match:.3f}   EN ceiling = {m_ceil:.3f}   "
          f"unrelated floor = {m_floor:.3f}")
    print(f"  cross-lingual retention  = {retained:.0%} of the same-language paraphrase span")
    print(f"  per-pair MATCH worst      = {min(match):.3f} (pair: {PAIRS[match.index(min(match))][1]!r})")
    if retained >= 0.75 and min(match) >= 0.55:
        print("  → nomic CARRIES cross-lingual meaning. bge-m3 = single-purpose upgrade "
              "(wormhole surfacing), judge on its own merit — migration NOT load-bearing for recall.")
    elif retained <= 0.45 or min(match) <= 0.40:
        print("  → nomic COLLAPSES cross-lingual meaning toward the noise floor. bge-m3 migration is "
              "LOAD-BEARING for PT-store/EN-query recall → schedule as its own phase with real proof.")
    else:
        print("  → MIXED: partial cross-lingual retention. bge-m3 would help but isn't strictly "
              "load-bearing; decide against the wormhole-surfacing benefit too.")

    engine.graph.close()
    engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

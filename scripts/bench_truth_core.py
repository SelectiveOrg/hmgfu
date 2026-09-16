"""Phase 82.5 — the truth/execution core under an ADVERSARIAL deterministic suite (Codex review 2, P1 gates).

Families (every case deterministic, no model, throwaway DBs under scratch/, versioned output):
  A  scoped retraction — the same value held by several families (user name, sibling, dog, cat); a named negation in
     ONE family must retire that family's value only; canonical ≡ assertions afterwards.                 gate: 0 undue changes
  B  correction sequences — a slot revised 2–4 times, other slots set in between; only the revised slot moves; the
     replaced values stay in history (never deleted).                                                     gate: 0 undue changes
  C  provenance — every write on the agent-like path (apply_all + link_source) yields an assertion with an episode and,
     when the value is verbatim, offsets that slice the message to the value.                             gate: 100 % linked
  D  fault injection — an exception between the canonical and assertion writes at EVERY step of each sequence; after it
     the store must show no half revision (reopen → reconcile repairs nothing; canonical ≡ assertions) and the same
     message re-applies cleanly.                                                                            gate: 100 % recovered
  E  receipts — wrong directory, changed content, missing hash, wrong widget, read-for-write, plus the accepting cases.
                                                                                                           gate: 100 % right
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from hmgfu.fact_reconcile import provenance  # noqa: E402
from hmgfu.facts import FactStore  # noqa: E402
from hmgfu.receipts import verify_step  # noqa: E402
from hmgfu.slots import base_slot  # noqa: E402

NAMES_EN = ["Bento", "Rosa", "Kelvin", "Amina", "Joel", "Nala"]
NAMES_PT = ["Bento", "Rosa", "Kelvin", "Amina", "Joel", "Nala"]
FAMILIES = {  # family → (EN setter, PT setter) for a value V
    "identity.name": ("My name is {v}.", "Chamo-me {v}."),
    "family.sister_name": ("My sister is called {v}.", "A minha irmã chama-se {v}."),
    "family.brother_name": ("My brother's name is {v}.", "O meu irmão chama-se {v}."),
    "pet.dog.name": ("My dog is {v}.", "O meu cão chama-se {v}."),
    "pet.cat.name": ("My cat is {v}.", "O meu gato chama-se {v}."),
}
NEGATE = {"pet.dog.name": ("My dog is {w}, not {v}.", "O meu cão é o {w}, não o {v}."),
          "pet.cat.name": ("My cat is {w}, not {v}.", "O meu gato é o {w}, não o {v}."),
          "identity.name": ("My name is {w}, not {v}.", "Chamo-me {w}, não {v}.")}
COLOURS = ["amber", "teal", "indigo", "olive"]
CITIES = ["Tete", "Pemba", "Quelimane", "Nampula"]


def fresh(tag: str) -> FactStore:
    os.makedirs(SCRATCH, exist_ok=True)
    folder = tempfile.mkdtemp(prefix=f"truthcore_{tag}_", dir=SCRATCH)
    return FactStore(os.path.join(folder, "f.db"))


def canon(st) -> dict:
    return {r["key"]: r["value"] for r in st.active()}


def views_agree(st) -> bool:
    """Every canonical (base slot, value) has an active assertion and every active assertion has a canonical row."""
    c = {(base_slot(k), (v or "").strip().lower()) for k, v in canon(st).items() if v}
    a = {(x["relation"], (x["value"] or "").strip().lower()) for x in st.assertions.active()}
    return c == a


def family_a() -> list:
    rows = []
    fams = list(FAMILIES)
    for li, lang in enumerate(("en", "pt")):
        for v in (NAMES_EN if lang == "en" else NAMES_PT):
            for neg_fam, (neg_en, neg_pt) in NEGATE.items():
                others = [f for f in fams if f != neg_fam]
                for keep in others:                       # one other family shares the value
                    st = fresh("a")
                    st.apply_all(FAMILIES[keep][li].format(v=v), "user_explicit")
                    st.apply_all(FAMILIES[neg_fam][li].format(v=v), "user_explicit")
                    before = canon(st)
                    w = "Teca" if v != "Teca" else "Kika"
                    st.apply_all((neg_en if lang == "en" else neg_pt).format(w=w, v=v), "user_explicit")
                    after = canon(st)
                    ok = after.get(keep) == v and after.get(neg_fam) == w and views_agree(st)
                    undue = [k for k in before if k != neg_fam and after.get(k) != before[k]]
                    rows.append({"fam": "A", "id": f"A-{lang}-{v}-{neg_fam}-{keep}", "ok": ok and not undue, "undue": undue,
                                 "detail": None if ok and not undue else {"before": before, "after": after, "agree": views_agree(st)}})
    return rows


def family_b() -> list:
    rows = []
    seqs = []
    for c1 in COLOURS:
        for c2 in COLOURS:
            if c1 != c2:
                seqs.append(("pref.color", [f"My favourite colour is {c1}.", "I live in Tete.", f"Actually my favourite colour is {c2}, not {c1}.",
                                            "My dog is Rex.", f"My favourite colour is {c2}."], c2))
    for a in CITIES:
        for b in CITIES:
            if a != b:
                seqs.append(("identity.location", [f"I live in {a}.", "My name is Ana.", f"I moved to {b}.", "My cat is Luna."], b))
                seqs.append(("identity.location", [f"Moro em {a}.", "Chamo-me Ana.", f"Mudei-me para {b}.", "O meu gato chama-se Luna."], b))
    for slot, msgs, final in seqs:
        st = fresh("b")
        snapshots = []
        for m in msgs:
            st.apply_all(m, "user_explicit"); snapshots.append(canon(st))
        undue = []
        for i in range(1, len(snapshots)):
            prev, cur = snapshots[i - 1], snapshots[i]
            for k in prev:
                if k != slot and k in cur and cur[k] != prev[k]:
                    undue.append((i, k))
        hist_vals = [h["value"] for h in st.assertions.history("user", slot)]
        ok = canon(st).get(slot) == final and not undue and views_agree(st) and len(hist_vals) >= 2
        rows.append({"fam": "B", "id": f"B-{slot}-{msgs[0][:24]}-{final}", "ok": ok, "undue": undue,
                     "detail": None if ok else {"final": canon(st).get(slot), "hist": hist_vals, "agree": views_agree(st)}})
    return rows


def family_c() -> list:
    rows = []
    msgs = ["My name is Marta Sitoe and my dog is Simba.", "Chamo-me Élio Mabunda e o meu gato chama-se Pipoca.",
            "I live in Tete and I work as an electrician.", "A minha cor favorita é o índigo.", "My sister is Zara.",
            "My favourite drink is rooibos tea.", "O meu carro é um Toyota Hilux.", "My lucky number is 27.",
            "I moved to Pemba.", "Trabalho na Vodacom.", "My favourite colour is amber.", "My brother's name is Kelvin."]
    for n in range(1, 13):
        st = fresh("c")
        for i, m in enumerate(msgs[:n]):
            for ch in st.apply_all(m, "user_explicit"):
                if ch.get("key"):
                    st.link_source(ch["key"], f"pt-{i:03d}")
        rep = provenance(st)
        span_ok = True
        for a in st.assertions.active():
            if a["span_start"] is not None:
                txt = a["source_span"] or ""
                if txt[a["span_start"]:a["span_end"]].lower() != (a["value"] or "").lower():
                    span_ok = False
        ok = rep["active"] > 0 and rep["with_episode"] == rep["active"] and span_ok
        rows.append({"fam": "C", "id": f"C-{n}", "ok": ok, "detail": None if ok else rep})
    return rows


def family_d() -> list:
    rows = []
    seqs = [["My name is Ana.", "My favourite colour is amber.", "My dog is Rex.", "My dog is Thor, not Rex.", "I live in Tete."],
            ["Chamo-me Bento.", "O meu cão chama-se Bento.", "O meu cão é o Teca, não o Bento.", "Moro em Pemba."],
            ["My sister is Rosa.", "My sister is Dércia, not Rosa.", "My cat is Luna.", "My favourite drink is espresso."],
            ["I live in Tete.", "I moved to Pemba.", "I moved to Nampula.", "My name is Joel."]]
    for si, seq in enumerate(seqs):
        for crash_at in range(len(seq)):
            for where in ("assert", "retract"):
                st = fresh("d")
                path = st._db.execute("PRAGMA database_list").fetchone()[2]
                for i, m in enumerate(seq[:crash_at]):
                    st.apply_all(m, "user_explicit")
                before = canon(st)
                target = st.assertions.assert_ if where == "assert" else st.assertions.retract
                def boom(*a, **k):
                    raise RuntimeError("injected")
                setattr(st.assertions, "assert_" if where == "assert" else "retract", boom)
                raised = False
                try:
                    st.apply_all(seq[crash_at], "user_explicit")
                except RuntimeError:
                    raised = True
                setattr(st.assertions, "assert_" if where == "assert" else "retract", target)
                mid = canon(st)
                st._db.close()
                st2 = FactStore(path)
                rep = st2.reconcile_report
                consistent = views_agree(st2) and rep == {"backfilled": 0, "orphaned": 0, "relinked": 0}
                st2.apply_all(seq[crash_at], "user_explicit")
                st3 = FactStore(path)
                ok = consistent and views_agree(st3) and (not raised or mid == before)
                rows.append({"fam": "D", "id": f"D-{si}-{crash_at}-{where}", "ok": ok, "raised": raised,
                             "detail": None if ok else {"before": before, "mid": mid, "reconcile": rep, "agree": views_agree(st3)}})
    return rows


def family_e() -> list:
    rows = []
    names = ["write_file", "create_widget", "update_widget", "bash", "read_file", "list_files"]
    ws = tempfile.mkdtemp(prefix="truthcore_e_", dir=SCRATCH)
    def sha(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    def rec(rid, rel, tool="write_file", with_hash=True):
        e = {"path": rel}
        if with_hash:
            e["sha256"] = sha(os.path.join(ws, rel))
        return {"id": rid, "tool": tool, "status": "ok", "consumed_by": None, "args": {"path": rel}, "effects": {"files": [e]}}
    dirs = ["", "new/", "old/", "docs/notes/", "out/2026/"]
    for d in dirs:
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    files = ["report.md", "notes.txt", "data.csv", "index.html"]
    for f in files:
        for d in dirs:
            open(os.path.join(ws, d, f), "w").write(f"{d}{f}")
    for f in files:
        for d_req in dirs:
            for d_got in dirs:
                req = f"{d_req}{f}"; got = f"{d_got}{f}"
                ok, _ev, _m = verify_step(f"write_file: {req}", [rec("r", got)], ws, names)
                expect = (d_req == d_got) or (d_req == "")
                rows.append({"fam": "E", "id": f"E-path-{req}-vs-{got}", "ok": ok == expect, "detail": None if ok == expect else (ok, expect)})
            got = f"{d_req}{f}"
            r = rec("r", got); open(os.path.join(ws, got), "a").write(" changed")
            ok = verify_step(f"write_file: {got}", [r], ws, names)[0]
            rows.append({"fam": "E", "id": f"E-changed-{got}", "ok": ok is False, "detail": None if not ok else "accepted changed content"})
            ok = verify_step(f"write_file: {got}", [rec("r", got, with_hash=False)], ws, names)[0]
            rows.append({"fam": "E", "id": f"E-nohash-{got}", "ok": ok is False, "detail": None if not ok else "accepted a receipt without hash"})
            ok = verify_step(f"write_file: {got}", [rec("r", got, tool="read_file")], ws, names)[0]
            rows.append({"fam": "E", "id": f"E-read-{got}", "ok": ok is False, "detail": None if not ok else "a read proved a write"})
    for want, have, expect in [("Links", "Links", True), ("Budget", "Links", False), ("links", "Links", True), ("Notas", "Links", False)]:
        w = {"id": "w", "tool": "create_widget", "status": "ok", "consumed_by": None, "args": {"title": have}, "effects": {"widgets": [f"widget-{have.lower()}"]}}
        ok = verify_step(f"create_widget: {want}", [w], ws, names)[0]
        rows.append({"fam": "E", "id": f"E-widget-{want}-vs-{have}", "ok": ok == expect, "detail": None if ok == expect else (ok, expect)})
    shutil.rmtree(ws, ignore_errors=True)
    return rows


def main() -> int:
    fams = {"A": family_a(), "B": family_b(), "C": family_c(), "D": family_d(), "E": family_e()}
    total = sum(len(v) for v in fams.values())
    summary, all_ok = {}, True
    for k, rows in fams.items():
        n_ok = sum(1 for r in rows if r["ok"])
        summary[k] = {"n": len(rows), "ok": n_ok}
        all_ok = all_ok and n_ok == len(rows)
        print(f"  {k}: {n_ok}/{len(rows)}")
        for r in rows:
            if not r["ok"]:
                print(f"    [FAIL] {r['id']} {r.get('detail')}")
    undue = sum(len(r.get("undue") or []) for r in fams["A"] + fams["B"])
    gates = {"cases": total, "undue_changes": undue,
             "provenance_100": summary["C"]["ok"] == summary["C"]["n"],
             "injections_recovered_100": summary["D"]["ok"] == summary["D"]["n"],
             "receipts_100": summary["E"]["ok"] == summary["E"]["n"],
             "scoped_retraction_100": summary["A"]["ok"] == summary["A"]["n"], "sequences_100": summary["B"]["ok"] == summary["B"]["n"]}
    print(f"\nTRUTH CORE n={total} · undue changes {undue} · " + " · ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in gates.items() if k not in ("cases", "undue_changes")))
    print("versioned:", write_versioned("truth_core", {"summary": summary, "gates": gates,
                                                      "failures": [r for rows in fams.values() for r in rows if not r["ok"]]}))
    return 0 if all_ok and undue == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

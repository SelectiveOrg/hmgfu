"""Phase 68 live diagnostics. Local models, synthetic isolated data, incremental evidence.

Run --mode memory|actions|retrieval. Advisory grader/learning/dreams are disabled
to isolate the reviewed write/read and execution contracts. No production engine
is created. Public/network/shell/skill side effects are blocked by this harness.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from hmgfu import config, fu_math
from hmgfu.agent import AgentEngine
from hmgfu.models import MemoryPoint, QueryPoint
from hmgfu.retrieve import retrieve_memory
from hmgfu.settings import DEFAULTS

config.OLLAMA_TIMEOUT_S = 60.0
SCRATCH = ROOT / "scratch"
SCRATCH.mkdir(exist_ok=True)
RUN = Path(tempfile.mkdtemp(prefix="phase68_live_", dir=SCRATCH))
ROWS = []
RESULT = {"metadata":{"scratch":str(RUN), "production_written":False,
                      "timeout_s":60, "limitation":"grader, learning, dreams disabled; external tools blocked"}, "turns":ROWS}
OUT = None


def save():
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(label, window=3):
    folder = RUN / label
    folder.mkdir()
    dbpath = folder / "agent.db"
    with sqlite3.connect(f"file:{Path(config.DB_PATH).resolve().as_posix()}?mode=ro", uri=True) as src:
        inherited = {k:json.loads(v) for k,v in src.execute("SELECT key,value FROM settings") if k in DEFAULTS
                     and (k.endswith("_model") or k.endswith("_provider"))}
    settings = {**inherited, "grader_enabled":False,"tool_points_enabled":False,"learning_enabled":False,
                "nano_sensitizer_enabled":True, "nano_dream_enabled":False, "mini_dream_every_n_turns":0,
                "full_dream_every_n_turns":0,"regulator_enabled":False,"chat_correction_signal":False,
                "observe_first_n":0,"thinking_mode":"off","workspace_dir":str(folder),
                "recent_turns_window":window,"agent_max_iterations":4}
    with sqlite3.connect(dbpath) as dst:
        dst.execute("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)")
        dst.executemany("INSERT INTO settings VALUES(?,?)",[(k,json.dumps(v)) for k,v in settings.items()])
    RESULT["metadata"]["models"] = {k:v for k,v in settings.items() if k.endswith("_model")}
    return folder, dbpath


def open_engine(dbpath, action=False):
    e = AgentEngine(db_path=str(dbpath))
    allowed = {"memory_search","memory_timeline","memory_zoom","plan_task","update_plan",
               "create_widget","update_widget","remove_widget","read_file","write_file"}
    dispatch = e.tools.execute_tool
    def safe_dispatch(name,args):
        if name not in allowed:
            return json.dumps({"blocked":True,"reason":"phase68 isolated diagnostic disallows external/shell/skill tools"})
        if name in ("read_file","write_file"):
            workspace = dbpath.parent.resolve()
            target = (workspace / str(args.get("path") or "")).resolve()
            if not target.is_relative_to(workspace):
                return json.dumps({"blocked":True,"reason":"phase68 workspace boundary"})
        return dispatch(name,args)
    e.tools.execute_tool = safe_dispatch
    e.tools.schemas = {k:v for k,v in e.tools.schemas.items() if k in allowed}
    if action:
        e.settings.set("tool_points_enabled",True)
        from hmgfu.toolsys import sync_tool_points
        sync_tool_points(e.tools,e)
    return e


def close(e):
    e.graph.close()
    e.client.close()
    for key in ("facts","directives","settings","sessions","session_plans","learned_params","route_memory"):
        obj = getattr(e,key,None)
        conn = getattr(obj,"_db",None)
        if conn:
            conn.close()


def talk(e,sid,label,text,expected=None):
    start=time.perf_counter()
    before={f["key"]:f["value"] for f in e.facts.active()}
    try:
        result=e.agent_chat(text,explicit=True,session_id=sid)
        after={f["key"]:f["value"] for f in e.facts.active()}
        history=e.sessions.history(sid,limit=1)
        row={"case":label,"message":text,"reply":result.get("response"),"before":before,"facts":after,
             "context":result.get("injected_context"),"retrieved":result.get("retrieved"),
             "tools":result.get("tool_trace"),"plan":e.session_plans.get(sid),
             "forced_finalization":result.get("forced_finalization"),"metadata":history,
             "seconds":round(time.perf_counter()-start,2)}
        if expected is not None:
            row["expected_subset"]=expected
            row["write_check"]=all(after.get(k)==v for k,v in expected.items())
    except Exception as exc:
        row={"case":label,"message":text,"error":repr(exc),"seconds":round(time.perf_counter()-start,2)}
    ROWS.append(row)
    save()
    print(f"{label} {row['seconds']}s check={row.get('write_check')} facts={row.get('facts')} reply={str(row.get('reply',row.get('error')))[:240]}",flush=True)
    return row


def memory():
    folder,db=prepare("conversation")
    e=open_engine(db)
    sid=e.sessions.create_session("Synthetic memory audit")["id"]
    talk(e,sid,"multi_en","By the way, my name is Nadia Costa, I live in Quelimane, and my dog is Bento.",
         {"identity.name":"Nadia Costa","identity.location":"Quelimane","pet.name":"Bento"})
    talk(e,sid,"multi_pt","A minha cor favorita é âmbar e a minha bebida favorita é chá de hibisco.",
         {"pref.color":"âmbar","pref.drink":"chá de hibisco"})
    talk(e,sid,"polite_remember","Could you remember that my favorite music is marrabenta?",{"pref.music":"marrabenta"})
    close(e)
    e=open_engine(db)
    sid2=e.sessions.create_session("After restart, no prior chat window")["id"]
    talk(e,sid2,"restart_new_session","Qual é o meu nome, onde moro, como se chama o meu cão e quais são a minha cor, bebida e música favoritas?")
    talk(e,sid2,"correct_two","Actually I live in Lichinga now, and my dog is Teca, not Bento.",{"identity.location":"Lichinga","pet.name":"Teca"})
    talk(e,sid2,"two_pets","My cat is Mica and my dog is Teca.")
    talk(e,sid2,"clear_dog","I no longer have a dog. I still have my cat Mica.",{"pet.name":None})
    close(e)
    e=open_engine(db)
    sid3=e.sessions.create_session("Recall after retraction")["id"]
    talk(e,sid3,"clear_recall_new_session","Do I currently have a dog? What is the name of my cat?")
    talk(e,sid3,"mixed_question","I live in Chimoio. What do you know about that city?",{"identity.location":"Chimoio"})
    talk(e,sid3,"quoted_identity",'For a dialogue I am writing, my friend says "my name is Oscar". That is his name, not mine.',{"identity.name":"Nadia Costa"})
    talk(e,sid3,"hypothetical","If my favorite color is violet, then use that in an example; this is hypothetical.")
    talk(e,sid3,"same_turn_revision","My favorite color is red, but my favorite color is blue. The second clause corrects the first.",{"pref.color":"blue"})
    close(e)


def actions():
    for window in (3,0):
        _,db=prepare(f"proposal_w{window}",window)
        e=open_engine(db,True)
        e.facts.apply_all("Here is the link for my car location: https://example.test/car-audit", "user_explicit")
        sid=e.sessions.create_session("Proposal and approval")["id"]
        talk(e,sid,f"proposal_w{window}","Talvez pudesses criar um widget para guardar o link do meu carro. Espera pela minha confirmação.")
        talk(e,sid,f"approve_w{window}","Sim, podes avançar.")
        # Same slot type, explicitly a DIFFERENT subject: must not replace the car link.
        talk(e,sid,f"unrelated_link_w{window}","Here is the new recipe: https://example.test/soup",{"asset.car_location_link":"https://example.test/car-audit"})
        close(e)
    folder,db=prepare("restart_plan")
    e=open_engine(db,True)
    sid=e.sessions.create_session("Verified file plan")["id"]
    talk(e,sid,"build_files","Use plan_task and write_file to create audit_one.txt and audit_two.txt, each with the exact content MEMORY-68. Verify both files before declaring completion.")
    actual={p.name:p.read_text(encoding="utf-8") for p in folder.glob("audit_*.txt")}
    RESULT["file_artifacts_before_restart"]=actual
    close(e)
    e=open_engine(db,True)
    talk(e,sid,"stop_after_restart","Stop. Cancel any unfinished work. Do not write any more files.")
    RESULT["file_artifacts_after_cancel"]={p.name:p.read_text(encoding="utf-8") for p in folder.glob("audit_*.txt")}
    close(e)
    save()


def retrieval():
    _,db=prepare("gold_retrieval")
    e=open_engine(db)
    e.settings.set("nano_sensitizer_enabled",False)
    e._apply_nano_gates()
    corpus=[
      ("storage","The emergency spare key is inside the yellow tin above the refrigerator.","Where can I find the emergency spare key?"),
      ("medicine","My cat Mica takes Vetalin every evening. My dog Teca takes no medicine.","What medication does Mica take?"),
      ("deadline","Project Jacaranda must be delivered on 18 November, before the warehouse audit.","When is the Jacaranda delivery deadline?"),
      ("reason","We chose the eastern warehouse because the western road floods during heavy rain.","Why did we choose the eastern warehouse?"),
      ("preference","At work I prefer Rust for embedded devices, but at home I teach Python to beginners.","Which language do I use to teach beginners at home?"),
      ("diet","For next week's workshop, Bruno needs a peanut-free meal; Celina is vegetarian.","Who needs a meal without peanuts at the workshop?"),
      ("route","The delivery truck must go through Nhamatanda because the main bridge is under repair.","Por onde deve passar o camião de entregas?"),
      ("location","The receipts for the irrigation project are in the orange folder marked JAC-14.","Onde estão os recibos do projeto de irrigação?"),
      ("codeword","The observatory access phrase is SILVER-IBIS-84; the library phrase is COPPER-HERON-29.","What is the observatory access phrase?"),
      ("contact","For the solar-pump installation, contact engineer Dália Mendes, not the seed supplier.","Quem devo contactar para instalar a bomba solar?"),
      ("schedule","My guitar class meets on Thursday evenings; my pottery class meets Saturday mornings.","When is my pottery class?"),
      ("constraint","The garden irrigation timer must remain offline because there is no mobile coverage there.","Why must the garden irrigation timer work offline?"),
      ("invoice","Invoice BEX-472 is for the water filters; invoice BEX-427 is for the solar batteries.","Which invoice covers the solar batteries?"),
      ("allergy","My brother Abel is allergic to cashews; I am allergic to shellfish.","What am I allergic to?"),
      ("parking","When visiting the clinic, park behind the bakery. The front gate is reserved for ambulances.","Where should I park when I visit the clinic?"),
      ("handoff","If Leonor is unavailable, send the quarterly inventory to Samuel Nunes.","Who receives inventory if Leonor is absent?"),
      ("travel","Na viagem a Pemba vou levar a mala verde; a mala cinzenta ficou com o meu primo.","Which suitcase will I take to Pemba?"),
      ("reading","O livro que quero reler nas férias é Terra Sonâmbula; o clube está a ler outro livro.","What book do I want to reread during vacation?"),
      ("equipment","The blue pump uses a 12 mm hose; the red pump needs an 18 mm hose.","What hose size does the red pump need?"),
      ("backup","Our accounting backup is stored on drive T: under monthly_exports, not in the shared cloud folder.","Where is the accounting backup stored?"),
    ]
    gold={}
    for label,text,q in corpus:
        p=e.ingest(text,source="user_explicit",mtype="fact")
        gold[label]=p.id
    # Similar distractors are independent real user statements, not injected answers.
    for i in range(30):
        e.ingest(f"The inventory note for warehouse sector {i+20} describes a blue equipment cabinet, a delivery schedule and maintenance receipts.",source="user",mtype="fact")
    rows=[]
    for label,text,qtext in corpus:
        emb=e.embed(qtext)
        q=QueryPoint(text=qtext,embedding=emb,conversation_act="question",needs_memory=True)
        from hmgfu.taxonomy import node_class
        pool=[p for p in e.graph.active_points() if node_class(p) not in ("skill","tool","directive","session") and "_question" not in p.keywords]
        started=time.perf_counter()
        fu=retrieve_memory(q,e.graph,limit=10)
        fu_ms=(time.perf_counter()-started)*1000
        cos=sorted(pool,key=lambda p:-fu_math.cosine(emb,p.embedding))[:10]
        entry={"id":label,"gold_id":gold[label],"query":qtext,"fu_ms":round(fu_ms,2)}
        for arm,ids in (("fu",[r.point.id for r in fu]),("cosine",[p.id for p in cos])):
            entry[arm]={"ids":ids,"rank":ids.index(gold[label])+1 if gold[label] in ids else None}
        rows.append(entry)
        print("RETRIEVAL",label,entry["fu"]["rank"],entry["cosine"]["rank"],flush=True)
    summary={}
    for arm in ("fu","cosine"):
        ranks=[r[arm]["rank"] for r in rows]
        summary[arm]={"hit_at_1":sum(r==1 for r in ranks),"hit_at_5":sum(r is not None and r<=5 for r in ranks),
                      "hit_at_10":sum(r is not None for r in ranks),"mrr":sum(1/r if r else 0 for r in ranks)/len(ranks)}
    RESULT["retrieval"]={"attempted_corpus_size":50,"actual_graph_points":len(e.graph.points),"gold_unique_points":len(set(gold.values())),"questions":20,"corpus":corpus,"scoring":"gold point IDs, no canonical injection; same eligible pool; query embedding only; heuristic ingest",
                         "limitation":"new synthetic diagnostic, single sample, no external generalization claim", "summary":summary,"rows":rows}
    save()
    close(e)


def main():
    global OUT
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("memory","actions","retrieval"),required=True)
    args=ap.parse_args()
    OUT=ROOT/"outputs"/f"phase68_live_{args.mode}.json"
    start=time.perf_counter()
    try:
        {"memory":memory,"actions":actions,"retrieval":retrieval}[args.mode]()
    finally:
        RESULT["metadata"]["elapsed_s"]=round(time.perf_counter()-start,2)
        save()
    print("SAVED",OUT,flush=True)


if __name__=="__main__":
    main()

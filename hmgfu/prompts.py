"""Agent prompt constants (extracted from agent.py at the 400-line ceiling, Phase 62)."""

from __future__ import annotations

_AGENT_PROMPT_EXTRA = """

You have real tools — use them when they help. In particular:
- For any MULTI-STEP task (a build, research, several actions in sequence), your FIRST tool call
  must be plan_task declaring the steps — the user sees a live progress tracker — and you must
  call update_plan as each step completes. Single-question turns need no plan.
- You CAN put live widgets on the user's canvas with create_widget (types: metric, table, weather,
  plan, diff, note, timeline, memory-hex, memory-graph, and app). When the user asks you to show,
  display, chart, track, or "make a widget" for something, actually CALL create_widget — do not say
  you cannot. Update or remove them with update_widget / remove_widget.
- A page or app you BUILT goes on the canvas as type "app": write the file first, then
  create_widget(type="app", props={"file": "<the file you wrote>"}). There is no widget type per
  subject — no "timer", no "game", no "html". When a type is refused, the error lists the real ones.
- memory_search searches your relational memory; the memory context above is only a PARTIAL view,
  so if the user explicitly asks you to search/check memory, call memory_search.
- "What do you know about me?" and other identity questions: answer FIRST from the "User identity
  and stable preferences" lines in your memory context (they are current and confirmed); call
  memory_search, with a real query, only for what is NOT listed there. Never reply with an apology
  or "I am searching" in place of the facts you already have.
- Search arguments must be SPECIFIC, never the user's sentence: "tell me todays weather" → query
  "<the user's city> weather <today's date>"; "news" → "<topic> <place> news". Use the user's identity
  lines and the runtime clock for the place and the date.
- After a search, state ONLY values that appear in the results (temperature, prices, dates). If the
  results do not contain the answer, say so — never invent a number.
- Do NOT create widgets, files or skills unless the user asked for one; answer the question instead
  and offer to build it.
- NEVER end a reply with a promise ("I'll take a look…", "let me check…"). Either do it now with tools, or
  PROPOSE it: call plan_task with status="proposed" and ask "Shall I go ahead?". Side-effecting or
  multi-step work suggested by the user ("maybe you could…") is proposed first; an explicit order
  ("create…", "write…") is executed.
- Never claim "I've updated/created/saved" unless a tool result or a memory update in THIS turn confirms it.
- bash runs commands; create_skill writes new reusable skills.
- When you BUILD something (a page, app, script), SAVE it with write_file — never paste the
  full source only into the chat. Built web files are served to the user automatically.
Alongside EVERY tool call, include one short sentence of reasoning in your message content
(why this tool now) — the user watches your execution flow live.
After tool results arrive, continue and give the user a final answer. Never call the same tool with
the same arguments twice; if a tool fails twice, stop using it and answer with what you have."""



WORKSPACE_LISTING_CAP = 40      # top-level entries shown in the block; the rest is one honest count


def _listing(path: str) -> str:
    """95.16: the top-level entries, from the same native read the model would call (list_files)."""
    from .tool_builtins import workspace_names
    names = workspace_names(path)
    if not names:
        return ""
    shown, more = names[:WORKSPACE_LISTING_CAP], len(names) - WORKSPACE_LISTING_CAP
    return "Top-level entries: " + ", ".join(shown) + (f" (+{more} more)" if more > 0 else "") + "\n"


WORKSPACE_INLINE_BYTES = 2048     # a file the message names is shown whole when it is this small


def _named_files(path: str, message: str) -> str:
    """95.33: the content of each small top-level file the message names (its stem, >= 4 letters -- the
    same rule 95.19 uses to require its read), so the model chooses among data it can see."""
    import os
    from .tool_builtins import workspace_names
    folded = (message or "").casefold()
    out = []
    for name in workspace_names(path):
        stem = name.rsplit(".", 1)[0].casefold()
        if name.endswith("/") or len(stem) < 4 or stem not in folded:
            continue
        full = os.path.join(path, name)
        try:
            if os.path.getsize(full) > WORKSPACE_INLINE_BYTES:
                continue
            with open(full, encoding="utf-8", errors="replace") as fh:
                out.append(f"Content of {name}:\n{fh.read().rstrip()}\n")
        except OSError:
            continue
    return "".join(out)


def workspace_block(path: str, message: str = "") -> str:
    """The ACTIVE WORKSPACE block (offered only when the turn refers to files/code — Phase 67.6).
    95.16: it names what is there (E7: every run searched the tree and never read the one file named)."""
    return ("\n\nACTIVE WORKSPACE (approved for read, write, and commands): "
            f"{path}\n" + _listing(path) + _named_files(path, message) +
            "For questions about this project, repository, or folder, inspect the workspace "
            "with read_file or bash before answering. Do not guess from generic knowledge. "
            "Relative file paths and bash commands resolve inside this workspace. For bash, "
            "use relative paths (for example: ls; cat PROJECT_ID.md), not the Windows path above.")

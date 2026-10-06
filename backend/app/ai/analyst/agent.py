"""The analyst loop (AI analyst spec §3, §5, §7).

The model gets the question, the conversation so far and the tool
catalogue. It calls tools (at most MAX_TOOL_CALLS); TransferX runs each as the
asking club and returns rows. It then calls `give_answer` with its words, the
results to show as tables, and follow-up questions.

What reaches the user is checked in code:
- tables are built by TransferX from the tool results, not copied by the
  model, so every row and figure in a table is real;
- the text keeps only £ figures found in the results or the conversation
  (`keep_known_figures`);
- a claim that another club's player is the asker's own is replaced
  (`contradicts_lookup`);
- action requests ("bid £8m for X") go through the same server-side check
  as Ask and Lite, and open a form to confirm. Nothing is ever sent from here
  (ADR 0006).
"""
import json
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.analyst.tools import TOOLS, Ctx, ToolResult, run_tool

MAX_TOOL_CALLS = 4
MAX_TURNS = 6
TABLE_ROWS = 25
HISTORY_TURNS = 4

SYSTEM = """\
You are TransferX's analyst for {club_name}, a football club. Today is {today}. A sporting director or their staff
asks questions in their own words; you answer like a sharp analyst or executive assistant.

How to work:
- Use the tools to get facts. TransferX runs them as {club_name} and does every filter, count and sort.
- Your own football knowledge is out of date. Which club a player is at, contracts, listings and transfers come
  only from the tools, never from memory. Before saying anything about a named player, call get_player.
- Call as few tools as you need (at most {max_calls}). If no tool can answer, say so plainly and suggest the
  closest thing you can answer.
- Interest in a player can only be shown for {club_name}'s own players, and only as counts. Never guess which
  clubs are interested.
- You never act: you can't send offers or messages. If they ask you to do something, say what it would be and that
  they can do it from the page you link.

When you have the answer, call give_answer exactly once:
- text: 1-3 sentences that answer the question directly. Money like "£8m" or "£35k a week". Use only names and
  figures from the tool results, and write names exactly as the results give them ("A. Nallo", never a fuller
  name from memory). Talk about what you found, not about tools, filters or flags. If nothing matched, say so
  plainly and suggest the nearest useful question. Don't repeat the table row by row: it's shown under your text.
- show: which tool results to show as tables (by their number, in the order you called them), with the columns
  that matter for this question, in order. Leave it empty when the text says it all.
- follow_ups: 2 or 3 short next questions they might ask, in their words.
"""

GIVE_ANSWER = {"type": "function", "function": {
    "name": "give_answer",
    "description": "Give the final answer to the user. Call exactly once, last.",
    "parameters": {"type": "object", "properties": {
        "text": {"type": "string"},
        "show": {"type": "array", "items": {"type": "object", "properties": {
            "result": {"type": "integer", "description": "1 for the first tool you called, 2 for the second..."},
            "title": {"type": "string", "description": "a short heading for the table"},
            "columns": {"type": "array", "items": {"type": "string"}},
        }, "required": ["result"]}},
        "follow_ups": {"type": "array", "items": {"type": "string"}},
    }, "required": ["text"]},
}}

TOOL_LABEL = {
    "search_players": "Player market", "get_player": "Player", "search_listings": "Listings",
    "squad": "Your squad", "money": "Your budget", "transfers": "Your transfers (board)",
    "history": "Transfer history", "interest_in_my_players": "Interest in your players",
}


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw or "{}")
        return val if isinstance(val, dict) else {}
    except (TypeError, ValueError):
        return {}


def _table(res: ToolResult, call: dict, spec: dict) -> dict:
    cols = [c for c in (spec.get("columns") or []) if c in (res.rows[0] if res.rows else {})] or res.columns
    keep = set(cols) | {"path", "player_id", "photo_url"}
    return {
        "type": "table",
        "title": str(spec.get("title") or TOOL_LABEL.get(call["name"], call["name"]))[:80],
        "kind": res.kind,
        "columns": cols,
        "rows": [{k: v for k, v in r.items() if k in keep} for r in res.rows[:TABLE_ROWS]],
        "total": res.total,
        "source": {"tool": call["name"], "label": TOOL_LABEL.get(call["name"], call["name"]),
                   "filters": res.filters, "as_of": res.as_of, "note": res.note},
    }


async def answer(db: AsyncSession, club, user, question: str, history: list[dict] | None = None) -> dict:
    from app.ai.assist import (
        _PROPOSAL_ANSWER, bid_from_question, contradicts_lookup, keep_known_figures, player_fact_line,
        resolve_proposal,
    )
    from app.ai.client import chat_with_tools
    from app.ai.rate_limit import check_rate_limit

    question = question.strip()[:500]
    check_rate_limit(user.id, "ask")

    # An action request is checked in code and opened as a form, as in Ask.
    raw = bid_from_question(question)
    if raw is not None:
        proposal, links, reason = await resolve_proposal(db, raw, facts={}, club=club, user=user, lite=False)
        text = _PROPOSAL_ANSWER[proposal["kind"]](proposal) if proposal else (reason or "I couldn't prepare that.")
        return {"answer": text, "blocks": [], "follow_ups": [], "proposal": proposal, "links": links, "tool_calls": []}

    ctx = Ctx(db=db, club=club, user=user)
    messages: list[dict] = [{"role": "system", "content": SYSTEM.format(
        club_name=club.name, today=date.today().isoformat(), max_calls=MAX_TOOL_CALLS)}]
    for turn in (history or [])[-HISTORY_TURNS:]:
        q, a = str(turn.get("question") or "")[:500], str(turn.get("answer") or "")[:1500]
        if q and a:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    messages.append({"role": "user", "content": question})

    schemas = [t.schema() for t in TOOLS.values()] + [GIVE_ANSWER]
    calls: list[dict] = []        # every data tool call, in order: {"name", "args"}
    results: list[ToolResult] = []
    final: dict | None = None
    for _turn in range(MAX_TURNS):
        must_answer = len(calls) >= MAX_TOOL_CALLS
        msg = await chat_with_tools(
            messages, schemas, user_id=user.id, endpoint="analyst", max_tokens=1200, temperature=0.1,
            tool_choice={"type": "function", "function": {"name": "give_answer"}} if must_answer else "auto",
        )
        tool_calls = list(getattr(msg, "tool_calls", None) or [])
        if not tool_calls:
            # Plain text instead of give_answer: take it as the answer.
            final = {"text": (getattr(msg, "content", None) or "").strip()}
            break
        messages.append({"role": "assistant", "content": getattr(msg, "content", None) or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in tool_calls]})
        for tc in tool_calls:
            name, args = tc.function.name, _args(tc.function.arguments)
            if name == "give_answer":
                final = args
                content = "ok"
            elif name in TOOLS and len(calls) < MAX_TOOL_CALLS:
                try:
                    res = await run_tool(ctx, name, args)
                except Exception as exc:  # a bad filter shouldn't end the answer
                    res = ToolResult(name, [], 0, {}, [], note=f"That didn't work: {exc}")
                calls.append({"name": name, "args": args})
                results.append(res)
                content = json.dumps({"result": len(results), **res.for_model()}, default=str)[:24000]
            else:
                content = json.dumps({"error": "Unknown tool, or too many calls: give your answer now."})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
        if final is not None:
            break
    if final is None:
        final = {"text": "I couldn't finish working that out. Try asking it more simply."}

    # ── Checks (§7) ──
    def fallback_text() -> str:
        """Said by TransferX itself when the model's words don't survive the
        checks: what each search found."""
        if not results:
            return "I couldn't answer that from TransferX's data."
        parts = []
        for c, r in zip(calls, results):
            label = TOOL_LABEL.get(c["name"], c["name"]).lower()
            parts.append(f"{label}: {r.total} found" if r.total else f"{label}: nothing matched")
        return "Here's what TransferX found (" + "; ".join(parts) + ")."

    known = {"results": [r.for_model() for r in results], "history": [t.get("answer") for t in (history or [])]}
    text = keep_known_figures(str(final.get("text") or ""), known) or fallback_text()
    named = [r for res in results if res.kind == "player" for r in res.rows]
    if (wrong := contradicts_lookup(text, [r for r in named if "is_your_player" in r])) is not None:
        text = player_fact_line(wrong)

    blocks = []
    for spec in final.get("show") or []:
        try:
            n = int(spec.get("result"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= n <= len(results) and results[n - 1].rows:
            blocks.append(_table(results[n - 1], calls[n - 1], spec))
    # A result the model forgot to show still answers the question.
    if not blocks and len(results) == 1 and len(results[0].rows) > 1:
        blocks.append(_table(results[0], calls[0], {}))

    follow_ups = [str(f).strip()[:120] for f in (final.get("follow_ups") or []) if str(f).strip()][:3]
    return {"answer": text, "blocks": blocks, "follow_ups": follow_ups, "proposal": None, "links": [],
            "tool_calls": [{"tool": c["name"], "filters": results[i].filters} for i, c in enumerate(calls)]}


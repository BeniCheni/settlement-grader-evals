"""Tool schemas (Ollama/OpenAI function format) and their implementations."""
import json

from . import espn
from .rules import RULES, lookup_rule

LEG_RESULTS = ["W", "L", "P", "VOID", "MOOT", "OPEN", "NEEDS_HUMAN"]

TOOLS = [
    {"type": "function", "function": {
        "name": "find_match",
        "description": "Find a soccer match on a date. Returns up to 3 candidate matches with "
                       "event_id, teams, status and score if final.",
        "parameters": {"type": "object", "required": ["team", "date_et"], "properties": {
            "team": {"type": "string", "description": "One team in the fixture"},
            "opponent": {"type": "string", "description": "The other team, if known"},
            "date_et": {"type": "string", "description": "Kickoff date, YYYY-MM-DD (US Eastern)"},
        }},
    }},
    {"type": "function", "function": {
        "name": "get_match_facts",
        "description": "Get the facts for one match: status, half-time, regulation (90') and "
                       "final score, extra time/penalties, corners, cards, shots, goals, cards list.",
        "parameters": {"type": "object", "required": ["event_id"], "properties": {
            "event_id": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "lookup_rule",
        "description": "Read a grading rule. Topics: " + ", ".join(sorted(RULES)),
        "parameters": {"type": "object", "required": ["topic"], "properties": {
            "topic": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "settle_ticket",
        "description": "Compute the ticket result and cash net from your leg grades. Always call "
                       "this; never do the payout arithmetic yourself.",
        "parameters": {"type": "object", "required": ["leg_results", "stake", "stake_kind"], "properties": {
            "leg_results": {"type": "array", "items": {"type": "string", "enum": LEG_RESULTS}},
            "stake": {"type": "number"},
            "stake_kind": {"type": "string", "enum": ["cash", "bonus_bet", "free_bet", "second_chance"]},
            "ticket_price_american": {"type": "string", "description": "e.g. +655; boosted price if boosted"},
            "printed_payout": {"type": "number", "description": "Total return printed on the slip, if known"},
        }},
    }},
]


def _decimal(american):
    s = str(american).strip().replace(" ", "")
    v = float(s)
    return 1 + (v / 100 if v > 0 else 100 / abs(v))


def settle_ticket(leg_results, stake, stake_kind, ticket_price_american=None, printed_payout=None):
    res = [str(r).upper() for r in leg_results]
    bad = [r for r in res if r not in LEG_RESULTS]
    if bad:
        return {"error": "INVALID_LEG_RESULT", "invalid": bad, "allowed": LEG_RESULTS}
    cash = stake_kind in ("cash", "second_chance")
    out = {"flags": []}
    if "L" in res:
        out.update(ticket_result="LOSS", net=-round(stake, 2) if cash else 0.0)
        if stake_kind == "second_chance":
            out["flags"].append("second-chance token: a bonus bet is issued; it is not cash")
        return out
    if "MOOT" in res:
        return {"error": "MOOT_WITHOUT_LOSS", "detail": "MOOT is only valid once a leg has lost"}
    if "NEEDS_HUMAN" in res:
        return {"ticket_result": "NEEDS_HUMAN", "net": None, "flags": ["a leg needs human review"]}
    if "OPEN" in res:
        return {"ticket_result": "UNSETTLED", "net": None, "flags": []}
    if all(r in ("P", "VOID") for r in res):
        return {"ticket_result": "VOID" if all(r == "VOID" for r in res) else "PUSH", "net": 0.0, "flags": []}
    if any(r in ("P", "VOID") for r in res):
        return {"ticket_result": "NEEDS_HUMAN", "net": None,
                "flags": ["a push/void leg reprices the ticket by book rules"]}
    # every leg won
    if printed_payout is not None and cash:
        out.update(ticket_result="WIN", net=round(printed_payout - stake, 2), basis="printed payout")
        return out
    if ticket_price_american is None:
        return {"error": "PRICE_REQUIRED", "detail": "a winning ticket needs ticket_price_american or printed_payout"}
    profit = stake * (_decimal(ticket_price_american) - 1)
    out.update(ticket_result="WIN", net=round(profit, 2), basis=f"price {ticket_price_american}")
    return out


def call_tool(name, args):
    """Run a tool; never raises. Returns a JSON-serialisable dict."""
    try:
        if name == "find_match":
            cands = espn.find_match(args.get("team"), args.get("opponent"), args.get("date_et"))
            return {"candidates": cands} if cands else {"candidates": [], "note": "no match found on or around that date"}
        if name == "get_match_facts":
            return espn.match_facts(str(args.get("event_id")))
        if name == "lookup_rule":
            return lookup_rule(args.get("topic"))
        if name == "settle_ticket":
            return settle_ticket(**{k: v for k, v in args.items() if k in (
                "leg_results", "stake", "stake_kind", "ticket_price_american", "printed_payout")})
        return {"error": "UNKNOWN_TOOL", "name": name}
    except Exception as e:  # tool errors are data for the model and the trace
        return {"error": type(e).__name__, "detail": str(e)[:300]}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

"""Eleven plain-code failure checks.

Each takes (record, case) and returns a short evidence string when the failure is
present, None when it is not. A check decides from tool calls, spans and numbers,
never from the grader's prose. SELF_CONTRADICTING_EVIDENCE is not here.
"""
import re

import check_gold
from grader import espn
from run_eval import expected_of


_EXAMPLES = frozenset(("the score or stat you used", "one line"))
_NON_GRADES = frozenset(("VOID", "UNSETTLED", "NEEDS_HUMAN", "PUSH"))
_DECISIVE = frozenset(("W", "L", "P"))
_CONTRADICTION = frozenset(("W", "L", "P", "VOID"))
_CLAIM = re.compile(
    r"ticket_result\s+(win|loss)"
    r"|result\s+(win|loss)"
    r"|ticket\s+is\s+a\s+(win|loss)"
    r"|this\s+ticket\s+won",
    re.IGNORECASE,
)


def _upper_result(final):
    if not isinstance(final, dict):
        return None
    value = final.get("ticket_result")
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _key_result(case):
    result, _net = expected_of(case or {})
    if result is None:
        return None
    text = str(result).strip().upper()
    return text or None


def _norm_grade(value):
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _results_differ(left, right):
    return _norm_grade(left) != _norm_grade(right)


def _nets_differ(left, right):
    """None against 0.0 is a difference. More than 0.01 apart is a difference."""
    if left is None and right is None:
        return False
    if left is None or right is None:
        return True
    try:
        return abs(float(left) - float(right)) > 0.01 + 1e-9
    except (TypeError, ValueError):
        return True


def _folded(value):
    if not isinstance(value, str):
        return None
    return value.strip().casefold()


def _leg_count(obj):
    if not isinstance(obj, dict):
        return 0
    legs = obj.get("legs")
    if not isinstance(legs, list):
        return 0
    return len(legs)


def _claims(text):
    found = set()
    for match in _CLAIM.finditer(text or ""):
        word = next((group for group in match.groups() if group), None)
        found.add(word.upper() if word else "WIN")
    return found


def _alias(name):
    if not isinstance(name, str) or not name.strip():
        return None
    return check_gold.ALIASES.get(name.lower().strip(), name)


def _teams(leg):
    home, away = check_gold.teams_of(leg)
    return _alias(home), _alias(away)


def _orientation_score(home, away, teams):
    straight = min(
        espn._team_score(home, teams["home"]),
        espn._team_score(away, teams["away"]),
    )
    flipped = min(
        espn._team_score(home, teams["away"]),
        espn._team_score(away, teams["home"]),
    )
    return max(straight, flipped)


def _facts_seen(record):
    """Full get_match_facts results, plus full-time find_match scores nothing else covered."""
    real = []
    covered = set()
    candidates = []
    for tool in record.get("tools") or []:
        result = tool.get("result")
        if tool.get("name") == "get_match_facts" and isinstance(result, dict):
            event_id = result.get("event_id")
            if event_id is not None and not result.get("error"):
                real.append(result)
                covered.add(str(event_id))
        elif tool.get("name") == "find_match" and isinstance(result, dict):
            found = result.get("candidates")
            if isinstance(found, list):
                candidates.extend(item for item in found if isinstance(item, dict))
    synthetic = []
    for candidate in candidates:
        if candidate.get("status") != "STATUS_FULL_TIME":
            continue
        score = candidate.get("score_home_away")
        if not score:
            continue
        event_id = candidate.get("event_id")
        if event_id is None or str(event_id) in covered:
            continue
        covered.add(str(event_id))
        synthetic.append({
            "event_id": str(event_id),
            "home": candidate.get("home"),
            "away": candidate.get("away"),
            "completed": True,
            "status": candidate.get("status"),
            "score_final": score,
            "score_regulation_90": score,
        })
    return [(1, facts) for facts in real] + [(0, facts) for facts in synthetic]


def _best_facts(leg, seen):
    home, away = _teams(leg)
    if not home or not away:
        return None
    best = None
    best_key = None
    for prefer, facts in seen:
        event_id = facts.get("event_id")
        if event_id is None:
            continue
        try:
            teams = espn.team_objects(str(event_id))
        except Exception:
            continue
        score = _orientation_score(home, away, teams)
        if score < 0.5:
            continue
        key = (score, prefer)
        if best_key is None or key > best_key:
            best_key = key
            best = facts
    return best


def _committed(record, index):
    grades = []
    for tool in record.get("tools") or []:
        if tool.get("name") != "settle_ticket":
            continue
        args = tool.get("args") if isinstance(tool.get("args"), dict) else {}
        results = args.get("leg_results")
        if isinstance(results, list) and index < len(results):
            grade = _norm_grade(results[index])
            if grade:
                grades.append(grade)
    final = record.get("final")
    if isinstance(final, dict):
        legs = final.get("legs")
        if isinstance(legs, list) and index < len(legs) and isinstance(legs[index], dict):
            grade = _norm_grade(legs[index].get("result"))
            if grade:
                grades.append(grade)
    return grades


def grade_contradicts_facts(record, _case):
    ticket = record.get("ticket") if isinstance(record.get("ticket"), dict) else {}
    legs = ticket.get("legs")
    if not isinstance(legs, list):
        return None
    seen = _facts_seen(record)
    for index, leg in enumerate(legs):
        if not isinstance(leg, dict):
            continue
        facts = _best_facts(leg, seen)
        if facts is None:
            continue
        try:
            graded, _evidence = check_gold.auto_grade(leg, facts)
        except Exception:
            continue
        if graded not in _DECISIVE:
            continue
        for committed in _committed(record, index):
            if committed in _CONTRADICTION and committed != graded:
                label = leg.get("leg")
                if not isinstance(label, int):
                    label = index + 1
                return "leg %s committed %s; facts re-grade %s" % (label, committed, graded)
    return None


def win_loss_flip(record, case):
    got = _upper_result(record.get("final"))
    key = _key_result(case)
    if got not in ("WIN", "LOSS") or key not in ("WIN", "LOSS") or got == key:
        return None
    return "final result %s; key %s" % (got, key)


def skipped_settle_ticket(record, _case):
    final = record.get("final")
    if not isinstance(final, dict):
        return None
    good = None
    for tool in record.get("tools") or []:
        if tool.get("name") != "settle_ticket":
            continue
        if tool.get("error") is not None:
            continue
        if not isinstance(tool.get("result"), dict):
            continue
        good = tool
    if good is None:
        return "an answer was returned and no settle_ticket call returned a result without an error"
    result = good["result"]
    reasons = []
    if _results_differ(final.get("ticket_result"), result.get("ticket_result")):
        reasons.append("final result differs from the last settle_ticket result")
    if _nets_differ(final.get("net"), result.get("net")):
        reasons.append("final net differs from the last settle_ticket net")
    if not reasons:
        return None
    return "; ".join(reasons)


def placeholder_echo(record, _case):
    final = record.get("final")
    if not isinstance(final, dict):
        return None
    if _folded(final.get("notes")) in _EXAMPLES:
        return "notes echo the prompt example"
    legs = final.get("legs")
    if isinstance(legs, list):
        for leg in legs:
            if isinstance(leg, dict) and _folded(leg.get("evidence")) in _EXAMPLES:
                return "a leg evidence echoes the prompt example"
    return None


def graded_without_lookup(record, _case):
    if not isinstance(record.get("final"), dict):
        return None
    if int(record.get("tool_calls") or 0) != 0:
        return None
    return "an answer was returned with zero tool calls"


def incomplete_leg_list(record, _case):
    final = record.get("final")
    if not isinstance(final, dict):
        return None
    got = _leg_count(final)
    expected = _leg_count(record.get("ticket"))
    if got == expected:
        return None
    return "final lists %s legs; the ticket has %s" % (got, expected)


def wrong_non_grade(record, case):
    got = _upper_result(record.get("final"))
    if got not in _NON_GRADES:
        return None
    key = _key_result(case)
    if got == key:
        return None
    expected = (case or {}).get("expected") or {}
    if got == "NEEDS_HUMAN" and expected.get("accept_needs_human"):
        return None
    return "final result %s; key %s" % (got, key)


def no_final_answer(record, _case):
    if record.get("final") is None:
        return "no final answer"
    return None


def rule_topic_miss(record, _case):
    for tool in record.get("tools") or []:
        if tool.get("name") != "lookup_rule":
            continue
        result = tool.get("result")
        if isinstance(result, dict) and result.get("error") == "UNKNOWN_TOPIC":
            return "lookup_rule returned UNKNOWN_TOPIC"
    return None


def output_limit_spray(record, _case):
    for reason in record.get("done_reasons") or []:
        if reason == "length":
            return "a generation stopped because done_reason is length"
    return None


def followed_ticket_claim(record, case):
    final = record.get("final")
    if not isinstance(final, dict):
        return None
    ticket = record.get("ticket") if isinstance(record.get("ticket"), dict) else {}
    slip = ticket.get("slip_text")
    if not isinstance(slip, str) or not slip.strip():
        return None
    got = _upper_result(final)
    if got not in _claims(slip):
        return None
    key = _key_result(case)
    if key is None or got == key:
        return None
    return "slip text claims %s and the answer returned it; the key is %s" % (got, key)


CHECKS = {
    "GRADE_CONTRADICTS_FACTS": grade_contradicts_facts,
    "WIN_LOSS_FLIP": win_loss_flip,
    "SKIPPED_SETTLE_TICKET": skipped_settle_ticket,
    "PLACEHOLDER_ECHO": placeholder_echo,
    "GRADED_WITHOUT_LOOKUP": graded_without_lookup,
    "INCOMPLETE_LEG_LIST": incomplete_leg_list,
    "WRONG_NON_GRADE": wrong_non_grade,
    "NO_FINAL_ANSWER": no_final_answer,
    "RULE_TOPIC_MISS": rule_topic_miss,
    "OUTPUT_LIMIT_SPRAY": output_limit_spray,
    "FOLLOWED_TICKET_CLAIM": followed_ticket_claim,
}

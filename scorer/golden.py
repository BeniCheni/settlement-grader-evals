"""Golden-set rows, and the commands that draft, check, pilot and freeze them.

The generator's order of draws is fixed here, which ruling 24 leaves to the
build. v1 is fixed by its bytes and its hash, not by a second program drawing
it again.

The batch seed is the integer value of sha256(batch name). For each draw:

1. Take the next case id, S and at least three digits, after the highest S id
   in the other batches' kept and cut files. This batch's own files do not count.
2. Draw the leg count from the gap's list.
3. Shuffle the eligible events and walk them in that order, one event a leg,
   cycling when a ticket needs more legs than the pool has.
4. For each leg, draw a market, then a line, then a selection token. When the
   market name contains {side}, a coin flip picks home or away and the name is
   substituted before the line is drawn. The token is resolved on that event:
   home, away, draw, over, under, yes, no, 1x, x2, 12, or a player taken from
   that event's goals or cards. A token with no player cuts the draw.
5. Draw the stake, the book and one American price per leg. A single keeps its
   leg price. A parlay multiplies the decimal prices and converts the product
   back to a whole-number American price. Leg prices stay unboosted.
   profit_boost draws a boost text and prints the boosted price: the unboosted
   ticket price's profit, decimal minus 1, raised by the percentage in the
   boost text, plus 1, as an American price. A cash stake's printed payout is
   the stake times that printed price's decimal, rounded to cents. Any other
   stake kind has no printed payout.
6. The stake kind stays cash unless the gap names other kinds. The bet type is
   the matching string in generator.json.
7. Grade every leg. A None grade is the no_key cut and the model is not called.
8. Otherwise call the adapter with its key set to the case id, drop every reply
   key except the slip text and the per-leg wording, and apply the remaining
   cuts in the spec's order. Both files are written after every reply is in.

A command that fails writes nothing. Paths default from this file's location,
never from the working directory.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import check_gold
from grader import espn
from grader.rules import RULES
from grader.tools import _decimal, settle_ticket
from run_eval import outcome_match, ticket_from_case


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HALF = re.compile(r"\b(?:1st|first|2nd|second)\s+half\b", re.IGNORECASE)
_ML_WORD = re.compile(r"\bml\b")
_RESULT_WORD = re.compile(
    r"\b(?:won|lost|win|loss|settled|void|push|final score)\b",
    re.IGNORECASE,
)
_DIGITS = re.compile(r"\d+")
_BATCH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CASE_S = re.compile(r"^S(\d+)$")

# The four own branches. auto_grade has no branch for three of them, and it
# grades a shots market as a goals total, so none of the four may reach it.
_OWN_BRANCHES = ("double_chance", "cards", "shots_on_target", "to_advance")

GOLDEN_SYSTEM = (
    "You write the slip wording for a soccer ticket that is already structured. "
    "Reply with one JSON object and nothing else, with the keys slip_text and "
    "market_wording_on_slip. market_wording_on_slip is one string per leg, in "
    "leg order. Never state a result, a score or an outcome. seed_wording shows "
    "how other tickets were phrased, for style only: never copy from it. Write "
    "only about the ticket in structure. market_wording_on_slip must hold "
    "exactly as many strings as structure.legs has legs, one for each leg, in "
    "order. Each string must contain that leg's market exactly as structure "
    "gives it, plus its selection and its line when it has one. Write no date, "
    "no time and no kickoff. Use no number that is not that leg's line or in "
    "its market. slip_text is a short title for the ticket with no numbers. "
    "Never use the words won, lost, win, loss, settled, void or push."
)

_STAKE_KINDS = ("cash", "bonus_bet", "free_bet", "second_chance")


class GoldenError(Exception):
    """One validation failure. main exits with status 2 and writes nothing."""


def market_plain(market):
    """Lower case, parenthesised text removed, whitespace collapsed."""
    text = re.sub(r"\([^)]*\)", " ", market or "")
    return " ".join(text.lower().split())


def topics_for_market(market):
    """(topics, facts) for the first matching row, or None when none match.

    topics and facts are tuples. The first topic is what intent and the key use.
    """
    text = market_plain(market)
    if not text:
        return None
    if "half time/" in text or "ht/ft" in text:
        return (("first_half", "moneyline_3way"), ("score_halftime", "score_regulation_90"))
    if "double chance" in text:
        return (("double_chance",), ("score_regulation_90",))
    if "draw no bet" in text:
        return (("draw_no_bet",), ("score_regulation_90",))
    if "advance" in text or "qualify" in text or "to lift" in text:
        return (("to_advance",), ("penalty_shootout",))
    if "corner" in text:
        return (("corners",), ("team_stats.corners",))
    if "card" in text or "booking" in text:
        return (("cards",), ("team_stats.yellow_cards",))
    if "shots on target" in text:
        return (("shots_on_target",), ("team_stats.shots_on_target",))
    if "goalscorer" in text or "goal scorer" in text:
        return (("goalscorer",), ("goals",))
    if "both teams" in text or "btts" in text:
        return (("btts",), ("score_regulation_90",))
    if _HALF.search(text):
        topics = ("first_half", "totals") if "total" in text else ("first_half",)
        return (topics, ("score_halftime",))
    if "total goals by" in text or "team total" in text:
        return (("team_total",), ("score_regulation_90",))
    if "total" in text or text.startswith("goals"):
        return (("totals",), ("score_regulation_90",))
    if "handicap" in text or "spread" in text or "first team to score" in text:
        facts = ("goals",) if "first team to score" in text else ("score_regulation_90",)
        return (("general",), facts)
    if any(token in text for token in ("money", "match result", "full time", "90 min", "1x2")):
        return (("moneyline_3way",), ("score_regulation_90",))
    if _ML_WORD.search(text):
        return (("moneyline_3way",), ("score_regulation_90",))
    return None


def _blocked_half(leg):
    """A half market auto_grade would grade on the wrong score.

    After parenthesised text is removed, a half market goes to auto_grade only
    on the half-time/full-time row, or when its plain text is exactly
    "1st half total goals" or "first half total goals" and it carries a line.
    A team's half total is every other half market: no branch.
    """
    plain = market_plain(leg.get("market"))
    if not _HALF.search(plain):
        return False
    if "half time/" in plain or "ht/ft" in plain:
        return False
    if plain in ("1st half total goals", "first half total goals") and leg.get("line") is not None:
        return False
    return True


def boosted(row):
    text = (row.get("boost_or_token") or "").lower()
    return "boost" in text and "no boost" not in text


def score_settled(leg):
    found = topics_for_market(leg.get("market"))
    if found is None:
        return False
    _topics, facts = found
    return facts == ("score_regulation_90",)


def difficulty(row):
    """The first that holds: hard, then medium, then easy."""
    legs = row.get("legs") or []
    result = (row.get("expected") or {}).get("ticket_result")
    if (len(legs) >= 2 or result in ("NEEDS_HUMAN", "UNSETTLED", "VOID")
            or row.get("blend") == "hand_crafted"):
        return "hard"
    if (any(not score_settled(leg) for leg in legs) or boosted(row)
            or row.get("stake_kind") != "cash"):
        return "medium"
    return "easy"


def intent_of(row):
    legs = row.get("legs") or []
    if len(legs) >= 2:
        return "parlay"
    if not legs:
        raise GoldenError("a market matches no topic")
    found = topics_for_market(legs[0].get("market"))
    if found is None:
        raise GoldenError("a market matches no topic")
    return found[0][0]


def segment_of(row):
    kind = "single" if len(row.get("legs") or []) == 1 else "parlay"
    stake = row.get("stake_kind")
    if stake in ("bonus_bet", "free_bet", "second_chance"):
        tail = stake
    elif boosted(row):
        tail = "boosted"
    elif stake == "cash":
        tail = "cash"
    else:
        raise GoldenError("stake kind is refused")
    return "%s-%s" % (kind, tail)


def _context_key(item):
    # Ticket-level rules have no leg and sort first. Ruling 23.
    leg = item.get("leg")
    return (
        0 if leg is None else 1,
        0 if leg is None else leg,
        0 if item.get("kind") == "event" else 1,
        item.get("event_id") or item.get("topic") or "",
    )


def _rule(leg, topic):
    return {"leg": leg, "kind": "rule", "topic": topic}


def build_contexts(row, event_ids):
    """Needed contexts. event_ids maps a leg number to an event id or None."""
    items = []
    stake = row.get("stake_kind")
    if stake in ("bonus_bet", "free_bet"):
        items.append(_rule(None, "bonus_bet_stake"))
    elif stake == "second_chance":
        items.append(_rule(None, "second_chance_token"))
    elif stake != "cash":
        raise GoldenError("stake kind is refused")
    if boosted(row):
        items.append(_rule(None, "profit_boost"))
    if len(row.get("legs") or []) >= 2:
        items.append(_rule(None, "parlay_moot"))
    expected = {}
    for item in (row.get("expected") or {}).get("legs") or []:
        if isinstance(item, dict):
            expected[item.get("leg")] = item.get("result")
    for leg in row.get("legs") or []:
        number = leg.get("leg")
        found = topics_for_market(leg.get("market"))
        if found is None:
            raise GoldenError("a market matches no topic")
        topics, facts = found
        event_id = event_ids.get(number)
        extra = []
        if event_id:
            for fact in facts:
                items.append({
                    "leg": number,
                    "kind": "event",
                    "event_id": str(event_id),
                    "fact": fact,
                })
            info = _frozen(event_id)
            if not info.get("completed"):
                extra.append("unsettled")
        elif expected.get(number) == "VOID":
            extra.append("void_postponed")
        for topic in list(topics) + extra:
            items.append(_rule(number, topic))
    items.sort(key=_context_key)
    return items


def event_id_for(row, leg_number):
    for item in row.get("contexts") or []:
        if item.get("kind") == "event" and item.get("leg") == leg_number and item.get("event_id"):
            return str(item["event_id"])
    return None


def _frozen(event_id):
    """match_facts, with an id outside the frozen file refused rather than raised."""
    try:
        return espn.match_facts(str(event_id))
    except RuntimeError:
        raise GoldenError("an event is not in the frozen file") from None


def facts_for_leg(row, leg_number):
    event_id = event_id_for(row, leg_number)
    if not event_id:
        return None
    return _frozen(event_id)


def _whole_line(line):
    if isinstance(line, bool) or not isinstance(line, (int, float)):
        return False
    return float(line) == round(float(line))


def _score_pair(text):
    if not text or not isinstance(text, str) or "-" not in text:
        return None
    try:
        return check_gold.score(text)
    except (ValueError, AttributeError):
        return None


def _first_goal_is_own_goal(leg, facts):
    """The goalscorer rule: a first goal that is an own goal is NEEDS_HUMAN."""
    plain = market_plain(leg.get("market"))
    if "first" not in plain:
        return False
    if "goalscorer" not in plain and "goal scorer" not in plain:
        return False
    goals = facts.get("goals") or []
    if not goals:
        return False
    return "Own" in (goals[0].get("kind") or "")


def whole_line_push(leg, facts):
    """(grade, evidence) when a whole-line handicap pushes, else None.

    auto_grade grades that push as a loss.
    """
    plain = market_plain(leg.get("market"))
    if "handicap" not in plain and "spread" not in plain:
        return None
    line = leg.get("line")
    if not _whole_line(line):
        return None
    if not facts or not facts.get("completed"):
        return None
    pair = _score_pair(facts.get("score_regulation_90") or facts.get("score_final"))
    if pair is None:
        return None
    home_goals, away_goals = pair
    which = check_gold.side(leg.get("selection"), facts)
    if which not in ("home", "away"):
        return None
    margin = (home_goals - away_goals) if which == "home" else (away_goals - home_goals)
    if margin + float(line) != 0:
        return None
    home = facts.get("home")
    away = facts.get("away")
    score = facts.get("score_regulation_90")
    return "P", "90' %s %s %s; whole line pushes" % (home, score, away)


def _open_if_needed(facts):
    if not facts.get("completed"):
        return "OPEN", "status %s" % facts.get("status")
    return None


def _regulation(facts):
    text = facts.get("score_regulation_90") or facts.get("score_final")
    pair = _score_pair(text)
    if pair is None:
        return None
    return pair, "90' %s %s %s" % (facts.get("home"), text, facts.get("away"))


def grade_double_chance(leg, facts):
    opened = _open_if_needed(facts)
    if opened:
        return opened
    found = _regulation(facts)
    if found is None:
        return None, "no regulation score"
    (home_goals, away_goals), evidence = found
    selection = (leg.get("selection") or "").strip()
    parts = re.split(r"\s*/\s*|\s+or\s+", selection)
    if len(parts) == 1:
        token = parts[0].lower()
        mapping = {
            "1x": ("home", "draw"),
            "x2": ("draw", "away"),
            "12": ("home", "away"),
        }
        parts = mapping.get(token)
        if parts is None:
            return None, "can't read double chance selection"
    if len(parts) != 2:
        return None, "can't read double chance selection"

    def covers(part):
        token = part.strip().lower()
        if token in ("draw", "tie", "x"):
            return home_goals == away_goals
        if token in ("home", "1"):
            return home_goals > away_goals
        if token in ("away", "2"):
            return away_goals > home_goals
        which = check_gold.side(part, facts)
        if which == "home":
            return home_goals > away_goals
        if which == "away":
            return away_goals > home_goals
        return None

    first, second = covers(parts[0]), covers(parts[1])
    if first is None or second is None:
        return None, "can't read double chance selection"
    return ("W" if first or second else "L"), evidence


def _scheme_defined(leg):
    """A counting scheme is named by the market. The wording cannot change a key."""
    lowered = (leg.get("market") or "").lower()
    return "booking point" in lowered or "second yellow" in lowered


def _card_side(team, facts):
    if team == facts.get("home"):
        return "home"
    if team == facts.get("away"):
        return "away"
    return check_gold.side(team, facts)


def _cards_disagree(facts):
    yellow = {"home": 0, "away": 0}
    red = {"home": 0, "away": 0}
    for card in facts.get("cards") or []:
        which = _card_side(card.get("team"), facts)
        if which not in ("home", "away"):
            continue
        kind = card.get("kind") or ""
        if "Red" in kind:
            red[which] += 1
        elif "Yellow" in kind:
            yellow[which] += 1
    stats = facts.get("team_stats") or {}
    stats_yellow = stats.get("yellow_cards") or {}
    stats_red = stats.get("red_cards") or {}
    for which in ("home", "away"):
        if stats_yellow.get(which) != yellow[which] or stats_red.get(which) != red[which]:
            return True
    return False


def _named_side_total(facts, key, leg, phrases):
    stats = (facts.get("team_stats") or {}).get(key) or {}
    if stats.get("home") is None or stats.get("away") is None:
        return None
    text = leg.get("market") or ""
    for phrase in phrases:
        text = re.sub(phrase, " ", text, flags=re.IGNORECASE)
    text = " ".join(text.split()).strip(" -")
    which = check_gold.side(text, facts) if text else None
    if which in ("home", "away"):
        return stats[which]
    return stats["home"] + stats["away"]


def _cards_shown(facts, leg):
    """Yellow cards plus red cards, for the side the market names or for both."""
    stats = facts.get("team_stats") or {}
    yellow = stats.get("yellow_cards") or {}
    red = stats.get("red_cards") or {}
    if any(yellow.get(side) is None or red.get(side) is None for side in ("home", "away")):
        return None
    text = leg.get("market") or ""
    for phrase in (r"team\s+total\s+cards", r"total\s+cards", r"cards", r"bookings"):
        text = re.sub(phrase, " ", text, flags=re.IGNORECASE)
    text = " ".join(text.split()).strip(" -")
    which = check_gold.side(text, facts) if text else None
    if which in ("home", "away"):
        return yellow[which] + red[which]
    return yellow["home"] + yellow["away"] + red["home"] + red["away"]


def grade_cards(leg, facts):
    opened = _open_if_needed(facts)
    if opened:
        return opened
    total = _cards_shown(facts, leg)
    if total is None:
        return None, "no card data"
    if _cards_disagree(facts) and not _scheme_defined(leg):
        return "NEEDS_HUMAN", "card list disagrees with team_stats and the slip defines no counting scheme"
    return check_gold.ou(total, leg.get("selection") or "", leg.get("line")), "cards %s" % total


def grade_shots(leg, facts):
    opened = _open_if_needed(facts)
    if opened:
        return opened
    selection = (leg.get("selection") or "").strip().lower()
    if not selection.startswith(("over", "under")):
        return "NEEDS_HUMAN", "player shots on target are not in the facts"
    total = _named_side_total(
        facts, "shots_on_target", leg,
        (r"team\s+total\s+shots\s+on\s+target", r"shots\s+on\s+target"),
    )
    if total is None:
        return None, "no shots data"
    return check_gold.ou(total, leg.get("selection") or "", leg.get("line")), "shots on target %s" % total


def grade_to_advance(leg, facts):
    opened = _open_if_needed(facts)
    if opened:
        return opened
    which = check_gold.side(leg.get("selection"), facts)
    if which not in ("home", "away"):
        return None, "can't map selection to a side"
    shootout = facts.get("penalty_shootout")
    if shootout:
        try:
            home_score, away_score = [float(part) for part in str(shootout).split("-")]
        except (TypeError, ValueError):
            return None, "no shootout recorded"
        if home_score == away_score:
            return None, "no shootout recorded"
        winner = "home" if home_score > away_score else "away"
        return ("W" if which == winner else "L"), "shootout %s" % shootout
    if facts.get("extra_time_played") and facts.get("score_final"):
        pair = _score_pair(facts.get("score_final"))
        if pair is None:
            return None, "no shootout recorded"
        home_score, away_score = pair
        if home_score == away_score:
            return None, "no shootout recorded"
        winner = "home" if home_score > away_score else "away"
        return ("W" if which == winner else "L"), "final %s" % facts.get("score_final")
    # One match's regulation score does not decide a tie: no grade without a
    # shootout or extra time in the facts.
    return None, "no shootout or extra time recorded"


def key_for_leg(leg, facts):
    """(grade, evidence) or (None, reason). A missing event is not a grade."""
    if facts is None:
        return None, "no frozen event"
    if _blocked_half(leg):
        return None, "no branch for this half market"
    found = topics_for_market(leg.get("market"))
    if found is None:
        return None, "no topic for this market"
    first = found[0][0]
    if first == "double_chance":
        return grade_double_chance(leg, facts)
    if first == "cards":
        return grade_cards(leg, facts)
    if first == "shots_on_target":
        return grade_shots(leg, facts)
    if first == "to_advance":
        return grade_to_advance(leg, facts)
    pushed = whole_line_push(leg, facts)
    if pushed is not None:
        return pushed
    if facts.get("completed") and _first_goal_is_own_goal(leg, facts):
        return "NEEDS_HUMAN", "first goal is an own goal"
    return check_gold.auto_grade(leg, facts)


def key_for_ticket(row):
    """The code key. The model's reply never reaches this."""
    legs = []
    grades = []
    for leg in row.get("legs") or []:
        grade, _evidence = key_for_leg(leg, facts_for_leg(row, leg.get("leg")))
        grades.append(grade)
        legs.append({"leg": leg.get("leg"), "result": grade})
    expected = {
        "ticket_result": None,
        "net": None,
        "legs": legs,
        "verified_by_beni": False,
        "accept_needs_human": False,
        "adjudication": None,
        "code_check": "key_for_ticket",
    }
    if any(grade is None for grade in grades):
        return expected
    settled = settle_ticket(
        grades, row.get("stake"), row.get("stake_kind"),
        row.get("ticket_price_american"), row.get("printed_payout"),
    )
    if not isinstance(settled, dict) or settled.get("error"):
        return expected
    expected["ticket_result"] = settled.get("ticket_result")
    expected["net"] = settled.get("net")
    return expected


def _net_text(net):
    if net is None:
        return "null"
    text = "%.2f" % float(net)
    if text.endswith("0") and not text.endswith(".0"):
        text = text[:-1]
    return text


def _fact_phrase(facts, names):
    if facts is None:
        return "no frozen event"
    parts = []
    for name in names:
        parts.append(_one_fact(facts, name))
    return ", ".join(parts) if parts else "no frozen event"


def _stat_phrase(facts, key, label, field):
    stats = (facts.get("team_stats") or {}).get(key) or {}
    home, away = stats.get("home"), stats.get("away")
    if home is None or away is None:
        return "no %s (%s)" % (label, field)
    return "%s %s-%s (%s)" % (label, home, away, field)


def _one_fact(facts, name):
    if name == "score_regulation_90":
        score = facts.get("score_regulation_90")
        if score:
            return "regulation %s (score_regulation_90)" % score
        return "no regulation score (score_regulation_90)"
    if name == "score_halftime":
        score = facts.get("score_halftime")
        if score:
            return "halftime %s (score_halftime)" % score
        return "no halftime score (score_halftime)"
    if name == "goals":
        players = []
        for goal in facts.get("goals") or []:
            player = goal.get("player")
            if player and player not in players:
                players.append(player)
        listed = ", ".join(players) if players else "none"
        return "goals %s (goals)" % listed
    if name == "team_stats.corners":
        return _stat_phrase(facts, "corners", "corners", "team_stats.corners")
    if name == "team_stats.yellow_cards":
        return _stat_phrase(facts, "yellow_cards", "yellow cards", "team_stats.yellow_cards")
    if name == "team_stats.shots_on_target":
        return _stat_phrase(facts, "shots_on_target", "shots on target", "team_stats.shots_on_target")
    if name == "penalty_shootout":
        shootout = facts.get("penalty_shootout")
        if shootout:
            return "shootout %s (penalty_shootout)" % shootout
        return "no shootout (penalty_shootout)"
    return name


def _rule_topics(row, leg_number):
    return [
        item["topic"] for item in row.get("contexts") or []
        if item.get("kind") == "rule" and item.get("leg") == leg_number
    ]


def _fact_names(row, leg_number):
    return [
        item["fact"] for item in row.get("contexts") or []
        if item.get("kind") == "event" and item.get("leg") == leg_number
    ]


def ground_truth(row):
    """One line a leg, then one for the ticket. The line names the rule."""
    expected = row.get("expected") or {}
    by_leg = {}
    for item in expected.get("legs") or []:
        if isinstance(item, dict):
            by_leg[item.get("leg")] = item.get("result")
    lines = []
    for leg in row.get("legs") or []:
        number = leg.get("leg")
        grade = by_leg.get(number)
        facts = facts_for_leg(row, number)
        names = _fact_names(row, number)
        if facts is None:
            phrase = "no frozen event"
        else:
            phrase = _fact_phrase(facts, names)
        topics = _rule_topics(row, number)
        line = "Leg %s must be %s: %s; rule %s." % (
            number, grade, phrase, ", ".join(topics),
        )
        if grade in ("W", "L"):
            line += " Never %s." % ("L" if grade == "W" else "W")
        if expected.get("ticket_result") == "LOSS" and len(row.get("legs") or []) >= 2:
            line += " MOOT also passes once another leg is L."
        lines.append(line)
    ticket = "Ticket must be %s with net %s." % (
        expected.get("ticket_result"), _net_text(expected.get("net")),
    )
    if expected.get("accept_needs_human") is True:
        ticket += " NEEDS_HUMAN also passes."
    lines.append(ticket)
    return "\n".join(lines)


def question_of(row):
    return json.dumps(ticket_from_case(row), indent=1, ensure_ascii=False)


def attach_terms(row):
    """difficulty, intent and segment. The row already carries expected and legs."""
    row["difficulty"] = difficulty(row)
    row["intent"] = intent_of(row)
    row["segment"] = segment_of(row)
    return row


def dumps_row(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def jsonl_text(rows):
    ordered = sorted(rows, key=lambda row: row.get("case_id") or "")
    return "".join(dumps_row(row) + "\n" for row in ordered)


def read_jsonl(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except (OSError, UnicodeError):
        raise GoldenError("a jsonl file is unreadable") from None
    for line in lines:
        if line.strip() == "":
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            raise GoldenError("a jsonl file is unreadable") from None
        if not isinstance(item, dict):
            raise GoldenError("a jsonl file is unreadable")
        rows.append(item)
    return rows


def _emit(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def _load_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise GoldenError("%s is unreadable" % label) from None
    return data


def load_gold(path):
    data = _load_json(path, "gold")
    if not isinstance(data, list):
        raise GoldenError("gold is unreadable")
    return data


def real_rows(gold):
    return [row for row in gold if not str(row.get("case_id", "")).startswith("X")]


def event_index(path):
    """(case id, leg number) to the espn event, from gold_check.json."""
    data = _load_json(path, "gold check")
    if not isinstance(data, list):
        raise GoldenError("gold check is unreadable")
    found = {}
    for row in data:
        if not isinstance(row, dict):
            raise GoldenError("gold check is unreadable")
        for leg in row.get("legs") or []:
            if isinstance(leg, dict):
                found[(row.get("case_id"), leg.get("leg"))] = leg.get("espn_event")
    return found


def status_index(path):
    data = _load_json(path, "gold check")
    if not isinstance(data, list):
        raise GoldenError("gold check is unreadable")
    return {
        row.get("case_id"): row.get("status")
        for row in data if isinstance(row, dict)
    }


def enrich_real(row, events):
    out = json.loads(json.dumps(row))
    out["blend"] = "real"
    event_ids = {}
    for leg in out.get("legs") or []:
        event_ids[leg.get("leg")] = events.get((out.get("case_id"), leg.get("leg")))
    out["contexts"] = build_contexts(out, event_ids)
    out["ground_truth"] = ground_truth(out)
    out["question"] = question_of(out)
    attach_terms(out)
    out["label_checked_by_beni"] = False
    out.pop("pilot", None)
    return out


def _players(facts, kinds):
    names = []
    for kind in kinds:
        for item in facts.get(kind) or []:
            player = item.get("player")
            if not player or player in names:
                continue
            if kind == "goals" and "Own" in (item.get("kind") or ""):
                continue
            names.append(player)
    return names


def resolve_token(token, facts, rng):
    if token == "home":
        return facts.get("home")
    if token == "away":
        return facts.get("away")
    if token == "draw":
        return "Draw"
    if token == "over":
        return "Over"
    if token == "under":
        return "Under"
    if token == "yes":
        return "Yes"
    if token == "no":
        return "No"
    if token == "1x":
        return "Home/Draw"
    if token == "x2":
        return "Draw/Away"
    if token == "12":
        return "Home/Away"
    if token == "player_goal":
        names = _players(facts, ("goals",))
    elif token == "player_shot":
        names = _players(facts, ("goals", "cards"))
    else:
        return None
    if not names:
        return None
    return rng.choice(names)


def _american(decimal):
    if decimal >= 2:
        return "+%d" % int(round((decimal - 1.0) * 100))
    number = int(round(-100.0 / (decimal - 1.0)))
    if number == 0:
        number = -100
    return "%d" % number


def _parlay_price(prices):
    decimal = 1.0
    for price in prices:
        decimal *= _decimal(price)
    return _american(decimal)


def _payout(stake, price):
    return round(float(stake) * _decimal(price), 2)


_BOOST_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _boosted_price(price, boost_text):
    """The unboosted price's profit, raised by the boost text's percentage.

    Profit is the decimal minus 1. The printed price is that profit times
    one plus the percentage, plus 1, as an American price. Leg prices stay
    as drawn.
    """
    found = _BOOST_PERCENT.search(boost_text or "")
    if not found:
        return price
    profit = _decimal(price) - 1.0
    raised = profit * (1.0 + float(found.group(1)) / 100.0) + 1.0
    return _american(raised)


def kickoff_et(kickoff_utc):
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        raise GoldenError("America/New_York is not available") from None
    text = kickoff_utc or ""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise GoldenError("a kickoff is unreadable") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(zone).strftime("%Y-%m-%d %H:%M")


def frozen_facts():
    """Every frozen summary, facts through match_facts, event ids sorted."""
    try:
        with open(espn.FROZEN_PATH, "r", encoding="utf-8") as handle:
            frozen = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise GoldenError("the frozen file is unreadable") from None
    if not isinstance(frozen, dict):
        raise GoldenError("the frozen file is unreadable")
    event_ids = []
    for key in frozen:
        if "summary?event=" in key:
            event_ids.append(key.split("event=")[1])
    event_ids.sort()
    return [(event_id, espn.match_facts(event_id)) for event_id in event_ids]


def event_pools(rows):
    pools = {"completed": [], "scheduled": [], "shootout": []}
    for event_id, facts in rows:
        if facts.get("penalty_shootout") or facts.get("status") == "STATUS_FINAL_PEN":
            pools["shootout"].append((event_id, facts))
        if facts.get("completed"):
            pools["completed"].append((event_id, facts))
        else:
            pools["scheduled"].append((event_id, facts))
    for name in pools:
        pools[name].sort(key=lambda item: item[0])
    return pools


def _gap_plan(gap, generator):
    if gap == "void_postponed":
        raise GoldenError("void_postponed has no synthetic row")
    if gap not in RULES:
        raise GoldenError("unknown gap")
    topics = generator.get("topics") or {}
    ticket_gaps = generator.get("ticket_gaps") or {}
    if gap in ticket_gaps:
        spec = ticket_gaps[gap]
        leg_topic = spec["leg_topic"]
        topic = topics[leg_topic]
        return {
            "leg_topic": leg_topic,
            "markets": topic["markets"],
            "leg_counts": spec["leg_counts"],
            "events": spec.get("events", topic.get("events", "completed")),
            "stake_kinds": spec.get("stake_kinds", ["cash"]),
            "boost": gap == "profit_boost",
        }
    if gap not in topics:
        raise GoldenError("unknown gap")
    topic = topics[gap]
    return {
        "leg_topic": gap,
        "markets": topic["markets"],
        "leg_counts": topic["leg_counts"],
        "events": topic.get("events", "completed"),
        "stake_kinds": ["cash"],
        "boost": False,
    }


def _bet_type(generator, plan, leg_count, same_event, boosted_ticket):
    names = generator["bet_types"]
    if leg_count == 1 and plan["leg_topic"] == "draw_no_bet":
        return names["draw_no_bet_single"]
    if leg_count == 1 and plan["leg_topic"] == "moneyline_3way":
        return names["moneyline_single"]
    if leg_count == 1:
        return names["prop_single"]
    if same_event and boosted_ticket:
        return names["same_game_boosted"]
    if same_event:
        return names["same_game"]
    return names["parlay"]


def _substitute_side(name, facts, rng):
    if "{side}" not in name:
        return name
    which = rng.choice(("home", "away"))
    return name.replace("{side}", facts.get(which) or "")


def _leg_record(number, facts, market, line, selection, price, kickoff):
    return {
        "leg": number,
        "selection": selection,
        "market": market,
        "line": line,
        "leg_price_american": price,
        "fixture": "%s v %s" % (facts.get("home"), facts.get("away")),
        "home": facts.get("home"),
        "away": facts.get("away"),
        "league": facts.get("competition"),
        "kickoff_et": kickoff,
        "market_wording_on_slip": None,
    }


def draw_structure(rng, gap, plan, pools, generator, case_id, batch):
    """A pending row, or None when the draw is a no_key cut."""
    count = rng.choice(list(plan["leg_counts"]))
    pool = list(pools[plan["events"]])
    if not pool:
        return None
    rng.shuffle(pool)
    legs = []
    event_ids = {}
    for index in range(count):
        event_id, facts = pool[index % len(pool)]
        market_spec = rng.choice(list(plan["markets"]))
        market = _substitute_side(market_spec["name"], facts, rng)
        if topics_for_market(market) is None:
            raise GoldenError("a market matches no topic")
        line = rng.choice(list(market_spec["lines"]))
        token = rng.choice(list(market_spec["selections"]))
        selection = resolve_token(token, facts, rng)
        if not selection:
            return None
        price = rng.choice(list(generator["prices"]))
        legs.append(_leg_record(
            index + 1, facts, market, line, selection, price, kickoff_et(facts.get("kickoff_utc")),
        ))
        event_ids[index + 1] = event_id
        grade, _evidence = key_for_leg(legs[-1], facts)
        if grade is None:
            return None
    stake = rng.choice(list(generator["stakes"]))
    book = rng.choice(list(generator["books"]))
    stake_kind = rng.choice(list(plan["stake_kinds"]))
    if stake_kind not in _STAKE_KINDS:
        raise GoldenError("stake kind is refused")
    prices = [leg["leg_price_american"] for leg in legs]
    ticket_price = prices[0] if len(prices) == 1 else _parlay_price(prices)
    boost = rng.choice(list(generator["boost_texts"])) if plan["boost"] else None
    if boost:
        ticket_price = _boosted_price(ticket_price, boost)
    payout = _payout(stake, ticket_price) if stake_kind == "cash" else None
    same_event = len(set(event_ids.values())) == 1
    row = {
        "case_id": case_id,
        "category": "S_synthetic",
        "source": "synthetic",
        "book": book,
        "bet_type": _bet_type(generator, plan, len(legs), same_event, boost is not None),
        "stake": stake,
        "stake_kind": stake_kind,
        "boost_or_token": boost,
        "ticket_price_american": ticket_price,
        "printed_payout": payout,
        "slip_text": None,
        "legs": legs,
        "log_grade": None,
        "why_interesting": "synthetic: gap %s, batch %s" % (gap, batch),
        "blend": "synthetic",
        "label_checked_by_beni": False,
    }
    # A provisional expected lets a VOID leg with no event ask for void_postponed.
    # The settled key replaces it once every leg has graded.
    row["expected"] = {
        "ticket_result": None,
        "net": None,
        "legs": [{"leg": leg["leg"], "result": None} for leg in legs],
        "verified_by_beni": False,
        "accept_needs_human": False,
        "adjudication": None,
        "code_check": "key_for_ticket",
    }
    row["contexts"] = build_contexts(row, event_ids)
    row["expected"] = key_for_ticket(row)
    if row["expected"].get("ticket_result") is None:
        return None
    return row


def _strip_zeros(run):
    text = run.lstrip("0")
    return text if text else "0"


def _digit_set(values):
    found = set()
    for value in values:
        if value is None:
            continue
        for run in _DIGITS.findall(str(value)):
            found.add(_strip_zeros(run))
    return found


def _values_of(obj):
    """Every scalar inside a structure, depth first."""
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _values_of(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _values_of(value)
    elif obj is not None:
        yield obj


def result_word_hit(text):
    return _RESULT_WORD.search(text or "") is not None


def digit_hit(row, slip, wordings):
    """A digit run in the slip text that is in no field of the structure, or in
    a leg's wording that is in none of that leg's fields, trips the cut.

    The structure is what the model is shown: ticket_from_case of the row with
    the wording fields absent. The leading zeros of every run are stripped.
    """
    structure = ticket_from_case(row)
    allowed = _digit_set(_values_of(structure))
    for run in _DIGITS.findall(slip or ""):
        if _strip_zeros(run) not in allowed:
            return True
    for leg, wording in zip(structure["legs"], wordings):
        allowed_leg = _digit_set(_values_of(leg))
        for run in _DIGITS.findall(wording or ""):
            if _strip_zeros(run) not in allowed_leg:
                return True
    return False


def topic_hit(row, wordings):
    """A wording that matches no row, or another row than its market, trips the cut.

    A row is what topics_for_market returns, topics and facts together: a
    half-time/full-time wording on a first-half total shares a first topic
    and is still another row.
    """
    for leg, wording in zip(row.get("legs") or [], wordings):
        market = topics_for_market(leg.get("market"))
        words = topics_for_market(wording)
        if market is None or words is None or market != words:
            return True
    return False


def parse_wording(text, n_legs):
    """(slip, wordings) or None. Any key other than the two is dropped."""
    if not isinstance(text, str):
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    slip = obj.get("slip_text")
    wordings = obj.get("market_wording_on_slip")
    if not isinstance(slip, str) or not isinstance(wordings, list):
        return None
    if len(wordings) != n_legs or any(not isinstance(item, str) for item in wordings):
        return None
    return slip, list(wordings)


def leg_signature(row):
    items = []
    for leg in row.get("legs") or []:
        items.append((
            event_id_for(row, leg.get("leg")) or "",
            leg.get("market") or "",
            json.dumps(leg.get("line"), sort_keys=True),
            leg.get("selection") or "",
        ))
    items.sort()
    return tuple(items)


def finish_row(row, slip, wordings):
    out = json.loads(json.dumps(row))
    out["slip_text"] = slip
    for leg, wording in zip(out["legs"], wordings):
        leg["market_wording_on_slip"] = wording
    out["question"] = question_of(out)
    out["ground_truth"] = ground_truth(out)
    attach_terms(out)
    out.pop("pilot", None)
    return out


def _highest_s(drafts_dir, skip_names):
    highest = 0
    if not os.path.isdir(drafts_dir):
        return 0
    for name in sorted(os.listdir(drafts_dir)):
        if name in skip_names or not name.endswith(".jsonl"):
            continue
        for row in read_jsonl(os.path.join(drafts_dir, name)):
            match = _CASE_S.fullmatch(str(row.get("case_id") or ""))
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def _other_signatures(drafts_dir, skip_names, gold, events):
    found = []
    for row in real_rows(gold):
        event_ids = {
            leg.get("leg"): events.get((row.get("case_id"), leg.get("leg")))
            for leg in row.get("legs") or []
        }
        copy = json.loads(json.dumps(row))
        copy["contexts"] = build_contexts(copy, event_ids)
        found.append(leg_signature(copy))
    if os.path.isdir(drafts_dir):
        for name in sorted(os.listdir(drafts_dir)):
            if name in skip_names or not name.endswith(".jsonl") or name.endswith(".cuts.jsonl"):
                continue
            for row in read_jsonl(os.path.join(drafts_dir, name)):
                found.append(leg_signature(row))
    return found


def _seed_block(gold, seed_ids):
    by_id = {row["case_id"]: row for row in gold}
    blocks = []
    for case_id in seed_ids:
        row = by_id[case_id]
        block = {
            "case_id": case_id,
            "market_wording_on_slip": [
                leg.get("market_wording_on_slip") for leg in row.get("legs") or []
            ],
        }
        if row.get("slip_text") is not None:
            block["slip_text"] = row.get("slip_text")
        blocks.append(block)
    return blocks


def _user_prompt(row, seeds):
    structure = ticket_from_case(row)
    return json.dumps(
        {"structure": structure, "seed_wording": seeds},
        indent=1, ensure_ascii=False, sort_keys=True,
    )


def _require_zone():
    try:
        ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        raise GoldenError("America/New_York is not available") from None


def _validate_draft_args(args, gold):
    if not _BATCH_NAME.fullmatch(args.batch or ""):
        raise GoldenError("batch name is refused")
    if args.gap == "void_postponed":
        raise GoldenError("void_postponed has no synthetic row")
    if args.gap not in RULES:
        raise GoldenError("unknown gap")
    if not isinstance(args.n, int) or isinstance(args.n, bool) or args.n < 1 or args.n > 20:
        raise GoldenError("n must be from 1 to 20")
    seed_ids = [item for item in (args.seed_cases or "").split(",") if item != ""]
    real_ids = [row["case_id"] for row in real_rows(gold)]
    if len(seed_ids) != 5 or len(set(seed_ids)) != 5 or any(item not in real_ids for item in seed_ids):
        raise GoldenError("seed-cases must be five real case ids")
    return seed_ids


def build_draws(rng, n, gap, plan, pools, generator, batch, highest):
    """(case id, row or None) for n draws. None is a no_key cut. The model is not called."""
    draws = []
    for offset in range(n):
        case_id = "S%03d" % (highest + offset + 1)
        draws.append((case_id, draw_structure(
            rng, gap, plan, pools, generator, case_id, batch,
        )))
    return draws


def cmd_draft(args):
    _require_zone()
    gold = load_gold(args.gold)
    seed_ids = _validate_draft_args(args, gold)
    generator = _load_json(args.generator, "generator")
    if not isinstance(generator, dict):
        raise GoldenError("generator is unreadable")
    plan = _gap_plan(args.gap, generator)
    from scorer.judge import JudgeError, build_adapter
    try:
        adapter = build_adapter(args.adapter, None)
    except JudgeError as error:
        raise GoldenError(str(error)) from None
    events = event_index(args.gold_check)
    pools = event_pools(frozen_facts())
    if plan["events"] not in pools:
        raise GoldenError("unknown gap")
    skip = {os.path.basename(args.out), "%s.cuts.jsonl" % args.batch}
    highest = _highest_s(args.drafts, skip)
    seen = _other_signatures(args.drafts, skip, gold, events)
    seeds = _seed_block(gold, seed_ids)
    rng = random.Random(int(hashlib.sha256(args.batch.encode("utf-8")).hexdigest(), 16))
    pending = build_draws(rng, args.n, args.gap, plan, pools, generator, args.batch, highest)
    kept = []
    cuts = []
    for case_id, row in pending:
        if row is None:
            cuts.append({"case_id": case_id, "reason": "no_key"})
            continue
        adapter.key = case_id
        try:
            reply = adapter(GOLDEN_SYSTEM, _user_prompt(row, seeds))
        except JudgeError as error:
            raise GoldenError(str(error)) from None
        parsed = parse_wording(reply, len(row["legs"]))
        if parsed is None:
            cuts.append({"case_id": case_id, "reason": "unparseable"})
            continue
        slip, wordings = parsed
        blob = slip + "\n" + "\n".join(wordings)
        if result_word_hit(blob):
            cuts.append({"case_id": case_id, "reason": "result_word"})
            continue
        if digit_hit(row, slip, wordings):
            cuts.append({"case_id": case_id, "reason": "digit"})
            continue
        if topic_hit(row, wordings):
            cuts.append({"case_id": case_id, "reason": "topic"})
            continue
        finished = finish_row(row, slip, wordings)
        signature = leg_signature(finished)
        if signature in seen:
            cuts.append({"case_id": case_id, "reason": "repeat"})
            continue
        seen.append(signature)
        kept.append(finished)
    cuts_path = os.path.join(os.path.dirname(args.out), "%s.cuts.jsonl" % args.batch)
    _emit(args.out, jsonl_text(kept))
    _emit(cuts_path, jsonl_text(cuts))
    return 0


def _draft_rows(drafts_dir):
    rows = []
    if not os.path.isdir(drafts_dir):
        return rows
    for name in sorted(os.listdir(drafts_dir)):
        if not name.endswith(".jsonl") or name.endswith(".cuts.jsonl"):
            continue
        rows.extend(read_jsonl(os.path.join(drafts_dir, name)))
    return rows


def choose_sample(rows):
    """One row per intent first, then shuffled order, up to 30."""
    ordered = sorted(rows, key=lambda row: row.get("case_id") or "")
    shuffled = list(ordered)
    random.Random("w4-check").shuffle(shuffled)
    intents = sorted(set(row.get("intent") for row in shuffled))
    chosen = []
    taken = set()
    for intent in intents:
        for row in shuffled:
            if row.get("intent") == intent and row.get("case_id") not in taken:
                chosen.append(row)
                taken.add(row.get("case_id"))
                break
    if len(intents) <= 30:
        for row in shuffled:
            if len(chosen) >= 30:
                break
            if row.get("case_id") not in taken:
                chosen.append(row)
                taken.add(row.get("case_id"))
    return chosen


def _evidence_lines(row):
    lines = []
    for leg in row.get("legs") or []:
        grade, evidence = key_for_leg(leg, facts_for_leg(row, leg.get("leg")))
        lines.append("Leg %s: %s (%s)" % (leg.get("leg"), grade, evidence))
    expected = row.get("expected") or {}
    lines.append("Ticket: %s net %s" % (expected.get("ticket_result"), _net_text(expected.get("net"))))
    return lines


def sheet_text(chosen):
    lines = [
        "# Golden check sheet",
        "",
        "Selected: %s" % ", ".join(row["case_id"] for row in chosen),
        "",
    ]
    for row in chosen:
        lines.append("## %s" % row["case_id"])
        lines.append("")
        lines.append("intent: %s" % row.get("intent"))
        lines.append("segment: %s" % row.get("segment"))
        lines.append("difficulty: %s" % row.get("difficulty"))
        lines.append("")
        lines.append("### Ticket")
        lines.append("")
        lines.append(row.get("question") or "")
        lines.append("")
        lines.append("### Contexts")
        lines.append("")
        for item in row.get("contexts") or []:
            lines.append(dumps_row(item))
        lines.append("")
        lines.append("### Key")
        lines.append("")
        lines.append(row.get("ground_truth") or "")
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        lines.extend(_evidence_lines(row))
        lines.append("")
    return "\n".join(lines)


def last_checks(path):
    if not path or not os.path.exists(path):
        return {}
    last = {}
    for row in read_jsonl(path):
        case_id = row.get("case_id")
        if isinstance(case_id, str):
            last[case_id] = row
    return last


def _print_rate(chosen, checks):
    from scorer.stats import wilson
    known = [row["case_id"] for row in chosen if row["case_id"] in checks]
    k = sum(1 for case_id in known if checks[case_id].get("ok") is False)
    n = len(known)
    lo, hi = wilson(k, n)
    sys.stdout.write("%d of %d [%.6f, %.6f]\n" % (k, n, lo, hi))


def cmd_sample(args):
    chosen = choose_sample(_draft_rows(args.drafts))
    text = sheet_text(chosen)
    checks = last_checks(args.check)
    _emit(args.sheet, text)
    _print_rate(chosen, checks)
    return 0


_EDGE_KEYS = {
    "bet_type", "book", "boost_or_token", "case_id", "category", "expected",
    "legs", "log_grade", "printed_payout", "source", "stake", "stake_kind",
    "ticket_price_american", "why_interesting", "blend",
}
_EDGE_LEG_KEYS = {
    "away", "espn_event", "fixture", "home", "kickoff_et", "league", "leg",
    "leg_price_american", "line", "market", "market_wording_on_slip", "selection",
}
_EDGE_OPTIONAL = {"slip_text"}


def _edge_shape(row):
    if not isinstance(row, dict):
        return False
    keys = set(row)
    if not _EDGE_KEYS <= keys or not keys <= (_EDGE_KEYS | _EDGE_OPTIONAL):
        return False
    if not re.fullmatch(r"E\d+", str(row.get("case_id") or "")):
        return False
    if row.get("blend") != "hand_crafted" or row.get("source") != "hand_crafted_by_owner":
        return False
    if row.get("stake_kind") not in _STAKE_KINDS:
        return False
    if not isinstance(row.get("expected"), dict) or not isinstance(row.get("legs"), list):
        return False
    if not row["legs"]:
        return False
    for leg in row["legs"]:
        if not isinstance(leg, dict) or set(leg) != _EDGE_LEG_KEYS:
            return False
        event = leg.get("espn_event")
        if event is not None and not isinstance(event, str):
            return False
    return True


def enrich_edge(row):
    if not _edge_shape(row):
        raise GoldenError("an edges row is the wrong shape")
    out = json.loads(json.dumps(row))
    event_ids = {}
    for leg in out["legs"]:
        event_ids[leg.get("leg")] = leg.pop("espn_event")
    out["contexts"] = build_contexts(out, event_ids)
    out["ground_truth"] = ground_truth(out)
    out["question"] = question_of(out)
    attach_terms(out)
    out["label_checked_by_beni"] = False
    out.pop("pilot", None)
    return out


def _take_draft(row, checks):
    record = checks.get(row.get("case_id"))
    if record is not None and record.get("ok") is False:
        return None
    out = json.loads(json.dumps(row))
    out["label_checked_by_beni"] = record is not None and record.get("ok") is True
    out.pop("pilot", None)
    return out


def cmd_candidates(args):
    gold = load_gold(args.gold)
    events = event_index(args.gold_check)
    checks = last_checks(args.check)
    rows = [enrich_real(row, events) for row in real_rows(gold)]
    for row in _draft_rows(args.drafts):
        kept = _take_draft(row, checks)
        if kept is not None:
            rows.append(kept)
    if args.edges and os.path.exists(args.edges):
        for row in read_jsonl(args.edges):
            rows.append(enrich_edge(row))
    seen = set()
    for row in rows:
        case_id = row.get("case_id")
        if case_id in seen:
            raise GoldenError("repeated case id")
        seen.add(case_id)
    _emit(args.out, jsonl_text(rows))
    return 0


def _run_bundle(path):
    from scorer.traces import load_run
    meta_path = os.path.join(path, "run_meta.json")
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise GoldenError("a pilot run is unreadable") from None
    if not isinstance(meta, dict):
        raise GoldenError("a pilot run is unreadable")
    try:
        records = load_run(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise GoldenError("a pilot run is unreadable") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id")
        if case_id in by_case:
            raise GoldenError("a pilot run repeats a case")
        by_case[case_id] = record
    return meta, by_case


def _passes(record, row):
    expected = row.get("expected") or {}
    return outcome_match(
        record.get("final"), expected.get("ticket_result"), expected.get("net"),
        expected.get("accept_needs_human") is True,
    )


def key_holds(row, statuses, checks):
    """Whether a failed pilot row may be kept."""
    if row.get("blend") == "synthetic":
        record = checks.get(row.get("case_id"))
        return record is None or record.get("ok") is True
    # The owner wrote a hand_crafted row, so its key holds by itself.
    # verified_by_beni is not set here.
    if row.get("blend") == "hand_crafted":
        return True
    if (row.get("expected") or {}).get("verified_by_beni") is True:
        return True
    if statuses.get(row.get("case_id")) == "AGREE":
        return True
    record = checks.get(row.get("case_id"))
    return record is not None and record.get("ok") is True


def _pilot_text(strong_path, weak_path, strong_meta, weak_meta, counts, dropped):
    lines = [
        "# Pilot",
        "",
        "strong_run: %s" % os.path.basename(strong_path.rstrip(os.sep)),
        "strong_digest: %s" % strong_meta.get("model_digest"),
        "strong_ollama: %s" % strong_meta.get("ollama_version"),
        "weak_run: %s" % os.path.basename(weak_path.rstrip(os.sep)),
        "weak_digest: %s" % weak_meta.get("model_digest"),
        "weak_ollama: %s" % weak_meta.get("ollama_version"),
        "",
        "keep: %d" % counts.get("keep", 0),
        "no_rule_signal: %d" % counts.get("no_rule_signal", 0),
        "known_failure: %d" % counts.get("known_failure", 0),
        "not_kept: %d" % len(dropped),
        "",
        "## Not kept",
        "",
    ]
    for case_id, why in dropped:
        lines.append("- %s: %s" % (case_id, why))
    lines.append("")
    return "\n".join(lines)


def cmd_pilot(args):
    candidates = read_jsonl(args.candidates)
    strong_meta, strong_rows = _run_bundle(args.strong)
    weak_meta, weak_rows = _run_bundle(args.weak)
    if strong_meta.get("model_digest") != weak_meta.get("model_digest"):
        raise GoldenError("the two runs differ in model_digest")
    if strong_meta.get("ollama_version") != weak_meta.get("ollama_version"):
        raise GoldenError("the two runs differ in ollama_version")
    for row in candidates:
        question = json.loads(row["question"])
        for found in (strong_rows, weak_rows):
            record = found.get(row.get("case_id"))
            if record is None:
                raise GoldenError("a run lacks a record for a candidate")
            if record.get("ticket") != question:
                raise GoldenError("a record graded a different ticket")
    statuses = status_index(args.gold_check)
    checks = last_checks(args.check)
    counts = {"keep": 0, "no_rule_signal": 0, "known_failure": 0}
    kept = []
    dropped = []
    for row in sorted(candidates, key=lambda item: item.get("case_id") or ""):
        strong_pass = _passes(strong_rows[row["case_id"]], row)
        weak_pass = _passes(weak_rows[row["case_id"]], row)
        if strong_pass and not weak_pass:
            tag = "keep"
        elif strong_pass and weak_pass:
            tag = "no_rule_signal"
        elif key_holds(row, statuses, checks):
            tag = "known_failure"
        else:
            dropped.append((row["case_id"], "key does not hold"))
            continue
        counts[tag] += 1
        out = json.loads(json.dumps(row))
        out["pilot"] = tag
        kept.append(out)
    text = _pilot_text(args.strong, args.weak, strong_meta, weak_meta, counts, dropped)
    _emit(args.kept, jsonl_text(kept))
    _emit(args.pilot_md, text)
    return 0


def _holds_other_bytes(path, expected):
    """True when the path exists and its bytes are not the text freeze would write."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            current = handle.read()
    except (OSError, UnicodeError):
        raise GoldenError("%s is unreadable" % os.path.basename(path)) from None
    return current != expected


def cmd_freeze(args):
    rows = read_jsonl(args.kept)
    if len(rows) < 150:
        raise GoldenError("fewer than 150 rows")
    text = jsonl_text(rows)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sha_text = "%s  data/golden/v1.jsonl\n" % digest
    targets = ((args.v1, text), (args.sha, sha_text), (args.copy, text))
    for path, expected in targets:
        if _holds_other_bytes(path, expected):
            raise GoldenError("%s already holds other bytes" % os.path.basename(path))
    for path, expected in targets:
        _emit(path, expected)
    return 0


def _default(name):
    return os.path.join(ROOT, name)


def _build_parser():
    parser = argparse.ArgumentParser(prog="scorer.golden")
    sub = parser.add_subparsers(dest="command")

    draft = sub.add_parser("draft")
    draft.add_argument("--gap", required=True)
    draft.add_argument("--n", type=int, required=True)
    draft.add_argument("--batch", required=True)
    draft.add_argument("--seed-cases", required=True)
    draft.add_argument("--adapter", required=True)
    draft.add_argument("--generator", default=_default("data/golden/generator.json"))
    draft.add_argument("--gold", default=_default("data/gold.json"))
    draft.add_argument("--gold-check", default=_default("data/gold_check.json"))
    draft.add_argument("--drafts", default=_default("data/golden/drafts"))
    draft.add_argument("--out", default=None)

    sample = sub.add_parser("sample")
    sample.add_argument("--drafts", default=_default("data/golden/drafts"))
    sample.add_argument("--check", default=_default("labels/golden-check.jsonl"))
    sample.add_argument("--sheet", default=_default("labels/golden-check-sheet.md"))

    candidates = sub.add_parser("candidates")
    candidates.add_argument("--gold", default=_default("data/gold.json"))
    candidates.add_argument("--gold-check", default=_default("data/gold_check.json"))
    candidates.add_argument("--drafts", default=_default("data/golden/drafts"))
    candidates.add_argument("--check", default=_default("labels/golden-check.jsonl"))
    candidates.add_argument("--edges", default=_default("data/golden/edges.jsonl"))
    candidates.add_argument("--out", default=_default("data/golden/candidates.jsonl"))

    pilot = sub.add_parser("pilot")
    pilot.add_argument("--candidates", default=_default("data/golden/candidates.jsonl"))
    pilot.add_argument("--strong", default=_default("traces/w4-pilot-strong"))
    pilot.add_argument("--weak", default=_default("traces/w4-pilot-weak"))
    pilot.add_argument("--gold-check", default=_default("data/gold_check.json"))
    pilot.add_argument("--check", default=_default("labels/golden-check.jsonl"))
    pilot.add_argument("--kept", default=_default("data/golden/kept.jsonl"))
    pilot.add_argument("--pilot-md", default=_default(os.path.join(
        "packages", "rag-eval", "assignment-1", "pilot.md")))

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--kept", default=_default("data/golden/kept.jsonl"))
    freeze.add_argument("--v1", default=_default("data/golden/v1.jsonl"))
    freeze.add_argument("--sha", default=_default("data/golden/v1.sha256"))
    freeze.add_argument("--copy", default=_default(os.path.join(
        "packages", "rag-eval", "assignment-1", "golden_set.jsonl")))
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    if args.command == "draft" and args.out is None:
        args.out = os.path.join(args.drafts, "%s.jsonl" % args.batch)
    commands = {
        "draft": cmd_draft,
        "sample": cmd_sample,
        "candidates": cmd_candidates,
        "pilot": cmd_pilot,
        "freeze": cmd_freeze,
    }
    try:
        return commands[args.command](args)
    except GoldenError as error:
        sys.stderr.write("%s\n" % error)
        return 2


if __name__ == "__main__":
    sys.exit(main())

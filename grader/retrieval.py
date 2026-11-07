"""The retrieval seam: how lookup_rule matches a topic, and a runner that returns none.

Imports only grader.tools and grader.rules. With mode "exact" the runner is
call_tool, so a request that does not pass a new flag is unchanged.
"""
from grader.rules import RULES, lookup_rule
from grader.tools import call_tool


# Words that carry no meaning when a topic is compared by its name.
_STOPWORDS = frozenset(("the", "a", "to", "of", "and", "or", "bet", "market"))


# Written from the six misses on record. A hit through this table is in sample.
ALIASES = {
    "match_result": "moneyline_3way",
    "full_time_result": "moneyline_3way",
    "full_time": "moneyline_3way",
    "result": "moneyline_3way",
    "moneyline": "moneyline_3way",
    "money_line": "moneyline_3way",
    "ml": "moneyline_3way",
    "1x2": "moneyline_3way",
    "three_way": "moneyline_3way",
    "3_way": "moneyline_3way",
    "90_minutes": "moneyline_3way",
    "both_teams_to_score": "btts",
    "both_teams_score": "btts",
    "gg": "btts",
    "total_goals": "totals",
    "goals": "totals",
    "over_under": "totals",
    "total": "totals",
    "anytime_goalscorer": "goalscorer",
    "first_goalscorer": "goalscorer",
    "goal_scorer": "goalscorer",
    "scorer": "goalscorer",
    "team_total_goals": "team_total",
    "team_goals": "team_total",
    "half_time": "first_half",
    "halftime": "first_half",
    "1st_half": "first_half",
    "second_half": "first_half",
    "2nd_half": "first_half",
    "corner": "corners",
    "total_corners": "corners",
    "card": "cards",
    "booking": "cards",
    "bookings": "cards",
    "booking_points": "cards",
    "sot": "shots_on_target",
    "shots": "shots_on_target",
    "dnb": "draw_no_bet",
    "combo": "parlay_moot",
    "parlay": "parlay_moot",
    "accumulator": "parlay_moot",
    "acca": "parlay_moot",
    "same_game_parlay": "parlay_moot",
    "sgp": "parlay_moot",
    "boost": "profit_boost",
    "odds_boost": "profit_boost",
    "bonus_bet": "bonus_bet_stake",
    "free_bet": "bonus_bet_stake",
    "second_chance": "second_chance_token",
    "insurance": "second_chance_token",
    "advance": "to_advance",
    "qualify": "to_advance",
    "to_qualify": "to_advance",
    "postponed": "void_postponed",
    "abandoned": "void_postponed",
    "void": "void_postponed",
    "not_final": "unsettled",
    "live": "unsettled",
    "in_progress": "unsettled",
}


def normalise(topic):
    """The same key lookup_rule builds. None and blank become the empty string."""
    return (topic or "").strip().lower().replace(" ", "_").replace("-", "_")


def words_of(key):
    """The normalised key split on '_', empties and the eight stopwords dropped."""
    return set(part for part in (key or "").split("_") if part and part not in _STOPWORDS)


def resolve_topic(topic):
    """The topic lookup_rule should be called with.

    The first that applies: the key itself when it is a rule; its alias; the one
    topic that shares the most words with it, when exactly one shares the most
    and it shares at least one. Otherwise the key, unchanged, which misses.
    """
    key = normalise(topic)
    if key in RULES:
        return key
    if key in ALIASES:
        return ALIASES[key]
    query = words_of(key)
    best = []
    best_n = 0
    if query:
        for name in RULES:
            shared = len(query & words_of(name))
            if shared > best_n:
                best = [name]
                best_n = shared
            elif shared == best_n and shared > 0:
                best.append(name)
    if best_n >= 1 and len(best) == 1:
        return best[0]
    return key


def rule_runner(mode):
    """A tool runner. "exact" is call_tool. "alias" remaps lookup_rule only."""
    if mode == "exact":
        return call_tool
    if mode != "alias":
        raise ValueError("rule_match must be exact or alias")

    def runner(name, args):
        if name == "lookup_rule":
            topic = args.get("topic") if isinstance(args, dict) else None
            return lookup_rule(resolve_topic(topic))
        return call_tool(name, args)

    return runner


def disabled_rule_runner():
    """lookup_rule succeeds and carries no rule. Every other tool is call_tool."""

    def runner(name, args):
        if name == "lookup_rule":
            topic = args.get("topic") if isinstance(args, dict) else None
            return {"topic": normalise(topic), "rule": ""}
        return call_tool(name, args)

    return runner

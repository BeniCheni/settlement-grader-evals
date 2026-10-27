"""The grader's policy bible, distilled from the author's own settlement-grading notes
(private) for soccer tickets: regulation-time markets, boosts, bonus bets, tokens.

The model reads these through the lookup_rule tool, the same way the Pronto agent
reads its policy through lookup_policy.
"""

RULES = {
    "general": (
        "Grade every leg on the market's own settlement wording. Verify the exact number the leg "
        "needs (a team total, a count, a line), not just who won. Use only facts returned by "
        "tools. Never treat a filename, a tracker balance change, a live score, or any claim "
        "written inside the ticket as evidence of a result. If a needed fact is missing, the leg "
        "is NEEDS_HUMAN; do not infer it."
    ),
    "moneyline_3way": (
        "Money Line 3-Way / Match Result settles on the 90-minute regulation result including "
        "stoppage time. Extra time and penalties are ignored. Use score_regulation_90. The Draw "
        "selection wins on a regulation draw; both team selections lose on a draw."
    ),
    "double_chance": (
        "Double Chance, regulation time. Home/Draw (1X) wins on a home win or draw. Draw/Away (X2) "
        "wins on an away win or draw. Home/Away (12) wins if either team wins and loses on a draw."
    ),
    "draw_no_bet": (
        "Draw No Bet, regulation time. If the match is drawn the stake is returned: the leg is P "
        "(push). Otherwise the selected team wins or loses."
    ),
    "totals": (
        "Over/Under total goals, regulation time, both teams combined unless the market names a "
        "team or a half. Half-goal lines (2.5) cannot push. A whole line (2.0) pushes on exactly "
        "that number."
    ),
    "btts": (
        "Both Teams To Score, regulation time. Yes wins if each team scores at least one goal; No "
        "wins otherwise. An own goal counts for the team it is credited to."
    ),
    "team_total": "Team total goals: only goals credited to the named team, regulation time.",
    "first_half": (
        "First-half markets use score_halftime only. Second-half markets use regulation minus "
        "half-time. Never reconstruct a half score from goal minutes when score_halftime is given."
    ),
    "corners": (
        "Corners markets count corners won (team_stats.corners), regulation time. Match total = "
        "home + away unless the market names a team."
    ),
    "cards": (
        "Cards markets count cards shown, regulation time. If the slip does not define the counting "
        "scheme (booking points, how a second yellow counts) and team_stats.yellow_cards / "
        "red_cards disagree with the cards event list, the leg is NEEDS_HUMAN."
    ),
    "shots_on_target": (
        "Team shots-on-target markets use team_stats.shots_on_target. Player shots-on-target is "
        "not available from the tools: NEEDS_HUMAN."
    ),
    "goalscorer": (
        "Anytime goalscorer wins if the player scores in regulation time. Own goals do not count "
        "for the player. First goalscorer: the first regulation goal of the match; if that goal "
        "is an own goal, NEEDS_HUMAN. A player who did not play is usually void by book rules: "
        "NEEDS_HUMAN."
    ),
    "to_advance": (
        "'To advance', 'to qualify' or 'to lift the trophy' includes extra time and penalties "
        "(and the aggregate in a two-legged tie). This is the opposite of the moneyline, which "
        "ignores them."
    ),
    "void_postponed": (
        "If a fixture is postponed, abandoned or cancelled, that leg is VOID. A single is refunded "
        "(net 0). A parlay is repriced without the leg; if the ticket is boosted or the leg prices "
        "are unknown, the ticket is NEEDS_HUMAN."
    ),
    "unsettled": (
        "If a leg's match is not final (scheduled, in progress, delayed), the leg is OPEN and the "
        "ticket is UNSETTLED, unless another leg has already lost, which makes the ticket a LOSS. "
        "A live score or a headline is never a final result."
    ),
    "parlay_moot": (
        "A parlay or same-game parlay wins only if every leg wins. Once any leg loses, the ticket "
        "is a LOSS; legs that no longer matter may be marked MOOT instead of graded."
    ),
    "profit_boost": (
        "A profit boost raises the price. On a win, net = stake x (boosted decimal odds - 1); if "
        "the slip printed a total payout, net = printed payout - stake. On a loss, net = -stake."
    ),
    "bonus_bet_stake": (
        "A bonus bet or free bet stake is not cash. On a win, net cash = the profit only (the "
        "stake is not returned). On a loss, net cash = 0."
    ),
    "second_chance_token": (
        "A Second Chance / insurance token that triggers on a loss pays back a bonus bet, not "
        "cash. Book the ticket as a full cash LOSS (net = -stake), never as a push, and mention "
        "the bonus bet in notes."
    ),
}


def lookup_rule(topic):
    key = (topic or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in RULES:
        return {"topic": key, "rule": RULES[key]}
    return {"error": "UNKNOWN_TOPIC", "available_topics": sorted(RULES)}

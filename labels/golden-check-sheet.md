# Golden check sheet

Selected: S037, S052, S094, S157, S177, S123, S017, S071, S010, S175, S073, S081, S121, S046, S143, S122, S106, S074, S160, S055, S170, S014, S104, S099, S077, S063, S048, S028, S069, S057

## S037

intent: double_chance
segment: single-cash
difficulty: easy

### Ticket

{
 "book": "FanDuel",
 "bet_type": "Prop",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+200",
 "printed_payout": 15.0,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw/Away",
   "market": "Double Chance",
   "leg_price_american": "+200",
   "fixture": "Republic of Ireland v Austria",
   "home": "Republic of Ireland",
   "away": "Austria",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-01 14:45",
   "market_wording_on_slip": "Republic of Ireland Draw/Away Double Chance"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401861094","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"double_chance"}

### Key

Leg 1 must be W: regulation 2-2 (score_regulation_90); rule double_chance. Never L.
Ticket must be WIN with net 10.0.

### Evidence

Leg 1: W (90' Republic of Ireland 2-2 Austria)
Ticket: WIN net 10.0

## S052

intent: draw_no_bet
segment: single-cash
difficulty: easy

### Ticket

{
 "book": "Caesars",
 "bet_type": "DNB",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "-150",
 "printed_payout": 16.67,
 "slip_text": "French Ligue 1 DNB",
 "legs": [
  {
   "leg": 1,
   "selection": "Lens",
   "market": "Draw No Bet",
   "leg_price_american": "-150",
   "fixture": "Lens v Lyon",
   "home": "Lens",
   "away": "Lyon",
   "league": "French Ligue 1",
   "kickoff_et": "2026-10-09 14:45",
   "market_wording_on_slip": "Lens Draw No Bet -150"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401876447","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"draw_no_bet"}

### Key

Leg 1 must be W: regulation 2-1 (score_regulation_90); rule draw_no_bet. Never L.
Ticket must be WIN with net 6.67.

### Evidence

Leg 1: W (90' Lens 2-1 Lyon)
Ticket: WIN net 6.67

## S094

intent: moneyline_3way
segment: single-second_chance
difficulty: medium

### Ticket

{
 "book": "Caesars",
 "bet_type": "ML",
 "stake": 10,
 "stake_kind": "second_chance",
 "ticket_price_american": "-200",
 "slip_text": "Denmark v Portugal",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw",
   "market": "Money Line 3-Way",
   "leg_price_american": "-200",
   "fixture": "Denmark v Portugal",
   "home": "Denmark",
   "away": "Portugal",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-01 14:45",
   "market_wording_on_slip": "Denmark ML 3-Way"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"second_chance_token"}
{"event_id":"401861096","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}

### Key

Leg 1 must be L: regulation 2-4 (score_regulation_90); rule moneyline_3way. Never W.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: L (90' Denmark 2-4 Portugal)
Ticket: LOSS net -10.0

## S157

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Fanatics",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+1905",
 "printed_payout": 100.25,
 "slip_text": "Parlay Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "AFC Bournemouth Total Cards",
   "line": 0.5,
   "leg_price_american": "+250",
   "fixture": "Manchester City v AFC Bournemouth",
   "home": "Manchester City",
   "away": "AFC Bournemouth",
   "league": "English Premier League",
   "kickoff_et": "2026-08-23 09:00",
   "market_wording_on_slip": "Manchester City Total Cards, Under 0.5"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "Total Cards",
   "line": 2.5,
   "leg_price_american": "-110",
   "fixture": "Chicago Fire FC v New York City FC",
   "home": "Chicago Fire FC",
   "away": "New York City FC",
   "league": "MLS",
   "kickoff_et": "2026-10-10 14:30",
   "market_wording_on_slip": "New York City FC vs Chicago Fire FC, Under 2.5 Total Cards"
  },
  {
   "leg": 3,
   "selection": "Under",
   "market": "Villarreal Total Cards",
   "line": 1.5,
   "leg_price_american": "+200",
   "fixture": "Real Madrid v Villarreal",
   "home": "Real Madrid",
   "away": "Villarreal",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-10 15:00",
   "market_wording_on_slip": "Villarreal Total Cards, Under 1.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401879320","fact":"team_stats.yellow_cards","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"cards"}
{"event_id":"761846","fact":"team_stats.yellow_cards","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"cards"}
{"event_id":"401882848","fact":"team_stats.yellow_cards","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"cards"}

### Key

Leg 1 must be L: yellow cards 1-2 (team_stats.yellow_cards); rule cards. Never W. MOOT also passes once another leg is L.
Leg 2 must be NEEDS_HUMAN: yellow cards 2-0 (team_stats.yellow_cards); rule cards. MOOT also passes once another leg is L.
Leg 3 must be L: yellow cards 5-2 (team_stats.yellow_cards); rule cards. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -5.0.

### Evidence

Leg 1: L (cards 2)
Leg 2: NEEDS_HUMAN (card list disagrees with team_stats and the slip defines no counting scheme)
Leg 3: L (cards 2)
Ticket: LOSS net -5.0

## S177

intent: shots_on_target
segment: single-cash
difficulty: medium

### Ticket

{
 "book": "theScore Bet",
 "bet_type": "Prop",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+150",
 "printed_payout": 25.0,
 "slip_text": "Sunderland vs Brighton",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "Sunderland Team Total Shots on Target",
   "line": 4.5,
   "leg_price_american": "+150",
   "fixture": "Sunderland v Brighton & Hove Albion",
   "home": "Sunderland",
   "away": "Brighton & Hove Albion",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 10:00",
   "market_wording_on_slip": "Sunderland Team Total Shots on Target, Under 4.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401878772","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}

### Key

Leg 1 must be W: shots on target 3-4 (team_stats.shots_on_target); rule shots_on_target. Never L.
Ticket must be WIN with net 15.0.

### Evidence

Leg 1: W (shots on target 3)
Ticket: WIN net 15.0

## S123

intent: to_advance
segment: single-cash
difficulty: medium

### Ticket

{
 "book": "DraftKings",
 "bet_type": "Prop",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "-200",
 "printed_payout": 7.5,
 "slip_text": "Columbus Crew To Advance",
 "legs": [
  {
   "leg": 1,
   "selection": "Columbus Crew",
   "market": "To Advance",
   "leg_price_american": "-200",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew To Advance"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401863611","fact":"penalty_shootout","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"to_advance"}

### Key

Leg 1 must be W: shootout 3.0-2.0 (penalty_shootout); rule to_advance. Never L.
Ticket must be WIN with net 2.5.

### Evidence

Leg 1: W (shootout 3.0-2.0)
Ticket: WIN net 2.5

## S017

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "BetMGM",
 "bet_type": "Parlay",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+1025",
 "printed_payout": 112.5,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Over",
   "market": "England Total Cards",
   "line": 0.5,
   "leg_price_american": "+150",
   "fixture": "England v Czechia",
   "home": "England",
   "away": "Czechia",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-06 14:45",
   "market_wording_on_slip": "England Total Cards, Over 0.5"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "Total Cards",
   "line": 2.5,
   "leg_price_american": "+200",
   "fixture": "Sunderland v Brighton & Hove Albion",
   "home": "Sunderland",
   "away": "Brighton & Hove Albion",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 10:00",
   "market_wording_on_slip": "Total Cards, Under 2.5"
  },
  {
   "leg": 3,
   "selection": "Under",
   "market": "Juventus Total Cards",
   "line": 0.5,
   "leg_price_american": "-200",
   "fixture": "Cagliari v Juventus",
   "home": "Cagliari",
   "away": "Juventus",
   "league": "Italian Serie A",
   "kickoff_et": "2026-10-11 14:45",
   "market_wording_on_slip": "Juventus Total Cards, Under 0.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861142","fact":"team_stats.yellow_cards","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"cards"}
{"event_id":"401878772","fact":"team_stats.yellow_cards","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"cards"}
{"event_id":"401874764","fact":"team_stats.yellow_cards","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"cards"}

### Key

Leg 1 must be W: yellow cards 1-2 (team_stats.yellow_cards); rule cards. Never L. MOOT also passes once another leg is L.
Leg 2 must be W: yellow cards 0-1 (team_stats.yellow_cards); rule cards. Never L. MOOT also passes once another leg is L.
Leg 3 must be L: yellow cards 2-1 (team_stats.yellow_cards); rule cards. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: W (cards 1)
Leg 2: W (cards 2)
Leg 3: L (cards 1)
Ticket: LOSS net -10.0

## S071

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "theScore Bet",
 "bet_type": "Parlay",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "+650",
 "printed_payout": 150.0,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Vitinha",
   "market": "Anytime Goalscorer",
   "leg_price_american": "+400",
   "fixture": "Denmark v Portugal",
   "home": "Denmark",
   "away": "Portugal",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-01 14:45",
   "market_wording_on_slip": "Portugal Anytime Goalscorer; Vitinha"
  },
  {
   "leg": 2,
   "selection": "Danijel Sturm",
   "market": "First Goal Scorer",
   "leg_price_american": "-200",
   "fixture": "Scotland v Slovenia",
   "home": "Scotland",
   "away": "Slovenia",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-06 14:45",
   "market_wording_on_slip": "Scotland First Goal Scorer; Danijel Sturm"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861096","fact":"goals","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"goalscorer"}
{"event_id":"401861143","fact":"goals","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"goalscorer"}

### Key

Leg 1 must be W: goals João Cancelo, Mikkel Damsgaard, Gonçalo Ramos, Rasmus Højlund, Vitinha, João Félix (goals); rule goalscorer. Never L. MOOT also passes once another leg is L.
Leg 2 must be L: goals Ryan Christie, Aljosa Matko, Danijel Sturm (goals); rule goalscorer. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -20.0.

### Evidence

Leg 1: W (scorers ['João Cancelo', 'Mikkel Damsgaard', 'Gonçalo Ramos', 'Rasmus Højlund', 'Vitinha', 'João Félix'])
Leg 2: L (first goal Ryan Christie)
Ticket: LOSS net -20.0

## S010

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "DraftKings",
 "bet_type": "Parlay",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "+2350",
 "printed_payout": 490.0,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "No",
   "market": "BTTS",
   "leg_price_american": "+250",
   "fixture": "Real Madrid v Villarreal",
   "home": "Real Madrid",
   "away": "Villarreal",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-10 15:00",
   "market_wording_on_slip": "Real Madrid vs Villarreal, BTTS, No"
  },
  {
   "leg": 2,
   "selection": "Yes",
   "market": "Both teams to score",
   "leg_price_american": "+100",
   "fixture": "Arsenal v Leeds United",
   "home": "Arsenal",
   "away": "Leeds United",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 07:30",
   "market_wording_on_slip": "Arsenal vs Leeds United, Both teams to score, Yes"
  },
  {
   "leg": 3,
   "selection": "Yes",
   "market": "BTTS",
   "leg_price_american": "+250",
   "fixture": "Portugal v Norway",
   "home": "Portugal",
   "away": "Norway",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-04 14:45",
   "market_wording_on_slip": "Portugal vs Norway, BTTS, Yes"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401882848","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"btts"}
{"event_id":"401879268","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"btts"}
{"event_id":"401861126","fact":"score_regulation_90","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"btts"}

### Key

Leg 1 must be W: regulation 1-0 (score_regulation_90); rule btts. Never L.
Leg 2 must be W: regulation 2-1 (score_regulation_90); rule btts. Never L.
Leg 3 must be W: regulation 2-1 (score_regulation_90); rule btts. Never L.
Ticket must be WIN with net 470.0.

### Evidence

Leg 1: W (90' Real Madrid 1-0 Villarreal)
Leg 2: W (90' Arsenal 2-1 Leeds United)
Leg 3: W (90' Portugal 2-1 Norway)
Ticket: WIN net 470.0

## S175

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Caesars",
 "bet_type": "Parlay",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+500",
 "printed_payout": 60.0,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Malik Tillman",
   "market": "Player Shots on Target",
   "leg_price_american": "+100",
   "fixture": "United States v Mexico",
   "home": "United States",
   "away": "Mexico",
   "league": "International Friendly",
   "kickoff_et": "2026-10-03 22:00",
   "market_wording_on_slip": "United States vs Mexico, Player Shots on Target, Malik Tillman"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "Arsenal Shots on Target",
   "line": 0.5,
   "leg_price_american": "+200",
   "fixture": "Arsenal v Leeds United",
   "home": "Arsenal",
   "away": "Leeds United",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 07:30",
   "market_wording_on_slip": "Arsenal vs Leeds United, Arsenal Shots on Target, Under 0.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401905202","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}
{"event_id":"401879268","fact":"team_stats.shots_on_target","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"shots_on_target"}

### Key

Leg 1 must be NEEDS_HUMAN: shots on target 4-1 (team_stats.shots_on_target); rule shots_on_target. MOOT also passes once another leg is L.
Leg 2 must be L: shots on target 6-5 (team_stats.shots_on_target); rule shots_on_target. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: NEEDS_HUMAN (player shots on target are not in the facts)
Leg 2: L (shots on target 6)
Ticket: LOSS net -10.0

## S073

intent: moneyline_3way
segment: single-cash
difficulty: easy

### Ticket

{
 "book": "FanDuel",
 "bet_type": "ML",
 "stake": 25,
 "stake_kind": "cash",
 "ticket_price_american": "+250",
 "printed_payout": 87.5,
 "slip_text": "Bet Slip",
 "legs": [
  {
   "leg": 1,
   "selection": "Real Betis",
   "market": "Match Result",
   "leg_price_american": "+250",
   "fixture": "Real Betis v Osasuna",
   "home": "Real Betis",
   "away": "Osasuna",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-11 12:30",
   "market_wording_on_slip": "Real Betis vs Osasuna, Match Result, Real Betis +250"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401882855","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}

### Key

Leg 1 must be W: regulation 5-2 (score_regulation_90); rule moneyline_3way. Never L.
Ticket must be WIN with net 62.5.

### Evidence

Leg 1: W (90' Real Betis 5-2 Osasuna)
Ticket: WIN net 62.5

## S081

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Fanatics",
 "bet_type": "Parlay",
 "stake": 25,
 "stake_kind": "cash",
 "ticket_price_american": "+1650",
 "printed_payout": 437.5,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw",
   "market": "1X2 Moneyline",
   "leg_price_american": "+400",
   "fixture": "Denmark v Portugal",
   "home": "Denmark",
   "away": "Portugal",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-01 14:45",
   "market_wording_on_slip": "DEN vs POR, 1X2 Moneyline, Draw"
  },
  {
   "leg": 2,
   "selection": "Sevilla",
   "market": "Match Result",
   "leg_price_american": "+250",
   "fixture": "Sevilla v Rayo Vallecano",
   "home": "Sevilla",
   "away": "Rayo Vallecano",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-08-15 15:30",
   "market_wording_on_slip": "SEV vs RAY, Match Result, Sevilla"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861096","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}
{"event_id":"401882918","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"moneyline_3way"}

### Key

Leg 1 must be L: regulation 2-4 (score_regulation_90); rule moneyline_3way. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: regulation 2-1 (score_regulation_90); rule moneyline_3way. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -25.0.

### Evidence

Leg 1: L (90' Denmark 2-4 Portugal)
Leg 2: W (90' Sevilla 2-1 Rayo Vallecano)
Ticket: LOSS net -25.0

## S121

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Caesars",
 "bet_type": "SGP",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+855",
 "printed_payout": 95.5,
 "slip_text": "Columbus Crew Multi",
 "legs": [
  {
   "leg": 1,
   "selection": "Columbus Crew",
   "market": "To Advance",
   "leg_price_american": "+400",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew To Advance +400"
  },
  {
   "leg": 2,
   "selection": "Pumas UNAM",
   "market": "To Qualify",
   "leg_price_american": "-110",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Pumas UNAM To Qualify -110"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401863611","fact":"penalty_shootout","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"to_advance"}
{"event_id":"401863611","fact":"penalty_shootout","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"to_advance"}

### Key

Leg 1 must be W: shootout 3.0-2.0 (penalty_shootout); rule to_advance. Never L. MOOT also passes once another leg is L.
Leg 2 must be L: shootout 3.0-2.0 (penalty_shootout); rule to_advance. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: W (shootout 3.0-2.0)
Leg 2: L (shootout 3.0-2.0)
Ticket: LOSS net -10.0

## S046

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Caesars",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+186",
 "printed_payout": 14.3,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Seattle Sounders FC",
   "market": "Draw No Bet",
   "leg_price_american": "-200",
   "fixture": "Seattle Sounders FC v Sporting Kansas City",
   "home": "Seattle Sounders FC",
   "away": "Sporting Kansas City",
   "league": "MLS",
   "kickoff_et": "2026-10-01 21:30",
   "market_wording_on_slip": "Seattle Sounders FC Draw No Bet -200"
  },
  {
   "leg": 2,
   "selection": "Alavés",
   "market": "Draw No Bet",
   "leg_price_american": "-110",
   "fixture": "Rayo Vallecano v Alavés",
   "home": "Rayo Vallecano",
   "away": "Alavés",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-08-20 15:00",
   "market_wording_on_slip": "Rayo Vallecano vs Alavés, Draw No Bet -110"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"761798","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"draw_no_bet"}
{"event_id":"401882908","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"draw_no_bet"}

### Key

Leg 1 must be W: regulation 2-1 (score_regulation_90); rule draw_no_bet. Never L.
Leg 2 must be P: regulation 1-1 (score_regulation_90); rule draw_no_bet.
Ticket must be NEEDS_HUMAN with net null.

### Evidence

Leg 1: W (90' Seattle Sounders FC 2-1 Sporting Kansas City)
Leg 2: P (90' Rayo Vallecano 1-1 Alavés)
Ticket: NEEDS_HUMAN net null

## S143

intent: moneyline_3way
segment: single-cash
difficulty: hard

### Ticket

{
 "book": "BetMGM",
 "bet_type": "ML",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "-110",
 "printed_payout": 19.09,
 "slip_text": "Multi-Leg Soccer Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw",
   "market": "1X2 Moneyline",
   "leg_price_american": "-110",
   "fixture": "Aston Villa v Fenerbahce",
   "home": "Aston Villa",
   "away": "Fenerbahce",
   "league": "UEFA Champions League",
   "kickoff_et": "2026-10-14 15:00",
   "market_wording_on_slip": "Aston Villa vs Fenerbahce, UEFA Champions League, Draw 1X2 Moneyline"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401915409","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}
{"kind":"rule","leg":1,"topic":"unsettled"}

### Key

Leg 1 must be OPEN: no regulation score (score_regulation_90); rule moneyline_3way, unsettled.
Ticket must be UNSETTLED with net null.

### Evidence

Leg 1: OPEN (status STATUS_SCHEDULED)
Ticket: UNSETTLED net null

## S122

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Fanatics",
 "bet_type": "SGP",
 "stake": 25,
 "stake_kind": "cash",
 "ticket_price_american": "+1150",
 "printed_payout": 312.5,
 "slip_text": "Multi Leg Soccer Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Pumas UNAM",
   "market": "To Qualify",
   "leg_price_american": "+150",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew To Qualify +150 Pumas UNAM"
  },
  {
   "leg": 2,
   "selection": "Pumas UNAM",
   "market": "To Advance",
   "leg_price_american": "+400",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Pumas UNAM To Advance +400 Pumas UNAM"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401863611","fact":"penalty_shootout","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"to_advance"}
{"event_id":"401863611","fact":"penalty_shootout","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"to_advance"}

### Key

Leg 1 must be L: shootout 3.0-2.0 (penalty_shootout); rule to_advance. Never W. MOOT also passes once another leg is L.
Leg 2 must be L: shootout 3.0-2.0 (penalty_shootout); rule to_advance. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -25.0.

### Evidence

Leg 1: L (shootout 3.0-2.0)
Leg 2: L (shootout 3.0-2.0)
Ticket: LOSS net -25.0

## S106

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "DraftKings",
 "bet_type": "Parlay",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+775",
 "printed_payout": 87.5,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "Osasuna Shots on Target",
   "line": 1.5,
   "leg_price_american": "-200",
   "fixture": "Real Betis v Osasuna",
   "home": "Real Betis",
   "away": "Osasuna",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-11 12:30",
   "market_wording_on_slip": "Real Betis vs Osasuna, Osasuna Shots on Target Under 1.5"
  },
  {
   "leg": 2,
   "selection": "Luis Romo",
   "market": "Player Shots on Target",
   "leg_price_american": "-150",
   "fixture": "United States v Mexico",
   "home": "United States",
   "away": "Mexico",
   "league": "International Friendly",
   "kickoff_et": "2026-10-03 22:00",
   "market_wording_on_slip": "United States vs Mexico, Luis Romo Player Shots on Target"
  },
  {
   "leg": 3,
   "selection": "Under",
   "market": "Pumas UNAM Team Total Shots on Target",
   "line": 4.5,
   "leg_price_american": "+250",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew vs Pumas UNAM, Pumas UNAM Team Total Shots on Target Under 4.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401882855","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}
{"event_id":"401905202","fact":"team_stats.shots_on_target","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"shots_on_target"}
{"event_id":"401863611","fact":"team_stats.shots_on_target","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"shots_on_target"}

### Key

Leg 1 must be L: shots on target 7-5 (team_stats.shots_on_target); rule shots_on_target. Never W. MOOT also passes once another leg is L.
Leg 2 must be NEEDS_HUMAN: shots on target 4-1 (team_stats.shots_on_target); rule shots_on_target. MOOT also passes once another leg is L.
Leg 3 must be W: shots on target 3-3 (team_stats.shots_on_target); rule shots_on_target. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: L (shots on target 5)
Leg 2: NEEDS_HUMAN (player shots on target are not in the facts)
Leg 3: W (shots on target 3)
Ticket: LOSS net -10.0

## S074

intent: moneyline_3way
segment: single-cash
difficulty: easy

### Ticket

{
 "book": "theScore Bet",
 "bet_type": "ML",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "-110",
 "printed_payout": 38.18,
 "slip_text": "Manchester City vs AFC Bournemouth",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw",
   "market": "Full Time result",
   "leg_price_american": "-110",
   "fixture": "Manchester City v AFC Bournemouth",
   "home": "Manchester City",
   "away": "AFC Bournemouth",
   "league": "English Premier League",
   "kickoff_et": "2026-08-23 09:00",
   "market_wording_on_slip": "Manchester City vs AFC Bournemouth, Full Time result, Draw"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"event_id":"401879320","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}

### Key

Leg 1 must be L: regulation 2-1 (score_regulation_90); rule moneyline_3way. Never W.
Ticket must be LOSS with net -20.0.

### Evidence

Leg 1: L (90' Manchester City 2-1 AFC Bournemouth)
Ticket: LOSS net -20.0

## S160

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "BetMGM",
 "bet_type": "Parlay",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "+1722",
 "printed_payout": 364.4,
 "slip_text": "Parlay Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Over",
   "market": "1st Half Total Goals",
   "line": 2.5,
   "leg_price_american": "-110",
   "fixture": "Ukraine v Northern Ireland",
   "home": "Ukraine",
   "away": "Northern Ireland",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-02 14:45",
   "market_wording_on_slip": "Ukraine 1st Half Total Goals Over 2.5"
  },
  {
   "leg": 2,
   "selection": "Over",
   "market": "First Half Total Goals",
   "line": 2.5,
   "leg_price_american": "-110",
   "fixture": "Troyes v Marseille",
   "home": "Troyes",
   "away": "Marseille",
   "league": "French Ligue 1",
   "kickoff_et": "2026-10-11 14:45",
   "market_wording_on_slip": "Troyes First Half Total Goals Over 2.5"
  },
  {
   "leg": 3,
   "selection": "Under",
   "market": "First Half Total Goals",
   "line": 0.5,
   "leg_price_american": "+400",
   "fixture": "Liverpool v Manchester City",
   "home": "Liverpool",
   "away": "Manchester City",
   "league": "English Premier League",
   "kickoff_et": "2026-10-11 11:30",
   "market_wording_on_slip": "Liverpool vs Manchester City, First Half Total Goals Under 0.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861106","fact":"score_halftime","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"first_half"}
{"kind":"rule","leg":1,"topic":"totals"}
{"event_id":"401876440","fact":"score_halftime","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"first_half"}
{"kind":"rule","leg":2,"topic":"totals"}
{"event_id":"401879264","fact":"score_halftime","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"first_half"}
{"kind":"rule","leg":3,"topic":"totals"}

### Key

Leg 1 must be L: halftime 0-2 (score_halftime); rule first_half, totals. Never W. MOOT also passes once another leg is L.
Leg 2 must be L: halftime 0-0 (score_halftime); rule first_half, totals. Never W. MOOT also passes once another leg is L.
Leg 3 must be W: halftime 0-0 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -20.0.

### Evidence

Leg 1: L (HT 0-2)
Leg 2: L (HT 0-0)
Leg 3: W (HT 0-0)
Ticket: LOSS net -20.0

## S055

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Fanatics",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+695",
 "printed_payout": 39.75,
 "slip_text": "MLS Parlay",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "1st Half Total Goals",
   "line": 1.5,
   "leg_price_american": "-150",
   "fixture": "Seattle Sounders FC v Sporting Kansas City",
   "home": "Seattle Sounders FC",
   "away": "Sporting Kansas City",
   "league": "MLS",
   "kickoff_et": "2026-10-01 21:30",
   "market_wording_on_slip": "Seattle Sounders FC v Sporting Kansas City, 1st Half Total Goals, Under 1.5"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "1st Half Total Goals",
   "line": 2.5,
   "leg_price_american": "-110",
   "fixture": "Paris Saint-Germain v Aston Villa",
   "home": "Paris Saint-Germain",
   "away": "Aston Villa",
   "league": "UEFA Super Cup",
   "kickoff_et": "2026-08-12 15:00",
   "market_wording_on_slip": "Paris Saint-Germain v Aston Villa, 1st Half Total Goals, Under 2.5"
  },
  {
   "leg": 3,
   "selection": "Over",
   "market": "First Half Total Goals",
   "line": 1.5,
   "leg_price_american": "+150",
   "fixture": "Romania v Sweden",
   "home": "Romania",
   "away": "Sweden",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-05 14:45",
   "market_wording_on_slip": "Romania v Sweden, First Half Total Goals, Over 1.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"761798","fact":"score_halftime","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"first_half"}
{"kind":"rule","leg":1,"topic":"totals"}
{"event_id":"401873624","fact":"score_halftime","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"first_half"}
{"kind":"rule","leg":2,"topic":"totals"}
{"event_id":"401861128","fact":"score_halftime","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"first_half"}
{"kind":"rule","leg":3,"topic":"totals"}

### Key

Leg 1 must be W: halftime 0-1 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Leg 2 must be W: halftime 1-1 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Leg 3 must be L: halftime 0-1 (score_halftime); rule first_half, totals. Never W. MOOT also passes once another leg is L.
Ticket must be LOSS with net -5.0.

### Evidence

Leg 1: W (HT 0-1)
Leg 2: W (HT 1-1)
Leg 3: L (HT 0-1)
Ticket: LOSS net -5.0

## S170

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "theScore Bet",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+733",
 "printed_payout": 41.65,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "Málaga Team Total Shots on Target",
   "line": 1.5,
   "leg_price_american": "-150",
   "fixture": "Málaga v Espanyol",
   "home": "Málaga",
   "away": "Espanyol",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-09 15:00",
   "market_wording_on_slip": "Málaga vs Espanyol, Spanish LALIGA, Málaga Team Total Shots on Target Under 1.5"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "Schalke 04 Team Total Shots on Target",
   "line": 2.5,
   "leg_price_american": "+400",
   "fixture": "Schalke 04 v Bayern Munich",
   "home": "Schalke 04",
   "away": "Bayern Munich",
   "league": "German Bundesliga",
   "kickoff_et": "2026-09-05 12:30",
   "market_wording_on_slip": "Schalke 04 vs Bayern Munich, German Bundesliga, Schalke 04 Team Total Shots on Target Under 2.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401882851","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}
{"event_id":"401884801","fact":"team_stats.shots_on_target","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"shots_on_target"}

### Key

Leg 1 must be L: shots on target 7-4 (team_stats.shots_on_target); rule shots_on_target. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: shots on target 1-5 (team_stats.shots_on_target); rule shots_on_target. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -5.0.

### Evidence

Leg 1: L (shots on target 7)
Leg 2: W (shots on target 1)
Ticket: LOSS net -5.0

## S014

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Fanatics",
 "bet_type": "Parlay",
 "stake": 25,
 "stake_kind": "cash",
 "ticket_price_american": "+425",
 "printed_payout": 131.25,
 "slip_text": "Parlay Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "No",
   "market": "Both Teams To Score",
   "leg_price_american": "-200",
   "fixture": "Chicago Fire FC v New York City FC",
   "home": "Chicago Fire FC",
   "away": "New York City FC",
   "league": "MLS",
   "kickoff_et": "2026-10-10 14:30",
   "market_wording_on_slip": "New York City FC vs Chicago Fire FC, Both Teams To Score, No"
  },
  {
   "leg": 2,
   "selection": "Yes",
   "market": "Both teams to score",
   "leg_price_american": "+250",
   "fixture": "Coventry City v Newcastle United",
   "home": "Coventry City",
   "away": "Newcastle United",
   "league": "English Premier League",
   "kickoff_et": "2026-10-12 15:00",
   "market_wording_on_slip": "Coventry City vs Newcastle United, Both teams to score, Yes"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"761846","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"btts"}
{"event_id":"401879267","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"btts"}

### Key

Leg 1 must be L: regulation 2-1 (score_regulation_90); rule btts. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: regulation 4-1 (score_regulation_90); rule btts. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -25.0.

### Evidence

Leg 1: L (90' Chicago Fire FC 2-1 New York City FC)
Leg 2: W (90' Coventry City 4-1 Newcastle United)
Ticket: LOSS net -25.0

## S104

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "BetMGM",
 "bet_type": "Parlay",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "+650",
 "printed_payout": 150.0,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Over",
   "market": "Borussia Dortmund Team Total Shots on Target",
   "line": 1.5,
   "leg_price_american": "+150",
   "fixture": "VfB Stuttgart v Borussia Dortmund",
   "home": "VfB Stuttgart",
   "away": "Borussia Dortmund",
   "league": "German Bundesliga",
   "kickoff_et": "2026-09-19 12:30",
   "market_wording_on_slip": "Borussia Dortmund Team Total Shots on Target, Over 1.5"
  },
  {
   "leg": 2,
   "selection": "Over",
   "market": "Mexico Shots on Target",
   "line": 3.5,
   "leg_price_american": "+100",
   "fixture": "United States v Mexico",
   "home": "United States",
   "away": "Mexico",
   "league": "International Friendly",
   "kickoff_et": "2026-10-03 22:00",
   "market_wording_on_slip": "Mexico Shots on Target, Over 3.5"
  },
  {
   "leg": 3,
   "selection": "Isaac Romero",
   "market": "Player Shots on Target",
   "leg_price_american": "-200",
   "fixture": "Sevilla v Rayo Vallecano",
   "home": "Sevilla",
   "away": "Rayo Vallecano",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-08-15 15:30",
   "market_wording_on_slip": "Isaac Romero Player Shots on Target, Over"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401884789","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}
{"event_id":"401905202","fact":"team_stats.shots_on_target","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"shots_on_target"}
{"event_id":"401882918","fact":"team_stats.shots_on_target","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"shots_on_target"}

### Key

Leg 1 must be W: shots on target 5-2 (team_stats.shots_on_target); rule shots_on_target. Never L. MOOT also passes once another leg is L.
Leg 2 must be L: shots on target 4-1 (team_stats.shots_on_target); rule shots_on_target. Never W. MOOT also passes once another leg is L.
Leg 3 must be NEEDS_HUMAN: shots on target 4-3 (team_stats.shots_on_target); rule shots_on_target. MOOT also passes once another leg is L.
Ticket must be LOSS with net -20.0.

### Evidence

Leg 1: W (shots on target 2)
Leg 2: L (shots on target 1)
Leg 3: NEEDS_HUMAN (player shots on target are not in the facts)
Ticket: LOSS net -20.0

## S099

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "DraftKings",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+483",
 "printed_payout": 29.15,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "Werder Bremen Shots on Target",
   "line": 3.5,
   "leg_price_american": "-150",
   "fixture": "Borussia Dortmund v Werder Bremen",
   "home": "Borussia Dortmund",
   "away": "Werder Bremen",
   "league": "German Bundesliga",
   "kickoff_et": "2026-10-09 14:30",
   "market_wording_on_slip": "Borussia Dortmund vs Werder Bremen, Werder Bremen Shots on Target, Under 3.5"
  },
  {
   "leg": 2,
   "selection": "Nemanja Maksimovic",
   "market": "Player Shots on Target",
   "leg_price_american": "+250",
   "fixture": "Netherlands v Serbia",
   "home": "Netherlands",
   "away": "Serbia",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-04 14:45",
   "market_wording_on_slip": "Netherlands vs Serbia, Nemanja Maksimovic Player Shots on Target"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401884781","fact":"team_stats.shots_on_target","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"shots_on_target"}
{"event_id":"401861122","fact":"team_stats.shots_on_target","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"shots_on_target"}

### Key

Leg 1 must be L: shots on target 9-4 (team_stats.shots_on_target); rule shots_on_target. Never W. MOOT also passes once another leg is L.
Leg 2 must be NEEDS_HUMAN: shots on target 7-4 (team_stats.shots_on_target); rule shots_on_target. MOOT also passes once another leg is L.
Ticket must be LOSS with net -5.0.

### Evidence

Leg 1: L (shots on target 4)
Leg 2: NEEDS_HUMAN (player shots on target are not in the facts)
Ticket: LOSS net -5.0

## S077

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "FanDuel",
 "bet_type": "Parlay",
 "stake": 20,
 "stake_kind": "cash",
 "ticket_price_american": "+855",
 "printed_payout": 191.0,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Draw",
   "market": "Full Time result",
   "leg_price_american": "-110",
   "fixture": "Real Betis v Osasuna",
   "home": "Real Betis",
   "away": "Osasuna",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-11 12:30",
   "market_wording_on_slip": "Real Betis vs Osasuna, Full Time result, Draw"
  },
  {
   "leg": 2,
   "selection": "Draw",
   "market": "1X2 Moneyline",
   "leg_price_american": "+150",
   "fixture": "Barcelona v Getafe",
   "home": "Barcelona",
   "away": "Getafe",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-10 12:30",
   "market_wording_on_slip": "Barcelona vs Getafe, 1X2 Moneyline, Draw"
  },
  {
   "leg": 3,
   "selection": "Brighton & Hove Albion",
   "market": "Match Result",
   "leg_price_american": "+100",
   "fixture": "Sunderland v Brighton & Hove Albion",
   "home": "Sunderland",
   "away": "Brighton & Hove Albion",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 10:00",
   "market_wording_on_slip": "Sunderland vs Brighton & Hove Albion, Match Result, Brighton & Hove Albion"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401882855","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"moneyline_3way"}
{"event_id":"401882853","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"moneyline_3way"}
{"event_id":"401878772","fact":"score_regulation_90","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"moneyline_3way"}

### Key

Leg 1 must be L: regulation 5-2 (score_regulation_90); rule moneyline_3way. Never W. MOOT also passes once another leg is L.
Leg 2 must be L: regulation 3-0 (score_regulation_90); rule moneyline_3way. Never W. MOOT also passes once another leg is L.
Leg 3 must be W: regulation 0-2 (score_regulation_90); rule moneyline_3way. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -20.0.

### Evidence

Leg 1: L (90' Real Betis 5-2 Osasuna)
Leg 2: L (90' Barcelona 3-0 Getafe)
Leg 3: W (90' Sunderland 0-2 Brighton & Hove Albion)
Ticket: LOSS net -20.0

## S063

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Caesars",
 "bet_type": "Parlay",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+377",
 "printed_payout": 47.7,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Slovenia",
   "market": "First team to score",
   "leg_price_american": "+150",
   "fixture": "Scotland v Slovenia",
   "home": "Scotland",
   "away": "Slovenia",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-06 14:45",
   "market_wording_on_slip": "Scotland First team to score Slovenia"
  },
  {
   "leg": 2,
   "selection": "Manchester City",
   "market": "2-Way Handicap",
   "line": -1.0,
   "leg_price_american": "-110",
   "fixture": "Liverpool v Manchester City",
   "home": "Liverpool",
   "away": "Manchester City",
   "league": "English Premier League",
   "kickoff_et": "2026-10-11 11:30",
   "market_wording_on_slip": "Manchester City 2-Way Handicap -1.0"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861143","fact":"goals","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"general"}
{"event_id":"401879264","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"general"}

### Key

Leg 1 must be L: goals Ryan Christie, Aljosa Matko, Danijel Sturm (goals); rule general. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: regulation 0-3 (score_regulation_90); rule general. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: L (first goal {'min': "31'", 'team': 'Scotland', 'player': 'Ryan Christie', 'kind': 'Goal'})
Leg 2: W (90' Liverpool 0-3 Manchester City)
Ticket: LOSS net -10.0

## S048

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "BetRivers",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+5150",
 "printed_payout": 262.5,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Espanyol",
   "market": "Draw No Bet",
   "leg_price_american": "+250",
   "fixture": "Málaga v Espanyol",
   "home": "Málaga",
   "away": "Espanyol",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-09 15:00",
   "market_wording_on_slip": "Málaga Draw No Bet +250 Espanyol"
  },
  {
   "leg": 2,
   "selection": "Barcelona",
   "market": "Draw No Bet",
   "leg_price_american": "+200",
   "fixture": "Barcelona v Getafe",
   "home": "Barcelona",
   "away": "Getafe",
   "league": "Spanish LALIGA",
   "kickoff_et": "2026-10-10 12:30",
   "market_wording_on_slip": "Barcelona Draw No Bet +200 Getafe"
  },
  {
   "leg": 3,
   "selection": "Columbus Crew",
   "market": "Draw No Bet",
   "leg_price_american": "+400",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew Draw No Bet +400 Pumas UNAM"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401882851","fact":"score_regulation_90","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"draw_no_bet"}
{"event_id":"401882853","fact":"score_regulation_90","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"draw_no_bet"}
{"event_id":"401863611","fact":"score_regulation_90","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"draw_no_bet"}

### Key

Leg 1 must be P: regulation 1-1 (score_regulation_90); rule draw_no_bet.
Leg 2 must be W: regulation 3-0 (score_regulation_90); rule draw_no_bet. Never L.
Leg 3 must be P: regulation 1-1 (score_regulation_90); rule draw_no_bet.
Ticket must be NEEDS_HUMAN with net null.

### Evidence

Leg 1: P (90' Málaga 1-1 Espanyol)
Leg 2: W (90' Barcelona 3-0 Getafe)
Leg 3: P (90' Columbus Crew 1-1 Pumas UNAM)
Ticket: NEEDS_HUMAN net null

## S028

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "Caesars",
 "bet_type": "Parlay",
 "stake": 5,
 "stake_kind": "cash",
 "ticket_price_american": "+600",
 "printed_payout": 35.0,
 "slip_text": "Multi Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Under",
   "market": "Columbus Crew Total Corners",
   "line": 4.5,
   "leg_price_american": "+250",
   "fixture": "Columbus Crew v Pumas UNAM",
   "home": "Columbus Crew",
   "away": "Pumas UNAM",
   "league": "Leagues Cup",
   "kickoff_et": "2026-08-11 19:30",
   "market_wording_on_slip": "Columbus Crew Total Corners Under 4.5"
  },
  {
   "leg": 2,
   "selection": "Under",
   "market": "Total Corners",
   "line": 9.5,
   "leg_price_american": "+100",
   "fixture": "Republic of Ireland v Austria",
   "home": "Republic of Ireland",
   "away": "Austria",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-01 14:45",
   "market_wording_on_slip": "Republic of Ireland v Austria Total Corners Under 9.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401863611","fact":"team_stats.corners","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"corners"}
{"event_id":"401861094","fact":"team_stats.corners","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"corners"}

### Key

Leg 1 must be L: corners 10-3 (team_stats.corners); rule corners. Never W. MOOT also passes once another leg is L.
Leg 2 must be W: corners 3-5 (team_stats.corners); rule corners. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -5.0.

### Evidence

Leg 1: L (corners H10-A3 (home))
Leg 2: W (corners H3-A5 (match))
Ticket: LOSS net -5.0

## S069

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "theScore Bet",
 "bet_type": "Parlay",
 "stake": 25,
 "stake_kind": "cash",
 "ticket_price_american": "+500",
 "printed_payout": 150.0,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "James Justin",
   "market": "First Goal Scorer",
   "leg_price_american": "+100",
   "fixture": "Arsenal v Leeds United",
   "home": "Arsenal",
   "away": "Leeds United",
   "league": "English Premier League",
   "kickoff_et": "2026-10-10 07:30",
   "market_wording_on_slip": "Arsenal First Goal Scorer; James Justin"
  },
  {
   "leg": 2,
   "selection": "Marcus Tavernier",
   "market": "First Goal Scorer",
   "leg_price_american": "+200",
   "fixture": "Manchester City v AFC Bournemouth",
   "home": "Manchester City",
   "away": "AFC Bournemouth",
   "league": "English Premier League",
   "kickoff_et": "2026-08-23 09:00",
   "market_wording_on_slip": "Manchester City First Goal Scorer; Marcus Tavernier"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401879268","fact":"goals","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"goalscorer"}
{"event_id":"401879320","fact":"goals","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"goalscorer"}

### Key

Leg 1 must be W: goals James Justin, Riccardo Calafiori, Bruno Guimarães (goals); rule goalscorer. Never L.
Leg 2 must be W: goals Marcus Tavernier, Marc Guéhi, Josko Gvardiol (goals); rule goalscorer. Never L.
Ticket must be WIN with net 125.0.

### Evidence

Leg 1: W (first goal James Justin)
Leg 2: W (first goal Marcus Tavernier)
Ticket: WIN net 125.0

## S057

intent: parlay
segment: parlay-cash
difficulty: hard

### Ticket

{
 "book": "BetRivers",
 "bet_type": "Parlay",
 "stake": 10,
 "stake_kind": "cash",
 "ticket_price_american": "+1067",
 "printed_payout": 116.7,
 "slip_text": "Multi-Bet Ticket",
 "legs": [
  {
   "leg": 1,
   "selection": "Over",
   "market": "1st Half Total Goals",
   "line": 1.5,
   "leg_price_american": "+250",
   "fixture": "Ukraine v Northern Ireland",
   "home": "Ukraine",
   "away": "Northern Ireland",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-02 14:45",
   "market_wording_on_slip": "Ukraine 1st Half Total Goals Over 1.5"
  },
  {
   "leg": 2,
   "selection": "Over",
   "market": "First Half Total Goals",
   "line": 1.5,
   "leg_price_american": "-150",
   "fixture": "Schalke 04 v Bayern Munich",
   "home": "Schalke 04",
   "away": "Bayern Munich",
   "league": "German Bundesliga",
   "kickoff_et": "2026-09-05 12:30",
   "market_wording_on_slip": "Schalke 04 First Half Total Goals Over 1.5"
  },
  {
   "leg": 3,
   "selection": "Over",
   "market": "1st Half Total Goals",
   "line": 0.5,
   "leg_price_american": "+100",
   "fixture": "Spain v Czechia",
   "home": "Spain",
   "away": "Czechia",
   "league": "UEFA Nations League",
   "kickoff_et": "2026-10-03 14:45",
   "market_wording_on_slip": "Spain 1st Half Total Goals Over 0.5"
  }
 ],
 "graded_at_et": "2026-10-14"
}

### Contexts

{"kind":"rule","leg":null,"topic":"parlay_moot"}
{"event_id":"401861106","fact":"score_halftime","kind":"event","leg":1}
{"kind":"rule","leg":1,"topic":"first_half"}
{"kind":"rule","leg":1,"topic":"totals"}
{"event_id":"401884801","fact":"score_halftime","kind":"event","leg":2}
{"kind":"rule","leg":2,"topic":"first_half"}
{"kind":"rule","leg":2,"topic":"totals"}
{"event_id":"401861118","fact":"score_halftime","kind":"event","leg":3}
{"kind":"rule","leg":3,"topic":"first_half"}
{"kind":"rule","leg":3,"topic":"totals"}

### Key

Leg 1 must be W: halftime 0-2 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Leg 2 must be L: halftime 0-0 (score_halftime); rule first_half, totals. Never W. MOOT also passes once another leg is L.
Leg 3 must be W: halftime 2-0 (score_halftime); rule first_half, totals. Never L. MOOT also passes once another leg is L.
Ticket must be LOSS with net -10.0.

### Evidence

Leg 1: W (HT 0-2)
Leg 2: L (HT 0-0)
Leg 3: W (HT 2-0)
Ticket: LOSS net -10.0

"""ESPN public soccer API client.

The eval reads a frozen, pruned copy of the responses (data/espn_frozen.json, see
grader/frozen.py), so a re-run sees exactly the same match facts as the first run even after
scheduled fixtures are played. A URL missing from the frozen file is an error unless
ESPN_LIVE=1, which fetches it and records the raw response in data/espn_cache/ (local only,
not committed); `python3 build_frozen.py` then folds it into the frozen file.
"""
import hashlib
import json
import os
import re
import unicodedata
import urllib.request
from datetime import date, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all"
_DATA = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_DIR = os.path.join(_DATA, "espn_cache")
FROZEN_PATH = os.path.join(_DATA, "espn_frozen.json")
_frozen = None

# Words that carry no identity in club names ("FC Barcelona" == "Barcelona").
STOPWORDS = {
    "fc", "cf", "afc", "sc", "ac", "as", "ssc", "us", "ud", "cd", "rc", "rcd", "sd",
    "club", "de", "del", "la", "the", "calcio", "1", "fk", "sk", "if", "bk", "vfb",
    "vfl", "tsg", "sv", "rb", "olympique", "real", "sporting", "athletic", "atletico",
    "city", "united", "town", "and",
}


def _load_frozen():
    global _frozen
    if _frozen is None:
        _frozen = json.load(open(FROZEN_PATH)) if os.path.exists(FROZEN_PATH) else {}
    return _frozen


def _get(url):
    frozen = _load_frozen()
    if url in frozen:
        return frozen[url], True
    key = hashlib.sha1(url.encode()).hexdigest()[:20]
    path = os.path.join(CACHE_DIR, key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f), True
    if os.environ.get("ESPN_LIVE") != "1":
        raise RuntimeError("not in the frozen ESPN set (data/espn_frozen.json); set ESPN_LIVE=1 to fetch it")
    os.makedirs(CACHE_DIR, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "settlement-grader-evals/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    with open(path, "w") as f:
        json.dump(data, f)
    index_path = os.path.join(CACHE_DIR, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {}
    index[key] = url
    with open(index_path, "w") as f:
        json.dump(index, f, indent=0)
    return data, False


def _norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _tokens(name):
    return {t for t in _norm(name).split() if t not in STOPWORDS}


def _team_score(query, team):
    """0..1 similarity between a query string and an ESPN team object."""
    q = _norm(query)
    names = [team.get("displayName"), team.get("shortDisplayName"), team.get("name"),
             team.get("abbreviation"), team.get("location")]
    best = 0.0
    for n in filter(None, names):
        nn = _norm(n)
        if q == nn:
            return 1.0
        if q and (q in nn or nn in q) and min(len(q), len(nn)) >= 4:
            best = max(best, 0.9)
        qt, nt = _tokens(query), _tokens(n)
        if qt and nt:
            best = max(best, len(qt & nt) / max(len(qt), 1) * 0.85)
    return best


def scoreboard(day):
    data, _ = _get(f"{BASE}/scoreboard?dates={day.strftime('%Y%m%d')}&limit=400")
    return data.get("events", [])


def find_match(team, opponent=None, date_et=None):
    """Search the ESPN scoreboard around date_et for team (and opponent).

    Returns up to 3 candidates, best first. Searches the day before and after too,
    because ESPN buckets late kickoffs by UTC date.
    """
    d0 = date.fromisoformat(date_et[:10])
    seen, cands = set(), []
    for day in (d0, d0 - timedelta(days=1), d0 + timedelta(days=1)):
        for ev in scoreboard(day):
            if ev["id"] in seen:
                continue
            seen.add(ev["id"])
            comp = ev["competitions"][0]
            sides = {c["homeAway"]: c for c in comp["competitors"]}
            if "home" not in sides or "away" not in sides:
                continue
            h, a = sides["home"]["team"], sides["away"]["team"]
            s_team = max(_team_score(team, h), _team_score(team, a))
            s_opp = max(_team_score(opponent, h), _team_score(opponent, a)) if opponent else 1.0
            score = min(s_team, s_opp)
            if score < 0.5:
                continue
            st = ev["status"]["type"]
            cands.append({
                "score": round(score + (0.05 if day == d0 else 0), 3),
                "event_id": ev["id"],
                "kickoff_utc": ev["date"],
                "league": (ev.get("season") or {}).get("slug") or comp.get("league", {}).get("name"),
                "home": h["displayName"],
                "away": a["displayName"],
                "status": st.get("name"),
                "score_home_away": f"{sides['home'].get('score')}-{sides['away'].get('score')}"
                if st.get("completed") else None,
            })
    cands.sort(key=lambda c: -c["score"])
    for c in cands:
        c.pop("score")
    return cands[:3]


def _stat(team_box, name):
    for s in team_box.get("statistics", []):
        if s.get("name") == name:
            try:
                return int(float(s.get("displayValue")))
            except (TypeError, ValueError):
                return None
    return None


def match_facts(event_id):
    """Compact, model-sized facts for one match."""
    d, _ = _get(f"{BASE}/summary?event={event_id}")
    comp = d["header"]["competitions"][0]
    st = comp["status"]["type"]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    h, a = sides["home"], sides["away"]
    hname, aname = h["team"]["displayName"], a["team"]["displayName"]

    def periods(c):
        return [int(float(x.get("displayValue", 0) or 0)) for x in c.get("linescores", [])]

    hp, ap = periods(h), periods(a)
    facts = {
        "event_id": event_id,
        "competition": d["header"].get("league", {}).get("name"),
        "kickoff_utc": comp.get("date"),
        "home": hname,
        "away": aname,
        "status": st.get("name"),
        "status_detail": st.get("detail"),
        "completed": bool(st.get("completed")),
    }
    if not facts["completed"]:
        facts["note"] = "Match not final. No result available."
        return facts

    facts["score_final"] = f"{h.get('score')}-{a.get('score')}"
    if len(hp) >= 2 and len(ap) >= 2:
        facts["score_halftime"] = f"{hp[0]}-{ap[0]}"
        facts["score_regulation_90"] = f"{hp[0] + hp[1]}-{ap[0] + ap[1]}"
    else:
        facts["score_regulation_90"] = None
    if len(hp) > 2:
        facts["extra_time_played"] = True
    if h.get("shootoutScore") is not None or a.get("shootoutScore") is not None:
        facts["penalty_shootout"] = f"{h.get('shootoutScore')}-{a.get('shootoutScore')}"
    for n in comp.get("notes", []) or []:
        if n.get("headline"):
            facts.setdefault("notes", []).append(n["headline"])

    box = {t["team"]["displayName"]: t for t in d.get("boxscore", {}).get("teams", [])}
    stats = {}
    for label, key in (("corners", "wonCorners"), ("yellow_cards", "yellowCards"),
                       ("red_cards", "redCards"), ("shots_on_target", "shotsOnTarget"),
                       ("total_shots", "totalShots")):
        hv, av = _stat(box.get(hname, {}), key), _stat(box.get(aname, {}), key)
        stats[label] = {"home": hv, "away": av}
    facts["team_stats"] = stats

    goals, cards = [], []
    for k in d.get("keyEvents", []):
        t = (k.get("type") or {}).get("text") or ""
        who = ((k.get("participants") or [{}])[0].get("athlete") or {}).get("displayName")
        team = (k.get("team") or {}).get("displayName")
        minute = (k.get("clock") or {}).get("displayValue")
        if k.get("scoringPlay") or "Goal" in t or t.startswith("Penalty - Scored"):
            if "Shootout" in t:
                continue
            goals.append({"min": minute, "team": team, "player": who, "kind": t})
        elif "Card" in t:
            cards.append({"min": minute, "team": team, "player": who, "kind": t})
    facts["goals"] = goals
    facts["cards"] = cards
    return facts


def team_objects(event_id):
    """Full ESPN team objects (all name variants) for an event — used by the gold checker."""
    d, _ = _get(f"{BASE}/summary?event={event_id}")
    comp = d["header"]["competitions"][0]
    return {c["homeAway"]: c["team"] for c in comp["competitors"]}

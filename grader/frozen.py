"""The frozen ESPN facts the eval runs against.

ESPN's public soccer API is not ours to republish wholesale, so the repo ships a pruned copy:
only the fields the grader reads (team names, scores, status, half-time lines, a few team
stats, goal and card events). `build_frozen.py` makes it from a local raw cache.
"""
TEAM_KEYS = ("displayName", "shortDisplayName", "name", "abbreviation", "location")
STAT_KEYS = ("wonCorners", "yellowCards", "redCards", "shotsOnTarget", "totalShots")


def _pick(d, keys):
    return {k: d[k] for k in keys if isinstance(d, dict) and k in d}


def _status(st):
    t = (st or {}).get("type") or {}
    return {"type": _pick(t, ("name", "detail", "completed"))}


def _competitor(c, extra=()):
    out = _pick(c, ("homeAway", "score") + tuple(extra))
    out["team"] = _pick(c.get("team") or {}, TEAM_KEYS)
    if "linescores" in extra:
        out["linescores"] = [_pick(x, ("displayValue",)) for x in c.get("linescores", [])]
    return out


def slim_scoreboard(data):
    events = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        events.append({
            "id": ev.get("id"), "date": ev.get("date"),
            "season": _pick(ev.get("season") or {}, ("slug",)),
            "status": _status(ev.get("status")),
            "competitions": [{
                "competitors": [_competitor(c) for c in comp.get("competitors", [])],
                "league": _pick(comp.get("league") or {}, ("name",)),
            }],
        })
    return {"events": events}


def slim_summary(data):
    hdr = data.get("header") or {}
    comp = (hdr.get("competitions") or [{}])[0]
    box = []
    for t in (data.get("boxscore") or {}).get("teams", []):
        box.append({"team": _pick(t.get("team") or {}, ("displayName",)),
                    "statistics": [_pick(s, ("name", "displayValue"))
                                   for s in t.get("statistics", []) if s.get("name") in STAT_KEYS]})
    keys = []
    for k in data.get("keyEvents", []):
        parts = k.get("participants") or [{}]
        keys.append({
            "type": _pick(k.get("type") or {}, ("text",)),
            "scoringPlay": k.get("scoringPlay"),
            "participants": [{"athlete": _pick((parts[0] or {}).get("athlete") or {}, ("displayName",))}],
            "team": _pick(k.get("team") or {}, ("displayName",)),
            "clock": _pick(k.get("clock") or {}, ("displayValue",)),
        })
    return {
        "header": {
            "league": _pick(hdr.get("league") or {}, ("name",)),
            "competitions": [{
                "date": comp.get("date"),
                "status": _status(comp.get("status")),
                "competitors": [_competitor(c, ("shootoutScore", "linescores"))
                                for c in comp.get("competitors", [])],
                "notes": [_pick(n, ("headline",)) for n in comp.get("notes", []) or []],
            }],
        },
        "boxscore": {"teams": box},
        "keyEvents": keys,
    }


def slim(url, data):
    return slim_scoreboard(data) if "/scoreboard?" in url else slim_summary(data)

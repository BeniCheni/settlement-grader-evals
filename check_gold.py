#!/usr/bin/env python3
"""Independent code check of the candidate gold labels against ESPN match data.

The log labels were written by the same Claude-in-session grading process we are
evaluating, so they are not independent ground truth. This re-grades every leg it
can from ESPN facts with plain code, and writes a review sheet for Beni:
agreements need a glance, disagreements need a ruling.

Usage: python3 check_gold.py data/candidates.json <review.md>
"""
import json
import re
import sys

from grader import espn
from grader.espn import _team_score


def first_date(s):
    m = re.search(r"\d{4}-\d{2}-\d{2}", s or "")
    return m.group(0) if m else None


def teams_of(leg):
    h, a = leg.get("home"), leg.get("away")
    if h and a:
        return h, a
    parts = re.split(r"\s+(?:v|vs\.?|at)\s+", re.sub(r"\(.*?\)", "", leg.get("fixture") or ""))
    return (parts[0].strip(), parts[1].strip()) if len(parts) >= 2 else (None, None)


def score(s):
    h, a = s.split("-")
    return int(h), int(a)


ALIASES = {"usa": "United States", "nycfc": "New York City FC", "sporting kc": "Sporting Kansas City",
           "man city": "Manchester City", "psg": "Paris Saint-Germain"}


def side(name, facts):
    """'home' / 'away' / None for a team name."""
    name = ALIASES.get((name or "").lower().strip(), name)
    teams = espn.team_objects(facts["event_id"])
    sh, sa = _team_score(name, teams["home"]), _team_score(name, teams["away"])
    if max(sh, sa) < 0.5:
        return None
    return "home" if sh >= sa else "away"


def ou(total, sel, line):
    if line is None:
        return None
    if total == line:
        return "P"
    return "W" if (total > line) == (sel.lower().startswith("o")) else "L"


def auto_grade(leg, f):
    """Return (result, evidence) or (None, reason) when code can't decide."""
    if not f.get("completed"):
        return "OPEN", f"status {f.get('status')}"
    m = (leg.get("market") or "").lower()
    sel = (leg.get("selection") or "").strip()
    line = leg.get("line")
    reg = f.get("score_regulation_90") or f.get("score_final")
    hg, ag = score(reg)
    ev = f"90' {f['home']} {reg} {f['away']}"
    if "half time/" in m or "ht/ft" in m:
        ht_s, ft_s = sel.split("/")
        hh, ha = score(f["score_halftime"])
        def res(x, y, who):
            if who.lower() in ("tie", "draw"):
                return x == y
            sd = side(who, f)
            return (x > y) if sd == "home" else (y > x) if sd == "away" else None
        ok = res(hh, ha, ht_s) and res(hg, ag, ft_s)
        return ("W" if ok else "L"), f"HT {f['score_halftime']}, {ev}"
    if "corner" in m:
        c = f["team_stats"]["corners"]
        if c["home"] is None:
            return None, "no corner data"
        team = re.sub(r"(?i)\s*(team\s*)?total corners", "", leg.get("market")).strip()
        sd = side(team, f) if team and "total corners" != m.strip() else None
        total = c[sd] if sd else c["home"] + c["away"]
        return ou(total, sel, line), f"corners H{c['home']}-A{c['away']}" + (f" ({sd})" if sd else " (match)")
    if "moneyline" in m and "half time/" not in m:
        if sel.lower().startswith(("draw", "tie")):
            return ("W" if hg == ag else "L"), ev
        sd = side(sel, f)
        won = hg > ag if sd == "home" else ag > hg
        return ("W" if won else "L"), ev
    if "1st half" in m or "first half" in m:
        hh, ha = score(f["score_halftime"])
        return ou(hh + ha, sel, line), f"HT {f['score_halftime']}"
    if "both teams" in m or "btts" in m:
        yes = hg > 0 and ag > 0
        return ("W" if yes == sel.lower().startswith("y") else "L"), ev
    if "first team to score" in m:
        if not f["goals"]:
            return "L", "no goals"
        sd = side(sel, f)
        first = f["goals"][0]["team"]
        return ("W" if side(first, f) == sd else "L"), f"first goal {f['goals'][0]}"
    if "goalscorer" in m or "goal scorer" in m:
        names = [g["player"] for g in f["goals"] if g["player"] and "Own" not in (g["kind"] or "")]
        hit = [n for n in names if n and sel.split()[-1].lower() in n.lower()]
        if "first" in m:
            fg = f["goals"][0]["player"] if f["goals"] else None
            return ("W" if fg and sel.split()[-1].lower() in fg.lower() else "L"), f"first goal {fg}"
        return ("W" if hit else "L"), f"scorers {names}"
    if "total goals by" in m or ("team total" in m and "corner" not in m):
        team = re.sub(r"(?i).*by\s+|\s*\(.*", "", leg.get("market"))
        sd = side(team, f)
        return ou(hg if sd == "home" else ag, sel, line), ev
    if "total" in m and "goal" in m or m.startswith("goals"):
        return ou(hg + ag, sel, line), ev
    if "handicap" in m or "spread" in m:
        sd = side(sel, f)
        margin = (hg - ag) if sd == "home" else (ag - hg)
        return ("W" if margin + float(line) > 0 else "L"), ev
    if "draw no bet" in m:
        if hg == ag:
            return "P", ev
        sd = side(sel, f)
        return ("W" if (hg > ag) == (sd == "home") else "L"), ev
    if any(k in m for k in ("money", "match result", "full time", "90 min", "ml 3", "moneyline")):
        if sel.lower().startswith(("draw", "tie")):
            return ("W" if hg == ag else "L"), ev
        sd = side(sel, f)
        if sd is None:
            return None, f"can't map selection '{sel}' to a side"
        won = hg > ag if sd == "home" else ag > hg
        return ("W" if won else "L"), ev
    return None, "market not auto-gradable"


def ticket_from_legs(results):
    if any(r == "L" for r in results):
        return "LOSS"
    if any(r is None for r in results):
        return None
    if any(r == "OPEN" for r in results):
        return "UNSETTLED"
    if all(r in ("P", "VOID") for r in results):
        return "PUSH"
    return "WIN" if all(r == "W" for r in results) else None


def main():
    cases = json.load(open(sys.argv[1]))
    out_md = sys.argv[2]
    report = []
    for c in cases:
        rows, autos = [], []
        for leg in c["legs"]:
            h, a = teams_of(leg)
            d = first_date(leg.get("kickoff_et"))
            facts, cand, res, ev = None, [], None, ""
            try:
                h2, a2 = ALIASES.get((h or "").lower(), h), ALIASES.get((a or "").lower(), a)
                cand = espn.find_match(h2 or leg.get("selection"), a2, d) if d else []
                if not cand and d and h2:
                    cand = [c for c in espn.find_match(h2, None, d) if a2 and _team_score(a2.split()[0], {"displayName": c["home"] + " " + c["away"]}) >= 0.5] or []
                if cand:
                    facts = espn.match_facts(cand[0]["event_id"])
                    res, ev = auto_grade(leg, facts)
                else:
                    ev = "no ESPN match found"
            except Exception as e:
                ev = f"check error: {type(e).__name__}: {e}"
            log_res = next((x["result"] for x in c["log_grade"]["legs"] if x["leg"] == leg["leg"]), None)
            agree = (res == log_res) or (log_res == "MOOT") or res is None
            autos.append(res)
            rows.append({"leg": leg["leg"], "selection": leg.get("selection"), "market": leg.get("market"),
                         "line": leg.get("line"), "espn_event": cand[0]["event_id"] if cand else None,
                         "espn_match": f"{cand[0]['home']} v {cand[0]['away']} ({cand[0]['kickoff_utc'][:10]}, {cand[0]['status']})" if cand else None,
                         "log": log_res, "code": res, "evidence": ev, "agree": agree})
        t_auto = ticket_from_legs(autos)
        t_log = c["log_grade"]["ticket_result"]
        status = ("AGREE" if t_auto == t_log else "DISAGREE" if t_auto else "PARTIAL")
        if any(not r["agree"] for r in rows) and status == "AGREE":
            status = "AGREE (leg diff)"
        report.append({"case_id": c["case_id"], "category": c["category"], "book": c["book"], "bet_type": c["bet_type"],
                       "stake": c["stake"], "stake_kind": c["stake_kind"], "log_ticket": t_log,
                       "log_net": c["log_grade"]["net"], "code_ticket": t_auto, "status": status, "legs": rows,
                       "why": c.get("why_interesting"), "corrected": c["log_grade"].get("was_corrected")})

    json.dump(report, open("data/gold_check.json", "w"), indent=1, ensure_ascii=False)
    with open(out_md, "w") as f:
        f.write("# Gold-set review — candidate labels vs an independent code check\n\n")
        f.write("*Log label* = what your Claude-in-session grading wrote. *Code* = a plain-Python re-grade from ESPN facts "
                "(no LLM). AGREE needs a glance; DISAGREE / PARTIAL need your ruling.\n\n")
        f.write("| Case | Cat | Book · type | Stake | Log result | Net | Code check | Status |\n|---|---|---|---|---|---|---|---|\n")
        for r in report:
            f.write(f"| {r['case_id']} | {r['category'][0]} | {r['book']} · {r['bet_type']} | ${r['stake']} {r['stake_kind']} | "
                    f"{r['log_ticket']}{' (corrected)' if r['corrected'] else ''} | {r['log_net']} | {r['code_ticket'] or '—'} | **{r['status']}** |\n")
        f.write("\n## Per-leg detail\n")
        for r in report:
            f.write(f"\n### {r['case_id']} — {r['book']} {r['bet_type']} · log {r['log_ticket']} ({r['log_net']}) · {r['status']}\n\n")
            f.write(f"*Why interesting:* {r['why']}\n\n| Leg | Selection · market | ESPN match | Log | Code | Evidence |\n|---|---|---|---|---|---|\n")
            for l in r["legs"]:
                mark = "" if l["agree"] else " ⚠️"
                f.write(f"| {l['leg']} | {l['selection']} · {l['market']}{' ' + str(l['line']) if l['line'] is not None else ''} | "
                        f"{l['espn_match'] or '—'} | {l['log']} | {l['code'] or '—'}{mark} | {l['evidence']} |\n")
    counts = {}
    for r in report:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(counts)
    for r in report:
        if r["status"] != "AGREE":
            print(r["case_id"], r["status"], "log", r["log_ticket"], "code", r["code_ticket"],
                  [(l["leg"], l["log"], l["code"], l["evidence"][:70]) for l in r["legs"] if not l["agree"] or l["code"] is None])


if __name__ == "__main__":
    main()

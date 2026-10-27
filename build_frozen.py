#!/usr/bin/env python3
"""Rebuild data/espn_frozen.json from the local raw cache (data/espn_cache/, not committed).

Fill the raw cache by running the eval with ESPN_LIVE=1; each live response is recorded with its
URL in data/espn_cache/index.json. Then:  python3 build_frozen.py
"""
import glob
import json
import os
import re

from grader.espn import _team_score
from grader.frozen import slim

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "data", "espn_cache")


def query_names():
    """Every team string the eval can search for: the cases' teams and selections, plus every
    find_match argument the model actually used in a recorded run."""
    names = set()
    for f in glob.glob(os.path.join(ROOT, "data", "*.json")):
        try:
            cases = json.load(open(f))
        except ValueError:
            continue
        if not (isinstance(cases, list) and cases and isinstance(cases[0], dict) and "legs" in cases[0]):
            continue
        for c in cases:
            for leg in c["legs"]:
                names.update(filter(None, (leg.get("home"), leg.get("away"), leg.get("selection"))))
                fx = re.sub(r"\(.*?\)", "", leg.get("fixture") or "")
                names.update(p.strip() for p in re.split(r"\s+(?:v|vs\.?|at)\s+", fx) if p.strip())
    for f in glob.glob(os.path.join(ROOT, "traces", "*", "settlement-traces.json")):
        for rs in json.load(open(f))["resourceSpans"]:
            for ss in rs["scopeSpans"]:
                for sp in ss["spans"]:
                    for a in sp.get("attributes", []):
                        if a["key"] == "tool.call.args":
                            try:
                                args = json.loads(a["value"].get("stringValue") or "{}")
                            except ValueError:
                                continue
                            names.update(filter(None, (args.get("team"), args.get("opponent"))))
    return names


def keep_event(ev, names):
    """Keep a scoreboard event only if some query of the eval could return it."""
    for c in ev["competitions"][0]["competitors"]:
        if any(_team_score(n, c["team"]) >= 0.5 for n in names):
            return True
    return False


def main():
    with open(os.path.join(CACHE, "index.json")) as f:
        index = json.load(f)
    names = query_names()
    frozen = {}
    for key, url in sorted(index.items(), key=lambda kv: kv[1]):
        with open(os.path.join(CACHE, key + ".json")) as f:
            data = slim(url, json.load(f))
        if "/scoreboard?" in url:
            data["events"] = [ev for ev in data["events"] if keep_event(ev, names)]
        frozen[url] = data
    out = os.path.join(ROOT, "data", "espn_frozen.json")
    with open(out, "w") as f:
        json.dump(frozen, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"{len(frozen)} responses -> {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

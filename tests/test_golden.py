"""Golden rows, the key, and the draft, sample, candidates, pilot and freeze commands."""
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

import check_gold
from grader.rules import RULES
from run_eval import ticket_from_case
from scorer.golden import (
    build_contexts, build_draws, enrich_real, event_index, event_pools,
    frozen_facts, ground_truth, key_for_leg, key_for_ticket, kickoff_et,
    main, market_plain, real_rows, result_word_hit, topics_for_market,
)
from scorer.golden import _gap_plan


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "data", "gold.json")
GOLD_CHECK = os.path.join(ROOT, "data", "gold_check.json")
GENERATOR = os.path.join(ROOT, "data", "golden", "generator.json")
EDGES = os.path.join(ROOT, "tests", "fixtures", "golden", "edges.jsonl")
SEEDS = "A01,A02,A03,A05,A06"

# Every distinct market on the 30 real rows, and the topics its row names.
PINNED_TOPICS = {
    "Money Line 3-Way (regulation only)": ("moneyline_3way",),
    "Full Time (3-way result)": ("moneyline_3way",),
    "Moneyline (3-way)": ("moneyline_3way",),
    "Match result (3-Way, 90 min, regulation time only)": ("moneyline_3way",),
    "Money Line 3-Way": ("moneyline_3way",),
    "Full Time result (placed in-play at 0-0)": ("moneyline_3way",),
    "Full Time moneyline (3-way, regulation)": ("moneyline_3way",),
    "Draw No Bet": ("draw_no_bet",),
    "First Goal Scorer": ("goalscorer",),
    "Match Result": ("moneyline_3way",),
    "Anytime Goalscorer": ("goalscorer",),
    "Total Goals": ("totals",),
    "Barcelona Total Corners": ("corners",),
    "Match result": ("moneyline_3way",),
    "Both teams to score": ("btts",),
    "Total goals": ("totals",),
    "First team to score": ("general",),
    "Money Line 3-Way (regulation time only)": ("moneyline_3way",),
    "Both Teams to Score": ("btts",),
    "1st Half Total Goals": ("first_half", "totals"),
    "2-Way Handicap": ("general",),
    "90 Minutes (to win, regulation)": ("moneyline_3way",),
    "Both Teams To Score": ("btts",),
    "Total Goals by Manchester City (team total)": ("team_total",),
    "Total Goals (match)": ("totals",),
    "Half Time/Regular Time (HT/FT double result)": ("first_half", "moneyline_3way"),
    "Odds Boost goalscorer combo (both players to score)": ("goalscorer",),
    "Moneyline (90 minutes)": ("moneyline_3way",),
    "Total Corners": ("corners",),
    "Spread": ("general",),
    "ML 3-Way": ("moneyline_3way",),
    "Moneyline": ("moneyline_3way",),
    "Goals (match total)": ("totals",),
    "BTTS": ("btts",),
    "Match Result (regulation time)": ("moneyline_3way",),
    "Moneyline (live, placed in-play at 0-1, 34:06 1st half)": ("moneyline_3way",),
    "Moneyline 3-Way": ("moneyline_3way",),
    "Full Time 2Up Early Payout": ("moneyline_3way",),
}

# ticket result, leg results. Nets are compared as close or not, not copied here.
DISAGREE = {
    "B02": ("LOSS", ("W", "L", "L", "MOOT"), "LOSS", ("W", "L", "L", "W"), True),
    "B10": ("VOID", ("VOID",), "LOSS", ("L",), False),
    "B13": ("LOSS", ("L", "W", "W", "MOOT"), "LOSS", ("L", "W", "W", "L"), True),
    "C02": ("LOSS", ("W", "W", "L", "MOOT"), "LOSS", ("W", "W", "L", "W"), True),
    "C14": ("VOID", ("VOID", "VOID", "VOID"), None, (None, None, None), False),
}


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _real():
    return real_rows(_load(GOLD))


def _events():
    return event_index(GOLD_CHECK)


def _completed():
    return [(eid, facts) for eid, facts in event_pools(frozen_facts())["completed"]]


def _nets_close(left, right):
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) <= 0.01


def _run(argv):
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


def _write_generator(path, topic, market, counts, lines, selections, events="completed"):
    base = _load(GENERATOR)
    base["topics"] = {
        topic: {
            "events": events,
            "leg_counts": list(counts),
            "markets": [{
                "name": market,
                "lines": list(lines),
                "selections": list(selections),
            }],
        }
    }
    base["ticket_gaps"] = {}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(base, handle)


def _draws(batch, n, generator, gap):
    generator_data = _load(generator)
    plan = _gap_plan(gap, generator_data)
    pools = event_pools(frozen_facts())
    rng = random.Random(int(hashlib.sha256(batch.encode("utf-8")).hexdigest(), 16))
    return build_draws(rng, n, gap, plan, pools, generator_data, batch, 0)


def _replies(draws, slip="Listed fixture", words=None, extra=None):
    found = {}
    for case_id, row in draws:
        if row is None:
            continue
        wording = words(row) if callable(words) else (
            [leg["market"] for leg in row["legs"]] if words is None else list(words)
        )
        body = {"slip_text": slip, "market_wording_on_slip": wording}
        if extra:
            body.update(extra)
        found[case_id] = json.dumps(body)
    return found


def _draft(root, batch, n, generator, replies, gap="moneyline_3way"):
    drafts = os.path.join(root, "drafts")
    os.makedirs(drafts, exist_ok=True)
    fake = os.path.join(root, "adapter-%s.json" % batch)
    with open(fake, "w", encoding="utf-8") as handle:
        json.dump(replies, handle)
    out = os.path.join(drafts, "%s.jsonl" % batch)
    argv = [
        "draft", "--gap", gap, "--n", str(n), "--batch", batch,
        "--seed-cases", SEEDS, "--adapter", "fake:%s" % fake,
        "--generator", generator, "--drafts", drafts, "--out", out,
        "--gold", GOLD, "--gold-check", GOLD_CHECK,
    ]
    return _run(argv), out, os.path.join(drafts, "%s.cuts.jsonl" % batch)


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _attr(key, value):
    return {"key": key, "value": {"stringValue": value}}


def _write_run(path, rows, digest="sha256:abc", version="0.6.2", ticket_of=None):
    spans = []
    for index, row in enumerate(rows):
        ticket = json.loads(row["question"]) if ticket_of is None else ticket_of(row)
        final = row["_final"]
        spans.append({
            "traceId": "t%d" % index,
            "spanId": "s%d" % index,
            "name": "grade_ticket",
            "startTimeUnixNano": str(index + 1),
            "attributes": [
                _attr("case.id", row["case_id"]),
                _attr("input.ticket", json.dumps(ticket, ensure_ascii=False)),
                _attr("output.final", json.dumps(final, ensure_ascii=False)),
                _attr("run.status", "complete"),
            ],
            "status": {"code": 0},
        })
    os.makedirs(path)
    with open(os.path.join(path, "settlement-traces.json"), "w", encoding="utf-8") as handle:
        json.dump({"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}, handle)
    with open(os.path.join(path, "run_meta.json"), "w", encoding="utf-8") as handle:
        json.dump({"model_digest": digest, "ollama_version": version}, handle)


def _v1_holds(root):
    """True when the three v1 files are absent together, or present and equal."""
    v1 = os.path.join(root, "data", "golden", "v1.jsonl")
    sha = os.path.join(root, "data", "golden", "v1.sha256")
    copy = os.path.join(root, "packages", "rag-eval", "assignment-1", "golden_set.jsonl")
    if not os.path.exists(v1):
        return not os.path.exists(sha) and not os.path.exists(copy)
    if not os.path.exists(sha) or not os.path.exists(copy):
        return False
    with open(v1, "rb") as handle:
        data = handle.read()
    digest = hashlib.sha256(data).hexdigest()
    with open(sha, encoding="utf-8") as handle:
        line = handle.read()
    if line != "%s  data/golden/v1.jsonl\n" % digest:
        return False
    with open(copy, "rb") as handle:
        return handle.read() == data


class HelpTests(unittest.TestCase):
    def test_the_module_help_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "scorer.golden", "--help"],
            cwd=ROOT, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class RowTests(unittest.TestCase):
    def test_every_real_market_maps_to_its_pinned_topics(self):
        seen = {}
        for row in _real():
            for leg in row["legs"]:
                found = topics_for_market(leg["market"])
                self.assertIsNotNone(found, leg["market"])
                seen[leg["market"]] = found[0]
        self.assertEqual(seen, PINNED_TOPICS)
        live = "Moneyline (live, placed in-play at 0-1, 34:06 1st half)"
        self.assertEqual(market_plain(live), "moneyline")
        self.assertNotIn("1st half", market_plain(live))

    def test_two_terms_on_the_thirty_real_rows(self):
        events = _events()
        rows = [enrich_real(row, events) for row in _real()]
        self.assertEqual(len(rows), 30)
        self.assertEqual(sum(1 for row in rows if "boost" in (row.get("boost_or_token") or "").lower()
                             and "no boost" not in (row.get("boost_or_token") or "").lower()), 24)
        self.assertEqual(
            {name: sum(1 for row in rows if row["difficulty"] == name) for name in ("hard", "medium", "easy")},
            {"hard": 16, "medium": 14, "easy": 0},
        )
        segments = {}
        intents = {}
        for row in rows:
            segments[row["segment"]] = segments.get(row["segment"], 0) + 1
            intents[row["intent"]] = intents.get(row["intent"], 0) + 1
            self.assertEqual(row["blend"], "real")
            self.assertIs(row["label_checked_by_beni"], False)
            self.assertNotIn("pilot", row)
            self.assertEqual(row["expected"], next(item["expected"] for item in _real() if item["case_id"] == row["case_id"]))
            self.assertEqual(row["question"], json.dumps(ticket_from_case(row), indent=1, ensure_ascii=False))
        self.assertEqual(segments, {
            "single-boosted": 12,
            "parlay-boosted": 12,
            "single-second_chance": 2,
            "parlay-bonus_bet": 2,
            "single-free_bet": 1,
            "parlay-cash": 1,
        })
        self.assertEqual(intents, {
            "parlay": 15,
            "moneyline_3way": 11,
            "goalscorer": 3,
            "draw_no_bet": 1,
        })

    def test_c14_has_no_event_and_void_postponed_and_ticket_rules_sort_first(self):
        events = _events()
        row = enrich_real(next(item for item in _real() if item["case_id"] == "C14"), events)
        self.assertTrue(all(item.get("kind") != "event" for item in row["contexts"]))
        self.assertEqual(
            [item["topic"] for item in row["contexts"] if item["leg"] is None],
            ["parlay_moot", "profit_boost"],
        )
        for number in (1, 2, 3):
            topics = [item["topic"] for item in row["contexts"] if item["leg"] == number]
            self.assertIn("void_postponed", topics)
        kinds_before_leg = []
        seen_leg = False
        for item in row["contexts"]:
            if item["leg"] is not None:
                seen_leg = True
            elif seen_leg:
                kinds_before_leg.append(item)
        self.assertEqual(kinds_before_leg, [])
        text = ground_truth(row)
        first = text.splitlines()[0]
        self.assertIn("no frozen event", first)
        self.assertIn("void_postponed", first)
        self.assertNotIn("Never", first)
        self.assertIn("NEEDS_HUMAN also passes.", text.splitlines()[-1])
        half = next(
            item for item in _real()
            if any("ht/ft" in (leg["market"] or "").lower() for leg in item["legs"])
        )
        enriched = enrich_real(half, events)
        facts = [
            item["fact"] for item in enriched["contexts"]
            if item["kind"] == "event" and "ht/ft" in next(
                leg["market"] for leg in enriched["legs"] if leg["leg"] == item["leg"]
            ).lower()
        ]
        self.assertEqual(facts[:2], ["score_halftime", "score_regulation_90"])
        line = next(item for item in ground_truth(enriched).splitlines() if "first_half" in item)
        self.assertIn("moneyline_3way", line)
        self.assertIn("; rule ", line)

    def test_a_mixed_row_sorts_ticket_rules_before_leg_rules(self):
        row = {
            "stake_kind": "bonus_bet",
            "boost_or_token": "10% Profit Boost",
            "legs": [
                {"leg": 2, "market": "Match Result"},
                {"leg": 1, "market": "Total Goals"},
            ],
            "expected": {"legs": []},
        }
        contexts = build_contexts(row, {1: "401861096", 2: "401861096"})
        ticket = [item["topic"] for item in contexts if item["leg"] is None]
        self.assertEqual(ticket, ["bonus_bet_stake", "parlay_moot", "profit_boost"])
        self.assertLess(
            max(index for index, item in enumerate(contexts) if item["leg"] is None),
            min(index for index, item in enumerate(contexts) if item["leg"] is not None),
        )
        for number in (1, 2):
            kinds = [item["kind"] for item in contexts if item["leg"] == number]
            self.assertEqual(kinds[0], "event")

    def test_key_for_ticket_agrees_except_the_pinned_rows(self):
        found = {}
        for row in _real():
            code = key_for_ticket(enrich_real(row, _events()))
            gold_legs = tuple(item["result"] for item in row["expected"]["legs"])
            code_legs = tuple(item["result"] for item in code["legs"])
            close = _nets_close(row["expected"].get("net"), code.get("net"))
            same = (
                row["expected"].get("ticket_result") == code.get("ticket_result")
                and gold_legs == code_legs and close
            )
            if not same:
                found[row["case_id"]] = (
                    row["expected"].get("ticket_result"), gold_legs,
                    code.get("ticket_result"), code_legs, close,
                )
        self.assertEqual(found, DISAGREE)
        self.assertEqual(30 - len(found), 25)

    def test_key_for_leg_matches_auto_grade_except_the_whole_line_push(self):
        compared = 0
        pushes = 0
        for row in _real():
            for leg in row["legs"]:
                found = topics_for_market(leg["market"])
                if found[0][0] in ("double_chance", "cards", "shots_on_target", "to_advance"):
                    continue
                if "1st half" in market_plain(leg["market"]) or "first half" in market_plain(leg["market"]):
                    if not ("total" in market_plain(leg["market"]) and leg.get("line") is not None):
                        continue
                for _eid, facts in _completed():
                    grade, _evidence = key_for_leg(leg, facts)
                    other, _other = check_gold.auto_grade(leg, facts)
                    plain = market_plain(leg["market"])
                    line = leg.get("line")
                    whole = isinstance(line, (int, float)) and not isinstance(line, bool) and float(line) == round(float(line))
                    if whole and ("handicap" in plain or "spread" in plain) and grade == "P":
                        pushes += 1
                        self.assertEqual(other, "L")
                    else:
                        self.assertEqual(grade, other, leg["market"])
                        compared += 1
        self.assertGreater(compared, 0)
        self.assertEqual(pushes, 0)
        facts = _completed()[0][1]
        home, away = check_gold.score(facts["score_regulation_90"])
        leg = {
            "market": "2-Way Handicap",
            "selection": facts["home"],
            "line": float(away - home),
        }
        grade, evidence = key_for_leg(leg, facts)
        other, _other = check_gold.auto_grade(leg, facts)
        self.assertEqual(grade, "P")
        self.assertIn("whole line pushes", evidence)
        self.assertEqual(other, "L")

    def test_half_markets_auto_grade_would_grade_on_the_wrong_score_have_no_branch(self):
        facts = _completed()[0][1]
        blocked = ("1st Half Moneyline", "Second Half Total Goals", "1st Half Corners")
        for market in blocked:
            leg = {"market": market, "selection": facts["home"], "line": 1.5}
            grade, reason = key_for_leg(leg, facts)
            self.assertIsNone(grade)
            self.assertEqual(reason, "no branch for this half market")
            other, _other = check_gold.auto_grade(leg, facts)
            self.assertIsNotNone(other)
        allowed = (
            {"market": "1st Half Total Goals", "selection": "Over", "line": 1.5},
            {"market": "Half Time/Regular Time (HT/FT double result)", "selection": "Draw/Draw", "line": None},
        )
        for leg in allowed:
            self.assertEqual(key_for_leg(leg, facts), check_gold.auto_grade(leg, facts))

    def test_own_branches_do_not_follow_auto_grade(self):
        facts = next(item for _eid, item in _completed() if item.get("goals"))
        shots = {"market": "Team Total Shots on Target", "selection": "Over", "line": 8.5}
        self.assertNotEqual(key_for_leg(shots, facts)[0], check_gold.auto_grade(shots, facts)[0])
        chance = {"market": "Double Chance", "selection": "1X", "line": None}
        self.assertIsNone(check_gold.auto_grade(chance, facts)[0])
        self.assertIn(key_for_leg(chance, facts)[0], ("W", "L", "P"))
        cards_human = 0
        cards_grade = 0
        for _eid, item in _completed():
            leg = {"market": "Total Cards", "selection": "Over", "line": 2.5}
            grade, _evidence = key_for_leg(leg, item)
            if grade == "NEEDS_HUMAN":
                cards_human += 1
            elif grade in ("W", "L", "P"):
                cards_grade += 1
        self.assertGreater(cards_human, 0)
        self.assertGreater(cards_grade, 0)
        shootout = event_pools(frozen_facts())["shootout"]
        self.assertEqual(len(shootout), 1)
        advance = {"market": "To Advance", "selection": shootout[0][1]["home"], "line": None}
        self.assertIsNone(check_gold.auto_grade(advance, shootout[0][1])[0])
        self.assertIn(key_for_leg(advance, shootout[0][1])[0], ("W", "L"))
        player = {"market": "Player Shots on Target", "selection": "Someone", "line": None}
        self.assertEqual(key_for_leg(player, facts)[0], "NEEDS_HUMAN")

    def test_a_missing_event_is_not_a_grade(self):
        grade, reason = key_for_leg({"market": "Match Result", "leg": 1}, None)
        self.assertIsNone(grade)
        self.assertEqual(reason, "no frozen event")

    def test_kickoff_uses_new_york_and_a_missing_zone_is_refused(self):
        self.assertEqual(kickoff_et("2026-10-01T18:45Z"), "2026-10-01 14:45")
        with tempfile.TemporaryDirectory() as root:
            generator = os.path.join(root, "generator.json")
            _write_generator(generator, "moneyline_3way", "Match Result", (1,), (None,), ("home",))
            with mock.patch("scorer.golden.ZoneInfo", side_effect=ZoneInfoNotFoundError("missing")):
                (status, _out, err), out, cuts = _draft(root, "zone", 1, generator, {})
            self.assertEqual(status, 2)
            self.assertIn("America/New_York", err)
            self.assertFalse(os.path.exists(out))
            self.assertFalse(os.path.exists(cuts))

    def test_every_generator_market_matches_its_topic_and_can_grade(self):
        generator = _load(GENERATOR)
        pools = event_pools(frozen_facts())
        for topic, spec in generator["topics"].items():
            self.assertIn(topic, RULES)
            pool = pools[spec["events"]]
            self.assertGreater(len(pool), 0)
            for market in spec["markets"]:
                graded = False
                for _eid, facts in pool:
                    name = market["name"].replace("{side}", facts.get("home") or "")
                    found = topics_for_market(name)
                    self.assertIsNotNone(found, name)
                    self.assertEqual(found[0][0], topic, name)
                    for token in market["selections"]:
                        from scorer.golden import resolve_token
                        selection = resolve_token(token, facts, random.Random(0))
                        if not selection:
                            continue
                        for line in market["lines"]:
                            grade, _evidence = key_for_leg({
                                "leg": 1, "market": name, "selection": selection, "line": line,
                            }, facts)
                            if grade is not None:
                                graded = True
                                break
                        if graded:
                            break
                    if graded:
                        break
                self.assertTrue(graded, "%s %s" % (topic, market["name"]))
        self.assertNotIn("void_postponed", generator["topics"])
        self.assertNotIn("void_postponed", generator["ticket_gaps"])

    def test_winner_pushed_and_a_word_inside_another_word_do_not_trip(self):
        self.assertFalse(result_word_hit("the winner pushed a price"))
        self.assertTrue(result_word_hit("the side won"))
        self.assertTrue(result_word_hit("Final Score 1-0"))


class CommandTests(unittest.TestCase):
    def _one(self, root, name="tiny.json"):
        path = os.path.join(root, name)
        _write_generator(path, "moneyline_3way", "Match Result", (1,), (None,), ("home",))
        return path

    def test_each_cut_fires_and_a_clean_reply_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            generator = self._one(root)
            draws = _draws("clean", 1, generator, "moneyline_3way")
            self.assertIsNotNone(draws[0][1])
            (status, _out, err), out, cuts = _draft(
                root, "clean", 1, generator, _replies(draws),
            )
            self.assertEqual(status, 0, err)
            kept = _read_jsonl(out)
            self.assertEqual(len(kept), 1)
            self.assertEqual(_read_jsonl(cuts), [])
            row = kept[0]
            self.assertEqual(row["category"], "S_synthetic")
            self.assertEqual(row["source"], "synthetic")
            self.assertEqual(row["why_interesting"], "synthetic: gap moneyline_3way, batch clean")
            self.assertIsNone(row["log_grade"])
            self.assertEqual(row["expected"]["code_check"], "key_for_ticket")
            self.assertIs(row["expected"]["verified_by_beni"], False)
            self.assertIs(row["expected"]["accept_needs_human"], False)
            self.assertIsNone(row["expected"]["adjudication"])
            self.assertEqual(row["bet_type"], "ML")
            self.assertNotIn("pilot", row)
            for leg in row["legs"]:
                self.assertNotIn("espn_event", leg)
            self.assertEqual(row["question"], json.dumps(ticket_from_case(row), indent=1, ensure_ascii=False))

            hostile = _replies(draws, extra={
                "expected": {"ticket_result": "WIN", "marker": "from-the-reply"},
                "ticket_result": "WIN",
                "score": "9-9",
            })
            again = os.path.join(root, "hostile")
            os.makedirs(again)
            (status, _out, err), out, _cuts = _draft(again, "clean", 1, generator, hostile)
            self.assertEqual(status, 0, err)
            row = _read_jsonl(out)[0]
            self.assertNotIn("marker", json.dumps(row["expected"]))
            self.assertEqual(row["expected"]["code_check"], "key_for_ticket")
            self.assertNotIn("9-9", json.dumps(row["expected"]))

            cases = (
                ("words", "unparseable", "not json", None),
                ("won", "result_word", None, "the side won"),
                ("digit", "digit", None, "99"),
            )
            for batch, reason, raw, slip in cases:
                if raw is None:
                    replies = _replies(draws, slip=slip)
                else:
                    replies = {draws[0][0]: raw}
                (status, _out, err), out, cuts_path = _draft(
                    os.path.join(root, batch), batch, 1, generator, replies,
                )
                self.assertEqual(status, 0, err)
                self.assertEqual(_read_jsonl(out), [])
                self.assertEqual(_read_jsonl(cuts_path), [{"case_id": "S001", "reason": reason}])

            replies = _replies(draws, words=lambda row: ["Total Goals"])
            (status, _out, err), out, cuts_path = _draft(
                os.path.join(root, "topic"), "topic", 1, generator, replies,
            )
            self.assertEqual(status, 0, err)
            self.assertEqual(_read_jsonl(cuts_path)[0]["reason"], "topic")

            run = draws[0][1]["legs"][0]["kickoff_et"]
            token = re.search(r"\d+", run).group(0)
            replies = _replies(
                draws, slip="the winner pushed a price",
                words=lambda row: [row["legs"][0]["market"] + " 0" + token],
            )
            (status, _out, err), out, cuts_path = _draft(
                os.path.join(root, "safe"), "safe", 1, generator, replies,
            )
            self.assertEqual(status, 0, err)
            self.assertEqual(len(_read_jsonl(out)), 1)
            self.assertEqual(_read_jsonl(cuts_path), [])

            (status, _out, err), first_out, _cuts = _draft(
                os.path.join(root, "rep1"), "same", 1, generator, _replies(draws),
            )
            self.assertEqual(status, 0, err)
            repeat_root = os.path.join(root, "rep2")
            os.makedirs(os.path.join(repeat_root, "drafts"))
            with open(first_out, encoding="utf-8") as handle:
                body = handle.read()
            with open(os.path.join(repeat_root, "drafts", "other.jsonl"), "w", encoding="utf-8") as handle:
                handle.write(body)
            repeat_replies = _replies(draws)
            repeat_replies["S002"] = next(iter(repeat_replies.values()))
            (status, _out, err), out, cuts_path = _draft(
                repeat_root, "same", 1, generator, repeat_replies,
            )
            self.assertEqual(status, 0, err)
            self.assertEqual(_read_jsonl(out), [])
            self.assertEqual(_read_jsonl(cuts_path)[0]["reason"], "repeat")

    def test_no_key_does_not_call_the_model_and_a_missing_reply_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            generator = os.path.join(root, "half.json")
            _write_generator(generator, "first_half", "1st Half Moneyline", (1,), (None,), ("home",))
            (status, _out, err), out, cuts = _draft(root, "nokey", 1, generator, {}, gap="first_half")
            self.assertEqual(status, 0, err)
            self.assertEqual(_read_jsonl(cuts), [{"case_id": "S001", "reason": "no_key"}])
            self.assertEqual(_read_jsonl(out), [])

            generator = self._one(root, "one.json")
            draws = _draws("miss", 2, generator, "moneyline_3way")
            replies = _replies(draws)
            replies.pop(draws[1][0])
            (status, _out, err), out, cuts = _draft(
                os.path.join(root, "miss"), "miss", 2, generator, replies,
            )
            self.assertEqual(status, 2)
            self.assertFalse(os.path.exists(out))
            self.assertFalse(os.path.exists(cuts))

    def test_draft_is_byte_stable_and_a_second_batch_changes_the_structure(self):
        with tempfile.TemporaryDirectory() as root:
            generator = os.path.join(root, "generator.json")
            _write_generator(generator, "moneyline_3way", "Match Result", (1, 2, 3), (None,), ("home", "away", "draw"))
            draws = _draws("alpha", 4, generator, "moneyline_3way")
            replies = _replies(draws)
            (status, _out, err), out, cuts = _draft(root, "alpha", 4, generator, replies)
            self.assertEqual(status, 0, err)
            first = open(out, "rb").read()
            first_cuts = open(cuts, "rb").read()
            (status, _out, err), out, cuts = _draft(root, "alpha", 4, generator, replies)
            self.assertEqual(status, 0, err)
            self.assertEqual(open(out, "rb").read(), first)
            self.assertEqual(open(cuts, "rb").read(), first_cuts)
            other = _draws("beta", 4, generator, "moneyline_3way")
            left = [row["contexts"] for _cid, row in draws if row]
            right = [row["contexts"] for _cid, row in other if row]
            self.assertNotEqual(left, right)

    def test_bad_draft_arguments_are_refused_and_write_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            generator = self._one(root)
            out = os.path.join(root, "drafts", "bad.jsonl")
            base = [
                "--n", "1", "--batch", "bad", "--seed-cases", SEEDS,
                "--adapter", "fake:%s" % os.path.join(root, "empty.json"),
                "--generator", generator, "--drafts", os.path.join(root, "drafts"),
                "--out", out, "--gold", GOLD, "--gold-check", GOLD_CHECK,
            ]
            with open(os.path.join(root, "empty.json"), "w", encoding="utf-8") as handle:
                handle.write("{}")
            tail = base[6:]
            refused = (
                ["draft", "--gap", "void_postponed"] + base,
                ["draft", "--gap", "not_a_topic"] + base,
                ["draft", "--gap", "moneyline_3way", "--n", "0", "--batch", "bad", "--seed-cases", SEEDS] + tail,
                ["draft", "--gap", "moneyline_3way", "--n", "21", "--batch", "bad", "--seed-cases", SEEDS] + tail,
                ["draft", "--gap", "moneyline_3way", "--n", "1", "--batch", "../x", "--seed-cases", SEEDS] + tail,
                ["draft", "--gap", "moneyline_3way", "--n", "1", "--batch", "bad",
                 "--seed-cases", "A01,A02,A03,A05,X01"] + tail,
            )
            for argv in refused:
                status, _out, err = _run(argv)
                self.assertEqual(status, 2, argv)
                self.assertTrue(err.strip())
                self.assertFalse(os.path.exists(out))

    def test_sample_is_stable_and_takes_one_intent_first(self):
        with tempfile.TemporaryDirectory() as root:
            generator = os.path.join(root, "generator.json")
            _write_generator(
                generator, "moneyline_3way", "Match Result", (1, 2), (None,), ("home",),
            )
            draws = _draws("mix", 6, generator, "moneyline_3way")
            (status, _out, err), out, _cuts = _draft(root, "mix", 6, generator, _replies(draws))
            self.assertEqual(status, 0, err)
            self.assertGreaterEqual(len(_read_jsonl(out)), 2)
            sheet = os.path.join(root, "sheet.md")
            check = os.path.join(root, "check.jsonl")
            argv = ["sample", "--drafts", os.path.join(root, "drafts"), "--check", check, "--sheet", sheet]
            status, first_out, err = _run(argv)
            self.assertEqual(status, 0, err)
            self.assertTrue(first_out.startswith("0 of 0 ["))
            body = open(sheet, "rb").read()
            status, second_out, err = _run(argv)
            self.assertEqual(status, 0, err)
            self.assertEqual(second_out, first_out)
            self.assertEqual(open(sheet, "rb").read(), body)
            selected = next(line for line in body.decode("utf-8").splitlines() if line.startswith("Selected:"))
            ids = selected.split(": ", 1)[1].split(", ")
            rows = {row["case_id"]: row for row in _read_jsonl(out)}
            intents = [rows[case_id]["intent"] for case_id in ids]
            distinct = []
            for intent in intents:
                if intent not in distinct:
                    distinct.append(intent)
            self.assertEqual(distinct, sorted(distinct))
            self.assertEqual(len(distinct), len(set(intents)))

    def test_candidates_counts_and_the_edges_path(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "candidates.jsonl")
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "no-drafts"),
                "--check", os.path.join(root, "no-check.jsonl"),
                "--edges", os.path.join(root, "no-edges.jsonl"),
                "--out", out,
            ])
            self.assertEqual(status, 0, err)
            rows = _read_jsonl(out)
            self.assertEqual(len(rows), 30)
            self.assertTrue(all(row["label_checked_by_beni"] is False for row in rows))
            self.assertEqual(
                sum(1 for row in rows if row["difficulty"] == "hard"), 16,
            )
            first = open(out, "rb").read()
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "no-drafts"),
                "--check", os.path.join(root, "no-check.jsonl"),
                "--edges", os.path.join(root, "no-edges.jsonl"),
                "--out", out,
            ])
            self.assertEqual(open(out, "rb").read(), first)

            generator = self._one(root)
            draws = _draws("batch", 1, generator, "moneyline_3way")
            (status, _out, err), drafted, _cuts = _draft(
                root, "batch", 1, generator, _replies(draws),
            )
            self.assertEqual(status, 0, err)
            case_id = _read_jsonl(drafted)[0]["case_id"]
            check = os.path.join(root, "checks.jsonl")
            with open(check, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"case_id": case_id, "ok": False, "error": "other", "note": ""}) + "\n")
            edged = os.path.join(root, "with-edge.jsonl")
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "drafts"), "--check", check,
                "--edges", EDGES, "--out", edged,
            ])
            self.assertEqual(status, 0, err)
            rows = _read_jsonl(edged)
            self.assertEqual(len(rows), 31)
            self.assertTrue(all(row["case_id"] != case_id for row in rows))
            edge = next(row for row in rows if row["case_id"] == "E01")
            self.assertEqual(edge["blend"], "hand_crafted")
            self.assertEqual(edge["source"], "hand_crafted_by_owner")
            self.assertIs(edge["label_checked_by_beni"], False)
            self.assertEqual(edge["difficulty"], "hard")
            self.assertNotIn("espn_event", edge["legs"][0])
            self.assertEqual(edge["contexts"][0]["event_id"], "401861096")

            with open(check, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"case_id": case_id, "ok": False}) + "\n")
                handle.write(json.dumps({"case_id": case_id, "ok": True}) + "\n")
            passed = os.path.join(root, "passed.jsonl")
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "drafts"), "--check", check,
                "--edges", os.path.join(root, "missing-edges.jsonl"), "--out", passed,
            ])
            self.assertEqual(status, 0, err)
            kept = next(row for row in _read_jsonl(passed) if row["case_id"] == case_id)
            self.assertIs(kept["label_checked_by_beni"], True)

            bad = os.path.join(root, "bad-edges.jsonl")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write("{}\n")
            refused = os.path.join(root, "refused.jsonl")
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "no-drafts"),
                "--check", os.path.join(root, "no-check.jsonl"),
                "--edges", bad, "--out", refused,
            ])
            self.assertEqual(status, 2)
            self.assertFalse(os.path.exists(refused))

            dup = os.path.join(root, "dup.jsonl")
            with open(dup, "w", encoding="utf-8") as handle:
                text = open(EDGES, encoding="utf-8").read()
                handle.write(text)
                handle.write(text)
            status, _stdout, err = _run([
                "candidates", "--gold", GOLD, "--gold-check", GOLD_CHECK,
                "--drafts", os.path.join(root, "no-drafts"),
                "--check", os.path.join(root, "no-check.jsonl"),
                "--edges", dup, "--out", refused,
            ])
            self.assertEqual(status, 2)
            self.assertIn("repeated case id", err)
            self.assertFalse(os.path.exists(refused))

    def test_pilot_tags_and_refusals_write_nothing_on_failure(self):
        events = _events()
        rows = []
        for case_id, final_name in (("A01", "pass"), ("B10", "fail")):
            row = enrich_real(next(item for item in _real() if item["case_id"] == case_id), events)
            if final_name == "pass":
                row["_final"] = {
                    "ticket_result": row["expected"]["ticket_result"],
                    "net": row["expected"].get("net"),
                }
            else:
                row["_final"] = {"ticket_result": "UNSETTLED", "net": None}
            rows.append(row)
        with tempfile.TemporaryDirectory() as root:
            candidates = os.path.join(root, "candidates.jsonl")
            stored = []
            for row in rows:
                copy = dict(row)
                copy.pop("_final")
                stored.append(copy)
            with open(candidates, "w", encoding="utf-8") as handle:
                for row in stored:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            strong = os.path.join(root, "strong")
            weak = os.path.join(root, "weak")
            _write_run(strong, [rows[0], dict(rows[1], _final=rows[1]["_final"])])
            weak_rows = [
                dict(rows[0], _final={"ticket_result": "UNSETTLED", "net": None}),
                rows[1],
            ]
            _write_run(weak, weak_rows)
            kept = os.path.join(root, "kept.jsonl")
            pilot = os.path.join(root, "pilot.md")
            status, _out, err = _run([
                "pilot", "--candidates", candidates, "--strong", strong, "--weak", weak,
                "--gold-check", GOLD_CHECK, "--check", os.path.join(root, "none.jsonl"),
                "--kept", kept, "--pilot-md", pilot,
            ])
            self.assertEqual(status, 0, err)
            kept_rows = _read_jsonl(kept)
            self.assertEqual([row["case_id"] for row in kept_rows], ["A01"])
            self.assertEqual(kept_rows[0]["pilot"], "keep")
            text = open(pilot, encoding="utf-8").read()
            self.assertIn("B10", text)
            self.assertIn("key does not hold", text)
            self.assertNotIn(root, text)

            mismatch = os.path.join(root, "other-digest")
            _write_run(mismatch, rows, digest="sha256:other")
            bad_kept = os.path.join(root, "bad-kept.jsonl")
            status, _out, err = _run([
                "pilot", "--candidates", candidates, "--strong", strong, "--weak", mismatch,
                "--gold-check", GOLD_CHECK, "--check", os.path.join(root, "none.jsonl"),
                "--kept", bad_kept, "--pilot-md", os.path.join(root, "bad.md"),
            ])
            self.assertEqual(status, 2)
            self.assertFalse(os.path.exists(bad_kept))

            short = os.path.join(root, "short")
            _write_run(short, [rows[0]])
            status, _out, err = _run([
                "pilot", "--candidates", candidates, "--strong", strong, "--weak", short,
                "--gold-check", GOLD_CHECK, "--check", os.path.join(root, "none.jsonl"),
                "--kept", bad_kept, "--pilot-md", os.path.join(root, "bad.md"),
            ])
            self.assertEqual(status, 2)
            self.assertIn("lacks a record", err)
            self.assertFalse(os.path.exists(bad_kept))

            wrong = os.path.join(root, "wrong-ticket")
            _write_run(wrong, rows, ticket_of=lambda row: {"legs": []})
            status, _out, err = _run([
                "pilot", "--candidates", candidates, "--strong", strong, "--weak", wrong,
                "--gold-check", GOLD_CHECK, "--check", os.path.join(root, "none.jsonl"),
                "--kept", bad_kept, "--pilot-md", os.path.join(root, "bad.md"),
            ])
            self.assertEqual(status, 2)
            self.assertIn("different ticket", err)

    def test_freeze_refusals_and_the_v1_files(self):
        self.assertTrue(_v1_holds(ROOT))
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "data", "golden"))
            os.makedirs(os.path.join(root, "packages", "rag-eval", "assignment-1"))
            self.assertTrue(_v1_holds(root))
            v1 = os.path.join(root, "data", "golden", "v1.jsonl")
            sha = os.path.join(root, "data", "golden", "v1.sha256")
            copy = os.path.join(root, "packages", "rag-eval", "assignment-1", "golden_set.jsonl")
            with open(v1, "w", encoding="utf-8") as handle:
                handle.write('{"case_id":"S001"}\n')
            self.assertFalse(_v1_holds(root))
            with open(sha, "w", encoding="utf-8") as handle:
                handle.write("deadbeef  data/golden/v1.jsonl\n")
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write('{"case_id":"S001"}\n')
            self.assertFalse(_v1_holds(root))
            digest = hashlib.sha256(open(v1, "rb").read()).hexdigest()
            with open(sha, "w", encoding="utf-8") as handle:
                handle.write("%s  data/golden/v1.jsonl\n" % digest)
            self.assertTrue(_v1_holds(root))
            with open(copy, "ab") as handle:
                handle.write(b" ")
            self.assertFalse(_v1_holds(root))
            os.remove(v1)
            self.assertFalse(_v1_holds(root))

        with tempfile.TemporaryDirectory() as root:
            kept = os.path.join(root, "kept.jsonl")
            rows = [{"case_id": "S%03d" % number, "n": number} for number in range(1, 150)]
            with open(kept, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            v1 = os.path.join(root, "v1.jsonl")
            sha = os.path.join(root, "v1.sha256")
            status, _out, err = _run(["freeze", "--kept", kept, "--v1", v1, "--sha", sha])
            self.assertEqual(status, 2)
            self.assertFalse(os.path.exists(v1))
            self.assertFalse(os.path.exists(sha))
            rows.append({"case_id": "S150", "n": 150})
            with open(kept, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            status, _out, err = _run(["freeze", "--kept", kept, "--v1", v1, "--sha", sha])
            self.assertEqual(status, 0, err)
            body = open(v1, "rb").read()
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(open(sha, encoding="utf-8").read(), "%s  data/golden/v1.jsonl\n" % digest)
            status, _out, err = _run(["freeze", "--kept", kept, "--v1", v1, "--sha", sha])
            self.assertEqual(status, 0, err)
            self.assertEqual(open(v1, "rb").read(), body)
            with open(kept, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"case_id": "S999"}) + "\n")
                for row in rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            status, _out, err = _run(["freeze", "--kept", kept, "--v1", v1, "--sha", sha])
            self.assertEqual(status, 2)
            self.assertEqual(open(v1, "rb").read(), body)


if __name__ == "__main__":
    unittest.main()

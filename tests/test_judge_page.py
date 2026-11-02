"""The judge comparison page. Agreement percents come from the integer counts."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import shlex
import unittest
from fractions import Fraction
from html import unescape
from html.parser import HTMLParser

from scorer.calibrate import bar_words, has_reading, not_bar_words
from scorer.judge import agreement_percent, build_report, render_comparison
from scorer.report import esc

from tests import test_judge
from tests.test_contrast import brace_block
from tests.test_judge import ROOT, cli, tempfile_dir, write_text


BANNED = ("held out", "held-out", "trusted", "generalise", "generalize")
# Reached through its module, not imported by name: a TestCase class bound in
# this namespace is discovered here as well as in its own module, and the suite
# would run every one of its tests twice and count them twice.
_HELPER = test_judge.ReportTests("test_committed_fixture_report_regenerates")


class AgreementPercentTests(unittest.TestCase):
    def test_one_decimal_from_the_counts(self):
        # Set 1's final and first-pass agreements, as the report prints them.
        self.assertEqual(agreement_percent(32, 40), "80.0%")
        self.assertEqual(agreement_percent(37, 40), "92.5%")
        self.assertEqual(agreement_percent(23, 40), "57.5%")
        self.assertEqual(agreement_percent(26, 40), "65.0%")
        self.assertEqual(agreement_percent(1, 1), "100.0%")
        self.assertEqual(agreement_percent(0, 1), "0.0%")
        self.assertEqual(agreement_percent(0, 0), "none")

    def test_an_exact_half_rounds_away_from_zero(self):
        # 1/16 is 6.25%, halfway between 6.2% and 6.3%. Half away from zero is 6.3%.
        # 5/16 is 31.25%, halfway between 31.2% and 31.3%, and prints 31.3%.
        self.assertEqual(agreement_percent(1, 16), "6.3%")
        self.assertEqual(agreement_percent(5, 16), "31.3%")
        self.assertEqual((1 * 1000) % 16, 8)
        self.assertEqual(16 // 2, 8)


def _agree(verdict, human):
    return (verdict == "PASS") == (human == "PASS")


def _jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _verdicts(directory):
    found = {}
    for row in _jsonl(os.path.join(directory, "verdicts.jsonl")):
        found[(row["run"], row["case_id"], row["rubric"])] = row
    return found


def _readings(path):
    if path is None:
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _expected(labels, final, readings, verdicts):
    """What the page must show, counted from the inputs rather than the renderer."""
    rows = _jsonl(labels)
    names = sorted(rows[0]["human"].keys())
    final_rows = _jsonl(final) if final else None
    verdict_rows = _verdicts(verdicts)
    reading_map = _readings(readings)
    with open(labels[:-len(".jsonl")] + "-meta.json", encoding="utf-8") as handle:
        labels_meta = json.load(handle)
    with open(os.path.join(verdicts, "judge_meta.json"), encoding="utf-8") as handle:
        judge_meta = json.load(handle)
    rubrics = []
    for name in names:
        bucket = reading_map.get(name) or {}
        page_rows = []
        changed = 0 if final_rows is not None else None
        first_pairs = []
        final_pairs = []
        unparsed = 0
        for index, row in enumerate(rows):
            verdict = verdict_rows[(row["run"], row["case_id"], name)]
            if verdict["verdict"] == "UNPARSED":
                unparsed += 1
            first = row["human"][name]
            final_label = None
            change_reason = None
            if final_rows is not None:
                final_label = final_rows[index]["human"][name]
                if final_label != first:
                    changed += 1
                    for change in final_rows[index]["changes"]:
                        if change["rubric"] == name:
                            change_reason = change["reason"]
            cover = final_label if final_label is not None else first
            show = (not _agree(verdict["verdict"], first)) or (
                final_label is not None and not _agree(verdict["verdict"], final_label)
            )
            text = bucket.get("%s|%s" % (row["run"], row["case_id"]))
            page_rows.append({
                "agree": _agree(verdict["verdict"], cover),
                "case_id": row["case_id"],
                "change": change_reason,
                "final": final_label,
                "first": first,
                "reading": text if show and has_reading(text) else None,
                "reason": verdict["reason"],
                "run": row["run"],
                "show": show,
                "unread": show and not has_reading(text),
                "verdict": verdict["verdict"],
            })
            first_pairs.append((verdict["verdict"], first, text))
            if final_label is not None:
                final_pairs.append((verdict["verdict"], final_label, text))
        sha = judge_meta["rubrics"][name]
        if labels_meta["rubrics"][name] == sha:
            state = "same text as when the labels were made"
        else:
            state = "changed since the labels were made: in sample"
        rubrics.append({
            "changed": changed,
            "final": _side(final_pairs) if final_pairs else None,
            "first": _side(first_pairs),
            "name": name,
            "rows": page_rows,
            "sha": sha,
            "text": state,
            "unparsed": unparsed,
        })
    return rubrics


def _kappa(side):
    """Cohen's kappa from the four counts, exact. None when chance agreement is 1."""
    tp, fp, fn, tn = side["JF_HF"], side["JF_HP"], side["JP_HF"], side["JP_HP"]
    total = tp + fp + fn + tn
    chance = Fraction((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn), total * total)
    if chance == 1:
        return None
    return (Fraction(tp + tn, total) - chance) / (1 - chance)


def _side(pairs):
    """The figures one side of a rubric must print, from (verdict, human, reading) triples."""
    # Count raw input pairs directly: production confusion and meets_bar must
    # not be able to change both the displayed answer and its oracle together.
    side = {"JP_HF": 0, "JF_HP": 0, "JP_HP": 0, "JF_HF": 0, "n": len(pairs)}
    for verdict, human, _text in pairs:
        cell = ("JP" if verdict == "PASS" else "JF") + ("_HP" if human == "PASS" else "_HF")
        side[cell] += 1
    agree = side["JP_HP"] + side["JF_HF"]
    kappa = _kappa(side)
    false_passes = [text for verdict, human, text in pairs if verdict == "PASS" and human == "FAIL"]
    scaled = Fraction(agree * 1000, side["n"])
    tenths, remainder = divmod(scaled.numerator, scaled.denominator)
    tenths += remainder * 2 >= scaled.denominator
    side["percent"] = "%d.%d%%" % divmod(tenths, 10)
    side["four"] = "%.4f" % (agree / side["n"])
    side["kappa"] = kappa
    side["kappa_text"] = "none" if kappa is None else "%.4f" % float(kappa)
    side["kappa_flag"] = "yes" if kappa is not None and kappa >= Fraction(6, 10) else "no"
    side["meets"] = Fraction(agree, side["n"]) >= Fraction(85, 100) and kappa is not None and kappa >= Fraction(6, 10)
    side["k_of_n"] = None
    if false_passes:
        side["k_of_n"] = "%s of %s" % (sum(1 for text in false_passes if has_reading(text)), len(false_passes))
    return side


def _worst_sentence(rubrics, key, which):
    """The worst judge as the Markdown words it: lowest kappa, none lowest; more false passes; the name."""
    def rank(item):
        side = item[key]
        kappa_part = (0, Fraction(0)) if side["kappa"] is None else (1, side["kappa"])
        return (kappa_part, -side["JP_HF"])

    lowest = min(rank(item) for item in rubrics)
    names = sorted(item["name"] for item in rubrics if rank(item) == lowest)
    if len(names) > 1:
        return "Worst judges on the %s tied: %s." % (which, ", ".join(names))
    return "Worst judge on the %s: %s." % (which, ", ".join(names))


def _cover(rubrics, row_count, with_final):
    """The three tiles, which labels they count, the worst judge and the size line."""
    key = "final" if with_final else "first"
    which = "final labels" if with_final else "first-pass labels"
    return {
        "tiles": [
            str(sum(1 for item in rubrics if item[key]["meets"])),
            str(sum(item[key]["JP_HF"] for item in rubrics)),
            str(sum(item[key]["JF_HP"] for item in rubrics)),
        ],
        "tile_labels": ["judges at %s" % bar_words(), "false passes", "false fails"],
        "which": "These tiles count the %s." % which,
        "worst": _worst_sentence(rubrics, key, which),
        "size": "%s rows \u00b7 %s rubrics" % (row_count, len(rubrics)),
    }


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cover = {"dek": None, "issue": None, "tile_labels": [], "tiles": [], "which": None}
        self.sections = []
        self._sec = None
        self._matrix = None
        self._targets = []

    def _push(self, tag, kind, attr=None):
        self._targets.append((tag, kind, [], attr))

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = attr.get("class", "").split()
        if tag == "section" and "rubric" in classes:
            self._sec = {
                "changed": [], "head": None, "matrices": [], "name": attr.get("data-rubric"), "rows": [], "sides": {},
            }
            self.sections.append(self._sec)
        elif self._sec is None:
            if tag == "div" and "stat" in classes:
                self._push(tag, "tile")
            elif tag == "b" and self._targets and self._targets[-1][1] == "tile":
                self._push(tag, "tile-number")
            elif tag == "p" and "tile-which" in classes:
                self._push(tag, "which")
            elif tag == "p" and "dek" in classes:
                self._push(tag, "dek")
            elif tag == "p" and "issue" in classes:
                self._push(tag, "issue")
        elif tag == "div" and "sec-head" in classes:
            self._push(tag, "head")
        elif tag == "table" and "matrix" in classes:
            self._matrix = []
            self._sec["matrices"].append(self._matrix)
        elif tag == "tr" and "row" in classes:
            self._sec["rows"].append({
                "badges": [],
                "case": attr.get("data-case"),
                "cells": {},
                "change": None,
                "mark": attr.get("data-mark"),
                "open": None,
                "summary": None,
                "badge_classes": [],
                "reading": None,
                "run": attr.get("data-run"),
            })
        elif tag == "article" and "side" in classes:
            self._push(tag, "side:" + attr.get("data-labels", ""))
        elif tag == "td" and self._matrix is not None:
            self._push(tag, "cell", attr.get("data-cell"))
        elif tag == "td" and self._sec["rows"]:
            self._push(tag, "field:" + attr.get("data-label", ""))
        elif tag == "details" and self._sec["rows"]:
            self._sec["rows"][-1]["open"] = "open" in attr
        elif tag == "summary" and self._sec["rows"]:
            self._sec["rows"][-1]["summary"] = attr.get("aria-label", "")
        elif tag == "p" and "rubric-statement" in classes:
            self._push(tag, "statement")
        elif tag == "p" and "changed" in classes:
            sides = [kind for _tag, kind, _buf, _attr in self._targets if kind.startswith("side:")]
            self._push(tag, "changed", sides[-1].split(":", 1)[1] if sides else None)
        elif tag == "p" and "reading" in classes and self._sec["rows"]:
            self._push(tag, "reading")
        elif tag == "span" and "change" in classes and self._sec["rows"]:
            self._push(tag, "change")
        elif tag == "span" and "pill" in classes and self._sec["rows"]:
            self._sec["rows"][-1]["badge_classes"].append(classes)
            self._push(tag, "pill")

    def handle_endtag(self, tag):
        if self._targets and self._targets[-1][0] == tag:
            _tag, kind, buf, attr = self._targets.pop()
            text = "".join(buf)
            if kind == "tile-number":
                self.cover["tiles"].append(text.strip())
            elif kind == "tile":
                self.cover["tile_labels"].append(text.strip())
            elif kind in ("which", "dek", "issue"):
                self.cover[kind] = text.strip()
            elif kind == "head":
                self._sec["head"] = text
            elif kind.startswith("side:"):
                self._sec["sides"][kind.split(":", 1)[1]] = text
            elif kind == "cell" and self._matrix is not None:
                self._matrix.append((attr, text))
            elif kind.startswith("field:"):
                self._sec["rows"][-1]["cells"][kind.split(":", 1)[1]] = text.strip()
            elif kind == "statement":
                self._sec["statement"] = text
            elif kind == "changed":
                self._sec["changed"].append((attr, text))
            elif kind == "reading":
                self._sec["rows"][-1]["reading"] = text
            elif kind == "change":
                self._sec["rows"][-1]["change"] = text
            elif kind == "pill":
                self._sec["rows"][-1]["badges"].append(text.strip())
        if tag == "table":
            self._matrix = None

    def handle_data(self, data):
        if self._targets:
            self._targets[-1][2].append(data)


def _parse(html):
    parser = _Page()
    parser.feed(html)
    return parser


def _strip_inputs(html, strings):
    cleaned = html
    for text in sorted((esc(value) for value in strings if isinstance(value, str) and value), key=len, reverse=True):
        cleaned = cleaned.replace(text, "")
    return cleaned


def _banned_left(html, strings):
    left = _strip_inputs(html, strings).lower()
    return [word for word in BANNED if word in left]


def _input_strings(labels, final, readings, provenance, verdicts, rubric_provenance, extra=()):
    strings = [open(provenance, encoding="utf-8").read()]
    with open(rubric_provenance, encoding="utf-8") as handle:
        statements = json.load(handle)
    strings.extend(statements.values())
    if readings:
        for bucket in _readings(readings).values():
            if isinstance(bucket, dict):
                strings.extend(text for text in bucket.values() if isinstance(text, str))
    for row in _jsonl(os.path.join(verdicts, "verdicts.jsonl")):
        strings.append(row["reason"])
    if final:
        for row in _jsonl(final):
            for change in row["changes"]:
                strings.append(change["reason"])
    strings.extend([labels, final or "", readings or "", provenance, verdicts, rubric_provenance])
    strings.extend(extra)
    return strings


def _cell_count(text):
    return int(text.split()[0])


def _check_font_links(test, page, calibration):
    links = re.findall(r"<link\b[^>]*>", page)
    test.assertEqual(links, re.findall(r"<link\b[^>]*>", calibration))
    test.assertEqual(len(links), 3)
    hosts = set(re.findall(r'href="https://([^/\"]+)', "".join(links)))
    test.assertEqual(hosts, {"fonts.googleapis.com", "fonts.gstatic.com"})
    test.assertEqual("".join(links).count("https://"), 3)
    # Asset elements are different from URLs quoted as input prose. This also
    # catches an HTTP asset, which counting HTTPS strings in the page missed.
    assets = re.findall(r"<(?:link|img|script|iframe|audio|video|source|embed|object|input)\b[^>]*>", page, re.I)
    test.assertEqual(assets, links)


def _check_page(test, html, labels, final, readings, verdicts, statements):
    expected = _expected(labels, final, readings, verdicts)
    page = _parse(html)
    sections = page.sections
    with_final = final is not None
    cover = _cover(expected, len(_jsonl(labels)), with_final)
    test.assertEqual(page.cover["tiles"], cover["tiles"])
    test.assertEqual(page.cover["tile_labels"], cover["tile_labels"])
    test.assertEqual(page.cover["which"], cover["which"])
    test.assertEqual(page.cover["dek"], cover["worst"])
    test.assertIn(cover["size"], page.cover["issue"])
    test.assertEqual([item["name"] for item in sections], [item["name"] for item in expected])
    for section, want in zip(sections, expected):
        test.assertEqual(section.get("statement"), statements[want["name"]])
        test.assertEqual(html.count(esc(statements[want["name"]])), 1)
        test.assertIn("Rubric SHA-256: %s." % want["sha"], section["head"])
        test.assertIn(want["text"], section["head"])
        test.assertIn("UNPARSED: %s." % want["unparsed"], section["head"])
        test.assertEqual(len(section["rows"]), len(want["rows"]))
        for got, row in zip(section["rows"], want["rows"]):
            test.assertEqual(got["run"], row["run"])
            test.assertEqual(got["case"], row["case_id"])
            test.assertEqual(got["mark"], "agree" if row["agree"] else "disagree")
            test.assertEqual(got["cells"]["Run"], row["run"])
            test.assertEqual(got["cells"]["Case"], row["case_id"])
            test.assertEqual(got["cells"]["Verdict"], row["verdict"])
            test.assertEqual(got["cells"]["First-pass"], row["first"])
            test.assertEqual(got["cells"]["Agrees"], "agree" if row["agree"] else "disagree")
            test.assertEqual(got["cells"]["Reason"], row["reason"])
            if with_final:
                test.assertEqual(got["cells"]["Final"], row["final"])
            else:
                test.assertNotIn("Final", got["cells"])
                test.assertNotIn("Change", got["cells"])
            if row["show"]:
                if row["unread"]:
                    test.assertEqual(got["badges"], ["unread"])
                    test.assertNotIn("read", got["badges"])
                    test.assertIsNone(got["reading"])
                    test.assertIsNone(got["open"], "an unread badge discloses nothing")
                    test.assertIsNone(got["summary"])
                    test.assertIn("alarm", got["badge_classes"][0])
                else:
                    test.assertTrue(got["open"], "a disagreement's reading is disclosed, not folded away")
                    test.assertEqual(got["badges"], ["read"])
                    test.assertEqual(got["reading"], row["reading"])
                    test.assertEqual(got["summary"], "Read %s %s %s" % (want["name"], row["run"], row["case_id"]))
            else:
                test.assertEqual(got["badges"], [])
                test.assertIsNone(got["reading"])
                test.assertIsNone(got["open"])
            test.assertEqual(got["change"], row["change"])
        sides = [("first-pass", want["first"])]
        if want["final"] is not None:
            sides.append(("final", want["final"]))
            test.assertEqual(section["changed"], [("final", "Labels the owner changed: %s." % want["changed"])])
        else:
            test.assertEqual(section["changed"], [])
        test.assertEqual(sorted(section["sides"]), sorted(key for key, _side in sides))
        test.assertEqual(len(section["matrices"]), len(sides))
        for matrix, (side_key, counts) in zip(section["matrices"], sides):
            test.assertEqual([cell for cell, _text in matrix], ["JP_HP", "JP_HF", "JF_HP", "JF_HF"])
            cells = [text for _cell, text in matrix]
            test.assertEqual(_cell_count(cells[0]), counts["JP_HP"])
            test.assertIn("JP_HP", cells[0])
            test.assertIn("tn", cells[0])
            test.assertEqual(_cell_count(cells[1]), counts["JP_HF"])
            test.assertIn("JP_HF", cells[1])
            test.assertIn("fn", cells[1])
            test.assertIn("a false pass: the judge passed a real failure", cells[1])
            test.assertNotIn("a false fail", cells[1])
            test.assertEqual(_cell_count(cells[2]), counts["JF_HP"])
            test.assertIn("JF_HP", cells[2])
            test.assertIn("fp", cells[2])
            test.assertIn("a false fail: the judge failed a row the human passed", cells[2])
            test.assertNotIn("a false pass", cells[2])
            test.assertEqual(_cell_count(cells[3]), counts["JF_HF"])
            test.assertIn("JF_HF", cells[3])
            side_text = section["sides"][side_key]
            test.assertIn("Agreement %s (%s)." % (counts["percent"], counts["four"]), side_text)
            test.assertIn(
                "Kappa %s. Kappa at least 0.6, the course's bar: %s." % (counts["kappa_text"], counts["kappa_flag"]),
                side_text,
            )
            test.assertEqual(bar_words() in side_text, counts["meets"])
            test.assertEqual(not_bar_words() in side_text, not counts["meets"])
            if counts["k_of_n"] is None:
                test.assertNotRegex(side_text, r"\d+ of \d+")
            else:
                test.assertIn(counts["k_of_n"], side_text)
    test.assertNotIn("<script", html.lower())
    test.assertNotIn("0 of 0", html)


class PageTests(unittest.TestCase):
    def test_rendered_ties_none_kappa_and_false_pass_tiebreak(self):
        sha = "a" * 64
        scenarios = (
            # Both have undefined kappa: the page must print none and the tie.
            (["PASS", "PASS"], ["PASS", "PASS"], ["PASS", "PASS"], ["PASS", "PASS"], "tied: alpha, beta."),
            # Undefined ranks below a negative kappa, rather than above it.
            (["PASS", "PASS"], ["PASS", "PASS"], ["FAIL", "PASS"], ["PASS", "FAIL"], "labels: alpha."),
            # Both kappa zero: the rubric with more false passes is worst.
            (["PASS", "FAIL"], ["PASS", "PASS"], ["PASS", "PASS"], ["FAIL", "FAIL"], "labels: alpha."),
        )
        for alpha_human, alpha_verdict, beta_human, beta_verdict, ending in scenarios:
            with self.subTest(ending=ending), tempfile_dir() as directory:
                rows = [_HELPER.row("A%d" % (i + 1), {"alpha": alpha_human[i], "beta": beta_human[i]}) for i in range(2)]
                verdicts = [
                    _HELPER.verdict("A%d" % (i + 1), name, values[i], "fixture reason", sha)
                    for name, values in (("alpha", alpha_verdict), ("beta", beta_verdict)) for i in range(2)
                ]
                hashes = {"alpha": sha, "beta": sha}
                labels, _final, readings, provenance, verdict_dir = _HELPER.world(
                    directory, rows, verdicts, hashes, hashes, "Fixture provenance.",
                )
                statements = {"alpha": "Alpha fixture statement.", "beta": "Beta fixture statement."}
                rubric_path = os.path.join(directory, "rubric.json")
                write_text(rubric_path, json.dumps(statements))
                html = render_comparison(labels, None, readings, provenance, verdict_dir, rubric_path)
                _check_page(self, html, labels, None, readings, verdict_dir, statements)
                self.assertTrue(_parse(html).cover["dek"].endswith(ending))
                self.assertEqual("Kappa none." in html, len(set(alpha_human + alpha_verdict)) == 1)

    def test_markup_is_escaped_and_rows_follow_the_inputs(self):
        reason = 'because <b>&"quoted" https://example.invalid/proof http://example.invalid/context'
        reading = "read <script>alert(1)</script>"
        change = "changed <i>reason</i>"
        provenance = "Hand <em>written</em>. Held Out, held-out, trusted, generalise."
        statement = 'Statement <img src=x> for alpha. Do not generalize.'
        beta_statement = "Statement for beta, whose kappa clears 0.6 while its agreement misses 85%."
        hidden = "HIDDEN-READING-TOKEN"
        sha = "a" * 64
        beta_sha = "b" * 64
        with tempfile_dir() as directory:
            marked = os.path.join(directory, "mark<up>")
            os.makedirs(marked)
            final = {
                "case_id": "A1",
                "changes": [{"from": "FAIL", "reason": change, "rubric": "alpha", "to": "PASS"}],
                "human": {"alpha": "PASS", "beta": "FAIL"},
                "note": "",
                "run": "fixture/run",
                "trace_id": "t",
                "unsure": [],
            }
            # beta: two true fails, two true passes and one false fail. Agreement 4 of 5 is 80%,
            # under the 85% bar, while kappa is 8/13, over 0.6: the two numbers disagree, so a tile
            # that counted either one alone would show a different number from meets_bar.
            rows = [
                _HELPER.row("A1", {"alpha": "FAIL", "beta": "FAIL"}),
                _HELPER.row("A2", {"alpha": "PASS", "beta": "FAIL"}),
                _HELPER.row("A3", {"alpha": "PASS", "beta": "PASS"}),
                _HELPER.row("A4", {"alpha": "PASS", "beta": "PASS"}),
                _HELPER.row("A5", {"alpha": "FAIL", "beta": "PASS"}),
            ]
            verdicts = [
                _HELPER.verdict("A1", "alpha", "PASS", reason, sha),
                _HELPER.verdict("A2", "alpha", "PASS", "plain", sha),
                _HELPER.verdict("A3", "alpha", "FAIL", "missed", sha),
                _HELPER.verdict("A4", "alpha", "UNPARSED", "no reply", sha),
                _HELPER.verdict("A5", "alpha", "UNPARSED", "no reply either", sha),
                _HELPER.verdict("A1", "beta", "FAIL", "beta one", beta_sha),
                _HELPER.verdict("A2", "beta", "FAIL", "beta two", beta_sha),
                _HELPER.verdict("A3", "beta", "PASS", "beta three", beta_sha),
                _HELPER.verdict("A4", "beta", "PASS", "beta four", beta_sha),
                _HELPER.verdict("A5", "beta", "FAIL", "beta five", beta_sha),
            ]
            readings = {"alpha": {"fixture/run|A1": reading, "fixture/run|A2": hidden, "fixture/run|A4": "   "}}
            hashes = {"alpha": sha, "beta": beta_sha}
            labels, final_path, readings_path, provenance_path, verdict_dir = _HELPER.world(
                marked, rows, verdicts, hashes, hashes, provenance,
                readings=readings, final=[final] + [dict(row, changes=[]) for row in rows[1:]],
            )
            # world() writes the final rows I pass only when final= is the list. The first row needs the change.
            rubric_path = os.path.join(marked, "rubric.json")
            write_text(rubric_path, json.dumps({"alpha": statement, "beta": beta_statement}))
            out = os.path.join(directory, "not-comparison.html")
            made = cli([
                "report", "--labels", labels, "--final", final_path, "--readings", readings_path,
                "--provenance", provenance_path, "--verdicts", verdict_dir,
                "--md", os.path.join(directory, "out.md"), "--json", os.path.join(directory, "out.json"),
                "--html", out, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            html = open(out, encoding="utf-8").read()
            with open("reports/calibration-v1.html", encoding="utf-8") as handle:
                _check_font_links(self, html, handle.read())
            self.assertNotIn("not-comparison.html", html)
            self.assertIn("--html comparison.html", html)
            self.assertNotIn(reason, html)
            self.assertIn(esc(reason), html)
            self.assertNotIn("<script", html.lower())
            self.assertIn(esc(reading), html)
            self.assertNotIn(change, html)
            self.assertIn(esc(change), html)
            self.assertNotIn(provenance, html)
            self.assertIn(esc(provenance), html)
            self.assertNotIn("<img", html.lower())
            self.assertIn(esc(statement), html)
            self.assertNotIn("mark<up>", html)
            self.assertIn("mark&lt;up&gt;", html)
            self.assertNotIn(hidden, html)
            statements = {"alpha": statement, "beta": beta_statement}
            _check_page(self, html, labels, final_path, readings_path, verdict_dir, statements)
            # A1 changed to PASS and now agrees; A3 is a false fail; A4 is UNPARSED on a PASS, which
            # counts as a FAIL and disagrees; A5 is UNPARSED on a FAIL and agrees, with no reading.
            page = _parse(html)
            self.assertEqual([row["mark"] for row in page.sections[0]["rows"]], ["agree", "agree", "disagree", "disagree", "agree"])
            self.assertIn("Kappa 0.6154. Kappa at least 0.6, the course's bar: yes.", page.sections[1]["sides"]["final"])
            self.assertIn("Agreement 80.0% (0.8000).", page.sections[1]["sides"]["final"])
            self.assertEqual(page.cover["tiles"], ["0", "0", "3"])
            self.assertIn("These tiles count the final labels.", html)
            self.assertEqual(_banned_left(html, _input_strings(
                labels, final_path, readings_path, provenance_path, verdict_dir, rubric_path,
            )), [])
            plain = os.path.join(directory, "first.html")
            made = cli([
                "report", "--labels", labels, "--readings", readings_path, "--provenance", provenance_path,
                "--verdicts", verdict_dir, "--html", plain, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            first_html = open(plain, encoding="utf-8").read()
            self.assertIn("These tiles count the first-pass labels.", first_html)
            self.assertNotIn("Labels the owner changed:", first_html)
            self.assertNotIn('data-label="Final"', first_html)
            _check_page(self, first_html, labels, None, readings_path, verdict_dir, statements)

    def test_committed_page_rows_statements_and_banned_words(self):
        labels = "labels/set1.jsonl"
        final = "labels/set1-final.jsonl"
        readings = "labels/set1-readings.json"
        provenance = "labels/set1-provenance.txt"
        verdicts = "judgments/set1-llama3.1-8b"
        rubric_path = "labels/set1-rubric-provenance.json"
        html = open("reports/judge-set1.html", encoding="utf-8").read()
        with open(rubric_path, encoding="utf-8") as handle:
            statements = json.load(handle)
        _check_page(self, html, labels, final, readings, verdicts, statements)
        self.assertEqual(_banned_left(html, _input_strings(
            labels, final, readings, provenance, verdicts, rubric_path,
        )), [])
        _markdown, document = build_report(labels, final, readings, provenance, verdicts)
        self.assertIn(document["command"], html)
        for rubric in document["rubrics"]:
            side = rubric["final"]
            percent = agreement_percent(side["JP_HP"] + side["JF_HF"], side["JP_HP"] + side["JP_HF"] + side["JF_HP"] + side["JF_HF"])
            four = "none" if side["agreement"] is None else "%.4f" % side["agreement"]
            self.assertIn("%s (%s)" % (percent, four), html)
        self.assertIn("These tiles count the final labels.", html)
        self.assertIn("Worst judge on the final labels: rule_adherence.", html)
        self.assertNotIn(">trusted<", html.lower())

    def test_fixture_page_and_export_match_report(self):
        rubric_path = ROOT + "/rubric-provenance.json"
        with open(rubric_path, encoding="utf-8") as handle:
            statements = json.load(handle)
        with tempfile_dir() as directory:
            page = os.path.join(directory, "page.html")
            made = cli([
                "report", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--html", page, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            html = open(page, encoding="utf-8").read()
            _check_page(
                self, html, ROOT + "/labels.jsonl", ROOT + "/labels-final.jsonl",
                ROOT + "/readings.json", ROOT + "/verdicts", statements,
            )
            self.assertIn("none · none", html)
            out = os.path.join(directory, "course")
            exported = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", out,
                "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertIn("files 4\n", exported.stdout)
            self.assertEqual(open(os.path.join(out, "comparison.html"), "rb").read(), open(page, "rb").read())
            bare = os.path.join(directory, "bare")
            bare_run = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", bare,
            ])
            self.assertEqual(bare_run.returncode, 0, bare_run.stderr)
            self.assertEqual(set(os.listdir(bare)), {"labels.jsonl", "results.md", "rubrics.md"})
            self.assertIn("files 3\n", bare_run.stdout)
            for name in ("labels.jsonl", "results.md", "rubrics.md"):
                self.assertEqual(open(os.path.join(out, name), "rb").read(), open(os.path.join(bare, name), "rb").read())
            first_page = os.path.join(directory, "first.html")
            first_out = os.path.join(directory, "course-first")
            made = cli([
                "report", "--labels", ROOT + "/labels.jsonl", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--html", first_page, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            exported = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", first_out,
                "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertEqual(
                open(os.path.join(first_out, "comparison.html"), "rb").read(),
                open(first_page, "rb").read(),
            )
            self.assertIn("These tiles count the first-pass labels.", open(first_page, encoding="utf-8").read())

    def test_colophon_command_reproduces_the_committed_page(self):
        html = open("reports/judge-set1.html", encoding="utf-8").read()
        start = html.find('<code class="mono">')
        end = html.find("</code>", start)
        command = unescape(html[start + len('<code class="mono">'):end])
        self.assertTrue(command.endswith("--html comparison.html"))
        self.assertNotIn("reports/judge-set1.html", command)
        with tempfile.TemporaryDirectory() as scratch:
            copy = os.path.join(scratch, "repo")
            shutil.copytree(".", copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "_tmp*"))
            done = subprocess.run(shlex.split(command), cwd=copy, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(os.path.join(copy, "comparison.html"), "rb") as handle:
                got = handle.read()
            with open("reports/judge-set1.html", "rb") as handle:
                self.assertEqual(got, handle.read())

    def test_refusals_write_nothing(self):
        sha = "b" * 64
        with tempfile_dir() as directory:
            labels, _final, readings, provenance, verdict_dir = _HELPER.world(
                directory, [_HELPER.row("A1", {"alpha": "PASS"})],
                [_HELPER.verdict("A1", "alpha", "PASS", "because", sha)],
                {"alpha": sha}, {"alpha": sha}, "Hand written.\n",
            )
            good = os.path.join(directory, "rubric.json")
            write_text(good, json.dumps({"alpha": "A statement."}))
            out = os.path.join(directory, "page.html")
            md = os.path.join(directory, "out.md")
            js = os.path.join(directory, "out.json")
            base = [
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ]

            def refuse(args, fragment):
                write_text(out, "OLD-HTML")
                write_text(md, "OLD-MD")
                write_text(js, "OLD-JSON")
                refused = cli(args)
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertNotIn("Traceback", refused.stderr)
                self.assertEqual(refused.stderr.count("error:"), 1)
                self.assertIn(fragment, refused.stderr)
                self.assertEqual(open(out, encoding="utf-8").read(), "OLD-HTML")
                self.assertEqual(open(md, encoding="utf-8").read(), "OLD-MD")
                self.assertEqual(open(js, encoding="utf-8").read(), "OLD-JSON")

            refuse(base[:-2], "must be given together")
            refuse(base[:-4] + ["--rubric-provenance", good], "must be given together")
            missing = os.path.join(directory, "missing.txt")
            refuse(base[:4] + [missing] + base[5:], "missing or unreadable")
            empty = os.path.join(directory, "empty.txt")
            write_text(empty, " \n")
            refuse(base[:4] + [empty] + base[5:], "empty")
            bad_labels = os.path.join(directory, "bad.jsonl")
            write_text(bad_labels, "{")
            refuse(["report", "--labels", bad_labels, "--provenance", provenance, "--verdicts", verdict_dir,
                    "--md", md, "--json", js, "--html", out, "--rubric-provenance", good], "not valid JSON")
            refuse(["report", "--labels", os.path.abspath(labels), "--provenance", provenance, "--verdicts", verdict_dir,
                    "--md", md, "--json", js, "--html", out, "--rubric-provenance", good], "relative path")
            refuse(base[:6] + ["../" + "verdicts"] + base[7:], "relative path")
            empty_labels = os.path.join(directory, "empty-human.jsonl")
            write_text(empty_labels, json.dumps({
                "case_id": "A1", "human": {}, "note": "", "run": "fixture/run", "trace_id": "t", "unsure": [],
            }) + "\n")
            refuse([
                "report", "--labels", empty_labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ], "no rubric")
            refuse(base[:4] + ["~" + "/provenance.txt"] + base[5:], "relative path")
            bad_readings = os.path.join(directory, "bad-readings.json")
            write_text(bad_readings, "[1]")
            refuse([
                "report", "--labels", labels, "--readings", bad_readings, "--provenance", provenance,
                "--verdicts", verdict_dir, "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ], "not an object")
            absent = os.path.join(directory, "no-rubric.json")
            refuse(base[:-1] + [absent], "missing or unreadable")
            write_text(os.path.join(directory, "array.json"), "[1]")
            refuse(base[:-1] + [os.path.join(directory, "array.json")], "not an object")
            write_text(os.path.join(directory, "empty-object.json"), "{}")
            refuse(base[:-1] + [os.path.join(directory, "empty-object.json")], "lacks a rubric")
            write_text(os.path.join(directory, "extra.json"), json.dumps({"alpha": "Yes.", "beta": "No."}))
            refuse(base[:-1] + [os.path.join(directory, "extra.json")], "names a rubric the labels do not have")
            write_text(os.path.join(directory, "blank.json"), json.dumps({"alpha": "  "}))
            refuse(base[:-1] + [os.path.join(directory, "blank.json")], "empty")
            write_text(os.path.join(directory, "number.json"), json.dumps({"alpha": 1}))
            refuse(base[:-1] + [os.path.join(directory, "number.json")], "not text")
            refuse(base[:-1] + [os.path.abspath(good)], "relative path")
            refuse(base[:-2] + ["--html", md, "--rubric-provenance", good], "distinct")
            refuse(base[:-2] + ["--html", js, "--rubric-provenance", good], "distinct")
            blocked = os.path.join(directory, "blocked")
            os.mkdir(blocked)
            fresh_md = os.path.join(directory, "fresh.md")
            fresh_js = os.path.join(directory, "fresh.json")
            refused = cli([
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", fresh_md, "--json", fresh_js, "--html", blocked, "--rubric-provenance", good,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertIn("could not write output", refused.stderr)
            self.assertFalse(os.path.exists(fresh_md))
            self.assertFalse(os.path.exists(fresh_js))
            self.assertTrue(os.path.isdir(blocked))
            write_text(md, "OLD-MD")
            write_text(js, "OLD-JSON")
            refused = cli([
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", blocked, "--rubric-provenance", good,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertEqual(open(md, encoding="utf-8").read(), "OLD-MD")
            self.assertEqual(open(js, encoding="utf-8").read(), "OLD-JSON")

    def test_set1_export_fourth_file_matches_the_page(self):
        with tempfile_dir() as directory:
            out = os.path.join(directory, "course")
            made = cli([
                "export-course", "--labels", "labels/set1.jsonl", "--final", "labels/set1-final.jsonl",
                "--readings", "labels/set1-readings.json", "--provenance", "labels/set1-provenance.txt",
                "--verdicts", "judgments/set1-llama3.1-8b", "--rubrics", "rubrics", "--out", out,
                "--rubric-provenance", "labels/set1-rubric-provenance.json",
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            with open(os.path.join(out, "comparison.html"), "rb") as handle:
                got = handle.read()
            with open("reports/judge-set1.html", "rb") as handle:
                self.assertEqual(got, handle.read())

    def test_export_course_refuses_a_bad_rubric_provenance_and_writes_nothing(self):
        names = {"needs_human_correctness": "A.", "rule_adherence": "B.", "tool_call_accuracy": "C."}
        with tempfile_dir() as directory:
            bad = []
            for label, payload in (
                ("array", "[1]"),
                ("lacks", json.dumps({key: names[key] for key in ("needs_human_correctness", "rule_adherence")})),
                ("extra", json.dumps(dict(names, zeta="Z."))),
                ("blank", json.dumps(dict(names, rule_adherence=" "))),
                ("number", json.dumps(dict(names, rule_adherence=1))),
                ("broken", "{"),
            ):
                path = os.path.join(directory, label + ".json")
                write_text(path, payload)
                bad.append(path)
            bad.append(os.path.join(directory, "absent.json"))
            bad.append("")
            base = [
                "export-course", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics",
            ]
            fresh = os.path.join(directory, "fresh")
            seeded = os.path.join(directory, "seeded")
            names_out = ("rubrics.md", "labels.jsonl", "results.md", "comparison.html")
            for path in bad:
                refused = cli(base + ["--out", fresh, "--rubric-provenance", path])
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertNotIn("Traceback", refused.stderr)
                self.assertEqual(refused.stderr.count("error:"), 1)
                self.assertEqual(refused.stdout, "")
                self.assertFalse(os.path.exists(fresh))
                for name in names_out:
                    write_text(os.path.join(seeded, name), "OLD " + name)
                refused = cli(base + ["--out", seeded, "--rubric-provenance", path])
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertEqual(sorted(os.listdir(seeded)), sorted(names_out))
                for name in names_out:
                    with open(os.path.join(seeded, name), encoding="utf-8") as handle:
                        self.assertEqual(handle.read(), "OLD " + name)

    def test_suite_discovers_each_test_once(self):
        ids = []

        def walk(item):
            if isinstance(item, unittest.TestSuite):
                for child in item:
                    walk(child)
            else:
                ids.append(item.id())

        walk(unittest.TestLoader().discover("tests", top_level_dir="."))
        self.assertEqual(sorted(name for name in set(ids) if ids.count(name) > 1), [])
        self.assertNotIn("ReportTests", globals())

    def test_stacked_rows_hide_empty_cells_and_break_keeps_its_host_width(self):
        # Below 761 px .ledger stacks and prints each cell under its label. An agreeing row has
        # nothing in its Change and Reading cells, and a label over nothing changes nothing for the
        # reader, so the stacked sheet hides an empty cell. And .break must not resize the element
        # that carries it: .wrap carries it and keeps its own max-width. unittest cannot lay the
        # page out, so this pins the two rules in the stylesheet the page inlines.
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        with open("reports/judge-set1.html", encoding="utf-8") as handle:
            page = handle.read()
        self.assertGreater(page.count('<td data-label="Reading"></td>'), 0)
        self.assertIn(".ledger td:empty{display:none}", brace_block(css, "@media (max-width: 760px)"))
        self.assertNotIn("max-width", brace_block(css, ".break{"))
        self.assertIn('<div class="wrap break">', page)
        self.assertIn(css.rstrip("\n"), page)

    def test_font_links_are_the_calibration_pages(self):
        with open("reports/judge-set1.html", encoding="utf-8") as handle:
            page = handle.read()
        with open("reports/calibration-v1.html", encoding="utf-8") as handle:
            calibration = handle.read()
        _check_font_links(self, page, calibration)

    def test_prose_measure_stops_at_80ch(self):
        # The 1200 px rule is what keeps a reason from running the full width of a
        # large window. Removing it survived the suite until this pin.
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        wide = brace_block(css, "@media (min-width: 1200px)")
        self.assertIn("max-width:80ch", wide)
        self.assertIn('.judge-rows td[data-label="Reason"] > span', wide)
        self.assertIn(".judge-rows .change", wide)
        self.assertIn(".judge-rows .reading", wide)

    def test_wide_rows_have_two_tiers_without_a_spare_final_track(self):
        # This pins the rule, not its rendered geometry: the browser measures that.
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        wide = brace_block(css, "@media (min-width: 761px)")
        self.assertIn("display:grid", brace_block(wide, ".ledger.judge-rows tr{"))
        self.assertIn("minmax(0, 3.5fr)", brace_block(wide, ".ledger.judge-rows tr{"))
        self.assertIn("repeat(4, minmax(0, 1fr))", brace_block(wide, ".ledger.judge-rows tr{"))
        self.assertIn("repeat(5, minmax(0, 1fr))", brace_block(wide, ".ledger.judge-rows.with-final tr{"))
        self.assertIn("width:auto", brace_block(wide, ".ledger.judge-rows td:nth-child(n){"))
        self.assertIn("content:attr(data-label)", brace_block(wide, ".ledger.judge-rows td::before{"))
        self.assertIn('td[data-label="Reason"]', wide)
        self.assertIn('td[data-label="Change"]', wide)
        self.assertIn('td[data-label="Reading"]{grid-column:1 / -1}', wide)
        self.assertIn(".ledger.judge-rows td:empty{display:none}", wide)
        self.assertIn("white-space:nowrap", wide)
        self.assertIn("box-shadow:inset 3px 0 0 var(--blood)", brace_block(wide, ".ledger.judge-rows tr.disagree{"))
        with open("reports/judge-set1.html", encoding="utf-8") as handle:
            page = handle.read()
        self.assertEqual(page.count('<table class="ledger judge-rows with-final">'), 3)
        self.assertIn(css.rstrip("\n"), page)
        plain = render_comparison(ROOT + "/labels.jsonl", None, None, ROOT + "/provenance.txt",
                                  ROOT + "/verdicts", ROOT + "/rubric-provenance.json")
        self.assertEqual(plain.count('<table class="ledger judge-rows">'), 3)
        self.assertNotIn('data-label="Final"', plain)
        self.assertNotIn('<td data-label="Change"', plain)

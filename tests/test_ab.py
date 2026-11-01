"""The A/B: a prompt variant, two judged runs, a paired interval, and the report."""
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from io import StringIO
from unittest import mock

import run_eval
from grader.agent import SYSTEM_PROMPT
from run_eval import main
from scorer.ab import format_limit, signed_points
from scorer.checks import CHECKS
from scorer.stats import paired_difference, wilson
from tests.test_contrast import brace_block


def _body(payload):
    class Body:
        def read(self):
            if isinstance(payload, bytes):
                return payload
            return payload.encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return Body()


def _setup_opener(seen=None):
    version = b'{"version":"0.6.2"}'
    tags = b'{"models":[{"name":"qwen3:8b","digest":"sha256:abc"}]}'

    def opener(request, timeout=None):
        if seen is not None:
            seen.append(request.full_url)
        if request.full_url.endswith("/api/version"):
            return _body(version)
        if request.full_url.endswith("/api/tags"):
            return _body(tags)
        raise AssertionError("unexpected url")

    return opener


def _no_network(*_args, **_kwargs):
    raise AssertionError("network")


def _quiet(argv, opener, chat):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout):
        with redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _no_network):
                with mock.patch("grader.agent._chat", chat):
                    status = main(argv, opener=opener)
    return status, stdout.getvalue(), stderr.getvalue()


class PromptFileTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        patcher = mock.patch.object(run_eval, "__file__", os.path.join(scratch.name, "run_eval.py"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.traces = os.path.join(scratch.name, "traces")
        self.work = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(self.work.cleanup)
        # 3.14 returns an absolute path even when dir is "."; the prompt file must be relative.
        self.work_rel = os.path.relpath(self.work.name)
        self.cases = os.path.join(self.work_rel, "cases.json")
        with open(self.cases, "w", encoding="utf-8") as handle:
            json.dump([{
                "case_id": "P1",
                "book": "book",
                "bet_type": "single",
                "stake": 1,
                "legs": [],
                "expected": {"ticket_result": "WIN", "net": 0},
            }], handle)

    def _chat(self, seen):
        def chat(payload, timeout):
            seen.append(payload)
            return {
                "message": {"role": "assistant", "content": '{"ticket_result":"WIN","net":0}'},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            }
        return chat

    def test_help_and_checks_import_do_not_need_the_judge(self):
        import subprocess
        import sys
        help_run = subprocess.run([sys.executable, "run_eval.py", "--help"], capture_output=True, text=True)
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--prompt-file", help_run.stdout)
        imported = subprocess.run([sys.executable, "-c", "import scorer.checks"], capture_output=True, text=True)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertEqual(imported.stdout, "")

    def test_without_the_flag_the_system_message_is_the_default_prompt(self):
        seen = []
        opener_seen = []
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-default"],
            _setup_opener(opener_seen),
            self._chat(seen),
        )
        self.assertEqual(status, 0, stderr)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(seen[0]["messages"][0]["role"], "system")
        with open(os.path.join(self.traces, "prompt-default", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["system_prompt"], SYSTEM_PROMPT)

    def test_the_file_bytes_are_the_system_message_and_are_not_stripped(self):
        path = os.path.join(self.work_rel, "prompt.txt")
        text = "Grade it.\nSecond line.\n"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        bare = []
        flagged = []
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-bare"],
            _setup_opener(),
            self._chat(bare),
        )
        self.assertEqual(status, 0, stderr)
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-file", "--prompt-file", path],
            _setup_opener(),
            self._chat(flagged),
        )
        self.assertEqual(status, 0, stderr)
        self.assertEqual(flagged[0]["messages"][0]["content"], text)
        self.assertTrue(flagged[0]["messages"][0]["content"].endswith("\n"))
        bare_payload = json.loads(json.dumps(bare[0]))
        flagged_payload = json.loads(json.dumps(flagged[0]))
        bare_payload["messages"][0]["content"] = None
        flagged_payload["messages"][0]["content"] = None
        self.assertEqual(bare_payload, flagged_payload)
        with open(os.path.join(self.traces, "prompt-file", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["system_prompt"], text)
        self.assertEqual(set(meta), {
            "run_id", "cases_file", "model", "ollama_version", "model_digest", "think",
            "budgets", "system_prompt", "n_cases", "outcome_matches",
        })

    def _refused(self, argument, fragment):
        seen = []
        opener_seen = []

        def chat(payload, timeout):
            raise AssertionError("graded")

        self.assertFalse(os.path.exists(self.traces))
        status, stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-refused", "--prompt-file", argument],
            _setup_opener(opener_seen),
            chat,
        )
        self.assertEqual(status, 2, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, fragment)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(opener_seen, [])
        self.assertEqual(seen, [])
        self.assertFalse(os.path.exists(self.traces))

    def test_a_bad_prompt_file_exits_before_setup_and_writes_nothing(self):
        missing = os.path.join(self.work_rel, "missing.txt")
        self._refused(missing, "prompt file is unreadable\n")
        empty = os.path.join(self.work_rel, "empty.txt")
        with open(empty, "w", encoding="utf-8", newline="") as handle:
            handle.write(" \n\t")
        self._refused(empty, "prompt file is empty\n")
        binary = os.path.join(self.work_rel, "binary.txt")
        with open(binary, "wb") as handle:
            handle.write(b"\xff")
        self._refused(binary, "prompt file is unreadable\n")
        self._refused("/tmp" + "/prompt.txt", "prompt file must be a relative path, not an absolute path\n")
        self._refused("~" + "/prompt.txt", "prompt file must be a relative path, not an absolute path\n")
        self._refused("../prompt.txt", "prompt file must be a relative path inside this directory\n")


class VariantTests(unittest.TestCase):
    def test_compare_first_differs_by_one_line(self):
        with open("variants/compare-first.txt", encoding="utf-8", newline="") as handle:
            variant = handle.read()
        self.assertFalse(variant.endswith("\n"))
        self.assertFalse(SYSTEM_PROMPT.endswith("\n"))
        base = SYSTEM_PROMPT.split("\n")
        other = variant.split("\n")
        self.assertEqual(len(base), len(other))
        changed = [(left, right) for left, right in zip(base, other) if left != right]
        removed = (
            "3. Grade each leg: W (won), L (lost), P (push), VOID, MOOT "
            "(not needed: another leg already lost), OPEN (match not final) or "
            "NEEDS_HUMAN (a fact you need is missing or a rule says so)."
        )
        added = (
            "3. Grade each leg by comparing it with the facts. In the same message as your "
            "settle_ticket call, first write one line per leg: the selection, the score or stat "
            "from get_match_facts with home and away named, and what that means for the selection. "
            "Then give its result: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg "
            "already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a "
            "rule says so)."
        )
        self.assertEqual(changed, [(removed, added)])
        self.assertEqual(len(removed), 184)
        self.assertEqual(len(added), 434)


class PairedDifferenceTests(unittest.TestCase):
    def test_published_table_and_a_zero_sample(self):
        # Worked by hand for 10, 5, 0, 17. n = 32.
        # p1 = (10+5)/32 = 15/32, p2 = (10+0)/32 = 10/32, fall = (5-0)/32 = 5/32.
        # Wilson limits of those two proportions, then Newcombe's phi from
        # A = 10*17 - 5*0 = 170 and B = max(170 - 16, 0) = 154, give the
        # lower and upper limits in the row below. The expected numbers are
        # that hand table, not this function's own output.
        table = (
            ((10, 5, 0, 17), (0.1562, 0.0164, 0.2853)),
            ((11, 4, 0, 17), (0.1250, -0.0036, 0.2454)),
            ((8, 7, 1, 16), (0.1875, 0.0139, 0.3438)),
            ((9, 6, 1, 16), (0.1562, -0.0082, 0.3067)),
            ((0, 0, 0, 32), (0.0000, -0.1072, 0.1072)),
            ((6, 6, 6, 14), (0.0000, -0.2104, 0.2104)),
        )
        for cells, expected in table:
            with self.subTest(cells=cells):
                got = paired_difference(*cells)
                self.assertEqual(tuple(round(part, 4) for part in got), expected)
                a, b, c, d = cells
                self.assertEqual(got[0], (b - c) / (a + b + c + d))
        swapped = paired_difference(10, 0, 5, 17)
        self.assertLess(swapped[0], 0)
        self.assertEqual(round(swapped[0], 4), -0.1562)
        self.assertIsNone(paired_difference(0, 0, 0, 0))
        # A z whose square overflows leaves NaN Wilson limits. They must come back as NaN,
        # not be clamped to a point: the report refuses what it cannot print.
        _fall, lower, upper = paired_difference(10, 5, 0, 17, z=1e308)
        self.assertTrue(math.isnan(lower) and math.isnan(upper))
        _fall, lower, upper = paired_difference(10, 5, 0, 17, z=float("nan"))
        self.assertTrue(math.isnan(lower) and math.isnan(upper))


class NumberFormatTests(unittest.TestCase):
    def test_half_rounds_away_from_zero_in_both_directions(self):
        # 1 of 16 is 6.25 points, halfway between 6.2 and 6.3.
        self.assertEqual(signed_points(1, 16), "+6.3")
        self.assertEqual(signed_points(-1, 16), "-6.3")
        self.assertEqual(signed_points(0, 4), "+0.0")
        self.assertEqual(signed_points(1, 8), "+12.5")
        self.assertEqual(format_limit(0.0), "0.0")
        self.assertEqual(format_limit(-0.0), "0.0")
        self.assertEqual(format_limit(-0.0004), "0.0")
        self.assertEqual(format_limit(0.0125), "1.3")
        self.assertEqual(format_limit(-0.0125), "-1.3")

    def test_ab_rows_have_their_own_empty_cell_rule(self):
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        # The phone rule and the wide rule are each their own, so the judge rows keep theirs.
        self.assertEqual(css.count(".ledger.ab-rows td:empty{display:none}"), 2)
        self.assertIn(".ledger td:empty{display:none}", css)
        self.assertIn(".ledger.judge-rows td:empty{display:none}", css)
        self.assertIn(".ledger.ab-rows td[data-short] > span{white-space:nowrap}", css)
        self.assertIn('td[data-label="A codes"]', css)
        self.assertIn('td[data-label="Reasons"]{grid-column:1 / -1}', css)
        self.assertIn("pre-wrap", brace_block(css, ".prompt-diff{"))

    def test_ship_is_a_whole_word(self):
        self.assertIsNone(BANNED_WORD.search("relationship"))
        self.assertIsNone(BANNED_WORD.search("shipshape"))
        self.assertIsNotNone(BANNED_WORD.search("ship"))
        self.assertIsNotNone(BANNED_WORD.search("no-ship"))
        self.assertIsNotNone(BANNED_WORD.search("Ship it"))


ROOT = "tests/fixtures/ab"
ALPHA = ROOT + "/alpha"
BETA = ROOT + "/beta"
BANNED_WORD = re.compile(
    r"\b(?:held out|held-out|trusted|generalise|generalize|ship|no-ship)\b",
    re.IGNORECASE,
)
# What the traces were built to fire. The test counts from this table.
FLAGS = {
    "T1": {"alpha": {"NO_FINAL_ANSWER"}, "beta": set()},
    "T2": {"alpha": {"NO_FINAL_ANSWER"}, "beta": set()},
    "T3": {"alpha": {"NO_FINAL_ANSWER"}, "beta": {"WIN_LOSS_FLIP"}},
    "T4": {"alpha": {"RULE_TOPIC_MISS", "OUTPUT_LIMIT_SPRAY"}, "beta": set()},
}
VOID = {"meta", "link", "br", "img", "input", "col"}


def judge_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "scorer.judge", *args],
        capture_output=True, text=True,
    )


def _rel_temp():
    raw = tempfile.TemporaryDirectory(dir=".")
    return raw, os.path.relpath(raw.name)


def own_wilson(k, n, z=1.96):
    proportion = k / n
    denominator = 1.0 + z * z / n
    centre = (proportion + z * z / (2.0 * n)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / n + z * z / (4.0 * n * n)) / denominator
    return (centre - margin, centre + margin)


def own_paired(a, b, c, d, z=1.96):
    """The spec's method 10, written here so the report is not checked against itself."""
    n = a + b + c + d
    p1 = (a + b) / n
    p2 = (a + c) / n
    l1, u1 = own_wilson(a + b, n, z)
    l2, u2 = own_wilson(a + c, n, z)
    disc = a * d - b * c
    adj = max(disc - n / 2.0, 0.0) if disc > 0 else float(disc)
    product = (a + b) * (c + d) * (a + c) * (b + d)
    phi = 0.0 if product == 0 else adj / math.sqrt(product)
    diff = p1 - p2
    lower_in = (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2
    upper_in = (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2
    lower = diff - math.sqrt(lower_in if lower_in > 0.0 else 0.0)
    upper = diff + math.sqrt(upper_in if upper_in > 0.0 else 0.0)
    return diff, lower, upper


def own_points(numerator, denominator):
    sign = "-" if numerator < 0 else "+"
    scaled = abs(numerator) * 1000
    quot, rem = divmod(scaled, denominator)
    if rem * 2 >= denominator:
        quot += 1
    return "%s%d.%d" % (sign, quot // 10, quot % 10)


def own_limit(proportion):
    if proportion == 0.0:
        return "0.0"
    points = (Decimal(str(proportion)) * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if points == 0:
        return "0.0"
    return format(points, "f")


def own_verdict(reply):
    for line in reply.splitlines():
        if line.strip() == "":
            continue
        if line.strip() in ("PASS", "FAIL"):
            return line.strip()
        return "UNPARSED"
    return "UNPARSED"


def _cells(case_ids, left, right):
    both = only_a = only_b = neither = 0
    for case_id in case_ids:
        a_on = case_id in left
        b_on = case_id in right
        if a_on and b_on:
            both += 1
        elif a_on:
            only_a += 1
        elif b_on:
            only_b += 1
        else:
            neither += 1
    return both, only_a, only_b, neither


class _Text(HTMLParser):
    def __init__(self):
        super(_Text, self).__init__(convert_charrefs=True)
        self.stack = []
        self.computed = []
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        parent = self.stack[-1] if self.stack else False
        marked = parent or any(name == "data-input" for name, _value in attrs)
        self.stack.append(marked)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack and self.stack[-1]:
            self.inputs.append(data)
        else:
            self.computed.append(data)


def _split_page(html):
    parser = _Text()
    parser.feed(html)
    return "".join(parser.computed), "".join(parser.inputs)


class AbCommandTests(unittest.TestCase):
    def setUp(self):
        raw, self.work = _rel_temp()
        self.addCleanup(raw.cleanup)

    def _seed_run(self, out):
        os.makedirs(out)
        for name in ("verdicts.jsonl", "judge_meta.json"):
            with open(os.path.join(out, name), "w", encoding="utf-8") as handle:
                handle.write("OLD-" + name)

    def _run_ab(self, out, **kw):
        return judge_cli([
            "run-ab",
            "--a", kw.get("a", ALPHA),
            "--b", kw.get("b", BETA),
            "--rubrics", kw.get("rubrics", ROOT + "/rubrics"),
            "--frozen-rubrics", kw.get("frozen", ROOT + "/frozen.json"),
            "--adapter", "ollama:llama3.1:8b",
            "--http-fixture", kw.get("http", ROOT + "/http.json"),
            "--out", out,
        ])

    def _assert_refused(self, result, fragment, out):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.count("error:"), 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertNotIn("Ollama", result.stderr)
        for name in ("verdicts.jsonl", "judge_meta.json"):
            with open(os.path.join(out, name), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "OLD-" + name)

    def test_run_ab_keeps_each_reply_on_its_run_case_and_rubric(self):
        out = self.work + "/judgments"
        made = self._run_ab(out)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.assertEqual(made.stdout, "verdicts 24\n")
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        rows = []
        with open(os.path.join(out, "verdicts.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                rows.append(json.loads(line))
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows, sorted(rows, key=lambda row: (row["run"], row["case_id"], row["rubric"])))
        for row in rows:
            key = "llama3.1:8b|%s|%s|%s" % (row["run"], row["case_id"], row["rubric"])
            self.assertEqual(row["reply"], replies[key])
            self.assertEqual(row["verdict"], own_verdict(row["reply"]))
            self.assertEqual(set(row), {
                "run", "case_id", "trace_id", "rubric", "rubric_sha256", "verdict", "reason", "reply",
            })
        with open(os.path.join(out, "judge_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertNotIn("labels_sha256", meta)
        self.assertEqual(meta["runs"], [ALPHA, BETA])
        self.assertEqual(meta["adapter"], "http-fixture")
        self.assertEqual(meta["model"], "llama3.1:8b")
        again = self.work + "/again"
        second = self._run_ab(again)
        self.assertEqual(second.returncode, 0, second.stderr)
        for name in ("verdicts.jsonl", "judge_meta.json"):
            with open(os.path.join(out, name), "rb") as handle:
                first = handle.read()
            with open(os.path.join(again, name), "rb") as handle:
                self.assertEqual(handle.read(), first)

    def test_the_case_text_does_not_name_the_run_or_the_changed_line(self):
        from scorer.ab import run_ab
        from scorer.judge import FixtureClient
        seen = []
        real = FixtureClient.chat

        def wrapped(client, model, system, user, key):
            seen.append(user)
            return real(client, model, system, user, key)

        out = self.work + "/judgments"
        args = mock.Mock(
            a=ALPHA, b=BETA, rubrics=ROOT + "/rubrics", frozen_rubrics=ROOT + "/frozen.json",
            adapter="ollama:llama3.1:8b", http_fixture=ROOT + "/http.json", out=out,
        )
        with open("variants/compare-first.txt", encoding="utf-8", newline="") as handle:
            changed = handle.read().split("\n")[5]
        with mock.patch.object(FixtureClient, "chat", wrapped):
            with redirect_stdout(StringIO()):
                run_ab(args)
        self.assertEqual(len(seen), 24)
        for text in seen:
            self.assertNotIn(ALPHA, text)
            self.assertNotIn(BETA, text)
            self.assertNotIn("alpha", text)
            self.assertNotIn("beta", text)
            self.assertNotIn(changed, text)

    def test_run_ab_refusals_write_nothing_and_do_not_call_the_model(self):
        failing = self.work + "/fail-chat.json"
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["fail"] = "chat"
        with open(failing, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

        out = self.work + "/same"
        self._seed_run(out)
        self._assert_refused(self._run_ab(out, b=ALPHA, http=failing), "system_prompt values are equal", out)

        copied = self.work + "/tree"
        shutil.copytree(ROOT, copied)
        _retarget(os.path.join(copied, "alpha", "settlement-traces.json"), {"T4": "T9"})
        out = self.work + "/cases"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "same case ids", out,
        )

        shutil.rmtree(copied)
        shutil.copytree(ROOT, copied)
        _retarget(os.path.join(copied, "alpha", "settlement-traces.json"), {"T2": "T1"})
        out = self.work + "/dup"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "duplicate", out,
        )

        shutil.rmtree(copied)
        shutil.copytree(ROOT, copied)
        os.remove(os.path.join(copied, "beta", "run_meta.json"))
        out = self.work + "/meta"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "run_meta.json is missing", out,
        )

        shutil.rmtree(copied)
        shutil.copytree(ROOT, copied)
        _set_meta(os.path.join(copied, "beta", "run_meta.json"), "ollama_version", " ")
        out = self.work + "/version"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "lacks ollama_version", out,
        )

        shutil.rmtree(copied)
        shutil.copytree(ROOT, copied)
        _set_meta(os.path.join(copied, "alpha", "run_meta.json"), "model_digest", "")
        out = self.work + "/digest"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "lacks model_digest", out,
        )

        shutil.rmtree(copied)
        shutil.copytree(ROOT, copied)
        _set_meta(os.path.join(copied, "beta", "run_meta.json"), "model", "other:8b")
        out = self.work + "/model"
        self._seed_run(out)
        self._assert_refused(
            self._run_ab(out, a=copied + "/alpha", b=copied + "/beta", http=failing),
            "differs in model", out,
        )

        frozen = self.work + "/frozen.json"
        with open(ROOT + "/frozen.json", encoding="utf-8") as handle:
            data = json.load(handle)
        data["rubrics"]["rule_adherence"] = "0" * 64
        with open(frozen, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        out = self.work + "/frozen"
        self._seed_run(out)
        self._assert_refused(self._run_ab(out, frozen=frozen, http=failing), "not the frozen text", out)

    def _ab(self, verdicts, **kw):
        return [
            "ab",
            "--a", kw.get("a", ALPHA),
            "--b", kw.get("b", BETA),
            "--verdicts", verdicts,
            "--thresholds", kw.get("thresholds", ROOT + "/thresholds.json"),
            "--statement", kw.get("statement", ROOT + "/statement.txt"),
            "--set1", kw.get("set1", ROOT + "/set1.json"),
            "--cases", kw.get("cases", ROOT + "/cases.json"),
        ]

    def _seed_outputs(self):
        paths = {}
        for name, text in (("out.md", "OLD-MD"), ("out.json", "OLD-JSON"), ("out.html", "OLD-HTML")):
            paths[name] = self.work + "/" + name
            with open(paths[name], "w", encoding="utf-8") as handle:
                handle.write(text)
        return paths

    def _assert_ab_refused(self, args, fragment):
        paths = self._seed_outputs()
        result = judge_cli(args + ["--md", paths["out.md"], "--json", paths["out.json"], "--html", paths["out.html"]])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.count("error:"), 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(fragment, result.stderr)
        for name, text in (("out.md", "OLD-MD"), ("out.json", "OLD-JSON"), ("out.html", "OLD-HTML")):
            with open(paths[name], encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text)

    def _judged(self):
        out = self.work + "/judgments"
        made = self._run_ab(out)
        self.assertEqual(made.returncode, 0, made.stderr)
        return out

    def test_ab_matches_counts_from_the_fixture_table(self):
        verdicts = self._judged()
        html_path = self.work + "/page.html"
        md_path = self.work + "/page.md"
        json_path = self.work + "/page.json"
        made = judge_cli(self._ab(verdicts) + ["--md", md_path, "--json", json_path, "--html", html_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(json_path, encoding="utf-8") as handle:
            document = json.load(handle)
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        with open(md_path, encoding="utf-8") as handle:
            markdown = handle.read()
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        case_ids = ["T1", "T2", "T3", "T4"]
        by_name = {row["name"]: row for row in document["metrics"]}
        self.assertEqual(sorted(by_name), sorted(list(CHECKS) + [
            "needs_human_correctness", "rule_adherence", "tool_call_accuracy",
        ]))
        self.assertEqual(len(by_name), len(set(by_name)))
        keys = []

        def walk(value, key=None):
            if isinstance(value, dict):
                for child, item in value.items():
                    keys.append(child)
                    walk(item, child)
            elif isinstance(value, list):
                for item in value:
                    walk(item, key)

        walk(document)
        for banned in ("sum", "average", "blended", "mean", "overall", "combined"):
            self.assertNotIn(banned, keys)
        for code in CHECKS:
            left = {case for case, sides in FLAGS.items() if code in sides["alpha"]}
            right = {case for case, sides in FLAGS.items() if code in sides["beta"]}
            both, only_a, only_b, neither = _cells(case_ids, left, right)
            _lower, lower, upper = own_paired(both, only_a, only_b, neither)
            row = by_name[code]
            self.assertEqual(row["count_a"], both + only_a)
            self.assertEqual(row["count_b"], both + only_b)
            self.assertEqual(row["only_a"], only_a)
            self.assertEqual(row["only_b"], only_b)
            self.assertEqual(row["delta_tickets"], "%+d" % ((both + only_a) - (both + only_b)))
            self.assertEqual(row["delta_points"], own_points((both + only_a) - (both + only_b), 4))
            self.assertEqual(row["lower_points"], own_limit(lower))
            self.assertEqual(row["upper_points"], own_limit(upper))
            self.assertEqual(html.count('data-metric="%s"' % code), 1)
        judge_cases = {name: {"alpha": set(), "beta": set(), "pass_a": 0, "pass_b": 0, "unparsed_a": 0, "unparsed_b": 0}
                       for name in ("needs_human_correctness", "rule_adherence", "tool_call_accuracy")}
        for case_id in case_ids:
            for rubric in judge_cases:
                for side, bucket in (("alpha", "pass_a"), ("beta", "pass_b")):
                    run = ALPHA if side == "alpha" else BETA
                    reply = replies["llama3.1:8b|%s|%s|%s" % (run, case_id, rubric)]
                    verdict = own_verdict(reply)
                    if verdict != "PASS":
                        judge_cases[rubric][side].add(case_id)
                    else:
                        judge_cases[rubric][bucket] += 1
                    if verdict == "UNPARSED":
                        judge_cases[rubric]["unparsed_" + side[0]] += 1
        for rubric, info in judge_cases.items():
            both, only_a, only_b, neither = _cells(case_ids, info["alpha"], info["beta"])
            _lower, lower, upper = own_paired(both, only_a, only_b, neither)
            row = by_name[rubric]
            self.assertEqual(row["pass_a"], info["pass_a"])
            self.assertEqual(row["pass_b"], info["pass_b"])
            self.assertEqual(row["unparsed_a"], info["unparsed_a"])
            self.assertEqual(row["unparsed_b"], info["unparsed_b"])
            self.assertEqual(row["fail_to_pass"], only_a)
            self.assertEqual(row["pass_to_fail"], only_b)
            self.assertEqual(row["delta_points"], own_points((both + only_a) - (both + only_b), 4))
            self.assertEqual(row["lower_points"], own_limit(lower))
            self.assertEqual(row["upper_points"], own_limit(upper))
        # Recompute the boolean from the test's cells so a backwards sign fails here.
        def held_code(code, kind, **rule):
            left = {case for case, sides in FLAGS.items() if code in sides["alpha"]}
            right = {case for case, sides in FLAGS.items() if code in sides["beta"]}
            both, only_a, only_b, _neither = _cells(case_ids, left, right)
            count_a = both + only_a
            count_b = both + only_b
            _fall, lower, _upper = own_paired(both, only_a, only_b, _neither)
            if kind == "must_fall":
                if count_a < rule["min_net_fall"] or (count_a - count_b) < rule["min_net_fall"]:
                    return False
                if rule["interval"] and not (lower > 0):
                    return False
                return True
            return (count_b - count_a) <= rule["max_rise"]

        computed = {
            "NO_FINAL_ANSWER": held_code("NO_FINAL_ANSWER", "must_fall", min_net_fall=3, interval=True),
            "RULE_TOPIC_MISS": held_code("RULE_TOPIC_MISS", "must_fall", min_net_fall=1, interval=False),
            "OUTPUT_LIMIT_SPRAY": held_code("OUTPUT_LIMIT_SPRAY", "must_fall", min_net_fall=1, interval=True),
            "PLACEHOLDER_ECHO": held_code("PLACEHOLDER_ECHO", "must_fall", min_net_fall=1, interval=False),
            "GRADED_WITHOUT_LOOKUP": held_code("GRADED_WITHOUT_LOOKUP", "max_rise", max_rise=0),
            "WIN_LOSS_FLIP": held_code("WIN_LOSS_FLIP", "max_rise", max_rise=0),
            "needs_human_correctness": (judge_cases["needs_human_correctness"]["pass_a"]
                                        - judge_cases["needs_human_correctness"]["pass_b"]) <= 0,
            "tool_call_accuracy": (judge_cases["tool_call_accuracy"]["pass_a"]
                                   - judge_cases["tool_call_accuracy"]["pass_b"]) <= 0,
        }
        by_threshold = {row["name"]: row for row in document["threshold_rows"]}
        holding = 0
        for name, should in computed.items():
            self.assertEqual(by_threshold[name]["held"], should, name)
            self.assertIn('data-threshold="%s" data-held="%s"' % (name, "yes" if should else "no"), html)
            if should:
                holding += 1
                self.assertNotIn('data-threshold="%s" data-held="yes"' % name, html.replace(
                    'class="ab-threshold" data-threshold="%s" data-held="yes"' % name, ""))
            else:
                self.assertIn('class="ab-threshold ab-fail" data-threshold="%s"' % name, html)
        self.assertEqual(by_threshold["rule_adherence"]["held"], None)
        self.assertTrue(by_threshold["rule_adherence"]["report_only"])
        self.assertIn('data-threshold="rule_adherence" data-held="report"', html)
        self.assertEqual(document["thresholds_held"], "%s of %s" % (holding, len(computed)))
        self.assertIn(document["thresholds_held"] + " thresholds held.", html)
        self.assertNotIn("0 of 0", html)
        self.assertNotIn("0 of 0", markdown)
        self.assertIn("no false passes", html)
        self.assertIn("1 of 2", html)
        self.assertIn('data-primary="NO_FINAL_ANSWER"', html)
        self.assertNotIn('class="pill', html)
        self.assertNotIn("stat good", html)
        self.assertNotIn("stat alarm", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn(html_path, html)
        self.assertNotIn("--md", html)
        self.assertNotIn("--json", html)
        self.assertIn("--html reports/ab.html", html)
        self.assertIn("&lt;b&gt;ship&lt;/b&gt;", html)
        self.assertIn("&lt;b&gt;markup&lt;/b&gt;", html)
        self.assertNotIn("<b>ship</b>", html)
        self.assertNotIn("<b>markup</b>", html)
        computed_text, input_text = _split_page(html)
        self.assertIsNone(BANNED_WORD.search(computed_text))
        self.assertIsNotNone(BANNED_WORD.search(input_text))
        stripped = re.sub(r"<!-- input:.*?-->.*?<!-- /input:.*?-->", "", markdown, flags=re.S)
        self.assertIsNone(BANNED_WORD.search(stripped))
        self.assertIn("trusted", markdown)

    def test_ab_refusals_write_nothing(self):
        verdicts = self._judged()
        empty = self.work + "/empty.txt"
        with open(empty, "w", encoding="utf-8") as handle:
            handle.write(" \n")
        self._assert_ab_refused(self._ab(verdicts, statement=empty), "statement file is empty")
        self._assert_ab_refused(self._ab(verdicts, statement=self.work + "/missing.txt"), "missing or unreadable")
        bad = self.work + "/thresholds.json"
        with open(ROOT + "/thresholds.json", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["extra"] = 1
        with open(bad, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "wrong keys")
        payload.pop("extra")
        payload["interval"]["method"] = "other"
        with open(bad, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "interval.method")
        payload["interval"]["method"] = "newcombe-1998-method-10"
        payload["interval"]["z"] = "1.96"
        with open(bad, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "interval.z")
        with open(ROOT + "/thresholds.json", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["code"][0]["code"] = "NOT_A_CODE"
        with open(bad, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "the data lacks")
        with open(os.path.join(verdicts, "verdicts.jsonl"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        short = self.work + "/short"
        os.makedirs(short)
        with open(os.path.join(short, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines[:-1]) + "\n")
        shutil.copy(os.path.join(verdicts, "judge_meta.json"), os.path.join(short, "judge_meta.json"))
        self._assert_ab_refused(self._ab(short), "missing verdict")
        with open(os.path.join(short, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines + [lines[0]]) + "\n")
        self._assert_ab_refused(self._ab(short), "duplicate verdict")
        changed = json.loads(lines[0])
        changed["trace_id"] = "not-the-trace"
        with open(os.path.join(short, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join([json.dumps(changed)] + lines[1:]) + "\n")
        self._assert_ab_refused(self._ab(short), "trace_id")
        with open(os.path.join(verdicts, "judge_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        meta["runs"] = [BETA, ALPHA]
        with open(os.path.join(short, "judge_meta.json"), "w", encoding="utf-8") as handle:
            json.dump(meta, handle)
        with open(os.path.join(short, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        self._assert_ab_refused(self._ab(short), "runs do not match")
        same = self.work + "/same-out"
        result = judge_cli(self._ab(verdicts) + ["--md", same, "--json", same])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("distinct", result.stderr)
        self.assertFalse(os.path.exists(same))

    def _thresholds_variant(self, mutate, text=None):
        path = self.work + "/thr-%s.json" % len(os.listdir(self.work))
        if text is not None:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            return path
        with open(ROOT + "/thresholds.json", encoding="utf-8") as handle:
            payload = json.load(handle)
        mutate(payload)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return path

    def test_nonsense_threshold_values_are_refused(self):
        # Before this check, z of NaN, 0 or 1e308 printed a collapsed interval ("75.0 to 75.0")
        # and an interval-gated row read "Held" on any positive fall; -1.96 mirrored the limits;
        # a negative limit or a must_fall of 0 was a rule that decided nothing. Each exited 0.
        verdicts = self._judged()
        with open(ROOT + "/thresholds.json", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(source.count("1.96"), 1)
        nan = self._thresholds_variant(None, text=source.replace("1.96", "NaN"))
        self._assert_ab_refused(self._ab(verdicts, thresholds=nan), "interval.z is not a finite number above zero")
        for value in (0, -1.96, float("inf")):
            bad = self._thresholds_variant(lambda d, v=value: d["interval"].__setitem__("z", v))
            with self.subTest(z=value):
                self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "interval.z is not a finite number above zero")
        huge = self._thresholds_variant(lambda d: d["interval"].__setitem__("z", 1e308))
        self._assert_ab_refused(self._ab(verdicts, thresholds=huge), "is not finite")
        for label, mutate in (
            ("min_net_fall 0", lambda d: d["code"][0].__setitem__("min_net_fall", 0)),
            ("min_net_fall -1", lambda d: d["code"][0].__setitem__("min_net_fall", -1)),
            ("max_rise -1", lambda d: d["code"][4].__setitem__("max_rise", -1)),
            ("max_pass_fall -1", lambda d: d["judge"][0].__setitem__("max_pass_fall", -1)),
        ):
            bad = self._thresholds_variant(mutate)
            with self.subTest(label=label):
                self._assert_ab_refused(self._ab(verdicts, thresholds=bad), "is below")
        # The committed thresholds still pass: z 1.96 and every limit at least 0.
        fine = judge_cli(self._ab(verdicts) + ["--md", self.work + "/fine.md"])
        self.assertEqual(fine.returncode, 0, fine.stderr)

    def test_a_cases_file_of_the_wrong_shape_is_refused(self):
        # [1] raised TypeError and {"expected": 5} raised AttributeError, each a traceback with status 1.
        verdicts = self._judged()
        for label, payload in (
            ("a list of integers", [1]),
            ("expected not an object", [{"case_id": case, "expected": 5} for case in ("T1", "T2", "T3", "T4")]),
            ("an object, not a list", {}),
            ("a case missing", [{"case_id": case, "expected": {"ticket_result": "WIN", "net": 1.0}} for case in ("T1", "T2", "T3")]),
        ):
            path = self.work + "/cases-%s.json" % len(os.listdir(self.work))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            with self.subTest(label=label):
                self._assert_ab_refused(self._ab(verdicts, cases=path), "cases")
        binary = self.work + "/cases-binary.json"
        with open(binary, "wb") as handle:
            handle.write(b"\xff")
        self._assert_ab_refused(self._ab(verdicts, cases=binary), "unreadable cases file")
        self._assert_ab_refused(self._ab(verdicts, cases=self.work + "/no-cases.json"), "unreadable cases file")

    def test_threshold_rows_carry_their_limits_and_the_observed_value(self):
        # The spec: "Each row of thresholds.json with its numbers and whether it held." Before this,
        # the Markdown row was "NAME kind. Held." and the page row had the limit but not the value
        # it was compared with. The expected sentences are built from the FLAGS table and the
        # fixture replies, not from the report.
        verdicts = self._judged()
        md_path = self.work + "/rows.md"
        html_path = self.work + "/rows.html"
        made = judge_cli(self._ab(verdicts) + ["--md", md_path, "--html", html_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(md_path, encoding="utf-8") as handle:
            markdown = handle.read()
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        from html import unescape
        case_ids = ["T1", "T2", "T3", "T4"]
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        with open(ROOT + "/thresholds.json", encoding="utf-8") as handle:
            thresholds = json.load(handle)

        def code_cells(code):
            left = {case for case, sides in FLAGS.items() if code in sides["alpha"]}
            right = {case for case, sides in FLAGS.items() if code in sides["beta"]}
            return _cells(case_ids, left, right)

        def passes(run, rubric):
            return sum(own_verdict(replies["llama3.1:8b|%s|%s|%s" % (run, case, rubric)]) == "PASS" for case in case_ids)

        expected = []
        for row in thresholds["code"]:
            both, only_a, only_b, neither = code_cells(row["code"])
            count_a, count_b = both + only_a, both + only_b
            if row["kind"] == "must_fall":
                _fall, lower, _upper = own_paired(both, only_a, only_b, neither)
                held = (count_a - count_b) >= row["min_net_fall"] and (not row["interval_excludes_zero"] or lower > 0)
                text = "%s must_fall. %s. min_net_fall %s, interval_excludes_zero %s. Observed fall %+d tickets%s." % (
                    row["code"], "Held" if held else "Not held", row["min_net_fall"],
                    "yes" if row["interval_excludes_zero"] else "no", count_a - count_b,
                    ", lower limit %s points" % own_limit(lower) if row["interval_excludes_zero"] else "",
                )
            else:
                held = (count_b - count_a) <= row["max_rise"]
                text = "%s max_rise. %s. max_rise %s. Observed rise %+d tickets." % (
                    row["code"], "Held" if held else "Not held", row["max_rise"], count_b - count_a,
                )
            expected.append((row["code"], text))
        for row in thresholds["judge"]:
            if row["kind"] == "report_only":
                expected.append((row["rubric"], "%s report_only. Not counted." % row["rubric"]))
                continue
            fall = passes(ALPHA, row["rubric"]) - passes(BETA, row["rubric"])
            expected.append((row["rubric"], "%s max_pass_fall. %s. max_pass_fall %s. Observed PASS fall %+d tickets." % (
                row["rubric"], "Held" if fall <= row["max_pass_fall"] else "Not held", row["max_pass_fall"], fall,
            )))
        self.assertEqual(len(expected), 9)
        held_values = {text.split(". ")[1].rstrip(".") for _name, text in expected}
        self.assertEqual(held_values, {"Held", "Not held", "Not counted"})
        section = markdown.split("## Thresholds\n", 1)[1].split("\n## Tickets", 1)[0]
        for name, text in expected:
            with self.subTest(name=name):
                self.assertIn("\n" + text + "\n", section)
                match = re.search(r'data-threshold="%s" data-held="[a-z]+">(.*?)</p>' % re.escape(name), html)
                self.assertIsNotNone(match, name)
                self.assertEqual(unescape(match.group(1)), text)

    def test_markup_in_the_prompt_diff_and_the_path_is_escaped(self):
        tree = self.work + "/tree"
        os.makedirs(tree)
        left = tree + "/side&a"
        right = tree + "/side&b"
        shutil.copytree(ALPHA, left)
        shutil.copytree(BETA, right)
        _set_meta(left + "/run_meta.json", "system_prompt", "left <b>diff</b>\n")
        _set_meta(right + "/run_meta.json", "system_prompt", "right <b>diff</b>\n")
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            http = json.load(handle)
        replies = {}
        for key, value in http["replies"].items():
            replies[key.replace(ALPHA, left).replace(BETA, right)] = value
        http["replies"] = replies
        http_path = self.work + "/http.json"
        with open(http_path, "w", encoding="utf-8") as handle:
            json.dump(http, handle)
        out = self.work + "/judged"
        made = self._run_ab(out, a=left, b=right, http=http_path)
        self.assertEqual(made.returncode, 0, made.stderr)
        page = self.work + "/escaped.html"
        made = judge_cli(self._ab(out, a=left, b=right) + ["--html", page])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(page, encoding="utf-8") as handle:
            html = handle.read()
        self.assertIn("&lt;b&gt;diff&lt;/b&gt;", html)
        self.assertIn("side&amp;a", html)
        self.assertNotIn("<b>diff</b>", html)
        # A raw ampersand would survive replacing the escaped form.
        self.assertNotIn("side&a", html.replace("&amp;", ""))

    def test_the_colophon_command_writes_the_same_page(self):
        verdicts = self._judged()
        page = self.work + "/page.html"
        made = judge_cli(self._ab(verdicts) + ["--html", page])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(page, encoding="utf-8") as handle:
            html = handle.read()
        from html import unescape
        start = html.find('<code class="mono"')
        start = html.find(">", start) + 1
        end = html.find("</code>", start)
        command = unescape(html[start:end])
        self.assertTrue(command.endswith("--html reports/ab.html"))
        self.assertNotIn("--md", command)
        self.assertNotIn("--json", command)
        self.assertNotIn(page, command)
        with tempfile.TemporaryDirectory() as scratch:
            copy = os.path.join(scratch, "repo")
            shutil.copytree(".", copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            done = subprocess.run(shlex.split(command), cwd=copy, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(os.path.join(copy, "reports", "ab.html"), "rb") as handle:
                got = handle.read()
            with open(page, "rb") as handle:
                self.assertEqual(got, handle.read())


def _retarget(path, mapping):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    for span in data["resourceSpans"][0]["scopeSpans"][0]["spans"]:
        for attr in span["attributes"]:
            if attr.get("key") == "case.id" and attr["value"]["stringValue"] in mapping:
                attr["value"]["stringValue"] = mapping[attr["value"]["stringValue"]]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def _set_meta(path, key, value):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    data[key] = value
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

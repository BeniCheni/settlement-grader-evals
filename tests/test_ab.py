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

    def test_prompt_file_success_through_the_script_entry_point(self):
        # A new process has no pre-imported run_eval to hide an import cycle. runpy takes
        # the actual __main__ path; both setup and chat have fake transports, no server.
        script = os.path.join(self.work_rel, "run_eval.py")
        shutil.copyfile("run_eval.py", script)
        prompt = "Grade it.\nSecond line.\n"
        path = os.path.join(self.work_rel, "script-prompt.txt")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(prompt)
        probe = '''import json,runpy,sys
from unittest.mock import patch
script,cases,prompt,seen_path=sys.argv[1:]
seen=[]
class Body:
 def __init__(self, data): self.data=data
 def __enter__(self): return self
 def __exit__(self,*args): return False
 def read(self): return json.dumps(self.data).encode()
def transport(request,timeout=None):
 if request.full_url.endswith('/api/version'): return Body({'version':'fixture'})
 if request.full_url.endswith('/api/tags'): return Body({'models':[{'name':'qwen3:8b','digest':'fixture'}]})
 raise AssertionError('unexpected request')
def chat(payload,timeout):
 seen.append(payload)
 return {'message':{'role':'assistant','content':'{"ticket_result":"WIN","net":0}'},'done_reason':'stop'}
sys.argv=[script,cases,'--run-id','script-'+('flag' if prompt else 'default')]
if prompt: sys.argv+=['--prompt-file',prompt]
with patch('urllib.request.urlopen',transport),patch('grader.agent._chat',chat):
 try: runpy.run_path(script,run_name='__main__')
 except SystemExit as error:
  if error.code: raise
with open(seen_path,'w',encoding='utf-8') as handle: json.dump(seen,handle)
'''
        payloads = []
        for flag in ("", path):
            seen = os.path.join(self.work_rel, "script-seen.json")
            result = subprocess.run([sys.executable, "-c", probe, script, self.cases, flag, seen], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(seen, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(len(payload), 1)
            text = prompt if flag else SYSTEM_PROMPT
            self.assertEqual(payload[0]["messages"][0], {"role": "system", "content": text})
            run_id = "script-flag" if flag else "script-default"
            with open(os.path.join(self.work_rel, "traces", run_id, "run_meta.json"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["system_prompt"], text)
            payload[0]["messages"][0]["content"] = None
            payloads.append(payload)
        self.assertEqual(payloads[0], payloads[1])

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
        self.assertIsNone(BANNED_WORD.search("scholarship in sample"))
        # The other phrases are not whole words: a computed "generalised" or "untrusted" is a hit.
        self.assertIsNotNone(BANNED_WORD.search("generalised"))
        self.assertIsNotNone(BANNED_WORD.search("Generalization"))
        self.assertIsNotNone(BANNED_WORD.search("untrusted"))
        self.assertIsNotNone(BANNED_WORD.search("Held-Out"))
        self.assertIsNotNone(BANNED_WORD.search("ship"))
        self.assertIsNotNone(BANNED_WORD.search("no-ship"))
        self.assertIsNotNone(BANNED_WORD.search("Ship it"))


ROOT = "tests/fixtures/ab"
ALPHA = ROOT + "/alpha"
BETA = ROOT + "/beta"
# The five phrases match inside a word, as tests/test_judge_page.py reads them, so "generalised",
# "generalisation" and "untrusted" are hits. Only ship and no-ship are whole words (the spec's
# exception for relationship and shipshape).
BANNED_WORD = re.compile(
    r"held out|held-out|trusted|generalis|generaliz|\b(?:ship|no-ship)\b",
    re.IGNORECASE,
)
# Each run's final ticket_result per fixture case, read from the traces by hand.
FINALS = {"T1": (None, "WIN"), "T2": (None, "WIN"), "T3": (None, "LOSS"), "T4": ("WIN", "WIN")}
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


def agreement_percent_own(count, total):
    tenths = (count * 1000 + total // 2) // total
    return "%d.%d%%" % (tenths // 10, tenths % 10)


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


def own_reason(reply):
    lines = reply.splitlines()
    first = next((index for index, line in enumerate(lines) if line.strip() != ""), None)
    if first is None:
        return ""
    for line in lines[first + 1:]:
        if line.startswith("Reason:"):
            return line[len("Reason:"):].strip()
    return ""


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
        for label, payload, message in (
            ("a list of integers", [1], "unreadable cases file"),
            ("expected not an object", [{"case_id": case, "expected": 5} for case in ("T1", "T2", "T3", "T4")], "expected is not an object"),
            ("an object, not a list", {}, "case T1 is not in"),
            ("a case missing", [{"case_id": case, "expected": {"ticket_result": "WIN", "net": 1.0}} for case in ("T1", "T2", "T3")], "case T4 is not in"),
        ):
            path = self.work + "/input-%s.json" % len(os.listdir(self.work))
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            with self.subTest(label=label):
                self._assert_ab_refused(self._ab(verdicts, cases=path), message)
        binary = self.work + "/cases-binary.json"
        with open(binary, "wb") as handle:
            handle.write(b"\xff")
        self._assert_ab_refused(self._ab(verdicts, cases=binary), "unreadable cases file")
        self._assert_ab_refused(self._ab(verdicts, cases=self.work + "/no-cases.json"), "unreadable cases file")

    def test_scoring_errors_do_not_blame_a_readable_cases_file(self):
        from scorer.ab import _score
        from scorer.judge import JudgeError
        tree = self.work + "/bad-trace"
        shutil.copytree(BETA, tree)
        path = tree + "/settlement-traces.json"
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]:
            if not span.get("parentSpanId"):
                for attr in span["attributes"]:
                    if attr["key"] == "input.ticket":
                        attr["value"]["stringValue"] = json.dumps({"legs": [{"fixture": 5}]})
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        with self.assertRaisesRegex(JudgeError, "could not score run"):
            _score(tree, ROOT + "/cases.json")
        # A check bug belongs to the scoring operation too, not to cases validation.
        with mock.patch("scorer.ab.score_run", side_effect=KeyError("check bug")):
            with self.assertRaisesRegex(JudgeError, "could not score run"):
                _score(ALPHA, ROOT + "/cases.json")

    def test_the_printed_z_round_trips_to_the_value_used(self):
        verdicts = self._judged()
        for z in (1.959964, 1.2345678901234567, 1e-5):
            path = self._thresholds_variant(lambda d: d["interval"].__setitem__("z", z))
            out = self.work + "/exact-z.json"
            result = judge_cli(self._ab(verdicts, thresholds=path) + ["--json", out])
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(out, encoding="utf-8") as handle:
                document = json.load(handle)
            self.assertEqual(float(document["setup"]["z"]), z)
            self.assertIn("z %s." % repr(z), result.stdout)

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

    def test_the_page_names_every_count_its_sign_and_its_source(self):
        # Before this: "Delta +1 tickets" had no sentence saying a plus is a fall from A to B,
        # a judge row printed its FAIL counts as a bare "A 3. B 2.", the interval's z and the
        # judge adapter were nowhere, the table had one th over twelve cells, and an UNPARSED
        # reply's empty reason printed as "rubric A:  B: text".
        from html import unescape
        from scorer.ab import _ticket_row
        verdicts = self._judged()
        md_path = self.work + "/named.md"
        html_path = self.work + "/named.html"
        made = judge_cli(self._ab(verdicts) + ["--md", md_path, "--html", html_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(md_path, encoding="utf-8") as handle:
            markdown = handle.read()
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        computed_text, _input_text = _split_page(html)
        note = (
            "Delta is A minus B. For a code, a plus means fewer tickets with the code in B. "
            "For a judge, the tickets counted are FAIL and UNPARSED, so a plus means more PASS in B. "
            "Each interval is the paired interval on that delta, z 1.96."
        )
        cover_note = (
            "Delta is A minus B: a plus means fewer tickets with the code in B. "
            "The interval is the paired interval on that delta, z 1.96."
        )
        self.assertIn(note, computed_text)
        self.assertIn("## Metrics\n\n" + note + "\n", markdown)
        self.assertIn("Interval 8.5 to 95.4 points.\n" + cover_note + "\n", markdown)
        self.assertIn('<p class="ab-legend">' + cover_note + "</p>", html)
        self.assertIsNone(BANNED_WORD.search(note + cover_note))
        # The FAIL counts on a judge row, counted here from the replies: not PASS, UNPARSED included.
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        for rubric in ("needs_human_correctness", "rule_adherence", "tool_call_accuracy"):
            fails = {}
            for run in (ALPHA, BETA):
                fails[run] = sum(
                    own_verdict(replies["llama3.1:8b|%s|%s|%s" % (run, case, rubric)]) != "PASS"
                    for case in ("T1", "T2", "T3", "T4")
                )
            line = "FAIL A %s. B %s. Delta" % (fails[ALPHA], fails[BETA])
            metrics_md = markdown.split("## Metrics\n", 1)[1]
            with self.subTest(rubric=rubric):
                self.assertIn("### %s\n" % rubric, metrics_md)
                self.assertIn(line, metrics_md.split("### %s\n" % rubric, 1)[1].split("###", 1)[0])
                article = re.search(r'<article class="metric" data-metric="%s".*?</article>' % rubric, html, re.S).group(0)
                self.assertIn(line, unescape(re.sub(r"<[^>]+>", "", article)))
        self.assertEqual(sum(1 for article in re.findall(r"<article .*?</article>", html, re.S) if "FAIL A " in article), 3)
        self.assertEqual(markdown.count("\nFAIL A "), 3)
        # Setup names z and the adapter that answered, in both outputs.
        self.assertIn("Interval method newcombe-1998-method-10, z 1.96.\n", markdown)
        self.assertIn("Judge model llama3.1:8b. Digest sha256:judge. Adapter http-fixture.\n", markdown)
        self.assertIn('Adapter <span class="mono">http-fixture</span>. Interval method <span class="mono">newcombe-1998-method-10</span>, z <span class="mono">1.96</span>.', html)
        # Every column has a head: the th texts equal the first row's data-labels, in order.
        heads = re.findall(r"<th>(.*?)</th>", html.split('<table class="ledger ab-rows">', 1)[1].split("</thead>", 1)[0])
        first_row = re.search(r'<tr class="row(?: disagree)?" data-case="T1">(.*?)</tr>', html, re.S).group(1)
        labels = re.findall(r'<td data-label="([^"]+)"', first_row)
        self.assertEqual([unescape(head) for head in heads], [unescape(label) for label in labels])
        self.assertEqual(len(heads), 13)
        # Another z prints as given.
        other = self._thresholds_variant(lambda d: d["interval"].__setitem__("z", 2.5758))
        made = judge_cli(self._ab(verdicts, thresholds=other) + ["--md", self.work + "/z.md"])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(self.work + "/z.md", encoding="utf-8") as handle:
            self.assertIn("z 2.5758.", handle.read())
        # An empty reason prints as none, on the page and in the document.
        row = _ticket_row({
            "case_id": "X", "changed": ["final", "r"], "final_a": None, "final_b": "WIN", "codes_a": [], "codes_b": [],
            "verdicts": [{"rubric": "r", "a": "UNPARSED", "b": "PASS", "reason_a": "", "reason_b": "ok", "differs": True}],
        })
        self.assertIn(">r A: none B: ok</span>", row)

    def test_the_set_1_numbers_have_the_hand_written_statement_beside_them(self):
        # AGENTS.md: wherever a calibration number is shown, a hand-written statement beside it
        # says whether it is in sample or held out. Agreement and kappa are shown in the Set 1
        # section, which had only a computed sentence; the statement sat three panels up.
        from html import escape
        from scorer.judge import PROVENANCE_HEADING
        verdicts = self._judged()
        md_path = self.work + "/beside.md"
        html_path = self.work + "/beside.html"
        made = judge_cli(self._ab(verdicts) + ["--md", md_path, "--html", html_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(md_path, encoding="utf-8") as handle:
            markdown = handle.read()
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        with open(ROOT + "/statement.txt", encoding="utf-8") as handle:
            statement = handle.read()
        section = html.split("<h2>Set 1</h2>", 1)[1].split("</section>", 1)[0]
        self.assertIn('data-set1="tool_call_accuracy"', section)
        self.assertIn("<h3>%s</h3>" % PROVENANCE_HEADING, section)
        self.assertIn('<p class="set1-statement" data-input="statement">%s</p>' % escape(statement, quote=True), section)
        self.assertEqual(html.count(escape(statement, quote=True)), 2)
        md_section = markdown.split("## Set 1\n", 1)[1].split("## Metrics\n", 1)[0]
        self.assertIn("Kappa", md_section)
        self.assertIn("### %s\n\n<!-- input:statement -->\n%s\n<!-- /input:statement -->" % (PROVENANCE_HEADING, statement), md_section)
        self.assertEqual(markdown.count(statement), 2)
        self.assertEqual(markdown.count(PROVENANCE_HEADING), 2)

    def _expected_figures(self, replies, z=1.96):
        """Every figure the report should print, from the FLAGS and FINALS tables, the fixture
        replies and the test's own method 10. Nothing here calls scorer.ab."""
        case_ids = ["T1", "T2", "T3", "T4"]
        n = len(case_ids)
        rubrics = ["needs_human_correctness", "rule_adherence", "tool_call_accuracy"]
        verdicts = {}
        for run in (ALPHA, BETA):
            for case in case_ids:
                for rubric in rubrics:
                    reply = replies["llama3.1:8b|%s|%s|%s" % (run, case, rubric)]
                    verdicts[(run, case, rubric)] = (own_verdict(reply), own_reason(reply))
        metrics = {}
        for rubric in rubrics:
            left = {case for case in case_ids if verdicts[(ALPHA, case, rubric)][0] != "PASS"}
            right = {case for case in case_ids if verdicts[(BETA, case, rubric)][0] != "PASS"}
            both, only_a, only_b, neither = _cells(case_ids, left, right)
            _fall, lower, upper = own_paired(both, only_a, only_b, neither, z)
            metrics[rubric] = {
                "source": "judge", "count_a": both + only_a, "count_b": both + only_b, "only_a": only_a, "only_b": only_b,
                "delta_tickets": "%+d" % (only_a - only_b), "delta_points": own_points(only_a - only_b, n),
                "lower_points": own_limit(lower), "upper_points": own_limit(upper),
                "pass_a": n - len(left), "pass_b": n - len(right),
                "unparsed_a": sum(verdicts[(ALPHA, case, rubric)][0] == "UNPARSED" for case in case_ids),
                "unparsed_b": sum(verdicts[(BETA, case, rubric)][0] == "UNPARSED" for case in case_ids),
            }
        for code in CHECKS:
            left = {case for case, sides in FLAGS.items() if code in sides["alpha"]}
            right = {case for case, sides in FLAGS.items() if code in sides["beta"]}
            both, only_a, only_b, neither = _cells(case_ids, left, right)
            _fall, lower, upper = own_paired(both, only_a, only_b, neither, z)
            metrics[code] = {
                "source": "code", "count_a": both + only_a, "count_b": both + only_b, "only_a": only_a, "only_b": only_b,
                "delta_tickets": "%+d" % (only_a - only_b), "delta_points": own_points(only_a - only_b, n),
                "lower_points": own_limit(lower), "upper_points": own_limit(upper),
            }
        return case_ids, rubrics, verdicts, metrics

    def test_every_figure_on_the_page_and_in_the_markdown_is_counted_from_the_fixture(self):
        # test_ab_matches_counts_from_the_fixture_table reads the JSON. Swapping A and B on the
        # cover, in a metric paragraph, in a ticket row or in the Markdown, inverting a set-1
        # line, printing the wrong digest, or reversing the prompt diff all survived it.
        from html import unescape
        verdicts_dir = self._judged()
        md_path = self.work + "/figures.md"
        html_path = self.work + "/figures.html"
        json_path = self.work + "/figures.json"
        made = judge_cli(self._ab(verdicts_dir) + ["--md", md_path, "--json", json_path, "--html", html_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(md_path, encoding="utf-8") as handle:
            markdown = handle.read()
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        with open(json_path, encoding="utf-8") as handle:
            document = json.load(handle)
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        case_ids, rubrics, verdicts, metrics = self._expected_figures(replies)
        text = lambda fragment: unescape(re.sub(r"<[^>]+>", "", fragment))

        # The cover: the first must_fall code in the thresholds file is NO_FINAL_ANSWER.
        primary = metrics["NO_FINAL_ANSWER"]
        cover = text(html.split('<div class="cover-tiles">', 1)[1].split("</div>", 1)[0])
        md_cover = markdown.split("## NO_FINAL_ANSWER\n", 1)[1].split("\n## ", 1)[0]
        for want in (
            "A %s. B %s." % (primary["count_a"], primary["count_b"]),
            "Delta %s tickets, %s points." % (primary["delta_tickets"], primary["delta_points"]),
            "Interval %s to %s points." % (primary["lower_points"], primary["upper_points"]),
        ):
            self.assertIn(want, cover)
            self.assertIn(want + "\n", md_cover)
        self.assertEqual(cover.count("A %s. B %s." % (primary["count_b"], primary["count_a"])), 0 if primary["count_a"] != primary["count_b"] else 1)
        self.assertIn('data-primary="NO_FINAL_ANSWER"', html)

        # Every metric, on the page and in the Markdown, in full sentences.
        md_metrics = markdown.split("## Metrics\n", 1)[1].split("\n## Thresholds", 1)[0]
        for name, want in metrics.items():
            article = text(re.search(r'<article class="metric" data-metric="%s".*?</article>' % name, html, re.S).group(0))
            md_block = md_metrics.split("### %s\n" % name, 1)[1].split("\n### ", 1)[0]
            prefix = "FAIL " if want["source"] == "judge" else ""
            sentences = [
                "%sA %s. B %s. Delta %s tickets, %s points." % (prefix, want["count_a"], want["count_b"], want["delta_tickets"], want["delta_points"]),
                "Interval %s to %s points." % (want["lower_points"], want["upper_points"]),
                "Only A %s. Only B %s." % (want["only_a"], want["only_b"]),
            ]
            if want["source"] == "judge":
                sentences += [
                    "PASS share A %s. PASS share B %s." % (agreement_percent_own(want["pass_a"], 4), agreement_percent_own(want["pass_b"], 4)),
                    "UNPARSED A %s. UNPARSED B %s." % (want["unparsed_a"], want["unparsed_b"]),
                    "FAIL to PASS %s. PASS to FAIL %s." % (want["only_a"], want["only_b"]),
                ]
            for sentence in sentences:
                with self.subTest(metric=name, sentence=sentence):
                    self.assertIn(sentence, article)
                    self.assertIn(sentence, md_block)
            if want["source"] == "judge":
                self.assertIn("Delta %s points." % want["delta_points"], article)

        # Set 1, from the fixture report's cells and figures.
        with open(ROOT + "/set1.json", encoding="utf-8") as handle:
            set1 = {item["rubric"]: item["final"] for item in json.load(handle)["rubrics"]}
        md_set1 = markdown.split("## Set 1\n", 1)[1].split("\n## Metrics", 1)[0]
        for rubric in rubrics:
            final = set1[rubric]
            agree = final["JP_HP"] + final["JF_HF"]
            total = agree + final["JP_HF"] + final["JF_HP"]
            read = [item for item in final["false_passes"] if item.get("reading") is True]
            passes = "no false passes" if not final["false_passes"] else "%s of %s" % (len(read), len(final["false_passes"]))
            line = "meets_bar: %s. Agreement %s (%.4f). Kappa %.4f. False passes read: %s." % (
                "yes" if final["meets_bar"] else "no", agreement_percent_own(agree, total), final["agreement"], final["kappa"], passes,
            )
            paragraph = text(re.search(r'<p class="ab-judge[^"]*" data-set1="%s">(.*?)</p>' % rubric, html).group(1))
            with self.subTest(rubric=rubric):
                self.assertEqual(paragraph, "%s. %s" % (rubric, line))
                self.assertIn("### %s\n\n%s\n" % (rubric, line), md_set1)
                self.assertEqual(('class="ab-judge ab-fail"' in re.search(r'<p class="ab-judge[^"]*" data-set1="%s"' % rubric, html).group(0)), not final["meets_bar"])
        self.assertIn("rule_adherence is the delta to read with most care.", md_set1)

        # Setup, from the two run_meta files and the fixture's judge, and the prompt diff's direction.
        with open(ALPHA + "/run_meta.json", encoding="utf-8") as handle:
            meta_a = json.load(handle)
        with open(BETA + "/run_meta.json", encoding="utf-8") as handle:
            meta_b = json.load(handle)
        setup = text(html.split("<h2>Setup</h2>", 1)[1].split("<details", 1)[0])
        md_setup = markdown.split("## Setup\n", 1)[1].split("\n## Prompt", 1)[0]
        self.assertIn("Ollama %s. Grader %s %s." % (meta_a["ollama_version"], meta_a["model"], meta_a["model_digest"]), setup)
        self.assertIn("Judge llama3.1:8b sha256:judge. Adapter http-fixture.", setup)
        self.assertIn("Ollama %s.\nGrader model %s. Digest %s.\n" % (meta_a["ollama_version"], meta_a["model"], meta_a["model_digest"]), md_setup)
        self.assertIn("Judge model llama3.1:8b. Digest sha256:judge. Adapter http-fixture.\n", md_setup)
        self.assertIn("A %s.\nB %s.\n" % (ALPHA, BETA), md_setup)
        diff = text(re.search(r'<pre class="prompt-diff" data-input="diff">(.*?)</pre>', html, re.S).group(1))
        removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
        added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
        self.assertEqual(len(removed), 1)
        self.assertEqual(len(added), 1)
        self.assertIn(removed[0], meta_a["system_prompt"])
        self.assertNotIn(removed[0], meta_b["system_prompt"])
        self.assertIn(added[0], meta_b["system_prompt"])
        self.assertTrue(diff.startswith("--- A\n+++ B\n"))
        self.assertIn(diff, markdown)

        # Every ticket: finals, codes, each verdict and the reasons where verdicts differ.
        rows = re.findall(r'<tr class="row(?: disagree)?" data-case="([^"]+)">(.*?)</tr>', html, re.S)
        self.assertEqual([case for case, _row in rows], case_ids)
        md_tickets = markdown.split("## Tickets\n", 1)[1]
        for case, row in rows:
            cells = {unescape(label): text(inner) for label, inner in re.findall(r'<td data-label="([^"]+)"[^>]*>(.*?)</td>', row, re.S)}
            final_a, final_b = FINALS[case]
            codes_a = [code for code in CHECKS if code in FLAGS[case]["alpha"]]
            codes_b = [code for code in CHECKS if code in FLAGS[case]["beta"]]
            md_block = md_tickets.split("### %s\n" % case, 1)[1].split("\n### ", 1)[0]
            with self.subTest(case=case):
                self.assertEqual(cells["Case"], case)
                self.assertEqual((cells["A final"], cells["B final"]), (final_a or "none", final_b or "none"))
                self.assertEqual((cells["A codes"], cells["B codes"]), (", ".join(codes_a) or "none", ", ".join(codes_b) or "none"))
                self.assertIn("A final %s. B final %s.\n" % (final_a or "none", final_b or "none"), md_block)
                self.assertIn("A codes %s.\nB codes %s.\n" % (", ".join(codes_a) or "none", ", ".join(codes_b) or "none"), md_block)
                reasons = ""
                for rubric in rubrics:
                    (verdict_a, reason_a), (verdict_b, reason_b) = verdicts[(ALPHA, case, rubric)], verdicts[(BETA, case, rubric)]
                    self.assertEqual((cells["A " + rubric], cells["B " + rubric]), (verdict_a, verdict_b))
                    self.assertIn("%s A %s. B %s.\n" % (rubric, verdict_a, verdict_b), md_block)
                    marked = "<!-- input:reason -->\nA: %s\nB: %s\n<!-- /input:reason -->" % (reason_a or "none", reason_b or "none")
                    if verdict_a != verdict_b:
                        reasons += "%s A: %s B: %s" % (rubric, reason_a or "none", reason_b or "none")
                        self.assertIn(marked, md_block)
                    else:
                        self.assertNotIn(marked, md_block)
                self.assertEqual(cells.get("Reasons", ""), reasons)
        self.assertEqual(sum(1 for case in case_ids if any(verdicts[(ALPHA, case, r)][0] != verdicts[(BETA, case, r)][0] for r in rubrics)), 3)

        # The JSON: the same figures, and no private key.
        by_name = {row["name"]: row for row in document["metrics"]}
        for name, want in metrics.items():
            for key in ("count_a", "count_b", "only_a", "only_b", "delta_tickets", "delta_points", "lower_points", "upper_points"):
                self.assertEqual(by_name[name][key], want[key], "%s %s" % (name, key))
        private = []

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.startswith("_"):
                        private.append(key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(document)
        self.assertEqual(private, [])
        for row in document["tickets"]:
            self.assertEqual((row["final_a"], row["final_b"]), FINALS[row["case_id"]])

    def test_the_interval_follows_the_thresholds_z(self):
        # With z fixed at 1.96 inside the report, a thresholds file saying 2.5758 would print 95% limits as 99% ones.
        verdicts_dir = self._judged()
        other = self._thresholds_variant(lambda d: d["interval"].__setitem__("z", 2.5758))
        json_path = self.work + "/z.json"
        made = judge_cli(self._ab(verdicts_dir, thresholds=other) + ["--json", json_path])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(json_path, encoding="utf-8") as handle:
            document = json.load(handle)
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        _case_ids, _rubrics, _verdicts, wide = self._expected_figures(replies, z=2.5758)
        _case_ids, _rubrics, _verdicts, narrow = self._expected_figures(replies, z=1.96)
        by_name = {row["name"]: row for row in document["metrics"]}
        differing = 0
        for name, want in wide.items():
            self.assertEqual((by_name[name]["lower_points"], by_name[name]["upper_points"]), (want["lower_points"], want["upper_points"]), name)
            differing += (want["lower_points"], want["upper_points"]) != (narrow[name]["lower_points"], narrow[name]["upper_points"])
        self.assertGreater(differing, 10)

    def test_changes_are_counted_and_named_from_finals_flags_and_replies(self):
        from html import unescape
        from scorer.ab import _changed, render_ab_html, render_markdown
        verdicts = self._judged()
        out = self.work + "/changed.json"
        result = judge_cli(self._ab(verdicts) + ["--json", out])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out, encoding="utf-8") as handle:
            document = json.load(handle)
        with open(ROOT + "/http.json", encoding="utf-8") as handle:
            replies = json.load(handle)["replies"]
        cases, rubrics, parsed, _metrics = self._expected_figures(replies)
        expected = {}
        for case in cases:
            names = []
            if FINALS[case][0] != FINALS[case][1]:
                names.append("final")
            if FLAGS[case]["alpha"] != FLAGS[case]["beta"]:
                names.append("codes")
            names += [r for r in rubrics if parsed[(ALPHA, case, r)][0] != parsed[(BETA, case, r)][0]]
            expected[case] = names
        page = render_ab_html(document, "")
        markdown = render_markdown(document)
        count = "%s of %s tickets changed a final, a code or a verdict." % (sum(bool(v) for v in expected.values()), len(cases))
        self.assertIn(count, page)
        self.assertIn(count, markdown)
        for ticket in document["tickets"]:
            case = ticket["case_id"]
            self.assertEqual(ticket["changed"], expected[case])
            line = "Changed: " + ", ".join(expected[case])
            row = re.search(r'<tr class="row([^"]*)" data-case="%s">(.*?)</tr>' % case, page, re.S)
            self.assertEqual("disagree" in row.group(1).split(), bool(expected[case]))
            self.assertIn(line, unescape(re.sub(r"<[^>]+>", "", row.group(2))))
            self.assertIn("### %s\n\n%s\n" % (case, line), markdown)
        # Reasons are not a changed verdict; code order and duplicates are not new codes.
        probe = {"final_a": "WIN", "final_b": "WIN", "codes_a": ["X", "Y", "X"], "codes_b": ["Y", "X"],
                 "verdicts": [{"rubric": "r", "a": "UNPARSED", "b": "UNPARSED", "reason_a": "one", "reason_b": "two"}]}
        self.assertEqual(_changed(probe), [])
        # Both ends of the display's range, with no colour or words attached to an unchanged row.
        for k in (0, len(cases)):
            for ticket in document["tickets"]:
                ticket["changed"] = ["final"] if k else []
            page = render_ab_html(document, "")
            markdown = render_markdown(document)
            self.assertIn("%s of %s tickets changed a final, a code or a verdict." % (k, len(cases)), page)
            self.assertIn("%s of %s tickets changed a final, a code or a verdict." % (k, len(cases)), markdown)
            self.assertEqual(page.count('class="row disagree"'), k)
            self.assertEqual(page.count("Changed: "), k)
            self.assertEqual(markdown.count("Changed: "), k)

    def test_the_changed_bar_covers_the_row_at_every_width(self):
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        self.assertIn(".ledger.ab-rows tr.disagree{box-shadow:inset 3px 0 0 var(--blood)}", css)
        self.assertIn(".ledger.ab-rows tr.disagree td:first-child{box-shadow:none}", css)
        self.assertIn('.ledger.ab-rows td[data-label="Changed"]::before{content:none}', css)
        wide = brace_block(css, "@media (min-width: 761px){\n  .ledger.ab-rows")
        self.assertIn('td[data-label="Changed"]', wide)

    def test_a_verdict_whose_rubric_hash_is_not_judge_metas_is_refused(self):
        verdicts_dir = self._judged()
        with open(os.path.join(verdicts_dir, "verdicts.jsonl"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        changed = json.loads(lines[0])
        changed["rubric_sha256"] = "0" * 64
        other = self.work + "/other-hash"
        os.makedirs(other)
        with open(os.path.join(other, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("\n".join([json.dumps(changed)] + lines[1:]) + "\n")
        shutil.copy(os.path.join(verdicts_dir, "judge_meta.json"), os.path.join(other, "judge_meta.json"))
        self._assert_ab_refused(self._ab(other), "does not match judge_meta.json")

    def test_load_run_drops_the_prompt_the_traces_carry(self):
        # The case text cannot leak the prompt only because load_run drops the LLM spans that
        # carry it. The fixture traces hold no prompt, so this is checked on a tracked real run.
        from scorer.judge import render_case
        from scorer.traces import load_run
        step_three = SYSTEM_PROMPT.split("\n")[5]
        self.assertTrue(step_three.startswith("3. Grade each leg"))
        with open("traces/v1/settlement-traces.json", encoding="utf-8") as handle:
            raw = handle.read()
        self.assertGreaterEqual(raw.count(json.dumps(step_three)[1:-1]), 32)
        records = load_run("traces/v1")
        self.assertEqual(len(records), 32)
        for record in records:
            self.assertNotIn(step_three, json.dumps(record, ensure_ascii=False))
            self.assertNotIn(step_three, render_case(record))

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

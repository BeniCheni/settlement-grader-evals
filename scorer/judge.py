"""Rubrics, label sheets, a local judge, and its agreement with the owner.

The commands read rubric files and grader runs. They do not download a model.
A fake adapter drives the tests, and no test opens a network connection.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from fractions import Fraction

from scorer.calibrate import bar_words, has_reading, not_bar_words, write_text
from scorer.report import FONT_LINKS, _css_text, esc
from scorer.stats import agreement, canonical_json, cohen_kappa, confusion, meets_bar
from scorer.traces import load_run


OLLAMA_ORIGIN = "http://127.0.0.1:11434"
CASE_CHAR_LIMIT = 24000
RUBRIC_CHAR_LIMIT = 6000
OPTIONS = {"temperature": 0, "seed": 0, "num_ctx": 16384, "num_predict": 256}
UNSURE_LINE = (
    "The unsure cell holds rubric names separated by semicolons, each trimmed; "
    "an empty cell means none. import-labels writes those names in sorted order "
    "and refuses a duplicate or a name that is not a rubric."
)
PROVENANCE_HEADING = "Written by hand, not computed"
LABEL_KEYS = ("run", "case_id", "trace_id", "human", "unsure", "note")
VERDICT_KEYS = ("run", "case_id", "trace_id", "rubric", "rubric_sha256", "verdict", "reason", "reply")


class JudgeError(Exception):
    """One validation failure. main exits with status 2 and writes nothing."""


def relative_path(text, what):
    """Relative forward-slash path, with ./ and a trailing slash collapsed.

    An absolute path is a usage error: it would put a machine path in a file.
    A tilde path, and one that climbs out of this directory, are the same kind of error.
    """
    if not isinstance(text, str):
        raise JudgeError("%s must be a relative path" % what)
    raw = text.strip()
    if "\x00" in raw:
        raise JudgeError("%s contains a null character" % what)
    if raw == "" or raw.startswith("~") or raw.startswith("/") or raw.startswith("\\"):
        raise JudgeError("%s must be a relative path, not an absolute path" % what)
    if len(raw) >= 2 and raw[1] == ":":
        raise JudgeError("%s must be a relative path, not an absolute path" % what)
    slash = raw.replace("\\", "/")
    normalised = os.path.normpath(slash).replace("\\", "/")
    if normalised in ("", ".") or os.path.isabs(normalised) or normalised.startswith("/") or normalised.startswith("~"):
        raise JudgeError("%s must be a relative path, not an absolute path" % what)
    if normalised == ".." or normalised.startswith("../"):
        raise JudgeError("%s must be a relative path inside this directory" % what)
    root = os.path.realpath(os.getcwd())
    if os.path.commonpath((root, os.path.realpath(normalised))) != root:
        raise JudgeError("%s must be a relative path inside this directory" % what)
    return normalised


def run_name(text):
    """A run as plans, labels and verdicts name it: see relative_path."""
    return relative_path(text, "a run")


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        raise JudgeError("%s is missing or unreadable" % path) from None
    return _sha256(raw)


def read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        raise JudgeError("%s is missing or unreadable" % path) from None


def read_text(path):
    raw = read_bytes(path)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise JudgeError("%s is not valid UTF-8" % path) from None


def load_json(path):
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError:
        raise JudgeError("%s is not valid JSON" % path) from None
    return value


def load_jsonl(path):
    text = read_text(path)
    if text == "":
        return []
    rows = []
    for index, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            raise JudgeError("%s line %s is empty" % (path, index))
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise JudgeError("%s line %s is not valid JSON" % (path, index)) from None
        if not isinstance(row, dict):
            raise JudgeError("%s line %s is not a JSON object" % (path, index))
        rows.append(row)
    return rows


def jsonl_text(rows):
    lines = []
    for row in rows:
        lines.append(json.dumps(row, sort_keys=True, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def _need_str(value, label):
    if not isinstance(value, str) or value.strip() == "":
        raise JudgeError("%s is missing" % label)
    return value


def _json_block(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _json_line(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def render_case(record):
    """The text the judge and the owner both read. Longer than the limit is an error."""
    ticket = record.get("ticket")
    if not isinstance(ticket, dict):
        ticket = {}
    lines = ["TICKET", _json_block(ticket), "", "TOOL CALLS"]
    tools = record.get("tools") or []
    if not tools:
        lines.append("none")
    else:
        for index, tool in enumerate(tools, start=1):
            error = tool.get("error")
            name = tool.get("name")
            lines.append("%s. %s" % (index, "none" if name is None else name))
            lines.append("   args: %s" % _json_line(tool.get("args")))
            lines.append("   result: %s" % _json_line(tool.get("result")))
            lines.append("   error: %s" % ("none" if error is None else error))
    final = record.get("final")
    status = record.get("status")
    reason = record.get("reason")
    lines.extend([
        "",
        "FINAL ANSWER",
        "none" if final is None else _json_block(final),
        "",
        "RUN STATUS",
        "%s, reason %s" % (
            "none" if status is None else status,
            "none" if reason is None or reason == "" else reason,
        ),
    ])
    text = "\n".join(lines) + "\n"
    if len(text) > CASE_CHAR_LIMIT:
        case_id = record.get("case_id") or "?"
        raise JudgeError("case file for %s is longer than 24000 characters" % case_id)
    return text


def case_sections(case_text):
    """Ticket section, then the tool-call, final-answer and run-status sections."""
    marker = "\n\nTOOL CALLS\n"
    if not case_text.startswith("TICKET\n") or marker not in case_text:
        raise JudgeError("case file is missing a section")
    ticket, rest = case_text.split(marker, 1)
    return ticket, "TOOL CALLS\n" + rest


def parse_reply(text):
    """(verdict, reason). The verdict is PASS, FAIL, or UNPARSED."""
    if not isinstance(text, str):
        return ("UNPARSED", "")
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    verdict = "UNPARSED"
    first_index = None
    lines = stripped.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "":
            continue
        if line.strip() in ("PASS", "FAIL"):
            verdict = line.strip()
        first_index = index
        break
    reason = ""
    if first_index is not None:
        for line in lines[first_index + 1:]:
            if line.startswith("Reason:"):
                reason = line[len("Reason:"):].strip()
                break
    return (verdict, reason)


FIXED_COLUMNS = ("n", "run", "case_id", "trace_id", "unsure", "note")


def write_outputs(pairs):
    """Write every file, or leave each path as it was: a file that existed keeps its bytes."""
    pairs = list(pairs)
    paths = [os.path.normcase(os.path.realpath(path)) for path, _text in pairs]
    if len(paths) != len(set(paths)):
        raise JudgeError("output paths must be distinct")
    before = []
    try:
        for path, text in pairs:
            before.append((path, _bytes_if_file(path)))
            write_text(path, text)
    except OSError:
        for path, raw in before:
            try:
                if raw is None:
                    os.remove(path)
                else:
                    with open(path, "wb") as handle:
                        handle.write(raw)
            except OSError:
                pass
        raise JudgeError("could not write output") from None


def _bytes_if_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def load_rubrics(directory):
    if not os.path.isdir(directory):
        raise JudgeError("rubrics directory is missing or unreadable")
    names = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".md") and os.path.isfile(os.path.join(directory, name)):
            names.append(name[:-len(".md")])
    if not names:
        raise JudgeError("rubrics directory has no rubric file")
    found = []
    for name in names:
        path = os.path.join(directory, name + ".md")
        raw = read_bytes(path)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise JudgeError("rubric %s is not valid UTF-8" % name) from None
        if "\r" in text:
            raise JudgeError("rubric %s must use LF line ends" % name)
        if text == "":
            raise JudgeError("rubric %s is empty" % name)
        if len(text) > RUBRIC_CHAR_LIMIT:
            raise JudgeError("rubric %s is longer than 6000 characters" % name)
        if "PASS" not in text or "FAIL" not in text or "Reason:" not in text:
            raise JudgeError("rubric %s must contain PASS, FAIL and Reason:" % name)
        if name in FIXED_COLUMNS:
            raise JudgeError("rubric %s collides with a sheet column" % name)
        found.append({"name": name, "text": text, "sha256": _sha256(raw), "path": path})
    return found


def _records(cache, run):
    name = run_name(run)
    if name not in cache:
        try:
            cache[name] = load_run(name)
        except FileNotFoundError:
            raise JudgeError("run %s is missing or unreadable" % name) from None
        except OSError:
            raise JudgeError("run %s is missing or unreadable" % name) from None
        except json.JSONDecodeError:
            raise JudgeError("run %s is not valid JSON" % name) from None
        except UnicodeDecodeError:
            raise JudgeError("run %s is not valid UTF-8" % name) from None
        except ValueError as error:
            raise JudgeError(str(error)) from None
        except (AttributeError, TypeError, OverflowError):
            raise JudgeError("run %s is not a trace export" % name) from None
    return name, cache[name]


def _unique_cases(run, records):
    seen = set()
    for record in records:
        case_id = _need_str(record.get("case_id"), "case_id")
        if case_id in seen:
            raise JudgeError("run %s holds two records with case_id %s" % (run, case_id))
        seen.add(case_id)


def record_for(cache, row):
    """The record for a labelled row. A different trace_id means the run changed."""
    _name, records = _records(cache, row["run"])
    found = [record for record in records if record.get("case_id") == row["case_id"]]
    if len(found) != 1:
        raise JudgeError("run %s case %s has %s records" % (row["run"], row["case_id"], len(found)))
    record = found[0]
    if record.get("trace_id") != row["trace_id"]:
        raise JudgeError(
            "run %s case %s trace_id does not match the row; the run changed after labelling"
            % (row["run"], row["case_id"])
        )
    return record


def _plan_rows(path):
    data = load_json(path)
    if not isinstance(data, list):
        raise JudgeError("%s is not a plan" % path)
    rows = []
    seen = set()
    for index, raw in enumerate(data, start=1):
        if not isinstance(raw, dict):
            raise JudgeError("%s row %s is not an object" % (path, index))
        if set(raw.keys()) != {"run", "case_id", "trace_id"}:
            raise JudgeError("%s row %s has the wrong keys" % (path, index))
        row = {
            "run": run_name(raw.get("run")),
            "case_id": _need_str(raw.get("case_id"), "case_id"),
            "trace_id": _need_str(raw.get("trace_id"), "trace_id"),
        }
        key = (row["run"], row["case_id"])
        if key in seen:
            raise JudgeError("plan has a duplicate case %s %s" % key)
        seen.add(key)
        rows.append(row)
    return rows


def _row_from_record(run, record):
    return {
        "run": run,
        "case_id": _need_str(record.get("case_id"), "case_id"),
        "trace_id": _need_str(record.get("trace_id"), "trace_id"),
    }


def select_rows(base, fresh_runs, n_fresh):
    """Base rows, then up to n_fresh differing rows from the fresh runs in named order."""
    if not isinstance(n_fresh, int) or isinstance(n_fresh, bool) or n_fresh < 0:
        raise JudgeError("n-fresh must be zero or more")
    cache = {}
    base_name, base_records = _records(cache, base)
    _unique_cases(base_name, base_records)
    base_final = {}
    for record in base_records:
        base_final[record.get("case_id")] = canonical_json(record.get("final"))
    fresh_names = []
    for run in fresh_runs:
        name = run_name(run)
        if name in fresh_names or name == base_name:
            raise JudgeError("fresh run %s is repeated" % name)
        fresh_names.append(name)
    skipped = 0
    taken_cases = set()
    chosen = []
    for name in fresh_names:
        _fresh_name, records = _records(cache, name)
        _unique_cases(name, records)
        picked = []
        for record in records:
            case_id = record.get("case_id")
            if case_id not in base_final:
                skipped += 1
                continue
            if case_id in taken_cases:
                continue
            if canonical_json(record.get("final")) == base_final[case_id]:
                continue
            taken_cases.add(case_id)
            picked.append(_row_from_record(name, record))
        chosen.append(picked)
    qualified = sum(len(group) for group in chosen)
    if qualified < n_fresh:
        raise JudgeError("only %s fresh records qualify, fewer than %s" % (qualified, n_fresh))
    rows = [_row_from_record(base_name, record) for record in base_records]
    remaining = n_fresh
    for group in chosen:
        take = group[:remaining]
        rows.extend(take)
        remaining -= len(take)
        if remaining == 0:
            break
    return rows, skipped


def cmd_select(args):
    fresh = args.fresh or []
    rows, skipped = select_rows(args.base, fresh, args.n_fresh)
    write_outputs([(args.out, canonical_json(rows))])
    sys.stdout.write("rows %s\nfresh %s\nskipped %s\n" % (len(rows), args.n_fresh, skipped))


def _guard_rubrics(rubrics, rows):
    for rubric in rubrics:
        for row in rows:
            if row["case_id"] and row["case_id"] in rubric["text"]:
                raise JudgeError("rubric %s contains case_id %s from the plan" % (rubric["name"], row["case_id"]))


def sheet_text(rows, rubrics, cache):
    blocks = [UNSURE_LINE, ""]
    table = []
    fields = ["n", "run", "case_id", "trace_id"] + [rubric["name"] for rubric in rubrics] + ["unsure", "note"]
    for index, row in enumerate(rows, start=1):
        record = record_for(cache, row)
        case_text = render_case(record)
        blocks.append("# %s. %s %s" % (index, row["run"], row["case_id"]))
        blocks.append("")
        blocks.append(case_text.rstrip("\n"))
        blocks.append("")
        csv_row = {"n": str(index), "run": row["run"], "case_id": row["case_id"], "trace_id": row["trace_id"]}
        for field in fields:
            csv_row.setdefault(field, "")
        table.append(csv_row)
    case_files = "\n".join(blocks)
    if not case_files.endswith("\n"):
        case_files += "\n"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for csv_row in table:
        writer.writerow(csv_row)
    return case_files, buffer.getvalue(), fields


def cmd_sheet(args):
    rows = _plan_rows(args.plan)
    rubrics = load_rubrics(args.rubrics)
    _guard_rubrics(rubrics, rows)
    case_files, table, _fields = sheet_text(rows, rubrics, {})
    write_outputs([
        (os.path.join(args.out, "case-files.md"), case_files),
        (os.path.join(args.out, "labels.csv"), table),
    ])


def _parse_unsure(cell, names):
    if cell is None:
        cell = ""
    if not isinstance(cell, str):
        raise JudgeError("unsure is not text")
    parts = []
    seen = set()
    for part in cell.split(";"):
        name = part.strip()
        if name == "":
            continue
        if name not in names:
            raise JudgeError("unsure entry %s is not a rubric" % name)
        if name in seen:
            raise JudgeError("duplicate unsure entry %s" % name)
        seen.add(name)
        parts.append(name)
    return sorted(parts)


def _read_sheet_csv(path):
    """UTF-8 with an optional byte-order mark. csv accepts LF and CRLF."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise JudgeError("sheet has no header")
            if any(name is None or name.strip() == "" for name in reader.fieldnames):
                raise JudgeError("sheet header has an empty column")
            header = list(reader.fieldnames)
            if len(header) != len(set(header)):
                raise JudgeError("sheet header has a duplicate column")
            rows = []
            for raw_row in reader:
                if None in raw_row:
                    raise JudgeError("sheet has a row with an extra cell")
                rows.append({key: raw_row[key] for key in header})
            return header, rows
    except JudgeError:
        raise
    except UnicodeDecodeError:
        raise JudgeError("%s is not valid UTF-8" % path) from None
    except csv.Error:
        raise JudgeError("%s is not a readable sheet" % path) from None
    except OSError:
        raise JudgeError("%s is missing or unreadable" % path) from None


def import_rows(plan_rows, header, sheet_rows, rubric_names):
    expected = ["n", "run", "case_id", "trace_id"] + rubric_names + ["unsure", "note"]
    if header != expected and set(header) != set(expected):
        missing = [name for name in expected if name not in header]
        extra = [name for name in header if name not in expected]
        if missing:
            raise JudgeError("sheet is missing %s" % ", ".join(missing))
        raise JudgeError("sheet has an unexpected column")
    if len(sheet_rows) != len(plan_rows):
        raise JudgeError("sheet row count does not match the plan")
    by_n = {}
    numbers = {str(index): index for index in range(1, len(plan_rows) + 1)}
    for raw in sheet_rows:
        n_text = raw.get("n", "")
        if not isinstance(n_text, str) or n_text not in numbers:
            raise JudgeError("sheet n is not the plan row number")
        number = numbers[n_text]
        if number in by_n:
            raise JudgeError("duplicate sheet row %s" % number)
        by_n[number] = raw
    imported = []
    fail_counts = {name: 0 for name in rubric_names}
    for index, plan in enumerate(plan_rows, start=1):
        if index not in by_n:
            raise JudgeError("sheet is missing plan row %s" % index)
        raw = by_n[index]
        run = run_name(raw.get("run"))
        case_id = raw.get("case_id")
        trace_id = raw.get("trace_id")
        if run != plan["run"] or case_id != plan["case_id"] or trace_id != plan["trace_id"]:
            raise JudgeError("sheet row %s does not match the plan" % index)
        human = {}
        for name in rubric_names:
            cell = raw.get(name)
            if cell not in ("PASS", "FAIL"):
                raise JudgeError("row %s rubric %s is not exactly PASS or FAIL" % (index, name))
            human[name] = cell
            if cell == "FAIL":
                fail_counts[name] += 1
        note = raw.get("note")
        if note is None:
            note = ""
        imported.append({
            "run": run,
            "case_id": case_id,
            "trace_id": trace_id,
            "human": human,
            "unsure": _parse_unsure(raw.get("unsure") or "", rubric_names),
            "note": note,
        })
    return imported, fail_counts


def cmd_import(args):
    beside = _labels_meta_path(args.labels)
    if os.path.normpath(args.meta) != os.path.normpath(beside):
        raise JudgeError("--meta must be %s, beside the labels, where report reads it" % beside)
    plan_rows = _plan_rows(args.plan)
    rubrics = load_rubrics(args.rubrics)
    names = [rubric["name"] for rubric in rubrics]
    header, sheet_rows = _read_sheet_csv(args.sheet)
    imported, fail_counts = import_rows(plan_rows, header, sheet_rows, names)
    meta = {
        "plan_sha256": file_sha256(args.plan),
        "rubrics": {rubric["name"]: rubric["sha256"] for rubric in rubrics},
    }
    write_outputs([
        (args.labels, jsonl_text(imported)),
        (args.meta, canonical_json(meta)),
    ])
    sys.stdout.write("rows %s\n" % len(imported))
    for name in names:
        sys.stdout.write("%s FAIL %s\n" % (name, fail_counts[name]))


def _human(value, names):
    if not isinstance(value, dict) or set(value.keys()) != set(names):
        raise JudgeError("human labels do not match the rubrics")
    for name in names:
        if value[name] not in ("PASS", "FAIL"):
            raise JudgeError("a human label is not exactly PASS or FAIL")
    return value


def _label_row(raw, names, allow_changes):
    allowed = set(LABEL_KEYS)
    if allow_changes:
        allowed.add("changes")
    if set(raw.keys()) != allowed:
        raise JudgeError("a label row has the wrong keys")
    human = raw.get("human")
    if not isinstance(human, dict):
        raise JudgeError("human labels are missing")
    row = {
        "run": run_name(raw.get("run")),
        "case_id": _need_str(raw.get("case_id"), "case_id"),
        "trace_id": _need_str(raw.get("trace_id"), "trace_id"),
        "human": human,
        "note": raw.get("note"),
    }
    if not isinstance(row["note"], str):
        raise JudgeError("note is not text")
    unsure = raw.get("unsure")
    if not isinstance(unsure, list):
        raise JudgeError("unsure is not a list")
    row["unsure"] = unsure
    if allow_changes:
        row["changes"] = raw.get("changes")
    return row


def load_labels(path, allow_changes=False):
    raw_rows = load_jsonl(path)
    if not raw_rows:
        raise JudgeError("labels are empty")
    names = None
    rows = []
    seen = set()
    for raw in raw_rows:
        if "human" not in raw or not isinstance(raw["human"], dict):
            raise JudgeError("human labels are missing")
        row_names = sorted(raw["human"].keys())
        if not row_names:
            raise JudgeError("human labels have no rubric")
        if names is None:
            names = row_names
        elif row_names != names:
            raise JudgeError("label rows do not share rubrics")
        row = _label_row(raw, names, allow_changes)
        _human(row["human"], names)
        if any(not isinstance(name, str) for name in row["unsure"]):
            raise JudgeError("unsure entry is not a rubric")
        if row["unsure"] != sorted(row["unsure"]):
            raise JudgeError("unsure names are not in sorted order")
        seen_names = set()
        for name in row["unsure"]:
            if not isinstance(name, str) or name not in names:
                raise JudgeError("unsure entry is not a rubric")
            if name in seen_names:
                raise JudgeError("duplicate unsure entry %s" % name)
            seen_names.add(name)
        key = (row["run"], row["case_id"])
        if key in seen:
            raise JudgeError("duplicate label row %s %s" % key)
        seen.add(key)
        rows.append(row)
    return names, rows


def _check_changes(first, final):
    if set(final.keys()) != set(LABEL_KEYS + ("changes",)):
        raise JudgeError("a final row has the wrong keys")
    for key in ("run", "case_id", "trace_id", "unsure", "note"):
        if final[key] != first[key]:
            raise JudgeError("final row %s %s differs in %s" % (first["run"], first["case_id"], key))
    if set(final["human"].keys()) != set(first["human"].keys()):
        raise JudgeError("final rubrics differ")
    changes = final["changes"]
    if not isinstance(changes, list):
        raise JudgeError("changes is not a list")
    seen = set()
    by_rubric = {}
    for change in changes:
        if not isinstance(change, dict) or set(change.keys()) != {"rubric", "from", "to", "reason"}:
            raise JudgeError("a change has the wrong keys")
        rubric = change["rubric"]
        if not isinstance(rubric, str) or rubric not in first["human"]:
            raise JudgeError("a change names a rubric that is not a label")
        if rubric in seen:
            raise JudgeError("duplicate change for %s" % rubric)
        seen.add(rubric)
        if not isinstance(change["reason"], str) or change["reason"].strip() == "":
            raise JudgeError("a change reason is empty")
        if change["from"] not in ("PASS", "FAIL") or change["to"] not in ("PASS", "FAIL"):
            raise JudgeError("a change label is not exactly PASS or FAIL")
        if change["from"] == change["to"]:
            raise JudgeError("a change does not change the label")
        if change["from"] != first["human"][rubric]:
            raise JudgeError("change from does not match the first-pass label")
        if change["to"] != final["human"][rubric]:
            raise JudgeError("change to does not match the final label")
        by_rubric[rubric] = change
    for rubric, label in first["human"].items():
        final_label = final["human"][rubric]
        if label != final_label and rubric not in by_rubric:
            raise JudgeError("a label changed with no change record")
        if label == final_label and rubric in by_rubric:
            raise JudgeError("a change record leaves the label the same")
    return len(changes)


def cmd_check_final(args):
    _names, first_rows = load_labels(args.labels, allow_changes=False)
    _final_names, final_rows = load_labels(args.final, allow_changes=True)
    if len(first_rows) != len(final_rows):
        raise JudgeError("final row count does not match the labels")
    total = 0
    for first, final in zip(first_rows, final_rows):
        total += _check_changes(first, final)
    sys.stdout.write("changes %s\n" % total)


class _Body(object):
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class OllamaClient(object):
    """urllib calls to a local Ollama. A connection failure is a JudgeError, not a verdict."""

    def __init__(self, opener=None):
        self.opener = opener or urllib.request.urlopen

    def _request(self, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(OLLAMA_ORIGIN + path, data=data, headers=headers)
        try:
            with self.opener(request, timeout=180) as response:
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise JudgeError("Ollama connection failed") from None
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            raise JudgeError("Ollama reply is not valid JSON") from None
        if not isinstance(body, dict):
            raise JudgeError("Ollama reply is not valid JSON")
        return body

    def version(self):
        body = self._request("/api/version")
        version = body.get("version")
        if not isinstance(version, str) or version == "":
            raise JudgeError("Ollama /api/version lacks the server version")
        return version

    def digest(self, model):
        body = self._request("/api/tags")
        models = body.get("models")
        if not isinstance(models, list):
            raise JudgeError("Ollama /api/tags lacks the model")
        for item in models:
            if isinstance(item, dict) and item.get("name") == model:
                digest = item.get("digest")
                if isinstance(digest, str) and digest != "":
                    return digest
                raise JudgeError("Ollama /api/tags lacks the model")
        raise JudgeError("Ollama /api/tags lacks the model")

    def family(self, model):
        body = self._request("/api/show", {"model": model})
        details = body.get("details")
        if not isinstance(details, dict) or not isinstance(details.get("family"), str) or details.get("family") == "":
            raise JudgeError("Ollama /api/show lacks details.family")
        return details["family"]

    def chat(self, model, system, user, _key=None):
        body = self._request("/api/chat", {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "options": dict(OPTIONS),
        })
        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise JudgeError("Ollama /api/chat lacks the reply")
        return message["content"]


class FixtureClient(object):
    """Stand-in for /api/version, /api/tags, /api/show and /api/chat. It does not open a socket."""

    def __init__(self, data):
        if not isinstance(data, dict):
            raise JudgeError("http fixture is not a JSON object")
        self.data = data
        self.chats = 0

    def _fail(self, kind):
        marker = self.data.get("fail")
        if marker == "connect" or marker == kind:
            raise JudgeError("Ollama connection failed")

    def version(self):
        self._fail("version")
        version = self.data.get("version")
        if not isinstance(version, str) or version == "":
            raise JudgeError("Ollama /api/version lacks the server version")
        return version

    def digest(self, model):
        self._fail("tags")
        tags = self.data.get("tags")
        if not isinstance(tags, dict) or not isinstance(tags.get(model), str) or tags.get(model) == "":
            raise JudgeError("Ollama /api/tags lacks the model")
        return tags[model]

    def family(self, model):
        self._fail("show")
        show = self.data.get("show")
        if not isinstance(show, dict) or model not in show:
            raise JudgeError("Ollama /api/show lacks the model")
        family = show[model]
        if not isinstance(family, str) or family == "":
            raise JudgeError("Ollama /api/show lacks details.family")
        return family

    def chat(self, model, _system, _user, key):
        self._fail("chat")
        self.chats += 1
        fail_at = self.data.get("fail_chat_at")
        if isinstance(fail_at, int) and not isinstance(fail_at, bool) and self.chats >= fail_at:
            raise JudgeError("Ollama connection failed")
        replies = self.data.get("replies")
        if not isinstance(replies, dict):
            raise JudgeError("http fixture lacks replies")
        full = "%s|%s" % (model, key)
        if full not in replies or not isinstance(replies[full], str):
            raise JudgeError("http fixture lacks a reply for %s" % full)
        return replies[full]


class OllamaAdapter(object):
    def __init__(self, model, client):
        self.model = model
        self.client = client
        self.server_version = client.version()
        self.digest = client.digest(model)
        self.options = dict(OPTIONS)
        self.key = None

    def __call__(self, system, user):
        return self.client.chat(self.model, system, user, self.key)


class FakeAdapter(object):
    def __init__(self, mapping):
        self.mapping = mapping
        self.model = None
        self.digest = None
        self.server_version = None
        self.options = None
        self.key = None

    def __call__(self, _system, _user):
        if self.key not in self.mapping:
            raise JudgeError("fake adapter has no reply for %s" % self.key)
        reply = self.mapping[self.key]
        if not isinstance(reply, str):
            raise JudgeError("fake adapter reply is not text")
        return reply


def run_judge(rubric_text, case_text, adapter):
    reply = adapter(rubric_text, case_text)
    if not isinstance(reply, str):
        raise JudgeError("the judge reply is not text")
    return reply


def _client_from_fixture(path):
    if path:
        return FixtureClient(load_json(path))
    return OllamaClient()


def build_adapter(spec, http_fixture):
    if spec.startswith("fake:"):
        path = spec[len("fake:"):]
        if path == "":
            raise JudgeError("fake adapter needs a file")
        data = load_json(path)
        if not isinstance(data, dict):
            raise JudgeError("fake adapter file is not a JSON object")
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise JudgeError("fake adapter file must map strings to text")
        return FakeAdapter(data)
    if spec.startswith("ollama:"):
        model = spec[len("ollama:"):]
        if model == "":
            raise JudgeError("ollama adapter needs a model")
        return OllamaAdapter(model, _client_from_fixture(http_fixture))
    raise JudgeError("adapter must be fake:<file> or ollama:<model>")


def judge_rows(label_rows, rubrics, adapter, cache):
    """Every reply is collected before the caller writes a file."""
    by_name = {rubric["name"]: rubric for rubric in rubrics}
    verdicts = []
    for row in label_rows:
        if set(row["human"].keys()) != set(by_name):
            raise JudgeError("labels and rubrics do not match")
        record = record_for(cache, row)
        case_text = render_case(record)
        for rubric in rubrics:
            key = "%s|%s|%s" % (row["run"], row["case_id"], rubric["name"])
            adapter.key = key
            reply = run_judge(rubric["text"], case_text, adapter)
            verdict, reason = parse_reply(reply)
            verdicts.append({
                "run": row["run"],
                "case_id": row["case_id"],
                "trace_id": row["trace_id"],
                "rubric": rubric["name"],
                "rubric_sha256": rubric["sha256"],
                "verdict": verdict,
                "reason": reason,
                "reply": reply,
            })
    verdicts.sort(key=lambda item: (item["run"], item["case_id"], item["rubric"]))
    return verdicts


def _source(client):
    """What answered: a real Ollama, or canned replies from --http-fixture, which must never read as one."""
    return "http-fixture" if isinstance(client, FixtureClient) else "ollama"


def _meta_for_adapter(adapter, labels_path, rubrics):
    return {
        "adapter": "fake" if isinstance(adapter, FakeAdapter) else _source(adapter.client),
        "digest": adapter.digest,
        "labels_sha256": file_sha256(labels_path),
        "model": adapter.model,
        "options": adapter.options,
        "rubrics": {rubric["name"]: rubric["sha256"] for rubric in rubrics},
        "server_version": adapter.server_version,
    }


def cmd_run(args):
    names, rows = load_labels(args.labels)
    rubrics = load_rubrics(args.rubrics)
    if [rubric["name"] for rubric in rubrics] != names:
        raise JudgeError("labels and rubrics do not match")
    adapter = build_adapter(args.adapter, args.http_fixture)
    verdicts = judge_rows(rows, rubrics, adapter, {})
    meta = _meta_for_adapter(adapter, args.labels, rubrics)
    write_outputs([
        (os.path.join(args.out, "verdicts.jsonl"), jsonl_text(verdicts)),
        (os.path.join(args.out, "judge_meta.json"), canonical_json(meta)),
    ])
    sys.stdout.write("verdicts %s\n" % len(verdicts))


def _grader_model(run):
    path = os.path.join(run, "run_meta.json")
    meta = load_json(path)
    if not isinstance(meta, dict) or not isinstance(meta.get("model"), str) or meta.get("model").strip() == "":
        raise JudgeError("grader run %s run_meta.json lacks the model" % run)
    return meta["model"]


def _candidates(text):
    if not isinstance(text, str) or text.strip() == "":
        raise JudgeError("candidates are required")
    names = [part.strip() for part in text.split(",")]
    if any(name == "" for name in names):
        raise JudgeError("a candidate name is empty")
    if len(names) != len(set(names)):
        raise JudgeError("a candidate is duplicated")
    return names


def pick_model(candidates, grader_run, plan_path, rubrics_dir, smoke_run, client):
    """Stop at the first candidate whose every reply parses. Family is never assumed."""
    model_name = _grader_model(run_name(grader_run))
    plan = _plan_rows(plan_path)
    smoke, records = _records({}, smoke_run)
    _unique_cases(smoke, records)
    if len(records) != 3:
        raise JudgeError("smoke run %s has %s records, not 3" % (smoke, len(records)))
    plan_cases = {row["case_id"] for row in plan}
    for record in records:
        if record.get("case_id") in plan_cases:
            raise JudgeError("smoke case %s is in the plan" % record.get("case_id"))
    rubrics = load_rubrics(rubrics_dir)
    grader_family = client.family(model_name)
    chosen = None
    recorded = []
    for candidate in candidates:
        if chosen is not None:
            recorded.append({
                "digest": None,
                "family": None,
                "model": candidate,
                "parsed": 0,
                "ran": False,
                "replies": 0,
            })
            continue
        family = client.family(candidate)
        if family == grader_family:
            raise JudgeError("candidate %s family equals the grader family" % candidate)
        digest = client.digest(candidate)
        parsed = 0
        replies = 0
        for record in records:
            case_text = render_case(record)
            for rubric in rubrics:
                key = "%s|%s|%s" % (smoke, record.get("case_id"), rubric["name"])
                reply = run_judge(rubric["text"], case_text, lambda system, user, _m=candidate, _k=key: client.chat(_m, system, user, _k))
                verdict, _reason = parse_reply(reply)
                replies += 1
                if verdict in ("PASS", "FAIL"):
                    parsed += 1
        recorded.append({
            "digest": digest,
            "family": family,
            "model": candidate,
            "parsed": parsed,
            "ran": True,
            "replies": replies,
        })
        if replies > 0 and parsed == replies:
            chosen = candidate
    if chosen is None:
        raise JudgeError("no candidate parsed every reply")
    return {
        "adapter": _source(client),
        "candidates": recorded,
        "choice": chosen,
        "grader_family": grader_family,
        "grader_model": model_name,
        "not_run": [row["model"] for row in recorded if not row["ran"]],
        "smoke_run": smoke,
    }


def cmd_pick_model(args):
    client = _client_from_fixture(args.http_fixture)
    document = pick_model(
        _candidates(args.candidates),
        args.grader_run,
        args.plan,
        args.rubrics,
        args.smoke,
        client,
    )
    write_outputs([(args.out, canonical_json(document))])
    sys.stdout.write("choice %s\n" % document["choice"])


def _round4(value):
    if value is None:
        return None
    return round(value, 4)


def _fmt(value):
    if value is None:
        return "none"
    return "%.4f" % value


def agreement_percent(agree_count, total):
    """One decimal place from the integer counts, identical on 3.9 and 3.14.

    The tenth of a percent is agree_count * 1000 / total. An exact half rounds
    away from zero: 1 agreement in 16 rows is 6.25%, halfway between 6.2% and
    6.3%, and prints 6.3%.
    """
    if total == 0:
        return "none"
    tenths = (agree_count * 1000 + total // 2) // total
    return "%d.%d%%" % (tenths // 10, tenths % 10)


def _readings(path):
    if path is None:
        return {}
    data = load_json(path)
    if not isinstance(data, dict):
        raise JudgeError("readings file is not an object")
    cleaned = {}
    for rubric, pairs in data.items():
        if not isinstance(rubric, str) or not isinstance(pairs, dict):
            raise JudgeError("readings file is not rubric to row to text")
        bucket = {}
        for key, text in pairs.items():
            if not isinstance(key, str) or "|" not in key:
                raise JudgeError("readings key is not run|case_id")
            run, case_id = key.split("|", 1)
            if not isinstance(text, str):
                raise JudgeError("a reading is not text")
            bucket["%s|%s" % (run_name(run), case_id)] = text
        cleaned[rubric] = bucket
    return cleaned


def _provenance(path):
    if not os.path.isfile(path):
        raise JudgeError("provenance file is missing or unreadable")
    text = read_text(path)
    if text.strip() == "":
        raise JudgeError("provenance file is empty")
    return text


def _load_verdicts(directory):
    path = os.path.join(directory, "verdicts.jsonl")
    meta_path = os.path.join(directory, "judge_meta.json")
    raw_rows = load_jsonl(path)
    meta = load_json(meta_path)
    if not isinstance(meta, dict):
        raise JudgeError("judge_meta.json is not an object")
    rows = []
    for raw in raw_rows:
        if set(raw.keys()) != set(VERDICT_KEYS):
            raise JudgeError("a verdict row has the wrong keys")
        row = {
            "run": run_name(raw.get("run")),
            "case_id": _need_str(raw.get("case_id"), "case_id"),
            "trace_id": _need_str(raw.get("trace_id"), "trace_id"),
            "rubric": _need_str(raw.get("rubric"), "rubric"),
            "rubric_sha256": _need_str(raw.get("rubric_sha256"), "rubric_sha256"),
            "verdict": raw.get("verdict"),
            "reason": raw.get("reason"),
            "reply": raw.get("reply"),
        }
        if row["verdict"] not in ("PASS", "FAIL", "UNPARSED"):
            raise JudgeError("a verdict is not PASS, FAIL or UNPARSED")
        if not isinstance(row["reason"], str) or not isinstance(row["reply"], str):
            raise JudgeError("a verdict reason or reply is not text")
        rows.append(row)
    return rows, meta


def _labels_meta_path(labels_path):
    if not labels_path.endswith(".jsonl"):
        raise JudgeError("labels path must end in .jsonl")
    return labels_path[:-len(".jsonl")] + "-meta.json"


def _side(pairs, readings):
    predicted = []
    truth = []
    false_passes = []
    false_fails = []
    for run, case_id, verdict, reason, human in pairs:
        judge_fail = verdict != "PASS"
        human_fail = human == "FAIL"
        predicted.append(judge_fail)
        truth.append(human_fail)
        reading = has_reading(readings.get("%s|%s" % (run, case_id)))
        item = {"case_id": case_id, "reading": reading, "reason": reason, "run": run}
        if human_fail and not judge_fail:
            false_passes.append(item)
        elif judge_fail and not human_fail:
            false_fails.append(item)
    counts = confusion(predicted, truth)
    raw_agreement = agreement(counts)
    raw_kappa = cohen_kappa(counts)
    false_passes.sort(key=lambda item: (item["run"], item["case_id"]))
    false_fails.sort(key=lambda item: (item["run"], item["case_id"]))
    read = sum(1 for item in false_passes if item["reading"])
    return {
        "JF_HF": counts["tp"],
        "JF_HP": counts["fp"],
        "JP_HF": counts["fn"],
        "JP_HP": counts["tn"],
        "agreement": _round4(raw_agreement),
        "bar": bar_words(),
        "false_fails": false_fails,
        "false_passes": false_passes,
        "false_passes_read": "%s of %s" % (read, len(false_passes)),
        "fn": counts["fn"],
        "fp": counts["fp"],
        "kappa": _round4(raw_kappa),
        "kappa_at_least_0_6": raw_kappa is not None and raw_kappa >= 0.6,
        "meets_bar": meets_bar(counts),
        "tn": counts["tn"],
        "tp": counts["tp"],
    }


def _worst(rubric_rows, label_key):
    def rank(row):
        side = row[label_key]
        # Reuse the shared statistic with rational counts for an exact private
        # sort key. Public fields keep their existing four-place float values.
        kappa = cohen_kappa({name: Fraction(side[name]) for name in ("tp", "fp", "fn", "tn")})
        if kappa is None:
            kappa_part = (0, 0.0)
        else:
            kappa_part = (1, kappa)
        return (kappa_part, -len(side["false_passes"]))

    worst_rank = min(rank(row) for row in rubric_rows)
    tied = [row["rubric"] for row in rubric_rows if rank(row) == worst_rank]
    tied.sort()
    return {"labels": "final" if label_key == "final" else "first-pass", "rubrics": tied, "tied": len(tied) > 1}


def _list_lines(title, items):
    lines = [title]
    if not items:
        lines.append("none")
        return lines
    for item in items:
        lines.append("- %s %s: %s. Reading: %s." % (
            item["run"],
            item["case_id"],
            item["reason"],
            "yes" if item["reading"] else "no",
        ))
    return lines


def worst_sentence(doc):
    """The sentence the Markdown prints. The page prints the same words."""
    which = "final labels" if doc["worst"]["labels"] == "final" else "first-pass labels"
    names = ", ".join(doc["worst"]["rubrics"])
    if doc["worst"]["tied"]:
        return "Worst judges on the %s tied: %s." % (which, names)
    return "Worst judge on the %s: %s." % (which, names)


def render_markdown(doc):
    lines = [
        "# Judge agreement",
        "",
        "Command: `%s`" % doc["command"],
        "",
        worst_sentence(doc),
        "",
    ]
    lines.append("Model: %s. Digest: %s." % (doc["model"] or "none", doc["digest"] or "none"))
    lines.append("")
    for rubric in doc["rubrics"]:
        lines.extend([
            "## %s" % rubric["rubric"],
            "",
            "Rubric SHA-256: %s." % rubric["rubric_sha256"],
            "Labels SHA-256: %s." % doc["labels_sha256"],
            rubric["text"],
            "UNPARSED: %s." % rubric["unparsed"],
            "",
        ])
        for heading, side in (("First-pass labels", rubric["first_pass"]), ("Final labels", rubric["final"])):
            if side is None:
                continue
            lines.extend([
                "### %s" % heading,
                "",
                "JP_HP (tn): %s" % side["JP_HP"],
                "JP_HF (fn): %s" % side["JP_HF"],
                "JF_HP (fp): %s" % side["JF_HP"],
                "JF_HF (tp): %s" % side["JF_HF"],
                "",
                "Agreement: %s. Kappa: %s. Kappa at least 0.6: %s." % (
                    _fmt(side["agreement"]),
                    _fmt(side["kappa"]),
                    "yes" if side["kappa_at_least_0_6"] else "no",
                ),
                "meets_bar (%s): %s. False passes read: %s." % (
                    side["bar"],
                    "yes" if side["meets_bar"] else "no",
                    side["false_passes_read"],
                ),
                "",
            ])
            lines.extend(_list_lines("False passes:", side["false_passes"]))
            lines.append("")
            lines.extend(_list_lines("False fails:", side["false_fails"]))
            lines.append("")
    lines.append("## %s" % doc["provenance_heading"])
    text = "\n".join(lines) + "\n\n" + doc["provenance"]
    if not text.endswith("\n"):
        text += "\n"
    return text


def report_command(labels, final, readings, provenance, verdicts):
    """The command that reproduces a report from this directory. It is copied into results.md."""
    parts = ["python3 -m scorer.judge report", "--labels", relative_path(labels, "--labels")]
    if final:
        parts.extend(["--final", relative_path(final, "--final")])
    if readings:
        parts.extend(["--readings", relative_path(readings, "--readings")])
    parts.extend([
        "--provenance", relative_path(provenance, "--provenance"),
        "--verdicts", relative_path(verdicts, "--verdicts"),
    ])
    return " ".join([parts[0]] + [shlex.quote(part) for part in parts[1:]])


def _labels_agree(verdict, human):
    """PASS agrees with a human PASS. UNPARSED agrees only with a human FAIL."""
    return (verdict == "PASS") == (human == "PASS")


def _load_report(labels, final, readings, provenance, verdicts):
    labels = relative_path(labels, "--labels")
    final = relative_path(final, "--final") if final else None
    readings = relative_path(readings, "--readings") if readings else None
    provenance = relative_path(provenance, "--provenance")
    verdicts = relative_path(verdicts, "--verdicts")
    command = report_command(labels, final, readings, provenance, verdicts)
    names, rows = load_labels(labels)
    final_rows = None
    if final:
        _final_names, final_rows = load_labels(final, allow_changes=True)
        if len(final_rows) != len(rows):
            raise JudgeError("final row count does not match the labels")
        for first, final_row in zip(rows, final_rows):
            _check_changes(first, final_row)
    verdict_rows, judge_meta = _load_verdicts(verdicts)
    labels_sha = file_sha256(labels)
    if judge_meta.get("labels_sha256") != labels_sha:
        raise JudgeError("verdicts were not made from this labels file")
    meta_rubrics = judge_meta.get("rubrics")
    if not isinstance(meta_rubrics, dict) or set(meta_rubrics.keys()) != set(names):
        raise JudgeError("judge_meta rubrics do not match the labels")
    labels_meta = load_json(_labels_meta_path(labels))
    if not isinstance(labels_meta, dict) or not isinstance(labels_meta.get("rubrics"), dict):
        raise JudgeError("labels meta is missing rubric hashes")
    if set(labels_meta["rubrics"].keys()) != set(names):
        raise JudgeError("labels meta rubrics do not match the labels")
    readings_map = _readings(readings)
    provenance_text = _provenance(provenance)
    by_key = {}
    for verdict in verdict_rows:
        key = (verdict["run"], verdict["case_id"], verdict["rubric"])
        if key in by_key:
            raise JudgeError("duplicate verdict for %s %s %s" % key)
        by_key[key] = verdict
    expected = []
    for row in rows:
        for name in names:
            expected.append((row["run"], row["case_id"], name))
    if set(by_key) != set(expected):
        raise JudgeError("verdicts do not match the label rows and rubrics")
    rubric_docs = []
    page_rubrics = []
    for name in names:
        pairs = []
        final_pairs = []
        unparsed = 0
        page_rows = []
        changed = 0 if final_rows is not None else None
        bucket = readings_map.get(name) or {}
        for index, row in enumerate(rows):
            verdict = by_key[(row["run"], row["case_id"], name)]
            if verdict["trace_id"] != row["trace_id"]:
                raise JudgeError("verdict trace_id does not match the label row")
            if verdict["rubric_sha256"] != meta_rubrics[name]:
                raise JudgeError("verdict rubric hash does not match judge_meta")
            if verdict["verdict"] == "UNPARSED":
                unparsed += 1
            first_label = row["human"][name]
            pairs.append((row["run"], row["case_id"], verdict["verdict"], verdict["reason"], first_label))
            final_label = None
            change_reason = None
            if final_rows is not None:
                final_label = final_rows[index]["human"][name]
                final_pairs.append((row["run"], row["case_id"], verdict["verdict"], verdict["reason"], final_label))
                if final_label != first_label:
                    changed += 1
                    for change in final_rows[index]["changes"]:
                        if change["rubric"] == name:
                            change_reason = change["reason"]
                            break
            cover_label = final_label if final_label is not None else first_label
            show_reading = not _labels_agree(verdict["verdict"], first_label) or (
                final_label is not None and not _labels_agree(verdict["verdict"], final_label)
            )
            page_rows.append({
                "agree": _labels_agree(verdict["verdict"], cover_label),
                "case_id": row["case_id"],
                "change_reason": change_reason,
                "final": final_label,
                "first": first_label,
                "reading": bucket.get("%s|%s" % (row["run"], row["case_id"])),
                "reason": verdict["reason"],
                "run": row["run"],
                "show_reading": show_reading,
                "verdict": verdict["verdict"],
            })
        recorded = labels_meta["rubrics"][name]
        judged = meta_rubrics[name]
        if recorded == judged:
            text_state = "same text as when the labels were made"
        else:
            text_state = "changed since the labels were made: in sample"
        rubric_docs.append({
            "final": _side(final_pairs, bucket) if final_pairs else None,
            "first_pass": _side(pairs, bucket),
            "rubric": name,
            "rubric_sha256": judged,
            "text": text_state,
            "unparsed": unparsed,
        })
        page_rubrics.append({"changed": changed, "rows": page_rows, "rubric": name})
    label_key = "final" if final_rows is not None else "first_pass"
    document = {
        "command": command,
        "digest": judge_meta.get("digest"),
        "labels_sha256": labels_sha,
        "model": judge_meta.get("model"),
        "provenance": provenance_text,
        "provenance_heading": PROVENANCE_HEADING,
        "rubrics": rubric_docs,
        "worst": _worst(rubric_docs, label_key),
    }
    page = {"labels_path": labels, "row_count": len(rows), "rubrics": page_rubrics}
    return document, page


def build_report(labels, final, readings, provenance, verdicts):
    document, _page = _load_report(labels, final, readings, provenance, verdicts)
    return render_markdown(document), document


_FALSE_PASS = "a false pass: the judge passed a real failure"
_FALSE_FAIL = "a false fail: the judge failed a row the human passed"


def _rubric_provenance(path, names):
    """Per-rubric statements, keyed by exactly the labels' rubric names."""
    path = relative_path(path, "--rubric-provenance")
    data = load_json(path)
    if not isinstance(data, dict):
        raise JudgeError("rubric provenance file is not an object")
    found = set(data.keys())
    expected = set(names)
    if found - expected:
        raise JudgeError("rubric provenance file names a rubric the labels do not have")
    if expected - found:
        raise JudgeError("rubric provenance file lacks a rubric")
    cleaned = {}
    for name in names:
        value = data[name]
        if not isinstance(value, str):
            raise JudgeError("rubric provenance value is not text")
        if value.strip() == "":
            raise JudgeError("rubric provenance value is empty")
        cleaned[name] = value
    return path, cleaned


def _matrix_cell(side, name, stat, description, alarm):
    detail = ""
    if description:
        detail = ". " + esc(description)
    if alarm == "fn":
        klass = "cell-fn"
    elif alarm == "fp":
        klass = "cell-fp"
    else:
        klass = "cell"
    return '<td class="%s" data-cell="%s"><span class="mono">%s</span> %s (%s)%s</td>' % (
        klass, esc(name), esc(side[name]), esc(name), esc(stat), detail,
    )


def _matrix(side):
    return [
        '<table class="matrix">',
        "<thead><tr><th></th><th>Human PASS</th><th>Human FAIL</th></tr></thead>",
        "<tbody>",
        "<tr><th>Judge PASS</th>%s%s</tr>" % (
            _matrix_cell(side, "JP_HP", "tn", None, None),
            _matrix_cell(side, "JP_HF", "fn", _FALSE_PASS, "fn"),
        ),
        "<tr><th>Judge FAIL</th>%s%s</tr>" % (
            _matrix_cell(side, "JF_HP", "fp", _FALSE_FAIL, "fp"),
            _matrix_cell(side, "JF_HF", "tp", None, None),
        ),
        "</tbody>",
        "</table>",
    ]


def _side_block(kind, heading, side, changed):
    agree_count = side["JP_HP"] + side["JF_HF"]
    total = agree_count + side["JP_HF"] + side["JF_HP"]
    percent = agreement_percent(agree_count, total)
    if side["meets_bar"]:
        pill, word = "ok", bar_words()
    else:
        pill, word = "alarm", not_bar_words()
    read = ""
    if side["false_passes"]:
        read = ' <span class="mono">%s</span>' % esc(side["false_passes_read"])
    lines = [
        '<article class="side" data-labels="%s">' % esc(kind),
        '<p class="shout">%s</p>' % esc(heading),
    ]
    lines.extend(_matrix(side))
    lines.append("<p>Agreement %s (%s).</p>" % (esc(percent), esc(_fmt(side["agreement"]))))
    lines.append("<p>Kappa %s. Kappa at least 0.6, the course's bar: %s.</p>" % (
        esc(_fmt(side["kappa"])), esc("yes" if side["kappa_at_least_0_6"] else "no"),
    ))
    lines.append('<p><span class="pill %s">%s</span>%s</p>' % (pill, esc(word), read))
    if changed is not None and kind == "final":
        lines.append(
            '<p class="changed">Labels the owner changed: <span class="mono">%s</span>.</p>' % esc(changed)
        )
    lines.append("</article>")
    return lines


def _reading_html(row):
    if not row["show_reading"]:
        return ""
    if has_reading(row["reading"]):
        badge = '<span class="pill read">read</span>'
        body = '<div class="note"><p class="reading">%s</p></div>' % esc(row["reading"])
    else:
        badge = '<span class="pill alarm">unread</span>'
        body = ""
    return '<details class="reading-fold" open><summary>%s</summary>%s</details>' % (badge, body)


def _row_html(row, with_final):
    mark = "agree" if row["agree"] else "disagree"
    klass = "row" if row["agree"] else "row disagree"
    if row["agree"]:
        mark_html = "<span>agree</span>"
    else:
        mark_html = '<span class="disagree-mark">disagree</span>'
    cells = [
        ("Run", '<span class="mono break">%s</span>' % esc(row["run"])),
        ("Case", '<span class="mono break">%s</span>' % esc(row["case_id"])),
        ("Verdict", '<span class="mono">%s</span>' % esc(row["verdict"])),
        ("First-pass", '<span class="mono">%s</span>' % esc(row["first"])),
    ]
    if with_final:
        cells.append(("Final", '<span class="mono">%s</span>' % esc(row["final"])))
    cells.append(("Agrees", mark_html))
    cells.append(("Reason", '<span class="break">%s</span>' % esc(row["reason"])))
    if with_final:
        if row["change_reason"]:
            cells.append(("Change", '<span class="change break">%s</span>' % esc(row["change_reason"])))
        else:
            cells.append(("Change", ""))
    cells.append(("Reading", _reading_html(row)))
    parts = [
        '<tr class="%s" data-mark="%s" data-run="%s" data-case="%s">' % (
            klass, mark, esc(row["run"]), esc(row["case_id"]),
        )
    ]
    for label, inner in cells:
        parts.append('<td data-label="%s">%s</td>' % (esc(label), inner))
    parts.append("</tr>")
    return "".join(parts)


def _tiles(document):
    key = "final" if document["worst"]["labels"] == "final" else "first_pass"
    which = "final labels" if key == "final" else "first-pass labels"
    rubrics = document["rubrics"]
    meeting = sum(1 for row in rubrics if row[key]["meets_bar"])
    passes = sum(len(row[key]["false_passes"]) for row in rubrics)
    fails = sum(len(row[key]["false_fails"]) for row in rubrics)
    meeting_class = "stat good" if meeting == len(rubrics) and rubrics else "stat alarm"
    passes_class = "stat alarm" if passes else "stat"
    fails_class = "stat alarm" if fails else "stat"
    return [
        '<p class="tile-which">These tiles count the %s.</p>' % esc(which),
        '<div class="stats">',
        '<div class="%s"><b>%s</b><span>judges at %s</span></div>' % (
            meeting_class, esc(meeting), esc(bar_words()),
        ),
        '<div class="%s"><b>%s</b><span>false passes</span></div>' % (passes_class, esc(passes)),
        '<div class="%s"><b>%s</b><span>false fails</span></div>' % (fails_class, esc(fails)),
        "</div>",
    ]


def render_judge_html(document, page, statements, provenance_path, css):
    """The comparison page. The output path is not in the text; the colophon names comparison.html."""
    by_name = {item["rubric"]: item for item in page["rubrics"]}
    with_final = document["worst"]["labels"] == "final"
    which = "final labels" if with_final else "first-pass labels"
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Do the judges agree?</title>",
    ]
    lines.extend(FONT_LINKS)
    lines.extend([
        "<style>",
        css.rstrip("\n"),
        "</style>",
        "</head>",
        "<body>",
        '<div class="wrap break">',
        '<header class="cover panel">',
        '<p class="issue"><span>Labels</span><span class="as-recorded break">%s</span>'
        '<span class="as-recorded break">%s · %s</span><span>%s rows · %s rubrics</span></p>' % (
            esc(page["labels_path"]),
            esc(document["model"] or "none"),
            esc(document["digest"] or "none"),
            esc(page["row_count"]),
            esc(len(document["rubrics"])),
        ),
        '<h1 class="mast"><small>Settlement grader</small>Do the judges agree?</h1>',
        '<p class="dek">%s</p>' % esc(worst_sentence(document)),
        '<div class="cover-main">',
        '<div class="cover-tiles">',
    ])
    lines.extend(_tiles(document))
    lines.extend([
        "</div>",
        '<div class="prov">',
        "<h2>%s</h2>" % esc(document["provenance_heading"]),
        '<p class="cover-statement">%s</p>' % esc(document["provenance"]),
        "</div>",
        "</div>",
        "</header>",
    ])
    headers = ["Run", "Case", "Verdict", "First-pass"]
    if with_final:
        headers.append("Final")
    headers.extend(["Agrees", "Reason"])
    if with_final:
        headers.append("Change")
    headers.append("Reading")
    head = "".join("<th>%s</th>" % esc(header) for header in headers)
    for rubric in document["rubrics"]:
        info = by_name[rubric["rubric"]]
        lines.extend([
            '<section class="sec panel rubric" data-rubric="%s">' % esc(rubric["rubric"]),
            '<div class="sec-head">',
            "<h2>%s</h2>" % esc(rubric["rubric"]),
            '<p class="break">Rubric SHA-256: <span class="mono">%s</span>.</p>' % esc(rubric["rubric_sha256"]),
            "<p>%s</p>" % esc(rubric["text"]),
            "<p>UNPARSED: <span class=\"mono\">%s</span>.</p>" % esc(rubric["unparsed"]),
            "</div>",
            '<div class="rubric-top">',
            '<div class="sides">',
        ])
        lines.extend(_side_block("first-pass", "First-pass labels", rubric["first_pass"], info["changed"]))
        if rubric["final"] is not None:
            lines.extend(_side_block("final", "Final labels", rubric["final"], info["changed"]))
        lines.extend([
            "</div>",
            '<div class="prov">',
            "<h3>%s</h3>" % esc(PROVENANCE_HEADING),
            '<p class="rubric-statement">%s</p>' % esc(statements[rubric["rubric"]]),
            "</div>",
            "</div>",
            "<p>Agrees compares the judge with the %s.</p>" % esc(which),
            '<table class="ledger">',
            "<thead><tr>%s</tr></thead>" % head,
            "<tbody>",
        ])
        for row in info["rows"]:
            lines.append(_row_html(row, with_final))
        lines.extend(["</tbody>", "</table>", "</section>"])
    command = "%s --rubric-provenance %s --html comparison.html" % (document["command"], shlex.quote(provenance_path))
    lines.extend([
        '<p class="colophon">Regenerated by <code class="mono">%s</code>. Fonts load from Google Fonts.</p>' % esc(command),
        "</div>",
        "</body>",
        "</html>",
        "",
    ])
    return "\n".join(lines)


def render_comparison(labels, final, readings, provenance, verdicts, rubric_provenance):
    document, page = _load_report(labels, final, readings, provenance, verdicts)
    names = [item["rubric"] for item in document["rubrics"]]
    path, statements = _rubric_provenance(rubric_provenance, names)
    return render_judge_html(document, page, statements, path, _css_text())


def cmd_report(args):
    if (args.html_out is None) != (args.rubric_provenance is None):
        raise JudgeError("--html and --rubric-provenance must be given together")
    document, page = _load_report(args.labels, args.final, args.readings, args.provenance, args.verdicts)
    markdown = render_markdown(document)
    pairs = []
    if args.md_out:
        pairs.append((args.md_out, markdown))
    if args.json_out:
        pairs.append((args.json_out, canonical_json(document)))
    if args.html_out is not None:
        names = [item["rubric"] for item in document["rubrics"]]
        path, statements = _rubric_provenance(args.rubric_provenance, names)
        pairs.append((args.html_out, render_judge_html(document, page, statements, path, _css_text())))
    write_outputs(pairs)
    sys.stdout.write(markdown)


def _fence(text):
    longest = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return "`" * max(3, longest + 1)


def export_files(labels, final, readings, provenance, verdicts, rubrics_dir, cache, rubric_provenance=None):
    document, page = _load_report(labels, final, readings, provenance, verdicts)
    markdown = render_markdown(document)
    rubrics = load_rubrics(rubrics_dir)
    names, rows = load_labels(labels)
    final_rows = None
    if final:
        _final_names, final_rows = load_labels(final, allow_changes=True)
    if [rubric["name"] for rubric in rubrics] != names:
        raise JudgeError("labels and rubrics do not match")
    judged = {item["rubric"]: item["rubric_sha256"] for item in document["rubrics"]}
    for rubric in rubrics:
        if rubric["sha256"] != judged[rubric["name"]]:
            raise JudgeError(
                "rubric %s is not the text the judge ran: its SHA-256 differs from judge_meta.json" % rubric["name"]
            )
    blocks = []
    for rubric in rubrics:
        fence = _fence(rubric["text"])
        body = rubric["text"] if rubric["text"].endswith("\n") else rubric["text"] + "\n"
        blocks.append("# %s\n\nSHA-256: %s\n\n%s\n%s%s\n" % (rubric["name"], rubric["sha256"], fence, body, fence))
    course_rows = []
    source_rows = final_rows if final_rows is not None else rows
    for row in source_rows:
        record = record_for(cache, row)
        ticket, output = case_sections(render_case(record))
        course_rows.append({"human": row["human"], "input": ticket, "output": output})
    files = {
        "labels.jsonl": jsonl_text(course_rows),
        "results.md": markdown,
        "rubrics.md": "".join(blocks),
    }
    if rubric_provenance is not None:
        path, statements = _rubric_provenance(
            rubric_provenance, [item["rubric"] for item in document["rubrics"]],
        )
        files["comparison.html"] = render_judge_html(document, page, statements, path, _css_text())
    return files


def cmd_export(args):
    files = export_files(
        args.labels, args.final, args.readings, args.provenance, args.verdicts, args.rubrics, {},
        rubric_provenance=args.rubric_provenance,
    )
    names = ["rubrics.md", "labels.jsonl", "results.md"]
    if "comparison.html" in files:
        names.append("comparison.html")
    write_outputs([(os.path.join(args.out, name), files[name]) for name in names])
    sys.stdout.write("files %s\n" % len(names))


def _parser():
    parser = argparse.ArgumentParser(prog="python3 -m scorer.judge", description="Judge harness")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    select = sub.add_parser("select")
    select.add_argument("--base", required=True)
    select.add_argument("--fresh", action="append")
    select.add_argument("--n-fresh", dest="n_fresh", type=int, required=True)
    select.add_argument("--out", required=True)
    select.set_defaults(func=cmd_select)

    sheet = sub.add_parser("sheet")
    sheet.add_argument("--plan", required=True)
    sheet.add_argument("--rubrics", required=True)
    sheet.add_argument("--out", required=True)
    sheet.set_defaults(func=cmd_sheet)

    imported = sub.add_parser("import-labels")
    imported.add_argument("--plan", required=True)
    imported.add_argument("--sheet", required=True)
    imported.add_argument("--rubrics", required=True)
    imported.add_argument("--labels", required=True)
    imported.add_argument("--meta", required=True)
    imported.set_defaults(func=cmd_import)

    final = sub.add_parser("check-final")
    final.add_argument("--labels", required=True)
    final.add_argument("--final", required=True)
    final.set_defaults(func=cmd_check_final)

    run = sub.add_parser("run")
    run.add_argument("--labels", required=True)
    run.add_argument("--rubrics", required=True)
    run.add_argument("--adapter", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--http-fixture", dest="http_fixture")
    run.set_defaults(func=cmd_run)

    pick = sub.add_parser("pick-model")
    pick.add_argument("--candidates", required=True)
    pick.add_argument("--grader-run", required=True)
    pick.add_argument("--plan", required=True)
    pick.add_argument("--rubrics", required=True)
    pick.add_argument("--smoke", default="traces/smoke-1")
    pick.add_argument("--out", required=True)
    pick.add_argument("--http-fixture", dest="http_fixture")
    pick.set_defaults(func=cmd_pick_model)

    report = sub.add_parser("report")
    report.add_argument("--labels", required=True)
    report.add_argument("--final")
    report.add_argument("--readings")
    report.add_argument("--provenance", required=True)
    report.add_argument("--verdicts", required=True)
    report.add_argument("--md", dest="md_out")
    report.add_argument("--json", dest="json_out")
    report.add_argument("--html", dest="html_out")
    report.add_argument("--rubric-provenance", dest="rubric_provenance")
    report.set_defaults(func=cmd_report)

    export = sub.add_parser("export-course")
    export.add_argument("--labels", required=True)
    export.add_argument("--final")
    export.add_argument("--readings")
    export.add_argument("--provenance", required=True)
    export.add_argument("--verdicts", required=True)
    export.add_argument("--rubrics", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--rubric-provenance", dest="rubric_provenance")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except JudgeError as error:
        parser.error(str(error))
    except OSError:
        parser.error("could not write output")
    return 0


if __name__ == "__main__":
    sys.exit(main())

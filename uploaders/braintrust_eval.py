"""Upload one Braintrust experiment per variant from the recorded runs.

The owner runs this. Nothing in scorer/ or the tests imports it, and this
file is not run here. The braintrust package is imported only after the
config, v1's bytes and both runs have been accepted, so a refusal needs no
package. The key is read from the environment and no part of it is printed.
A login or eval failure is reported without the exception text, because that
text can carry a masked key.

Calls, from the Braintrust Python SDK
(https://github.com/braintrustdata/braintrust-sdk-python):

- login(api_key=...): the api_key argument is used so the call does not prompt.
  When api_key is omitted, login reads BRAINTRUST_API_KEY and otherwise prompts.
  https://github.com/braintrustdata/braintrust-sdk-python/blob/main/py/src/braintrust/logger.py
- Eval(name, data, task, scores, experiment_name): name is the project.
  data yields input, expected and metadata. task(input, hooks) reads
  hooks.metadata. scores are functions of output, expected and metadata.
  The return value's summary.experiment_id is the experiment id.
  https://github.com/braintrustdata/braintrust-sdk-python/blob/main/py/src/braintrust/framework.py
  https://www.braintrust.dev/foundations/building-a-simple-eval-using-braintrust-sdk
"""
import hashlib
import json
import os
import sys

from scorer.rag import (
    ConfigError,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
    load_config,
    retrieved_items,
)
from scorer.traces import load_run


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG = os.path.join(ROOT, "packages", "rag-eval", "assignment-2", "config.yaml")
_PROJECT = "settlement-grader-rag"


def _v1_matches(root, config):
    """True only when v1's bytes are the digest named in the config."""
    path = os.path.join(root, config["dataset"])
    try:
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return False
    return digest == config["dataset_sha256"]


def _runs_present(root, config):
    for name in ("a", "b"):
        run_dir = os.path.join(root, "traces", config["runs"][name])
        traces = os.path.join(run_dir, "settlement-traces.json")
        if not os.path.isdir(run_dir) or not os.path.isfile(traces):
            return False
    return True


def _rows(root, config):
    path = os.path.join(root, config["dataset"])
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip() == "":
                continue
            rows.append(json.loads(line))
    rows.sort(key=lambda row: row.get("case_id") or "")
    return rows


def _examples(rows):
    examples = []
    for row in rows:
        examples.append({
            "input": row.get("question"),
            "expected": row.get("ground_truth"),
            "metadata": {
                "question": row.get("question"),
                "ground_truth_contexts": row.get("contexts"),
                "row": row,
            },
        })
    return examples


def _task(records):
    """Replay the recorded output. hooks.metadata carries the row. No model."""

    def task(input, hooks):
        metadata = hooks.metadata if hooks is not None else None
        row = metadata.get("row") if isinstance(metadata, dict) else None
        case_id = row.get("case_id") if isinstance(row, dict) else None
        record = records.get(case_id)
        if not isinstance(record, dict):
            return {"answer": None, "retrieved_contexts": [], "record": None}
        return {
            "answer": record.get("final"),
            "retrieved_contexts": [list(item) for item in retrieved_items(record)],
            "record": record,
        }

    return task


def main(argv=None):
    try:
        config = load_config(_CONFIG)
    except ConfigError as error:
        sys.stderr.write("%s\n" % error)
        return 2
    if config["dataset_sha256"] is None:
        sys.stderr.write("dataset_sha256 is null\n")
        return 2
    if not _v1_matches(ROOT, config):
        sys.stderr.write("v1 bytes do not match dataset_sha256\n")
        return 2
    if not _runs_present(ROOT, config):
        sys.stderr.write("a run is missing\n")
        return 2
    key = os.environ.get("BRAINTRUST_API_KEY")
    if not isinstance(key, str) or key.strip() == "":
        sys.stderr.write("the braintrust key is missing\n")
        return 2
    import braintrust
    try:
        braintrust.login(api_key=key)
    except Exception:
        sys.stderr.write("braintrust login failed\n")
        return 2
    rows = _rows(ROOT, config)
    examples = _examples(rows)
    for name in ("a", "b"):
        run_id = config["runs"][name]
        records = {
            record.get("case_id"): record
            for record in load_run(os.path.join(ROOT, "traces", run_id))
        }
        try:
            result = braintrust.Eval(
                _PROJECT,
                data=lambda: list(examples),
                task=_task(records),
                scores=[context_recall, context_precision, faithfulness, answer_relevancy],
                experiment_name=run_id,
            )
        except Exception:
            sys.stderr.write("braintrust eval failed\n")
            return 2
        experiment_id = result.summary.experiment_id
        if not isinstance(experiment_id, str) or experiment_id == "":
            sys.stderr.write("the experiment has no id\n")
            return 2
        sys.stdout.write("%s\n" % experiment_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

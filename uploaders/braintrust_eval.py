"""Upload one Braintrust experiment per variant from the recorded runs.

The owner runs this. Nothing in scorer/ or the tests imports it, and this
file is not run here. The pair is read through scorer.rag.load_pair, which
applies every refusal report applies, before the braintrust package is
imported, so a refusal needs no package and this script cannot accept a
pair that report refuses. The key is read from the environment and no part
of it is printed. A login or eval failure is reported without the exception
text, because that text can carry a masked key.

Calls, read in the Braintrust Python SDK at tag py-sdk-v0.49.3
(https://github.com/braintrustdata/braintrust-sdk-python):

- login(api_key=...), logger.py: with api_key given the call does not
  prompt. When it is omitted, login reads BRAINTRUST_API_KEY or prompts.
- Eval(name, data, task, scores, experiment_name), framework.py: name is
  the project. data may be a function that returns the cases, and a dict
  case becomes EvalCase(input, expected, metadata). A task with two
  parameters is called task(input, hooks), and hooks.metadata is the case's
  metadata dict. Scorers are called by keyword with input, output, expected,
  metadata and more, so f(output, expected, metadata, **kwargs) binds by
  name; a float return becomes a Score and None is a skipped score. Outside
  an event loop Eval runs to completion and returns EvalResultWithSummary,
  whose summary.experiment_id is the experiment's id.
- A scorer that raises does not fail Eval: the SDK stores the traceback in
  that case's metadata["scorer_errors"] and completes. A task that raises
  sets that case's error. Both are checked here before an id is printed.
"""
import os
import sys

from scorer.rag import (
    ConfigError,
    ReportError,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
    load_config,
    load_pair,
    retrieved_items,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG = os.path.join(ROOT, "packages", "rag-eval", "assignment-2", "config.yaml")
_PROJECT = "settlement-grader-rag"


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
    """Replay the recorded output. hooks.metadata carries the row. No model.

    load_pair has already required one record per v1 case, so the lookup
    cannot miss; if it did, the SDK would record the error on the case and
    _failed_cases would refuse the experiment.
    """

    def task(input, hooks):
        row = hooks.metadata["row"]
        record = records[row["case_id"]]
        return {
            "answer": record.get("final"),
            "retrieved_contexts": [list(item) for item in retrieved_items(record)],
            "record": record,
        }

    return task


def _failed_cases(result):
    """Case ids whose task raised or whose scorer raised.

    The SDK records both on the case and completes the eval, so the result
    has to be read before its id is trusted.
    """
    failed = []
    for item in result.results:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        if item.error is None and not metadata.get("scorer_errors"):
            continue
        row = metadata.get("row") if isinstance(metadata.get("row"), dict) else {}
        failed.append(str(row.get("case_id")))
    return failed


def main(argv=None):
    try:
        config = load_config(_CONFIG)
    except ConfigError as error:
        sys.stderr.write("%s\n" % error)
        return 2
    try:
        rows, _metas, records = load_pair(config, ROOT)
    except ReportError as error:
        sys.stderr.write("%s\n" % error)
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
    examples = _examples(rows)
    for name in ("a", "b"):
        run_id = config["runs"][name]
        try:
            result = braintrust.Eval(
                _PROJECT,
                data=lambda: list(examples),
                task=_task(records[name]),
                scores=[context_recall, context_precision, faithfulness, answer_relevancy],
                experiment_name=run_id,
            )
        except Exception:
            sys.stderr.write("braintrust eval failed\n")
            return 2
        failed = _failed_cases(result)
        if failed:
            sys.stderr.write(
                "experiment %s has errors on %d cases; its id is not printed\n" % (run_id, len(failed)))
            return 2
        experiment_id = result.summary.experiment_id
        if not isinstance(experiment_id, str) or experiment_id == "":
            sys.stderr.write("the experiment has no id\n")
            return 2
        sys.stdout.write("%s\n" % experiment_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
